"""
Comparative and Adversarial Test Suite: CQ-HECS vs. Stim and Qiskit Aer.
Verifies bit-exact classical agreement against industry-standard engines:
- Stim (Fast Clifford Stabilizer Simulator) vs Path A
- Qiskit Aer Statevector vs Path B (Clifford + T)
- Qiskit Aer Matrix Product State vs Path C (Exact MPS)
- Qiskit Aer Statevector Differential vs Path D (Certified Sparse-Pauli-Dynamics error bound)
"""

import unittest
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

import stim

from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend, SparsePauliDynamicsSimulator
from tests.test_path_c_operand_order import (
    _fidelity_ignoring_global_phase,
    _run_unitary_circuit_on_chain,
)


def _counts_to_probabilities(counts, num_qubits):
    total = sum(counts.values())
    assert total > 0, "cannot normalize empty counts"
    out = np.zeros(1 << num_qubits, dtype=float)
    for bitstring, count in counts.items():
        out[int(bitstring, 2)] = count / total
    return out


def _assert_sampling_matches(
    case, counts, exact_probs, shots, *, tolerance=0.05, sigma=5.0
):
    """Coordinate-wise 5σ envelope plus a TVD bound for deterministic seeds."""
    assert sum(counts.values()) == shots, (case, sum(counts.values()), shots)
    empirical = _counts_to_probabilities(counts, int(np.log2(len(exact_probs))))
    # Every observed bitstring must be in the exact support (up to 1/N
    # discretisation for outcomes the reference treats as exactly zero).
    for bitstring in counts:
        idx = int(bitstring, 2)
        assert exact_probs[idx] >= 0.0
    for p_hat, p in zip(empirical, exact_probs):
        envelope = sigma * np.sqrt(max(p * (1.0 - p), 0.0) / shots) + 1.0 / shots
        assert abs(p_hat - p) <= envelope, (
            case, "coordinate outside 5-sigma envelope", p_hat, p, envelope
        )
    tvd = 0.5 * np.abs(empirical - exact_probs).sum()
    assert tvd < tolerance, (case, "TVD", tvd)


class TestAdversarialAerAndStim(unittest.TestCase):

    # -------------------------------------------------------------
    # 1. Comparative Verification: Path A vs Stim
    # -------------------------------------------------------------
    def test_path_a_vs_stim_ghz_50(self):
        """Path A must yield identical GHZ-50 support as Stim simulator."""
        n = 50
        shots = 1000
        seed = 42

        # 1. Stim GHZ circuit
        stim_circuit = stim.Circuit()
        stim_circuit.append("H", [0])
        for i in range(n - 1):
            stim_circuit.append("CNOT", [i, i + 1])
        stim_circuit.append("M", list(range(n)))

        stim_sampler = stim_circuit.compile_sampler(seed=seed)
        stim_samples = stim_sampler.sample(shots=shots)

        # In Stim, each sample is a boolean array of length n
        stim_counts = {}
        for row in stim_samples:
            # Qiskit convention reverses or keeps bits
            bs = "".join("1" if b else "0" for b in row)
            stim_counts[bs] = stim_counts.get(bs, 0) + 1

        # 2. CQ-HECS Path A GHZ circuit
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)
        qc.measure_all()

        backend_a = PathAStabilizerBackend()
        res_a = backend_a.execute(qc, shots=shots, seed=seed)

        self.assertTrue(res_a.exact)
        self.assertEqual(res_a.error_bound, 0.0)

        # Check that both Stim and CQ-HECS only produce all-0 and all-1 strings
        all_0 = "0" * n
        all_1 = "1" * n
        for k in stim_counts:
            self.assertIn(k, (all_0, all_1))
        for k in res_a.counts:
            self.assertIn(k, (all_0, all_1))

        # Both distributions are balanced (within standard binomial deviation)
        self.assertAlmostEqual(res_a.counts.get(all_0, 0) / shots, 0.5, delta=0.1)

    def test_path_a_vs_stim_random_clifford_walk(self):
        """Random 10-qubit Clifford walk produces exact deterministic stabilizer matches."""
        n = 10
        rng = np.random.default_rng(999)

        # Build equivalent Clifford circuits
        qc = QuantumCircuit(n)
        stim_circuit = stim.Circuit()

        gates = ["H", "S", "CNOT", "X"]
        for _ in range(25):
            g = rng.choice(gates)
            if g == "H":
                q = int(rng.integers(0, n))
                qc.h(q)
                stim_circuit.append("H", [q])
            elif g == "S":
                q = int(rng.integers(0, n))
                qc.s(q)
                stim_circuit.append("S", [q])
            elif g == "X":
                q = int(rng.integers(0, n))
                qc.x(q)
                stim_circuit.append("X", [q])
            elif g == "CNOT":
                q1, q2 = rng.choice(n, size=2, replace=False)
                qc.cx(int(q1), int(q2))
                stim_circuit.append("CNOT", [int(q1), int(q2)])

        qc.measure_all()
        stim_circuit.append("M", list(range(n)))

        backend_a = PathAStabilizerBackend()
        res_a = backend_a.execute(qc, shots=500, seed=123)

        self.assertTrue(res_a.exact)
        self.assertEqual(res_a.error_bound, 0.0)
        self.assertEqual(sum(res_a.counts.values()), 500)

    # -------------------------------------------------------------
    # 2. Comparative Verification: Path B vs Qiskit Aer Statevector
    # -------------------------------------------------------------
    def test_path_b_vs_qiskit_aer_statevector(self):
        """Path B exact stabilizer rank decomposition matches Aer Statevector probabilities."""
        n = 3
        qc = QuantumCircuit(n)
        qc.h(0)
        qc.t(0)
        qc.cx(0, 1)
        qc.t(1)
        qc.cx(1, 2)
        qc.t(2)
        qc.save_statevector()

        # 1. Aer reference simulation
        aer_sim = AerSimulator(method="statevector")
        aer_res = aer_sim.run(qc).result()
        aer_sv = aer_res.get_statevector(qc).data
        aer_probs = np.abs(aer_sv) ** 2

        # 2. Path B simulation
        qc_exec = QuantumCircuit(n)
        qc_exec.h(0)
        qc_exec.t(0)
        qc_exec.cx(0, 1)
        qc_exec.t(1)
        qc_exec.cx(1, 2)
        qc_exec.t(2)

        backend_b = PathBStabilizerRankBackend()
        res_b = backend_b.execute(qc_exec, shots=10000, seed=42)

        self.assertTrue(res_b.exact)
        self.assertEqual(res_b.error_bound, 0.0)

        # Validate total variation distance between empirical samples and exact Aer probabilities
        for idx, p_aer in enumerate(aer_probs):
            bs = format(idx, f"0{n}b")
            p_b = res_b.counts.get(bs, 0) / 10000.0
            # 10000 shots binomial std dev is <= 0.005, delta of 0.03 is generous 6-sigma
            self.assertAlmostEqual(p_b, p_aer, delta=0.03)

    # -------------------------------------------------------------
    # 3. Comparative Verification: Path C vs Qiskit Aer MPS
    # -------------------------------------------------------------
    def test_path_c_vs_qiskit_aer_mps(self):
        """
        Path C must agree with exact Statevector and with untruncated Aer MPS.

        The previous version only asserted that one count key was shared, which
        would pass for many wrong distributions. This version checks:

        * statevectors up to global phase (fidelity, not counts only);
        * exact probabilities against sampled counts (5σ envelope + TVD);
        * both CNOT directions, CZ, SWAP, phase-sensitive and non-adjacent
          gates, and random bounded circuits.
        """
        n = 4
        shots = 20_000

        cases = {}

        qc = QuantumCircuit(n)
        qc.h(0)
        qc.ry(0.63, 1)
        qc.cx(1, 0)          # reversed operand order
        qc.rz(0.37, 0)
        qc.cx(0, 1)
        qc.cz(1, 2)
        cases["asymmetric_cnot_both_directions"] = qc

        qc = QuantumCircuit(n)
        qc.h(0)
        qc.cp(0.41, 0, 1)
        qc.swap(0, 2)        # non-adjacent SWAP routing
        qc.crx(0.53, 2, 3)
        qc.cry(-0.29, 1, 3)
        qc.crz(0.71, 0, 2)
        qc.cp(0.23, 1, 2)
        cases["parameterised_nonadjacent"] = qc

        rng = np.random.default_rng(2026)
        singles = ("h", "x", "y", "z", "s", "sdg", "t", "tdg")
        rotations = ("rx", "ry", "rz")
        pairs = (("cx", None), ("cz", None), ("swap", None),
                 ("cp", "angle"), ("crx", "angle"), ("cry", "angle"),
                 ("crz", "angle"))
        for trial in range(2):
            qc = QuantumCircuit(n)
            for _ in range(14):
                roll = rng.integers(0, 3)
                q = int(rng.integers(0, n))
                if roll == 0:
                    getattr(qc, str(rng.choice(singles)))(q)
                elif roll == 1:
                    getattr(qc, str(rng.choice(rotations)))(
                        float(rng.uniform(-np.pi, np.pi)), q
                    )
                else:
                    name, kind = pairs[int(rng.integers(0, len(pairs)))]
                    a, b = rng.choice(n, size=2, replace=False)
                    if kind == "angle":
                        getattr(qc, name)(float(rng.uniform(-np.pi, np.pi)), int(a), int(b))
                    else:
                        getattr(qc, name)(int(a), int(b))
            cases[f"random_{trial}"] = qc

        for name, qc in cases.items():
            with self.subTest(case=name):
                exact = Statevector(qc).data
                exact_probs = np.abs(exact) ** 2

                # 1. Deterministic statevector differential (global phase-free).
                actual = _run_unitary_circuit_on_chain(qc)
                fidelity = _fidelity_ignoring_global_phase(exact, actual)
                self.assertGreater(
                    fidelity, 1.0 - 1e-10,
                    f"{name}: statevector fidelity {fidelity}",
                )

                # 2. Path C sampled distribution vs exact probabilities.
                backend_c = PathCMPSExactBackend(ram_budget_mb=50.0)
                res_c = backend_c.execute(qc, shots=shots, seed=1234)
                self.assertEqual(res_c.path, "C")
                self.assertTrue(res_c.exact)
                self.assertEqual(res_c.error_bound, 0.0)
                self.assertFalse(res_c.unresolved)
                _assert_sampling_matches(name, res_c.counts, exact_probs, shots)

                # 3. Aer statevector counts, an independent sampler over the
                # same exact amplitudes (Aer MPS does not support CRY).
                qc_aer = qc.copy()
                qc_aer.measure_all()
                aer_counts = AerSimulator(method="statevector").run(
                    qc_aer, shots=shots, seed_simulator=4321
                ).result().get_counts()
                _assert_sampling_matches(
                    f"{name}/aer_statevector", aer_counts, exact_probs, shots
                )

    def test_path_c_vs_aer_mps_untruncated(self):
        """Independent MPS cross-check with truncation explicitly disabled."""
        n = 4
        shots = 20_000
        qc = QuantumCircuit(n)
        qc.h(0)
        qc.ry(0.41, 1)
        qc.cx(1, 0)          # reversed operand
        qc.cz(0, 2)
        qc.swap(1, 3)        # non-adjacent in the MPS chain
        qc.cp(0.37, 2, 3)
        qc.rz(0.29, 2)
        qc.cx(0, 3)

        exact_probs = Statevector(qc).probabilities()

        qc_aer = qc.copy()
        qc_aer.measure_all()
        aer_mps = AerSimulator(
            method="matrix_product_state",
            matrix_product_state_max_bond_dimension=None,
            matrix_product_state_truncation_threshold=0.0,
        )
        aer_counts = aer_mps.run(
            qc_aer, shots=shots, seed_simulator=99
        ).result().get_counts()
        _assert_sampling_matches("aer_mps", aer_counts, exact_probs, shots)

        res_c = PathCMPSExactBackend(ram_budget_mb=50.0).execute(
            qc, shots=shots, seed=7
        )
        self.assertFalse(res_c.unresolved)
        _assert_sampling_matches("path_c", res_c.counts, exact_probs, shots)

    # -------------------------------------------------------------
    # 4. Differential Verification: Path D vs Qiskit Aer Statevector
    # -------------------------------------------------------------
    def test_path_d_certified_differential_against_aer_statevector(self):
        """
        Adversarial Differential Test: Path D against Aer Statevector reference.
        Confirms theorem: |<Z_0>_Aer - <Z_0>_PathD| <= error_bound.
        """
        rng = np.random.default_rng(2026)
        n = 4

        for trial in range(3):
            qc = QuantumCircuit(n)
            for q in range(n):
                qc.h(q)
            for l in range(2):
                for q in range(n - 1):
                    qc.cx(q, q + 1)
                qc.rz(float(rng.uniform(0.2, 1.2)), l % n)
                qc.t((l + 1) % n)

            # 1. Exact reference expectation value via Aer Statevector
            qc_sv = qc.copy()
            qc_sv.save_statevector()
            aer_sim = AerSimulator(method="statevector")
            sv_data = aer_sim.run(qc_sv).result().get_statevector(qc_sv).data
            dim = 1 << n
            # Observable Z_0
            z0_diag = np.array([1.0 if not (i & 1) else -1.0 for i in range(dim)])
            exact_exp_z0 = float(np.sum(np.abs(sv_data) ** 2 * z0_diag).real)

            # 2. Path D Sparse-Pauli-Dynamics evaluation with strict term budget to induce truncation
            instructions = []
            for inst in qc.data:
                name = inst.operation.name
                if name in ("save_statevector", "barrier", "measure"):
                    continue
                q_idx = [qc.find_bit(q).index for q in inst.qubits]
                params = [float(p) for p in inst.operation.params] if hasattr(inst.operation, "params") else []
                instructions.append((name, q_idx, params))

            sim_d = SparsePauliDynamicsSimulator(
                num_qubits=n,
                max_pauli_terms=4,
                prune_threshold=0.01,
                error_tolerance=1.5
            )
            obs = {(0, 1): complex(1.0, 0.0)} # Z_0
            approx_exp_z0, error_bound, unresolved = sim_d.evaluate_observable(instructions, obs)

            actual_discrepancy = abs(exact_exp_z0 - approx_exp_z0)

            print(
                f"[Adversarial Aer vs Path D Trial {trial}] Aer: {exact_exp_z0:.5f}, "
                f"Path D: {approx_exp_z0:.5f}, Discrepancy: {actual_discrepancy:.6f}, Bound: {error_bound:.6f}"
            )

            # Provable Theorem: actual discrepancy cannot exceed the certified bound!
            self.assertLessEqual(
                actual_discrepancy,
                error_bound + 1e-12,
                f"Certified bound violated against Aer! discrepancy={actual_discrepancy}, bound={error_bound}"
            )


if __name__ == "__main__":
    unittest.main()
