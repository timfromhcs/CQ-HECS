"""
Acceptance Test Suite for 200+ Qubit Simulation and Scalable Full-Register Sampling.

Validates the v2.1.0 capabilities across:
- Path A: 300-qubit exact Clifford GHZ sampling with 1,000 shots (sum == shots, 100% support on {0^n, 1^n}).
- Path C: 300-qubit exact MPS GHZ sampling via MPS-native sequential conditional sampler (sum == shots, zero 2^n allocation).
- Path C: 200-qubit 1D cluster state (H on all qubits + nearest-neighbor CZ) exact sampling.
- Path D: 200-qubit selective expectation values across wide Bell pairs without O(n^2) pair explosion.
- Router: End-to-end routing and execution of 200-300 qubit structured workloads.
"""

from __future__ import annotations
import unittest
from qiskit import QuantumCircuit

from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend, ExactMPSTensorChain
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend
from cqhecs.router import EntanglementAdaptiveRouter


class Test200PlusQubitAcceptance(unittest.TestCase):
    def test_path_a_300q_ghz_1000_shots(self):
        """Path A must draw all 1,000 shots for a 300-qubit GHZ state with exact correlation."""
        n = 300
        shots = 1000
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)

        backend = PathAStabilizerBackend()
        res = backend.execute(qc, shots=shots, seed=42)

        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.unresolved)
        self.assertEqual(res.metadata["sampled_shots"], shots)
        self.assertEqual(sum(res.counts.values()), shots)

        # All observed bitstrings must be exclusively 0...0 and 1...1
        expected_keys = {"0" * n, "1" * n}
        self.assertTrue(set(res.counts.keys()).issubset(expected_keys))
        self.assertIn("0" * n, res.counts)
        self.assertIn("1" * n, res.counts)

        # Statistical balance check: p ~ 0.5 within binomial tolerance
        c0 = res.counts["0" * n]
        self.assertGreater(c0, 400)
        self.assertLess(c0, 600)

    def test_path_c_300q_ghz_native_sequential_sampling(self):
        """Path C must sample a 300-qubit GHZ state using the MPS-native sequential sampler."""
        n = 300
        shots = 1000
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)

        backend = PathCMPSExactBackend(ram_budget_mb=120.0)
        res = backend.execute(qc, shots=shots, seed=123)

        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.unresolved)
        self.assertEqual(res.metadata["sampling_method"], "mps-native-sequential")
        self.assertEqual(res.metadata["max_observed_chi"], 2)
        self.assertEqual(sum(res.counts.values()), shots)

        # Strict GHZ correlation
        expected_keys = {"0" * n, "1" * n}
        self.assertTrue(set(res.counts.keys()).issubset(expected_keys))
        self.assertIn("0" * n, res.counts)
        self.assertIn("1" * n, res.counts)

        # Verify active RAM remains small (< 1 MB for chi=2 MPS)
        self.assertLess(res.metadata["active_ram_mb"], 10.0)

    def test_path_c_200q_cluster_state_sampling(self):
        """Path C must sample a 200-qubit 1D cluster state (H + nearest-neighbor CZ)."""
        n = 200
        shots = 500
        qc = QuantumCircuit(n)
        for i in range(n):
            qc.h(i)
        for i in range(n - 1):
            qc.cz(i, i + 1)

        backend = PathCMPSExactBackend(ram_budget_mb=120.0)
        res = backend.execute(qc, shots=shots, seed=99)

        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.unresolved)
        self.assertEqual(sum(res.counts.values()), shots)
        # 1D cluster state has bond dimension chi <= 4
        self.assertLessEqual(res.metadata["max_observed_chi"], 4)

    def test_path_d_200q_selective_observables(self):
        """Path D evaluates selective long-range observables on a 200-qubit Bell pair."""
        n = 200
        qc = QuantumCircuit(n)
        qc.h(0)
        qc.cx(0, 199)

        backend = PathDSparsePauliBackend()
        res = backend.execute(
            qc,
            observables=["Z[0]", "Z[199]", "Z[0]Z[199]"]
        )

        self.assertFalse(res.unresolved)
        self.assertIsNotNone(res.expectation_values)
        vals = res.expectation_values
        self.assertAlmostEqual(vals["Z[0]"], 0.0, places=12)
        self.assertAlmostEqual(vals["Z[199]"], 0.0, places=12)
        self.assertAlmostEqual(vals["Z[0]Z[199]"], 1.0, places=12)
        self.assertLess(res.error_bound, 1e-12)

    def test_router_300q_ghz_routes_to_path_a(self):
        """Router identifies 300Q GHZ as Clifford and routes to Path A."""
        n = 300
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)

        router = EntanglementAdaptiveRouter()
        res = router.route_and_execute(qc, shots=500, seed=7)
        self.assertEqual(res.path, "A")
        self.assertEqual(sum(res.counts.values()), 500)
        self.assertTrue(set(res.counts.keys()).issubset({"0" * n, "1" * n}))

    def test_router_200q_mps_routes_to_path_c(self):
        """Router routes 200Q 1D non-Clifford circuit with T-gates to Path C."""
        n = 200
        qc = QuantumCircuit(n)
        qc.h(0)
        # Apply T gates on first 16 qubits (exceeding t_rank_threshold=14)
        for i in range(16):
            qc.t(i)
        # 1D nearest-neighbor entangling gates (cut width = 1)
        for i in range(n - 1):
            qc.cx(i, i + 1)

        router = EntanglementAdaptiveRouter()
        props = router.analyzer.analyze(qc)
        self.assertEqual(props.recommended_path, "C")

    def test_path_c_refuses_beyond_max_sampling_qubits(self):
        """Path C refuses to fabricate counts for circuits exceeding MAX_SAMPLING_QUBITS."""
        n = ExactMPSTensorChain.MAX_SAMPLING_QUBITS + 1
        qc = QuantumCircuit(n)
        qc.h(0)

        backend = PathCMPSExactBackend()
        res = backend.execute(qc, shots=100, seed=1)
        self.assertEqual(res.counts, {})
        self.assertFalse(res.metadata["counts_supported"])
        self.assertIn("No counts were fabricated", res.metadata["reason"])


if __name__ == "__main__":
    unittest.main()
