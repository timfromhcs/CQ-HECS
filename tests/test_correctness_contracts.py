"""
Regression tests for the Four-Path correctness contracts.

Each test here corresponds to a defect that was found and fixed: fabricated
results, silent truncation, silently-ignored gates, and fail-open routing.
These are written as *stronger* tests for the correct specification rather than
loosened versions of the old assertions.
"""

from __future__ import annotations
import math
import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector

from cqhecs.result import SimulationState, hoeffding_total_variation_bound
from cqhecs.circuit_parsing import parse_circuit
from cqhecs.router import FourPathRouter, UnsupportedCircuitError
from cqhecs.circuit_analyzer import CircuitAnalyzer, UnsupportedCircuitInput
from cqhecs.backends.path_a_stabilizer import (
    PathAStabilizerBackend,
    StabilizerTableauSimulator,
)
from cqhecs.backends.path_b_stabilizer_rank import (
    PathBStabilizerRankBackend,
    StabilizerRankError,
)
from cqhecs.backends.path_c_mps_exact import (
    ExactMPSTensorChain,
    PathCMPSExactBackend,
)
from cqhecs.backends.path_d_sparse_pauli import (
    PathDSparsePauliBackend,
    UnsupportedPathDOperation,
)


def _counts_to_probs(counts, num_qubits):
    """
    Converts counts to a probability vector in statevector index order.

    Qiskit renders bitstrings with qubit 0 rightmost, so for a 2-qubit circuit
    "01" means q1=0, q0=1, i.e. statevector index 1. Reading the string
    directly as an integer already gives that index.
    """
    total = sum(counts.values())
    vec = np.zeros(1 << num_qubits)
    for bits, n in counts.items():
        vec[int(bits, 2)] = n / total
    return vec


class TestResultSchema(unittest.TestCase):
    """The correctness contract must keep the three error sources separate."""

    def test_hoeffding_bound_is_rigorous_and_monotonic(self):
        # More shots can only reduce the sampling bound.
        small = hoeffding_total_variation_bound(100, support_size=2)
        large = hoeffding_total_variation_bound(10000, support_size=2)
        self.assertLess(large, small)
        self.assertGreater(small, 0.0)
        # For a binary outcome it is exactly the classic Hoeffding expression.
        self.assertAlmostEqual(
            small, math.sqrt(math.log(40.0) / 200.0), places=12
        )

    def test_bound_reduces_to_classic_hoeffding_for_binary(self):
        """K=2 must reproduce sqrt(ln(2/delta)/(2n)) exactly."""
        for shots in (100, 1000):
            for delta in (0.05, 0.01):
                ours = hoeffding_total_variation_bound(shots, support_size=2,
                                                      delta=delta)
                classic = math.sqrt(math.log(2.0 / delta) / (2.0 * shots))
                self.assertAlmostEqual(ours, classic, places=15)

    def test_bound_grows_with_support_size(self):
        """A wider measurement alphabet needs a looser bound."""
        bounds = [
            hoeffding_total_variation_bound(1000, support_size=k)
            for k in (2, 4, 16, 64)
        ]
        for smaller, larger in zip(bounds, bounds[1:]):
            self.assertLess(smaller, larger)

    def test_degenerate_support_is_exactly_zero(self):
        """A single-outcome distribution cannot deviate."""
        self.assertEqual(hoeffding_total_variation_bound(1000, support_size=1), 0.0)

    def test_bound_is_clamped_to_one(self):
        """TV distance cannot exceed 1, so the bound must not claim otherwise."""
        huge = hoeffding_total_variation_bound(2, support_size=1 << 40)
        self.assertLessEqual(huge, 1.0)

    def test_bound_does_not_overflow_for_wide_registers(self):
        """2**K overflows float64 around K=1024; the log-space form must not."""
        for k in (512, 1024, 4096):
            value = hoeffding_total_variation_bound(1000, support_size=k)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_bound_holds_at_stated_confidence_for_high_cardinality(self):
        """
        The bound may be violated with probability up to delta, so this checks
        the *violation rate*, not each individual trial.

        This is the counterexample for a dimension-free claim: the previous
        implementation used sqrt(ln(2/delta)/(2n)) regardless of support, which
        is exceeded on essentially every trial once K reaches 64.
        """
        shots, delta, trials = 200, 0.05, 1500
        rng = np.random.default_rng(12345)
        naive = math.sqrt(math.log(2.0 / delta) / (2.0 * shots))

        for k in (4, 16, 64):
            bound = hoeffding_total_variation_bound(shots, support_size=k,
                                                    delta=delta)
            p = np.ones(k) / k  # uniform is the worst case for TV
            samples = rng.integers(0, k, size=(trials, shots))
            counts = np.stack(
                [np.bincount(row, minlength=k) for row in samples]
            ) / shots
            tv = 0.5 * np.abs(counts - p).sum(axis=1)
            with self.subTest(support_size=k):
                self.assertLessEqual(float((tv > bound).mean()), delta)
                if k >= 16:
                    # The dimension-free bound really is violated here.
                    self.assertGreater(float((tv > naive).mean()), delta)

    def test_hoeffding_rejects_invalid_arguments(self):
        with self.assertRaises(ValueError):
            hoeffding_total_variation_bound(0)
        with self.assertRaises(ValueError):
            hoeffding_total_variation_bound(-1)
        with self.assertRaises(ValueError):
            hoeffding_total_variation_bound(100, delta=0.0)
        with self.assertRaises(ValueError):
            hoeffding_total_variation_bound(100, delta=1.0)
        with self.assertRaises(ValueError):
            hoeffding_total_variation_bound(100, support_size=0)

    def test_total_error_bound_sums_distribution_metrics(self):
        from cqhecs.result import SimulationResult
        res = SimulationResult(
            path="X", exact=False, error_bound=0.1, unresolved=False,
            numerical_error_bound=1e-12, sampling_error_bound=0.05,
        )
        self.assertAlmostEqual(res.total_error_bound, 0.1 + 1e-12 + 0.05, places=15)

    def test_total_error_bound_is_none_for_observable_only_results(self):
        """
        A bound on expectation values does not bound a bitstring distribution,
        so the two must not be summed into one number.
        """
        from cqhecs.result import SimulationResult
        res = SimulationResult(
            path="D", exact=False, error_bound=0.01, unresolved=False,
            expectation_values={"Z[0]": 0.5}, counts={},
        )
        self.assertIsNone(res.total_error_bound)
        self.assertIsNone(res.to_dict()["error_bound_metric"])

    def test_exact_state_requires_zero_approximation_error(self):
        from cqhecs.result import SimulationResult
        res = SimulationResult(
            path="X", exact=True, error_bound=0.0, unresolved=False
        )
        self.assertEqual(res.state, SimulationState.EXACT)
        # A deliberate approximation must never be labelled EXACT.
        approx = SimulationResult(
            path="X", exact=True, error_bound=1e-3, unresolved=False
        )
        self.assertEqual(approx.state, SimulationState.CERTIFIED)


class TestPathCContract(unittest.TestCase):
    """Path C must not truncate silently and must not fabricate counts."""

    def setUp(self):
        self.backend = PathCMPSExactBackend(ram_budget_mb=100.0)

    def test_rank_selection_discards_only_roundoff(self):
        """The discarded mass must be at the float64 noise floor, not a budget."""
        n = 4
        qc = QuantumCircuit(n)
        for i in range(n):
            qc.h(i)
        for i in range(n - 1):
            qc.cx(i, i + 1)
        qc.rz(0.45, 1)
        qc.cx(0, 1)

        instructions, n_q = parse_circuit(qc)
        mps = ExactMPSTensorChain(num_qubits=n_q)
        import numpy as _np
        for name, qubits, params in instructions:
            if name == "h":
                mps.apply_single_qubit_gate(
                    qubits[0],
                    _np.array([[1, 1], [1, -1]], dtype=complex) / _np.sqrt(2.0),
                )
            elif name == "cx":
                mps.apply_two_qubit_gate(
                    qubits[0], qubits[1],
                    _np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                               [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex),
                )
            elif name == "rz":
                th = params[0]
                mps.apply_single_qubit_gate(
                    qubits[0],
                    _np.array([[_np.exp(-1j * th / 2), 0],
                               [0, _np.exp(1j * th / 2)]], dtype=complex),
                )

        # Roundoff-level, and reported rather than hidden.
        self.assertLess(mps.discarded_spectral_norm, 1e-12)
        self.assertGreaterEqual(mps.max_retained_singular_value, 0.5)

    def test_result_reports_roundoff_separately_from_approximation(self):
        n = 3
        qc = QuantumCircuit(n)
        qc.h(0)
        qc.cx(0, 1)
        qc.t(1)
        res = self.backend.execute(qc, shots=200, seed=42)
        # No deliberate approximation was applied.
        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertFalse(res.metadata["silent_truncation"])

        # Path C does NOT claim a certified roundoff bound: the per-SVD
        # discarded mass does not compose into a state-norm error without a
        # propagation analysis it does not perform. Claiming otherwise would
        # overstate what is known.
        self.assertIsNone(res.numerical_error_bound)
        self.assertIn(
            "not derived", res.metadata["numerical_error_bound_reason"]
        )
        # The measured mass is still reported, labelled as a diagnostic.
        self.assertLess(
            res.metadata["discarded_spectral_mass_diagnostic"], 1e-12
        )

    def test_discarded_mass_is_not_presented_as_a_bound(self):
        """The diagnostic must never masquerade as a certified bound."""
        qc = QuantumCircuit(4)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.rz(0.31, 2)
        qc.cx(2, 3)
        res = self.backend.execute(qc, shots=100, seed=5)
        payload = res.to_dict()
        self.assertIsNone(payload["numerical_error_bound"])
        # The sampling bound is still valid and is a different metric.
        self.assertIsNotNone(payload["sampling_error_bound"])
        self.assertNotIn(
            "discarded_spectral_norm", res.metadata
        )

    def test_matches_exact_statevector(self):
        n = 3
        qc = QuantumCircuit(n)
        qc.h(0)
        qc.cx(0, 1)
        qc.rz(0.31, 1)
        qc.t(2)
        res = self.backend.execute(qc, shots=200000, seed=11)
        exact = Statevector(qc).probabilities()
        got = _counts_to_probs(res.counts, n)
        self.assertLess(0.5 * np.abs(got - exact).sum(), 0.01)

    def test_wide_circuit_returns_no_counts_rather_than_zeros(self):
        """Regression: n>14 used to return {'0'*n: shots}."""
        n = ExactMPSTensorChain.MAX_SAMPLING_QUBITS + 1
        qc = QuantumCircuit(n)
        qc.h(0)
        res = self.backend.execute(qc, shots=100, seed=1)
        self.assertEqual(res.counts, {})
        self.assertFalse(res.metadata.get("counts_supported", False))
        self.assertIn("No counts were fabricated", res.metadata["reason"])

    def test_memory_ceiling_refusal_leaves_state_coherent(self):
        """A refused allocation must not leave a half-applied rewrite."""
        mps = ExactMPSTensorChain(num_qubits=4, max_storage_mb=0.0001)
        mps.max_storage_bytes = 1  # force immediate refusal
        before = mps.to_statevector().copy()
        cx = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                       [0, 0, 0, 1], [0, 0, 1, 0]], dtype=np.complex128)
        # Entangle so a partial rewrite would be observable.
        mps.apply_single_qubit_gate(
            0, np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)
        )
        entangled_before = mps.to_statevector().copy()
        mps.apply_two_qubit_gate(0, 1, cx)
        self.assertTrue(mps.memory_limit_exceeded)
        after = mps.to_statevector()
        np.testing.assert_allclose(after, entangled_before, atol=1e-12)

    def test_unsupported_gate_is_refused(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        instructions, _ = parse_circuit(qc)
        bad = instructions + [("u3", [0], [0.1, 0.2, 0.3])]
        with self.assertRaises(ValueError) as ctx:
            self.backend._validate_instructions(bad)
        self.assertIn("u3", str(ctx.exception))

    def test_rotation_without_parameter_is_refused(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        instructions, _ = parse_circuit(qc)
        with self.assertRaises(ValueError):
            self.backend._validate_instructions(instructions + [("rz", [0], [])])

    def test_mid_circuit_measurement_is_refused(self):
        mc = QuantumCircuit(2, 2)
        mc.h(0)
        mc.measure(0, 0)
        mc.cx(0, 1)
        mc.measure(1, 1)
        with self.assertRaises(ValueError) as ctx:
            self.backend.execute(mc, shots=50)
        self.assertIn("mid-circuit measurement", str(ctx.exception))

    def test_terminal_measurement_marginalizes_correctly(self):
        """Partial measurement must reproduce the exact marginal."""
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.x(2)
        measured = QuantumCircuit(3, 2)
        measured.h(0)
        measured.cx(0, 1)
        measured.x(2)
        measured.measure(0, 0)
        measured.measure(1, 1)

        res = self.backend.execute(measured, shots=200000, seed=5)
        got = _counts_to_probs(res.counts, 2)

        full = Statevector(qc).probabilities()
        # index = q0 + 2*q1 + 4*q2 -> reshape [q2, q1, q0]; marginalise q2.
        expected = full.reshape(2, 2, 2).sum(axis=0).reshape(4)
        self.assertLess(0.5 * np.abs(got - expected).sum(), 0.01)

    def test_swap_files_do_not_collide_across_chains(self):
        """Regression: swap files used fixed names shared between chains."""
        a = ExactMPSTensorChain(num_qubits=4)
        b = ExactMPSTensorChain(num_qubits=4)
        self.assertNotEqual(a.temp_dir, b.temp_dir)
        a.cleanup()
        b.cleanup()


class TestPathBContract(unittest.TestCase):
    """Path B must not fabricate distributions and must apply every gate."""

    def setUp(self):
        self.backend = PathBStabilizerRankBackend()

    def _check_matches_statevector(self, qc, seed=7, shots=200000, tol=0.01):
        res = self.backend.execute(qc, shots=shots, seed=seed)
        exact = Statevector(qc).probabilities()
        got = _counts_to_probs(res.counts, qc.num_qubits)
        tv = 0.5 * np.abs(got - exact).sum()
        self.assertLess(tv, tol, f"TV distance {tv} exceeded {tol}")
        return res

    def test_t_and_tdg_gate(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(0)
        self._check_matches_statevector(qc)

    def test_tdg_t_inverse_is_identity(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.tdg(0)
        qc.t(0)
        self._check_matches_statevector(qc)

    def test_rx_and_ry_are_implemented(self):
        """Regression: RX/RY previously hit an unknown-gate fallthrough."""
        for gate in ("rx", "ry"):
            qc = QuantumCircuit(2)
            qc.h(0)
            getattr(qc, gate)(0.9, 0)
            self._check_matches_statevector(qc)

    def test_clifford_angle_rotation_is_applied(self):
        """Regression: Clifford-angle RZ was silently ignored."""
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cx(0, 1)
        qc.rz(math.pi / 2, 1)
        self._check_matches_statevector(qc)

    def test_mixed_rotations_match_exactly(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cx(0, 1)
        qc.rz(0.7, 0)
        qc.rx(0.9, 1)
        qc.ry(0.3, 0)
        self._check_matches_statevector(qc)

    def test_wide_circuits_match_exact_statevector(self):
        """
        Path B now vectorises its two-qubit gates, so it handles widths that a
        per-amplitude Python loop could not.

        Shot count is chosen against the *state* support: a dense n-qubit state
        has 2**n outcomes, and far fewer shots than that leaves a large
        statistical gap that has nothing to do with correctness.
        """
        for n in (14, 18):
            qc = QuantumCircuit(n)
            qc.h(0)
            for i in range(n - 1):
                qc.cx(i, i + 1)
            qc.t(1)
            qc.rz(0.37, n - 1)
            shots = 400000
            res = self.backend.execute(qc, shots=shots, seed=3)
            self.assertEqual(res.path, "B")
            exact = Statevector(qc).probabilities()
            got = _counts_to_probs(res.counts, n)
            self.assertEqual(sum(res.counts.values()), shots)
            self.assertLess(0.5 * np.abs(got - exact).sum(), 0.05)

    def test_two_qubit_gates_are_vectorised_correctly(self):
        """CX/CZ/SWAP must be exact for every control/target orientation."""
        from cqhecs.backends.path_b_stabilizer_rank import (
            _apply_cx, _apply_cz, _apply_swap,
        )
        n = 4
        dim = 1 << n
        rng = np.random.default_rng(0)
        for a in range(n):
            for b in range(n):
                if a == b:
                    continue
                with self.subTest(pair=(a, b)):
                    state = rng.normal(size=dim) + 1j * rng.normal(size=dim)

                    # CX: only the ctrl=1 row swaps its target halves.
                    want = state.copy()
                    for i in range(dim):
                        if (i >> a) & 1 and not (i >> b) & 1:
                            want[i], want[i | (1 << b)] = (
                                state[i | (1 << b)], state[i],
                            )
                    self.assertTrue(
                        np.allclose(_apply_cx(state.copy(), n, a, b), want,
                                    atol=1e-12)
                    )

                    # CZ: negate |1,1>.
                    want = state.copy()
                    for i in range(dim):
                        if (i >> a) & 1 and (i >> b) & 1:
                            want[i] = -state[i]
                    self.assertTrue(
                        np.allclose(_apply_cz(state.copy(), n, a, b), want,
                                    atol=1e-12)
                    )

                    # SWAP: exchange the differing-bit amplitudes.
                    want = state.copy()
                    for i in range(dim):
                        ba, bb = (i >> a) & 1, (i >> b) & 1
                        if ba != bb:
                            j = (i & ~(1 << a) & ~(1 << b)) | (ba << b) | (bb << a)
                            want[i], want[j] = state[j], state[i]
                    self.assertTrue(
                        np.allclose(_apply_swap(state.copy(), n, a, b), want,
                                    atol=1e-12)
                    )

    def test_two_qubit_gates_do_not_mutate_their_input(self):
        """
        Regression: reshape() returns a view, so writing through it modified the
        caller's statevector. A gate applied to an already-permuted vector
        therefore produced the wrong result.
        """
        from cqhecs.backends.path_b_stabilizer_rank import (
            _apply_cx, _apply_cz, _apply_swap,
        )
        n = 3
        dim = 1 << n
        rng = np.random.default_rng(2)
        for fn in (_apply_cx, _apply_cz, _apply_swap):
            for a, b in ((0, 1), (1, 0), (0, 2), (2, 0)):
                with self.subTest(gate=fn.__name__, pair=(a, b)):
                    state = rng.normal(size=dim) + 1j * rng.normal(size=dim)
                    before = state.copy()
                    fn(state, n, a, b)      # deliberately NOT .copy()
                    np.testing.assert_array_equal(state, before)

    def test_cx_and_cz_are_orientation_symmetric(self):
        """CX(c,t) and CX(t,c) must both be correct unitaries."""
        from cqhecs.backends.path_b_stabilizer_rank import _apply_cx, _apply_swap
        n = 3
        dim = 1 << n
        rng = np.random.default_rng(1)
        state = rng.normal(size=dim) + 1j * rng.normal(size=dim)
        forward = _apply_cx(state.copy(), n, 0, 1)
        backward = _apply_cx(state.copy(), n, 1, 0)
        # Both are involutions.
        self.assertTrue(
            np.allclose(_apply_cx(forward, n, 0, 1), state, atol=1e-12)
        )
        self.assertTrue(
            np.allclose(_apply_cx(backward, n, 1, 0), state, atol=1e-12)
        )
        # Reversing the orientation conjugates by SWAP on that qubit pair:
        # CX(t,c) == SWAP . CX(c,t) . SWAP
        conjugated = _apply_swap(
            _apply_cx(_apply_swap(state.copy(), n, 0, 1), n, 0, 1), n, 0, 1
        )
        self.assertTrue(np.allclose(conjugated, backward, atol=1e-12))

    def test_no_sampling_error_claim_of_zero_total_error(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(0)
        res = self.backend.execute(qc, shots=1000, seed=1)
        # Exact computation, but counts are a finite sample.
        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)
        self.assertIsNotNone(res.sampling_error_bound)
        self.assertGreater(res.total_error_bound, 0.0)

    def test_wide_circuit_raises_instead_of_returning_zeros(self):
        """Regression: n>16 returned {'0'*n: shots}."""
        n = ExactMPSTensorChain.MAX_SAMPLING_QUBITS + 4
        self.assertGreater(n, 16)
        qc = QuantumCircuit(n)
        qc.h(0)
        with self.assertRaises(StabilizerRankError):
            self.backend.execute(qc, shots=10)

    def test_rank_budget_limit_raises(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(0)
        qc.t(1)
        backend = PathBStabilizerRankBackend(max_rank_branches=1)
        with self.assertRaises(ValueError):
            backend.execute(qc, shots=10)

    def test_unknown_gate_is_refused(self):
        instructions = [("h", [0], []), ("u3", [0], [0.1, 0.2, 0.3])]
        with self.assertRaises(StabilizerRankError) as ctx:
            self.backend._validate_instructions(instructions)
        self.assertIn("u3", str(ctx.exception))

    def test_measure_is_refused(self):
        with self.assertRaises(StabilizerRankError):
            self.backend._validate_instructions([("measure", [0], [])])

    def test_invalid_shots_rejected(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        with self.assertRaises(ValueError):
            self.backend.execute(qc, shots=0)


class TestPathDContract(unittest.TestCase):
    """Path D must certify expectation values, not fabricate joint counts."""

    def setUp(self):
        self.backend = PathDSparsePauliBackend()

    def _expectation(self, qc, pauli_label):
        """Reference expectation value from an exact statevector."""
        return float(
            Statevector(qc).expectation_value(SparsePauliOp(pauli_label)).real
        )

    def test_bell_parity_is_recovered(self):
        """Regression: independent marginals gave Z[0]Z[1] = 0 instead of +1."""
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        res = self.backend.execute(qc, shots=10)
        self.assertAlmostEqual(res.expectation_values["Z[0]Z[1]"], 1.0, places=6)
        self.assertAlmostEqual(res.expectation_values["Z[0]"], 0.0, places=6)
        self.assertAlmostEqual(res.expectation_values["Z[1]"], 0.0, places=6)

    def test_ghz_parities_are_recovered(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        res = self.backend.execute(qc, shots=10)
        ev = res.expectation_values
        self.assertAlmostEqual(ev["Z[0]Z[1]"], 1.0, places=6)
        self.assertAlmostEqual(ev["Z[1]Z[2]"], 1.0, places=6)
        self.assertAlmostEqual(ev["Z[0]Z[2]"], 1.0, places=6)
        self.assertAlmostEqual(ev["Z[0]"], 0.0, places=6)

    def test_expectations_match_statevector(self):
        """Covers gates that previously hit the identity fallthrough."""
        circuits = {}
        qc = QuantumCircuit(2); qc.h(0); qc.h(1); qc.cz(0, 1); qc.h(0)
        circuits["cz"] = qc
        qc = QuantumCircuit(2); qc.x(0); qc.swap(0, 1)
        circuits["swap"] = qc
        qc = QuantumCircuit(1); qc.rx(0.9, 0)
        circuits["rx"] = qc
        qc = QuantumCircuit(1); qc.h(0); qc.ry(0.4, 0)
        circuits["ry"] = qc
        qc = QuantumCircuit(1); qc.h(0); qc.t(0)
        circuits["t"] = qc
        qc = QuantumCircuit(2); qc.h(0); qc.cx(0, 1); qc.rz(0.7, 1); qc.t(0)
        circuits["mixed"] = qc

        for name, circuit in circuits.items():
            with self.subTest(circuit=name):
                res = self.backend.execute(circuit, shots=10)
                n = circuit.num_qubits
                for key, value in res.expectation_values.items():
                    qubits = [int(x) for x in __import__("re").findall(r"Z\[(\d+)\]", key)]
                    label = ["I"] * n
                    for q in qubits:
                        label[n - 1 - q] = "Z"
                    expected = self._expectation(circuit, "".join(label))
                    self.assertAlmostEqual(
                        value, expected, places=6,
                        msg=f"{name}/{key}: got {value}, expected {expected}",
                    )

    def test_counts_are_not_produced_by_default(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        res = self.backend.execute(qc, shots=1000, seed=1)
        self.assertEqual(res.counts, {})
        self.assertFalse(res.metadata["counts_supported"])
        self.assertFalse(res.metadata["counts_are_joint_distribution"])
        self.assertIsNotNone(res.expectation_values)

    def test_opt_in_marginal_counts_are_labelled_uncertified(self):
        backend = PathDSparsePauliBackend(allow_uncertified_joint_counts=True)
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        res = backend.execute(qc, shots=1000, seed=1)
        self.assertTrue(res.metadata["counts_supported"])
        self.assertFalse(res.metadata["counts_are_joint_distribution"])
        self.assertEqual(res.metadata["error_bound_covers"], "expectation_values")
        self.assertEqual(res.metadata["error_bound_excludes"], "sampled_counts")
        # The point of the label: the marginals really do lose correlation.
        total = sum(res.counts.values())
        joint_parity = sum(
            v for k, v in res.counts.items() if k[0] == k[1]
        ) / total
        self.assertLess(joint_parity, 0.7)

    def test_unknown_gate_is_refused(self):
        with self.assertRaises(UnsupportedPathDOperation) as ctx:
            self.backend.execute(
                [("h", [0], []), ("ccx", [0, 1, 2], [])], shots=10
            )
        self.assertIn("ccx", str(ctx.exception))

    def test_mid_circuit_measurement_is_refused(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.measure(0, 0)
        qc.cx(0, 1)
        qc.measure(1, 1)
        with self.assertRaises(UnsupportedPathDOperation):
            self.backend.execute(qc, shots=10)

    def test_unresolved_when_bound_exceeds_tolerance(self):
        n = 4
        qc = QuantumCircuit(n)
        for _ in range(4):
            for i in range(n):
                qc.h(i)
                qc.rz(0.5, i)
            for i in range(n - 1):
                qc.cx(i, i + 1)
        backend = PathDSparsePauliBackend(max_pauli_terms=4, error_tolerance=1e-4)
        res = backend.execute(qc, shots=100)
        self.assertTrue(res.unresolved)
        self.assertGreater(res.error_bound, 1e-4)
        self.assertIsNone(res.expectation_values)
        self.assertEqual(res.counts, {})

    def test_invalid_shots_rejected(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        with self.assertRaises(ValueError):
            self.backend.execute(qc, shots=0)


class TestFailClosedRouting(unittest.TestCase):
    """Routing must never silently pick a path that cannot run the circuit."""

    def setUp(self):
        self.router = FourPathRouter()

    def test_analyzer_rejects_unknown_input_types(self):
        for value in (42, None, object(), 3.14, {1, 2}):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(UnsupportedCircuitInput):
                    CircuitAnalyzer().analyze(value)

    def test_analyzer_handles_real_instruction_lists(self):
        props = CircuitAnalyzer().analyze([("h", [0], []), ("cx", [0, 1], [])])
        self.assertEqual(props.num_qubits, 2)
        self.assertTrue(props.is_clifford)
        self.assertEqual(props.recommended_path, "A")

    def test_analyzer_rejects_malformed_instruction_lists(self):
        for bad in ([("h", [0])], [("h", [0], [], 1)], [(1, [0], [])], [("h", ["x"], [])]):
            with self.subTest(bad=bad):
                with self.assertRaises(UnsupportedCircuitInput):
                    CircuitAnalyzer().analyze(bad)

    def test_forced_path_a_on_non_clifford_is_refused(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(1)
        with self.assertRaises(UnsupportedCircuitError) as ctx:
            self.router.route_and_execute(qc, preferred_path="A")
        # The capability check names the offending gate.
        self.assertIn("'t'", str(ctx.exception))
        self.assertIn("Refusing to silently reroute", str(ctx.exception))

    def test_forced_path_with_unsupported_gate_is_refused(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.rx(0.3, 0)
        with self.assertRaises(UnsupportedCircuitError) as ctx:
            self.router.route_and_execute(qc, preferred_path="A")
        self.assertIn("rx", str(ctx.exception))

    def test_auto_mode_still_routes_correctly(self):
        clifford = QuantumCircuit(3)
        clifford.h(0)
        clifford.cx(0, 1)
        clifford.cx(1, 2)
        res = self.router.route_and_execute(clifford, shots=200)
        self.assertEqual(res.path, "A")

        non_clifford = QuantumCircuit(2)
        non_clifford.h(0)
        non_clifford.t(0)
        res = self.router.route_and_execute(non_clifford, shots=200)
        self.assertIn(res.path, ("B", "C"))
        self.assertNotEqual(res.path, "A")

    def test_invalid_run_arguments_are_rejected(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        for kwargs in (
            {"shots": 0}, {"shots": -1}, {"shots": 1.5},
            {"seed": "abc"}, {"error_tolerance": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.router.route_and_execute(qc, **kwargs)

    def test_unknown_path_is_rejected(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        with self.assertRaises(ValueError):
            self.router.route_and_execute(qc, preferred_path="Z")

    def test_router_constructor_validates_arguments(self):
        for kwargs in (
            {"error_tolerance": 0},
            {"max_storage_mb": 0},
            {"max_pauli_terms": 0},
            {"t_rank_threshold": -1},
            {"mps_entanglement_threshold": -1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    FourPathRouter(**kwargs)

    def test_programming_errors_are_not_swallowed(self):
        """A backend bug must surface, not be read as 'try the next path'."""
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(0)
        router = FourPathRouter()

        def boom(*args, **kwargs):
            raise TypeError("internal programming error")

        router.backend_b.execute = boom
        with self.assertRaises(TypeError):
            router.route_and_execute(qc, preferred_path="B", shots=10)


class TestSeedDeterminism(unittest.TestCase):
    """Seeded runs must be reproducible across all paths that emit counts."""

    def test_path_c_is_deterministic(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.rz(0.3, 2)
        backend = PathCMPSExactBackend()
        first = backend.execute(qc, shots=500, seed=99)
        second = backend.execute(qc, shots=500, seed=99)
        self.assertEqual(first.counts, second.counts)

    def test_path_b_is_deterministic(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.t(0)
        qc.cx(0, 1)
        backend = PathBStabilizerRankBackend()
        first = backend.execute(qc, shots=500, seed=99)
        second = backend.execute(qc, shots=500, seed=99)
        self.assertEqual(first.counts, second.counts)


class TestBitstringOrdering(unittest.TestCase):
    """
    Qiskit renders qubit 0 rightmost.

    Every path that emits counts must agree with that convention, otherwise
    results silently disagree with Aer/Stim and with each other.
    """

    def _check_backend(self, backend, circuit, expected_key):
        res = backend.execute(circuit, shots=200, seed=3)
        self.assertEqual(
            sum(res.counts.values()), 200,
            f"{type(backend).__name__} did not emit exactly 200 shots",
        )
        self.assertIn(expected_key, res.counts)

    def test_path_a_bit_order(self):
        # X on qubit 0 of a 3-qubit circuit -> "001"
        qc = QuantumCircuit(3)
        qc.x(0)
        self._check_backend(PathAStabilizerBackend(), qc, "001")

    def test_path_b_bit_order(self):
        qc = QuantumCircuit(3)
        qc.x(0)
        qc.t(0)
        self._check_backend(PathBStabilizerRankBackend(), qc, "001")

    def test_path_c_bit_order(self):
        qc = QuantumCircuit(3)
        qc.x(0)
        qc.t(0)
        self._check_backend(PathCMPSExactBackend(), qc, "001")

    def test_all_paths_agree_on_x_on_qubit_two(self):
        """X on the highest qubit must render as the leftmost character."""
        qc = QuantumCircuit(3)
        qc.x(2)
        expected = "100"
        self._check_backend(PathAStabilizerBackend(), qc, expected)
        self._check_backend(PathBStabilizerRankBackend(), qc, expected)
        self._check_backend(PathCMPSExactBackend(), qc, expected)

    def test_ghz_agreement_across_paths(self):
        """A GHZ state must give 00..0 / 11..1 on every exact path."""
        n = 4
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)
        for backend in (
            PathAStabilizerBackend(),
            PathCMPSExactBackend(),
        ):
            with self.subTest(backend=type(backend).__name__):
                res = backend.execute(qc, shots=400, seed=5)
                total = sum(res.counts.values())
                self.assertGreater(total, 0)
                self.assertTrue(
                    set(res.counts) <= {"0" * n, "1" * n},
                    f"unexpected outcomes: {set(res.counts)}",
                )

    def test_terminal_measurement_marginalizes(self):
        """Measuring a subset must yield the exact marginal on every path."""
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.x(2)

        measured = QuantumCircuit(3, 2)
        measured.h(0)
        measured.cx(0, 1)
        measured.x(2)
        measured.measure(0, 0)
        measured.measure(1, 1)

        full = Statevector(qc).probabilities()
        expected = full.reshape(2, 2, 2).sum(axis=0).reshape(4)

        for backend in (PathAStabilizerBackend(), PathCMPSExactBackend()):
            with self.subTest(backend=type(backend).__name__):
                res = backend.execute(measured, shots=200000, seed=9)
                got = _counts_to_probs(res.counts, 2)
                self.assertLess(0.5 * np.abs(got - expected).sum(), 0.01)


class TestNativePythonParity(unittest.TestCase):
    """
    The native C++ engine and the Python tableau must agree.

    The native HybridEngine renders qubit 0 leftmost while every Python path
    uses the Qiskit convention (qubit 0 rightmost), so its output must be
    normalised rather than passed through.
    """

    def _native_available(self):
        import cqhecs.backends.path_a_stabilizer as pa
        return pa._native is not None and hasattr(pa._native, "HybridEngine")

    def test_native_bit_order_matches_python(self):
        if not self._native_available():
            self.skipTest("native _cqhecs_core not available")
        import cqhecs.backends.path_a_stabilizer as pa

        qc = QuantumCircuit(3)
        qc.x(0)
        engine = pa._native.HybridEngine(3)
        engine.apply_x(0)
        native_counts = pa._reverse_counts(engine.sample_counts(50, 1))
        self.assertIn("001", native_counts)

        py_counts = StabilizerTableauSimulator(3)
        py_counts.apply_x(0)
        py_result, _ = py_counts.sample(shots=50, seed=1)
        self.assertIn("001", py_result)
        self.assertEqual(native_counts, py_result)

    def test_native_falls_back_for_unsupported_gates(self):
        """CZ must not be silently dropped by the native path."""
        import cqhecs.backends.path_a_stabilizer as pa
        # CZ is absent from the native engine's method set.
        self.assertFalse(hasattr(pa._native, "HybridEngine") and
                         hasattr(pa._native.HybridEngine(2), "apply_cz"))
        # ...and the router therefore declines to use native for CZ circuits.
        self.assertFalse(pa._native_can_run([("cz", [0, 1], [])]))
        self.assertTrue(pa._native_can_run([("h", [0], []), ("cx", [0, 1], [])]))

    def test_cz_result_matches_statevector(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cz(0, 1)
        res = PathAStabilizerBackend().execute(qc, shots=200000, seed=4)
        expected = Statevector(qc).probabilities()
        got = _counts_to_probs(res.counts, 2)
        self.assertLess(0.5 * np.abs(got - expected).sum(), 0.01)

    def test_clifford_rotation_via_path_a(self):
        """RZ(pi/2) is the S gate and must be applied, not ignored."""
        rotated = QuantumCircuit(1)
        rotated.h(0)
        rotated.rz(math.pi / 2, 0)
        equivalent = QuantumCircuit(1)
        equivalent.h(0)
        equivalent.s(0)

        r1 = PathAStabilizerBackend().execute(rotated, shots=200000, seed=6)
        r2 = PathAStabilizerBackend().execute(equivalent, shots=200000, seed=6)
        # Both must give the same distribution; exact count equality is not
        # expected because the two circuits are distinct objects.
        p1 = _counts_to_probs(r1.counts, 1)
        p2 = _counts_to_probs(r2.counts, 1)
        self.assertLess(0.5 * np.abs(p1 - p2).sum(), 0.02)
        expected = Statevector(rotated).probabilities()
        self.assertLess(0.5 * np.abs(p1 - expected).sum(), 0.02)

    def test_non_clifford_rotation_is_refused_by_path_a(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.rz(0.7, 0)
        with self.assertRaises(ValueError):
            PathAStabilizerBackend().execute(qc, shots=100)


if __name__ == "__main__":
    unittest.main()