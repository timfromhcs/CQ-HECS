"""Path C numerical assurance (W6 / B1).

Scope: tiny-n comparison against independent dense references (Qiskit
Statevector), SVD/numerical-rank instrumentation, sampled-count and
reduced-density-matrix checks, and deliberately injected mapping defects that
the tests must catch. These are TESTS of float64 agreement, not proofs of a
propagated numerical error bound (none is derived; see research/v7/NUMERICS_B_C.md).
"""

import unittest
from unittest import mock

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector, partial_trace, DensityMatrix

import cqhecs.backends.path_c_mps_exact as pc
from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain, PathCMPSExactBackend

STATE_TOL = 1e-10


def _chain_matrix(op_matrix: np.ndarray, k: int) -> np.ndarray:
    t = np.asarray(op_matrix, dtype=np.complex128).reshape((2,) * (2 * k))
    out = tuple(reversed(range(k)))
    inn = tuple(reversed(range(k, 2 * k)))
    return t.transpose(out + inn).reshape(1 << k, 1 << k)


def _to_qiskit_order(vec: np.ndarray, n: int) -> np.ndarray:
    return np.asarray(vec).reshape((2,) * n).transpose(tuple(reversed(range(n)))).reshape(-1)


def build_chain(qc: QuantumCircuit) -> ExactMPSTensorChain:
    """Drive the chain with exact matrices taken from Qiskit operators."""
    n = qc.num_qubits
    mps = ExactMPSTensorChain(n)
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        m = Operator(inst.operation).data
        if len(qs) == 1:
            mps.apply_single_qubit_gate(qs[0], m)
        else:
            mps.apply_two_qubit_gate(qs[0], qs[1], _chain_matrix(m, 2))
    return mps


def chain_state(mps, n):
    return _to_qiskit_order(mps.to_statevector(), n)


def circuits():
    out = {}
    q = QuantumCircuit(2)
    q.h(0)
    q.cx(0, 1)
    out["bell"] = q
    q = QuantumCircuit(5)
    q.h(0)
    for i in range(4):
        q.cx(i, i + 1)
    out["ghz5"] = q
    q = QuantumCircuit(4)
    q.x(1)
    for j in range(4):
        q.h(j)
        for k in range(j + 1, 4):
            q.cp(np.pi / 2 ** (k - j), k, j)
    q.swap(0, 3)
    q.swap(1, 2)
    out["qft4"] = q
    q = QuantumCircuit(6)
    q.h(0)
    q.h(5)
    q.cx(0, 5)
    q.cx(5, 2)
    q.cz(1, 4)
    q.t(5)
    q.cx(4, 0)
    out["long_range"] = q
    q = QuantumCircuit(5)
    q.h(range(5))
    q.swap(0, 4)
    q.swap(1, 3)
    q.cx(4, 0)
    out["swap_net"] = q
    q = QuantumCircuit(4)
    q.h(range(4))
    q.crx(0.7, 3, 0)
    q.cry(1.1, 2, 0)
    q.crz(0.4, 1, 3)
    q.cp(0.9, 3, 1)
    out["controlled_rot_reversed"] = q
    q = QuantumCircuit(4)
    q.h(range(4))
    q.cx(0, 3)
    q.cx(0, 3)
    q.h(range(4))
    out["inverse_identity"] = q
    rng = np.random.default_rng(7)
    for n in (3, 5, 7):
        q = QuantumCircuit(n)
        for _ in range(14):
            g = int(rng.integers(0, 6))
            a, b = (int(x) for x in rng.choice(n, 2, replace=False))
            if g == 0:
                q.h(a)
            elif g == 1:
                q.t(a)
            elif g == 2:
                q.rx(float(rng.uniform(0, 6)), a)
            elif g == 3:
                q.ry(float(rng.uniform(0, 6)), a)
            elif g == 4:
                q.cx(a, b)
            else:
                q.cz(a, b)
        out[f"random{n}"] = q
    return out


class TestPathCDenseAgreement(unittest.TestCase):
    def test_state_matches_dense_reference_all_families(self):
        for name, qc in circuits().items():
            with self.subTest(name):
                ref = Statevector(qc).data
                mps = build_chain(qc)
                try:
                    got = chain_state(mps, qc.num_qubits)
                finally:
                    mps.cleanup()
                self.assertLess(np.max(np.abs(got - ref)), STATE_TOL)
                self.assertAlmostEqual(float(np.linalg.norm(got)), 1.0, places=10)

    def test_rank_floor_not_triggered_on_generic_circuits(self):
        for name, qc in circuits().items():
            with self.subTest(name):
                mps = build_chain(qc)
                try:
                    self.assertLessEqual(
                        mps.max_discarded_relative,
                        ExactMPSTensorChain.SINGULAR_VALUE_ROUNDOFF_RATIO,
                    )
                    self.assertGreater(
                        mps.min_retained_relative,
                        ExactMPSTensorChain.SINGULAR_VALUE_ROUNDOFF_RATIO,
                    )
                finally:
                    mps.cleanup()

    def test_reduced_density_matrices_match_dense(self):
        for name in ("ghz5", "random5", "random7", "long_range"):
            qc = circuits()[name]
            n = qc.num_qubits
            mps = build_chain(qc)
            try:
                sv = chain_state(mps, n)
            finally:
                mps.cleanup()
            ref = DensityMatrix(Statevector(qc))
            got = DensityMatrix(Statevector(sv))
            for keep in ([0], [1, 2], [0, n - 1]):
                with self.subTest(name=name, keep=keep):
                    trace_out = [q for q in range(n) if q not in keep]
                    a = partial_trace(ref, trace_out).data
                    b = partial_trace(got, trace_out).data
                    self.assertLess(np.max(np.abs(a - b)), STATE_TOL)

    def test_sampled_counts_within_reported_hoeffding_bound(self):
        shots = 20000
        for name in ("bell", "qft4", "random5", "controlled_rot_reversed"):
            qc = circuits()[name]
            n = qc.num_qubits
            res = PathCMPSExactBackend().execute(qc, shots=shots, seed=11)
            self.assertFalse(res.unresolved)
            probs = Statevector(qc).probabilities()
            emp = np.zeros(1 << n)
            for bs, c in res.counts.items():
                emp[int(bs, 2)] = c / shots
            tv = 0.5 * float(np.sum(np.abs(emp - probs)))
            with self.subTest(name):
                self.assertLessEqual(tv, res.sampling_error_bound)


class TestPathCErrorSemantics(unittest.TestCase):
    def test_error_fields_keep_contract(self):
        qc = circuits()["random5"]
        res = PathCMPSExactBackend().execute(qc, shots=64, seed=1)
        self.assertEqual(res.error_bound, 0.0)
        self.assertIsNone(res.numerical_error_bound)
        md = res.metadata
        for key in (
            "max_discarded_singular_value",
            "max_discarded_relative",
            "min_retained_relative",
            "svd_count",
            "svd_steps_with_discard",
            "state_norm_sq_at_sampling",
            "numerical_error_bound_reason",
        ):
            self.assertIn(key, md)
        self.assertAlmostEqual(md["state_norm_sq_at_sampling"], 1.0, places=10)
        self.assertGreater(md["svd_count"], 0)

    def test_floor_discards_tiny_physical_schmidt_value_and_reports_it(self):
        """A genuine entangler of angle ~4e-14 is below the 1e-13 relative floor.

        The floor discards it; the result must say so and still carry NO
        numerical_error_bound. The small observed state error is an
        observation, not a certificate.
        """
        theta = 4e-14
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.crx(theta, 0, 1)
        res = PathCMPSExactBackend().execute(qc, shots=32, seed=3)
        md = res.metadata
        self.assertTrue(md["numerical_rank_truncation_applied"])
        self.assertGreater(md["max_discarded_singular_value"], 0.0)
        self.assertLessEqual(
            md["max_discarded_relative"], ExactMPSTensorChain.SINGULAR_VALUE_ROUNDOFF_RATIO
        )
        self.assertEqual(md["numerical_status"], "numerical_rank_reduced")
        self.assertEqual(res.error_bound, 0.0)
        self.assertIsNone(res.numerical_error_bound)
        mps = build_chain(qc)
        try:
            err = np.max(np.abs(chain_state(mps, 2) - Statevector(qc).data))
            self.assertGreater(mps.svd_steps_with_discard, 0)
        finally:
            mps.cleanup()
        self.assertLess(err, 1e-12)

    def test_resource_refusal_has_no_counts_and_no_certificate(self):
        qc = circuits()["random7"]
        res = PathCMPSExactBackend(ram_budget_mb=1, max_storage_mb=1).execute(qc, shots=8)
        if res.unresolved:
            self.assertEqual(res.counts, {})
            self.assertFalse(res.exact)
            self.assertEqual(res.error_bound, float("inf"))


class TestPathCInjectedDefectsAreCaught(unittest.TestCase):
    """The comparison harness must fail when the mapping is deliberately wrong."""

    def _max_err(self, qc):
        mps = build_chain(qc)
        try:
            return float(
                np.max(np.abs(chain_state(mps, qc.num_qubits) - Statevector(qc).data))
            )
        finally:
            mps.cleanup()

    def test_injected_missing_swap_back_is_caught(self):
        qc = circuits()["long_range"]
        self.assertLess(self._max_err(qc), STATE_TOL)

        def no_swap_back(self_, q1, q2, g):
            lo, hi = min(q1, q2), max(q1, q2)
            swap = np.array(
                [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=complex
            )
            for i in range(lo, hi - 1):
                self_.apply_two_qubit_gate(i, i + 1, swap)
            if q1 < q2:
                self_.apply_two_qubit_gate(hi - 1, hi, g)
            else:
                self_.apply_two_qubit_gate(hi, hi - 1, g)
            # defect: swaps are not undone

        with mock.patch.object(
            ExactMPSTensorChain, "_apply_non_adjacent_two_qubit_gate", no_swap_back
        ):
            self.assertGreater(self._max_err(qc), 1e-3)

    def test_injected_operand_order_defect_is_caught_at_backend_level(self):
        qc = circuits()["controlled_rot_reversed"]
        shots = 20000
        probs = Statevector(qc).probabilities()

        def tv(res):
            emp = np.zeros(len(probs))
            for bs, c in res.counts.items():
                emp[int(bs, 2)] = c / shots
            return 0.5 * float(np.sum(np.abs(emp - probs)))

        good = PathCMPSExactBackend().execute(qc, shots=shots, seed=5)
        self.assertLessEqual(tv(good), good.sampling_error_bound)
        with mock.patch.object(
            pc, "_chain_two_qubit_matrix", lambda m: np.asarray(m, dtype=np.complex128)
        ):
            bad = PathCMPSExactBackend().execute(qc, shots=shots, seed=5)
        self.assertGreater(tv(bad), good.sampling_error_bound)

    def test_injected_endianness_defect_is_caught(self):
        qc = circuits()["random5"]
        mps = build_chain(qc)
        try:
            raw = mps.to_statevector()  # chain order (q0 outermost), not Qiskit order
        finally:
            mps.cleanup()
        self.assertGreater(np.max(np.abs(raw - Statevector(qc).data)), 1e-3)


if __name__ == "__main__":
    unittest.main()
