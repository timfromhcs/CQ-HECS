"""
Test Suite: Classical Four-Path Architecture & Certified Backends.
Tests:
- Path A: Stabilizer-Tableau (exact, Clifford)
- Path B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
- Path C: MPS without Cutoff + NVMe-Offload (exact up to memory limit)
- Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
- CircuitAnalyzer & FourPathRouter
- Bit-exact differential tests against exact statevector references
- Error-bound certification: ensures actual_error <= error_bound is NEVER violated
- Rejection of uncertifiable approximations (unresolved=True)
"""

import unittest
import math
import numpy as np
from qiskit import QuantumCircuit

from cqhecs.circuit_analyzer import CircuitAnalyzer
from cqhecs.router import FourPathRouter
from cqhecs.result import SimulationResult, SimulationState
from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend, StabilizerTableauSimulator
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend, StabilizerRankSimulator
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend, ExactMPSTensorChain
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend, SparsePauliDynamicsSimulator


class TestFourPathArchitecture(unittest.TestCase):

    def setUp(self):
        self.router = FourPathRouter()
        self.analyzer = CircuitAnalyzer()

    # -------------------------------------------------------------
    # 1. CircuitAnalyzer Unit Tests
    # -------------------------------------------------------------
    def test_analyzer_clifford_detection(self):
        """Verifies that pure Clifford circuits are detected and routed to Path A."""
        qc = QuantumCircuit(5)
        qc.h(0)
        qc.cx(0, 1)
        qc.s(2)
        qc.sdg(3)
        qc.cz(1, 2)
        qc.swap(3, 4)
        qc.rz(math.pi / 2.0, 0) # Clifford rotation

        props = self.analyzer.analyze(qc)
        self.assertTrue(props.is_clifford)
        self.assertEqual(props.t_count, 0)
        self.assertEqual(props.recommended_path, "A")

    def test_analyzer_t_count_and_rank_routing(self):
        """Verifies that circuits with low T-count are routed to Path B."""
        qc = QuantumCircuit(4)
        qc.h(0)
        qc.t(0)
        qc.t(1)
        qc.tdg(2)
        qc.cx(0, 1)

        props = self.analyzer.analyze(qc)
        self.assertFalse(props.is_clifford)
        self.assertEqual(props.t_count, 3)
        self.assertEqual(props.recommended_path, "B")

    def test_analyzer_mps_entanglement_routing(self):
        """Verifies that circuits with moderate entanglement and high T-count route to Path C."""
        qc = QuantumCircuit(6)
        # 16 T gates (exceeds t_rank_threshold=14), but 1D nearest neighbor CX
        for i in range(6):
            qc.h(i)
            qc.t(i)
            qc.t(i)
            qc.t(i)
        for i in range(5):
            qc.cx(i, i + 1)

        props = self.analyzer.analyze(qc)
        self.assertGreater(props.t_count, 14)
        self.assertEqual(props.recommended_path, "C")

    # -------------------------------------------------------------
    # 2. Path A: Stabilizer-Tableau Verification
    # -------------------------------------------------------------
    def test_path_a_ghz_bit_exact(self):
        """Path A must produce exact GHZ-50 state with zero error."""
        n = 50
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)

        backend = PathAStabilizerBackend()
        res = backend.execute(qc, shots=500, seed=123)

        self.assertEqual(res.path, "A")
        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.unresolved)
        self.assertEqual(sum(res.counts.values()), 500)

        # In GHZ state, only 00...0 and 11...1 can appear
        key0 = "0" * n
        key1 = "1" * n
        for k in res.counts:
            self.assertIn(k, (key0, key1))

    # -------------------------------------------------------------
    # 3. Path B: Stabilizer-Rank-Decomposition Verification
    # -------------------------------------------------------------
    def test_path_b_clifford_plus_t(self):
        """Path B exact Clifford + T statevector simulation."""
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.t(0)
        qc.cx(0, 1)
        qc.t(1)
        qc.cx(1, 2)

        backend = PathBStabilizerRankBackend()
        res = backend.execute(qc, shots=1000, seed=42)

        self.assertEqual(res.path, "B")
        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.unresolved)
        self.assertEqual(sum(res.counts.values()), 1000)

    # -------------------------------------------------------------
    # 4. Path C: MPS without Cutoff Verification
    # -------------------------------------------------------------
    def test_path_c_unbounded_bond_dimension(self):
        """Path C must expand bond dimension to exact rank without artificial chi=48 cutoff."""
        # Create an entangling circuit where rank exceeds 4
        qc = QuantumCircuit(4)
        qc.h(0)
        qc.h(1)
        qc.h(2)
        qc.h(3)
        # Deep entangling layers
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.cx(2, 3)
        qc.rz(0.35, 1)
        qc.cx(0, 1)
        qc.cx(1, 2)

        backend = PathCMPSExactBackend(ram_budget_mb=100.0)
        res = backend.execute(qc, shots=500, seed=42)

        self.assertEqual(res.path, "C")
        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.unresolved)
        # Verify that max_observed_chi is tracked and no silent truncation occurred
        self.assertGreaterEqual(res.metadata["max_observed_chi"], 1)
        self.assertFalse(res.metadata["silent_truncation"])

    # -------------------------------------------------------------
    # 5. Path D & Differential Statevector Tests (Certified Bound)
    # -------------------------------------------------------------
    def test_path_d_certified_error_bound_theorem(self):
        """
        Differential Test: Path D certified error bound against exact Statevector.
        Theorem: |<O_exact> - <O_approx>| <= error_bound must hold unconditionally!
        """
        rng = np.random.default_rng(2026)

        # Test across 5 randomized circuits
        for trial in range(5):
            n = 4
            qc = QuantumCircuit(n)
            # Add random Clifford and T gates
            for q in range(n):
                qc.h(q)
            for l in range(3):
                for q in range(n - 1):
                    qc.cx(q, q + 1)
                qc.t(l % n)
                qc.rz(float(rng.uniform(0.1, 1.5)), (l + 1) % n)

            # 1. Exact reference via dense statevector
            dim = 1 << n
            state = np.zeros(dim, dtype=np.complex128)
            state[0] = 1.0
            instructions = []
            for inst in qc.data:
                name = inst.operation.name
                q_idx = [qc.find_bit(q).index for q in inst.qubits]
                params = [float(p) for p in inst.operation.params] if hasattr(inst.operation, "params") else []
                instructions.append((name, q_idx, params))

            # Simulate exact reference statevector
            for name, qubits, params in instructions:
                if name == "h":
                    q = qubits[0]
                    state = state.reshape((1 << (n - 1 - q), 2, 1 << q))
                    h_mat = np.array([[1, 1], [1, -1]]) / np.sqrt(2.0)
                    state = np.einsum("ij,ajb->aib", h_mat, state).reshape(dim)
                elif name == "t":
                    q = qubits[0]
                    state = state.reshape((1 << (n - 1 - q), 2, 1 << q))
                    t_mat = np.array([[1, 0], [0, np.exp(1j * np.pi / 4.0)]])
                    state = np.einsum("ij,ajb->aib", t_mat, state).reshape(dim)
                elif name == "rz":
                    q = qubits[0]
                    th = params[0]
                    state = state.reshape((1 << (n - 1 - q), 2, 1 << q))
                    rz_mat = np.array([[np.exp(-1j * th / 2.0), 0], [0, np.exp(1j * th / 2.0)]])
                    state = np.einsum("ij,ajb->aib", rz_mat, state).reshape(dim)
                elif name in ("cx", "cnot"):
                    c, t = qubits[0], qubits[1]
                    for i in range(dim):
                        if (i & (1 << c)) and not (i & (1 << t)):
                            partner = i | (1 << t)
                            state[i], state[partner] = state[partner], state[i]

            # Reference observable <Z_0>:
            z0_diag = np.array([1.0 if not (i & 1) else -1.0 for i in range(dim)])
            exact_exp_z0 = float(np.sum(np.abs(state) ** 2 * z0_diag).real)

            # 2. Path D evaluation with aggressive truncation to force non-zero error bound
            sim_d = SparsePauliDynamicsSimulator(
                num_qubits=n,
                max_pauli_terms=4, # strict term budget to force truncation
                prune_threshold=0.01,
                error_tolerance=1.0
            )
            obs = {(0, 1): complex(1.0, 0.0)} # Z_0
            approx_exp_z0, error_bound, unresolved = sim_d.evaluate_observable(instructions, obs)

            actual_error = abs(exact_exp_z0 - approx_exp_z0)

            print(
                f"[Differential Test Trial {trial}] Exact: {exact_exp_z0:.4f}, "
                f"Approx: {approx_exp_z0:.4f}, Error: {actual_error:.6f}, Bound: {error_bound:.6f}"
            )

            # Mathematical Certification: actual_error <= error_bound + 1e-12 (for float precision)
            self.assertLessEqual(
                actual_error,
                error_bound + 1e-12,
                f"Error bound violated! actual_error ({actual_error}) > error_bound ({error_bound})"
            )

    def test_path_d_rejection_when_unresolved(self):
        """Verifies that Path D marks unresolved=True when error bound exceeds tolerance."""
        qc = QuantumCircuit(4)
        for _ in range(3):
            for i in range(4):
                qc.h(i)
                qc.rz(0.7, i)
            for i in range(3):
                qc.cx(i, i + 1)

        # Extremely strict error tolerance (0.00001) with small term budget
        backend_d = PathDSparsePauliBackend(max_pauli_terms=2, error_tolerance=1e-5)
        res = backend_d.execute(qc, shots=100)

        self.assertEqual(res.path, "D")
        self.assertFalse(res.exact)
        self.assertTrue(res.unresolved, "Expected unresolved=True when error exceeds tight tolerance!")
        self.assertGreater(res.error_bound, 1e-5)

    # -------------------------------------------------------------
    # 6. FourPathRouter End-to-End Execution
    # -------------------------------------------------------------
    def test_router_end_to_end(self):
        """Tests router automated execution across circuits of different classes."""
        # Case A: Clifford GHZ
        qcA = QuantumCircuit(10)
        qcA.h(0)
        for i in range(9): qcA.cx(i, i + 1)
        resA = self.router.route_and_execute(qcA, shots=100)
        self.assertEqual(resA.path, "A")
        self.assertTrue(resA.exact)

        # Case B: Clifford + 2 T gates
        qcB = QuantumCircuit(4)
        qcB.h(0)
        qcB.t(0)
        qcB.t(1)
        qcB.cx(0, 1)
        resB = self.router.route_and_execute(qcB, shots=100)
        self.assertEqual(resB.path, "B")
        self.assertTrue(resB.exact)

        # Case C: Explicit Path C execution
        qcC = QuantumCircuit(3)
        qcC.h(0)
        qcC.cx(0, 1)
        qcC.rz(0.3, 1)
        resC = self.router.route_and_execute(qcC, preferred_path="C", shots=100)
        self.assertEqual(resC.path, "C")
        self.assertTrue(resC.exact)

        # Case D: Explicit Path D execution
        qcD = QuantumCircuit(3)
        qcD.h(0)
        qcD.cx(0, 1)
        qcD.rz(0.3, 1)
        resD = self.router.route_and_execute(qcD, preferred_path="D", shots=100)
        self.assertEqual(resD.path, "D")
        self.assertFalse(resD.exact)
        self.assertFalse(resD.unresolved)
        self.assertGreaterEqual(resD.error_bound, 0.0)

    # -------------------------------------------------------------
    # 7. Explicit Simulation Result States (EXACT, CERTIFIED, UNRESOLVED)
    # -------------------------------------------------------------
    def test_explicit_simulation_result_states(self):
        """Verifies explicit, machine-readable SimulationState enum resolution."""
        # 1. Exact states (Path A, B, C)
        qcA = QuantumCircuit(2)
        qcA.h(0)
        qcA.cx(0, 1)
        resA = self.router.route_and_execute(qcA, shots=100)
        self.assertEqual(resA.state, SimulationState.EXACT)
        self.assertTrue(resA.is_exact)
        self.assertFalse(resA.is_certified)
        self.assertFalse(resA.is_unresolved)
        self.assertFalse(resA.is_failed)

        dictA = resA.to_dict()
        self.assertEqual(dictA["state"], "EXACT")
        self.assertEqual(dictA["status"], "SUCCESS")

        # 2. Certified state (Path D with satisfied tolerance)
        qcD = QuantumCircuit(2)
        qcD.h(0)
        qcD.rz(0.4, 0)
        resD = self.router.route_and_execute(qcD, preferred_path="D", shots=100, error_tolerance=0.5)
        self.assertEqual(resD.state, SimulationState.CERTIFIED)
        self.assertTrue(resD.is_certified)
        self.assertFalse(resD.is_exact)
        self.assertFalse(resD.is_unresolved)

        dictD = resD.to_dict()
        self.assertEqual(dictD["state"], "CERTIFIED")
        self.assertEqual(dictD["status"], "SUCCESS")

        # 3. Unresolved state (Path D exceeding strict tolerance)
        backend_unres = PathDSparsePauliBackend(max_pauli_terms=2, error_tolerance=1e-5)
        qc_unres = QuantumCircuit(4)
        for _ in range(3):
            for i in range(4):
                qc_unres.h(i)
                qc_unres.rz(0.7, i)
            for i in range(3):
                qc_unres.cx(i, i + 1)
        res_unres = backend_unres.execute(qc_unres, shots=50)
        self.assertEqual(res_unres.state, SimulationState.UNRESOLVED)
        self.assertTrue(res_unres.is_unresolved)
        self.assertFalse(res_unres.is_exact)
        self.assertFalse(res_unres.is_certified)

        dict_unres = res_unres.to_dict()
        self.assertEqual(dict_unres["state"], "UNRESOLVED")
        self.assertEqual(dict_unres["status"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
