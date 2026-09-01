"""
Test Suite: Path Transitions and Boundary Conditions.
Verifies the exact transitions between:
  Path A (Clifford, T=0)
  Path B (Clifford + Low T, T <= 14)
  Path C (MPS without cutoff, 1D nearest-neighbor topology)
  Path D (Certified Sparse-Pauli-Dynamics approximation)
Also tests error tolerance bounds, storage budget escalations, and unresolved flags.
"""

import unittest
import math
from qiskit import QuantumCircuit

from cqhecs.circuit_analyzer import CircuitAnalyzer
from cqhecs.router import FourPathRouter
from cqhecs.result import SimulationResult
from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend


class TestPathTransitionsAndBoundaries(unittest.TestCase):

    def setUp(self):
        self.router = FourPathRouter()
        self.analyzer = CircuitAnalyzer()

    # -------------------------------------------------------------
    # 1. Boundary A -> B: Clifford vs Single T / RZ non-Clifford
    # -------------------------------------------------------------
    def test_transition_a_to_b_on_first_t_gate(self):
        """Zero T gates routes to A; exactly one T gate routes to B."""
        qc_a = QuantumCircuit(4)
        qc_a.h(0)
        qc_a.cx(0, 1)
        qc_a.s(2)
        qc_a.rz(math.pi / 2.0, 3) # Clifford RZ(pi/2) = S

        res_a = self.router.route_and_execute(qc_a, shots=200)
        self.assertEqual(res_a.path, "A")
        self.assertTrue(res_a.exact)
        self.assertEqual(res_a.error_bound, 0.0)

        # Now add a single T gate: MUST transition to Path B
        qc_b = qc_a.copy()
        qc_b.t(1)

        res_b = self.router.route_and_execute(qc_b, shots=200)
        self.assertEqual(res_b.path, "B")
        self.assertTrue(res_b.exact)
        self.assertEqual(res_b.error_bound, 0.0)

    # -------------------------------------------------------------
    # 2. Boundary B -> C: T-Count Threshold (T=14 vs T=15)
    # -------------------------------------------------------------
    def test_transition_b_to_c_at_threshold(self):
        """T-count <= 14 routes to Path B; T-count >= 15 with 1D connectivity routes to C."""
        n = 6
        # Case B: exactly 14 T-gates
        qc_b = QuantumCircuit(n)
        for i in range(n):
            qc_b.h(i)
        for i in range(14):
            qc_b.t(i % n)
        for i in range(n - 1):
            qc_b.cx(i, i + 1)

        props_b = self.analyzer.analyze(qc_b)
        self.assertEqual(props_b.t_count, 14)
        self.assertEqual(props_b.recommended_path, "B")

        # Case C: exactly 15 T-gates (exceeds t_rank_threshold of 14)
        qc_c = QuantumCircuit(n)
        for i in range(n):
            qc_c.h(i)
        for i in range(15):
            qc_c.t(i % n)
        for i in range(n - 1):
            qc_c.cx(i, i + 1)

        props_c = self.analyzer.analyze(qc_c)
        self.assertEqual(props_c.t_count, 15)
        self.assertEqual(props_c.recommended_path, "C")

    # -------------------------------------------------------------
    # 3. Boundary C -> D: Entanglement & Non-1D All-to-All Topology
    # -------------------------------------------------------------
    def test_transition_c_to_d_on_high_cross_entanglement(self):
        """High qubit count, high T-count, and non-1D long-range CX gates route to Path D."""
        analyzer = CircuitAnalyzer(t_rank_threshold=14, mps_entanglement_threshold=4)
        n = 30
        qc_d = QuantumCircuit(n)
        for i in range(n):
            qc_d.h(i)
            qc_d.t(i)
            qc_d.t(i) # 60 T gates total
        # Non-1D long-range cross-entanglement across central bipartite cut
        for i in range(10):
            qc_d.cx(i, 29 - i)
            qc_d.cx(i, 20 + i)

        props_d = analyzer.analyze(qc_d)
        self.assertGreater(props_d.t_count, 14)
        self.assertGreater(props_d.max_cut_width, 4)
        self.assertEqual(props_d.recommended_path, "D")

    # -------------------------------------------------------------
    # 4. Storage Limit & Budget Guard in Path C
    # -------------------------------------------------------------
    def test_path_c_storage_budget_tracking(self):
        """Path C tracks tensor byte allocations and respects storage budget."""
        qc = QuantumCircuit(4)
        for i in range(4):
            qc.h(i)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.cx(2, 3)

        # Budget of 50 MB
        backend_c = PathCMPSExactBackend(ram_budget_mb=50.0, max_storage_mb=100.0)
        res = backend_c.execute(qc, shots=100)

        self.assertEqual(res.path, "C")
        self.assertTrue(res.exact)
        self.assertFalse(res.unresolved)
        self.assertIn("max_observed_chi", res.metadata)
        self.assertIn("active_ram_mb", res.metadata)

    # -------------------------------------------------------------
    # 5. Path D Certification & Rejection Strictness
    # -------------------------------------------------------------
    def test_path_d_strict_tolerance_rejection(self):
        """Path D must mark unresolved=True whenever error bound exceeds error_tolerance."""
        qc = QuantumCircuit(4)
        for _ in range(4):
            for i in range(4):
                qc.h(i)
                qc.rz(0.5, i)
            for i in range(3):
                qc.cx(i, i + 1)

        # Router with small term budget of 4 to force truncation
        router_strict = FourPathRouter(max_pauli_terms=4)

        # Tolerance of 0.0001 with 4 max terms
        res_rejected = router_strict.route_and_execute(
            qc,
            preferred_path="D",
            error_tolerance=1e-4,
            shots=100
        )
        self.assertEqual(res_rejected.path, "D")
        self.assertTrue(res_rejected.unresolved)
        self.assertGreater(res_rejected.error_bound, 1e-4)

        # Tolerance of 2.0 (broad enough for the small circuit)
        res_accepted = self.router.route_and_execute(
            qc,
            preferred_path="D",
            error_tolerance=2.5,
            shots=100
        )
        self.assertEqual(res_accepted.path, "D")
        self.assertFalse(res_accepted.unresolved)


if __name__ == "__main__":
    unittest.main()
