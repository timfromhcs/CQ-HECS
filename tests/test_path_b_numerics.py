"""Path B numerical assurance (W6 / B1): branch mass, conditioning, dense agreement.

These tests check float64 agreement with an independent dense reference and
the reporting of dropped branch mass. They do not prove a round-off bound.
"""

import unittest
from unittest import mock

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from cqhecs.backends.path_b_stabilizer_rank import (
    PathBStabilizerRankBackend,
    StabilizerRankError,
    StabilizerRankSimulator,
)
from cqhecs.circuit_parsing import parse_circuit


def _sim_state(qc, **kw):
    instrs, n = parse_circuit(qc)
    sim = StabilizerRankSimulator(n, **kw)
    sim.execute_circuit(instrs, shots=16, seed=1)
    return sim, n


def _families():
    out = {}
    q = QuantumCircuit(3)
    q.h(0)
    q.t(0)
    q.cx(0, 1)
    q.tdg(1)
    q.h(1)
    q.t(2)
    q.cx(1, 2)
    out["clifford_t"] = q
    q = QuantumCircuit(4)
    q.h(range(4))
    q.rx(0.7, 0)
    q.ry(1.3, 1)
    q.rz(2.1, 2)
    q.cx(0, 3)
    q.t(3)
    out["rotations"] = q
    q = QuantumCircuit(5)
    rng = np.random.default_rng(3)
    t = 0
    for _ in range(16):
        a, b = (int(x) for x in rng.choice(5, 2, replace=False))
        g = int(rng.integers(0, 4))
        if g == 0:
            q.h(a)
        elif g == 1:
            q.cx(a, b)
        elif g == 2 and t < 5:
            q.t(a)
            t += 1
        else:
            q.s(a)
    out["random_low_t"] = q
    return out


class TestPathBDenseAgreement(unittest.TestCase):
    def test_statevector_matches_dense_reference(self):
        for name, qc in _families().items():
            with self.subTest(name):
                sim, _ = _sim_state(qc)
                ref = Statevector(qc).data
                self.assertLess(np.max(np.abs(sim.last_statevector - ref)), 1e-12)

    def test_sampled_counts_within_hoeffding_bound(self):
        shots = 20000
        for name, qc in _families().items():
            res = PathBStabilizerRankBackend().execute(qc, shots=shots, seed=2)
            probs = Statevector(qc).probabilities()
            emp = np.zeros(len(probs))
            for bs, c in res.counts.items():
                emp[int(bs, 2)] = c / shots
            with self.subTest(name):
                self.assertLessEqual(
                    0.5 * float(np.abs(emp - probs).sum()), res.sampling_error_bound
                )


class TestPathBBranchMassAndConditioning(unittest.TestCase):
    def test_no_drop_reports_zero_mass_and_unit_norm(self):
        res = PathBStabilizerRankBackend().execute(_families()["clifford_t"], shots=32)
        md = res.metadata
        self.assertEqual(md["discarded_branch_weight_mass"], 0.0)
        self.assertEqual(md["discarded_branch_count"], 0)
        self.assertFalse(md["truncation_applied"])
        self.assertLess(md["norm_deviation"], 1e-12)
        self.assertAlmostEqual(md["renormalization_factor"], 1.0, places=10)
        self.assertEqual(res.error_bound, 0.0)
        self.assertIsNone(res.numerical_error_bound)
        self.assertIn("numerical_error_bound_reason", md)

    def test_dropped_branch_mass_is_reported_and_bounds_observed_error(self):
        # A single small angle is treated as Clifford (|theta| < 1e-7 tolerance),
        # so the numerical-zero drop is only reachable through a product of many
        # small weights: the all-ones branch has weight sin(0.05)**12 ~ 2.4e-16.
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        for _ in range(12):
            qc.rx(0.1, 0)
        sim, _ = _sim_state(qc)
        self.assertEqual(sim.discarded_branch_count, 1)
        self.assertGreater(sim.discarded_branch_weight_mass, 0.0)
        err = float(np.linalg.norm(sim.last_statevector - Statevector(qc).data))
        # Dropped Clifford branch states have unit norm, so by the triangle
        # inequality the dropped-branch contribution alone is at most the dropped
        # mass. The OBSERVED error also contains float64 round-off from summing
        # thousands of branches (here larger than the dropped mass itself), which
        # is why error_bound is NOT a total-error certificate and
        # numerical_error_bound stays None. Assert only the loose total.
        self.assertLessEqual(err, sim.discarded_branch_weight_mass + 1e-12)
        self.assertGreater(sim.discarded_branch_count, 0)
        res = PathBStabilizerRankBackend().execute(qc, shots=16)
        self.assertEqual(res.error_bound, res.metadata["discarded_branch_weight_mass"])
        self.assertTrue(res.metadata["truncation_applied"])
        self.assertIsNone(res.numerical_error_bound)

    def test_broken_normalisation_is_refused_not_renormalised(self):
        qc = _families()["clifford_t"]
        orig = StabilizerRankSimulator._evolve_clifford_statevector

        def doubled(self_, instrs):
            return 2.0 * orig(self_, instrs)

        with mock.patch.object(
            StabilizerRankSimulator, "_evolve_clifford_statevector", doubled
        ):
            with self.assertRaises(StabilizerRankError):
                PathBStabilizerRankBackend().execute(qc, shots=8)

    def test_branch_budget_refusal_is_typed(self):
        qc = QuantumCircuit(1)
        for _ in range(5):
            qc.t(0)
        with self.assertRaises(ValueError):
            PathBStabilizerRankBackend(max_rank_branches=8).execute(qc, shots=8)

    def test_injected_coefficient_defect_is_caught(self):
        """A conjugated T decomposition must be flagged by the dense oracle."""
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.t(0)
        qc.h(0)
        sim, _ = _sim_state(qc)
        self.assertLess(np.max(np.abs(sim.last_statevector - Statevector(qc).data)), 1e-12)
        wrong = QuantumCircuit(1)
        wrong.h(0)
        wrong.tdg(0)
        wrong.h(0)
        self.assertGreater(
            np.max(np.abs(sim.last_statevector - Statevector(wrong).data)), 1e-3
        )


if __name__ == "__main__":
    unittest.main()
