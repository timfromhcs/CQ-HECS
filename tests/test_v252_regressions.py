"""
Regressions for the defects recorded in research/v2_5_2/FINDINGS.md.

- CQ-V252-01: Path B decomposed T as diag(e^{i pi/4}, 1) (the adjoint up to a
  global phase) and Tdg as T. The swap only shows once another phase breaks
  the mirror symmetry of the probabilities, e.g. ``h t s h``.
- CQ-V252-02: ``BackendProfile.to_noise_model`` used the reported gate error
  (an average gate infidelity, as in Qiskit's ``InstructionProperties.error``)
  directly as the depolarizing parameter, halving 1q and shrinking 2q noise.
- CQ-V252-03: the native HybridEngine applied SWAP twice to the tableau, so a
  Clifford circuit's SWAP was the identity on Path A's native engine.
- CQ-V252-04: ``BackendProfile`` accepted float/bool qubit indices, T1/T2 for
  qubits that do not exist, T2 > 2 T1, non-finite values and gate-error keys
  whose width the noise model then dropped silently.
- CQ-V252-05: the noisy density-matrix backend refused ``cu1``, ``crx``,
  ``cry`` and ``crz`` although the router executes them.

Oracles are independent of the code under test: closed-form probabilities,
``qiskit.quantum_info.Statevector`` / ``DensityMatrix`` and
``qiskit.quantum_info.average_gate_fidelity`` on the produced Kraus operators.
"""

from __future__ import annotations

import math
import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Kraus, Statevector, average_gate_fidelity

from cqhecs.backends import path_a_stabilizer
from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.hardware_bridge import (
    BackendProfile,
    InvalidNoiseModelError,
    InvalidProfileError,
    create_fake_manila_profile,
    create_linear_profile,
    depolarizing_parameter_from_infidelity,
)
from cqhecs.router import FourPathRouter
from cqhecs.result import SimulationState


def _frequencies(counts):
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()}


def _tv(p, q):
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in set(p) | set(q))


def _qiskit_probabilities(instructions, n):
    qc = QuantumCircuit(n)
    for name, qubits, params in instructions:
        getattr(qc, name)(*params, *qubits)
    return {k: float(v) for k, v in Statevector(qc).probabilities_dict().items()}


class TestPathBTGateSign(unittest.TestCase):
    """CQ-V252-01."""

    SHOTS = 20000

    def _p0(self, gates):
        router = FourPathRouter()
        res = router.route_and_execute(
            [(g, [0], []) for g in gates], shots=self.SHOTS, seed=11, preferred_path="B"
        )
        self.assertEqual(res.state, SimulationState.EXACT)
        self.assertEqual(res.path, "B")
        return res.counts.get("0", 0) / self.SHOTS, res.sampling_error_bound

    def test_phase_gates_compose_with_the_right_sign(self):
        # H diag(1, e^{i phi}) H |0> gives P(0) = (1 + cos phi) / 2.
        cases = {
            ("h", "t", "s", "h"): math.pi / 4 + math.pi / 2,
            ("h", "s", "t", "h"): math.pi / 4 + math.pi / 2,
            ("h", "tdg", "s", "h"): -math.pi / 4 + math.pi / 2,
            ("h", "t", "sdg", "h"): math.pi / 4 - math.pi / 2,
            ("h", "tdg", "sdg", "h"): -math.pi / 4 - math.pi / 2,
            ("h", "t", "h"): math.pi / 4,
        }
        for gates, phi in cases.items():
            with self.subTest(gates=gates):
                p0, bound = self._p0(gates)
                expected = (1.0 + math.cos(phi)) / 2.0
                # The pre-fix result is 1 - expected (|diff| >= 0.7 here);
                # the bound is the reported finite-shot TV bound.
                self.assertLessEqual(abs(p0 - expected), bound)

    def test_t_then_tdg_is_identity_and_t_twice_is_s(self):
        router = FourPathRouter()
        ref = router.route_and_execute(
            [("h", [0], []), ("s", [0], []), ("h", [0], [])],
            shots=self.SHOTS, seed=5, preferred_path="C",
        )
        res = router.route_and_execute(
            [("h", [0], []), ("t", [0], []), ("t", [0], []), ("h", [0], [])],
            shots=self.SHOTS, seed=5, preferred_path="B",
        )
        self.assertLessEqual(
            _tv(_frequencies(res.counts), _frequencies(ref.counts)),
            res.sampling_error_bound + ref.sampling_error_bound,
        )

    def test_random_clifford_t_circuits_match_qiskit(self):
        rng = np.random.default_rng(2052)
        one_q = ["h", "s", "sdg", "t", "tdg", "x", "y", "z"]
        router = FourPathRouter()
        for trial in range(25):
            n = int(rng.integers(1, 4))
            ins = [("h", [q], []) for q in range(n)]
            for _ in range(int(rng.integers(2, 10))):
                if n > 1 and rng.random() < 0.3:
                    a, b = (int(x) for x in rng.choice(n, size=2, replace=False))
                    ins.append(("cx", [a, b], []))
                else:
                    ins.append((str(rng.choice(one_q)), [int(rng.integers(n))], []))
            ins += [("h", [q], []) for q in range(n)]
            res = router.route_and_execute(ins, shots=self.SHOTS, seed=trial, preferred_path="B")
            with self.subTest(trial=trial, circuit=ins):
                self.assertLessEqual(
                    _tv(_frequencies(res.counts), _qiskit_probabilities(ins, n)),
                    res.sampling_error_bound,
                )


class TestPathASwap(unittest.TestCase):
    """CQ-V252-03 (runs on the native engine whenever it is built)."""

    def test_swap_moves_the_excitation(self):
        router = FourPathRouter()
        for order in ([0, 1], [1, 0]):
            for prep in ("x", "y"):
                with self.subTest(order=order, prep=prep):
                    res = router.route_and_execute(
                        [(prep, [0], []), ("swap", order, [])],
                        shots=64, seed=3, preferred_path="A",
                    )
                    self.assertEqual(res.counts, {"10": 64})

    def test_native_and_python_tableaus_agree_on_random_cliffords(self):
        rng = np.random.default_rng(31)
        backend = path_a_stabilizer.PathAStabilizerBackend()
        gates_1q = ["h", "s", "sdg", "x", "y", "z"]
        for trial in range(30):
            n = int(rng.integers(2, 5))
            ins = []
            for _ in range(int(rng.integers(1, 12))):
                r = rng.random()
                if r < 0.25:
                    a, b = (int(x) for x in rng.choice(n, size=2, replace=False))
                    ins.append(("swap", [a, b], []))
                elif r < 0.45:
                    a, b = (int(x) for x in rng.choice(n, size=2, replace=False))
                    ins.append(("cx", [a, b], []))
                else:
                    ins.append((str(rng.choice(gates_1q)), [int(rng.integers(n))], []))
            ins = [("id", [q], []) for q in range(n)] + ins
            res = backend.execute(ins, shots=4000, seed=trial)
            with self.subTest(trial=trial, native=res.metadata["native_engine"], circuit=ins):
                self.assertLessEqual(
                    _tv(_frequencies(res.counts), _qiskit_probabilities(
                        [g for g in ins if g[0] != "id"], n)),
                    res.sampling_error_bound,
                )


def _average_infidelity(kraus):
    return 1.0 - float(average_gate_fidelity(Kraus(kraus)))


class TestGateErrorIsInfidelity(unittest.TestCase):
    """CQ-V252-02."""

    def test_channel_infidelity_equals_reported_gate_error(self):
        profile = create_fake_manila_profile()
        model = profile.to_noise_model()
        for gate, qmap in profile.gate_errors.items():
            for qubits, err in qmap.items():
                if len(qubits) == 1:
                    channels = model.channels_1q[gate][qubits[0]]
                else:
                    channels = model.channels_2q[gate][qubits]
                self.assertEqual(len(channels), 1)
                with self.subTest(gate=gate, qubits=qubits):
                    self.assertAlmostEqual(
                        _average_infidelity(channels[0].kraus_operators), err, places=12
                    )

    def test_conversion_closed_form(self):
        self.assertAlmostEqual(depolarizing_parameter_from_infidelity(0.01, 1), 0.02)
        self.assertAlmostEqual(depolarizing_parameter_from_infidelity(0.03, 2), 0.04)
        self.assertEqual(depolarizing_parameter_from_infidelity(0.5, 1), 1.0)
        self.assertEqual(depolarizing_parameter_from_infidelity(0.75, 2), 1.0)
        self.assertEqual(depolarizing_parameter_from_infidelity(0.0, 2), 0.0)

    def test_unrepresentable_infidelity_is_refused(self):
        for value, k in ((0.51, 1), (0.76, 2), (-0.1, 1), (float("nan"), 1), (True, 1)):
            with self.subTest(value=value, k=k):
                with self.assertRaises(InvalidNoiseModelError):
                    depolarizing_parameter_from_infidelity(value, k)
        with self.assertRaises(InvalidNoiseModelError):
            depolarizing_parameter_from_infidelity(0.1, 3)
        profile = BackendProfile(name="t", num_qubits=1, gate_errors={"x": {(0,): 0.9}})
        with self.assertRaises(InvalidNoiseModelError):
            profile.to_noise_model()

    def test_noisy_x_matches_independent_density_matrix(self):
        # X with reported infidelity r on |0>, evaluated from the channel's
        # definition on an independently prepared density matrix.
        r = 0.03
        profile = BackendProfile(name="t", num_qubits=1, gate_errors={"x": {(0,): r}})
        res = NoisyDensityMatrixBackend().simulate(
            [("x", [0], [])], noise_model=profile.to_noise_model(), shots=10, seed=1
        )
        # E(rho) = (1 - p) rho + p I/2 with p = 2r (Nielsen 2002).
        p = 2 * r
        rho = DensityMatrix.from_label("1").data
        expected = (1 - p) * rho + p * np.eye(2) / 2
        self.assertAlmostEqual(res.probabilities["1"], float(expected[1, 1].real), places=12)
        self.assertAlmostEqual(res.probabilities["0"], float(expected[0, 0].real), places=12)


class TestProfileValidation(unittest.TestCase):
    """CQ-V252-04."""

    INVALID = [
        {"t1_us": {7: 100.0}},
        {"t2_us": {-1: 50.0}},
        {"t1_us": {0: 10.0}, "t2_us": {0: 20.5}},
        {"t1_us": {0: float("inf")}},
        {"t2_us": {0: float("nan")}},
        {"t1_us": {0: True}},
        {"coupling_map": [(0.9, 1)]},
        {"coupling_map": [(True, 0)]},
        {"gate_errors": {"sx": {(0, 1, 2): 0.1}}},
        {"gate_errors": {"vendor_ms": {(0, 1, 2): 0.1}}},
        {"gate_errors": {"cx": {(0,): 0.1}}},
        {"gate_errors": {"x": {(0, 1): 0.1}}},
        {"gate_errors": {"cx": {(1, 1): 0.1}}},
        {"gate_errors": {"x": {(0,): "0.1"}}},
        {"gate_errors": {"x": {(0,): float("nan")}}},
        {"gate_errors": {"x": {0: 0.1}}},
        {"gate_durations_ns": {"x": {(0,): -1.0}}},
        {"gate_durations_ns": {"x": {(5,): 35.0}}},
        {"readout_errors": {0: (0.1,)}},
        {"readout_errors": {0.0: (0.1, 0.1)}},
    ]

    def test_invalid_profiles_are_refused(self):
        for kwargs in self.INVALID:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(InvalidProfileError):
                    BackendProfile(name="t", num_qubits=3, **kwargs)

    def test_t2_equal_to_twice_t1_is_allowed(self):
        BackendProfile(name="t", num_qubits=1, t1_us={0: 10.0}, t2_us={0: 20.0})

    def test_builtin_profiles_still_validate_and_round_trip(self):
        for profile in (create_fake_manila_profile(), create_linear_profile(4)):
            again = BackendProfile.from_dict(profile.to_dict())
            self.assertEqual(again.gate_errors, profile.gate_errors)
            self.assertEqual(again.t2_us, profile.t2_us)
            profile.to_noise_model()


class TestNoisyDMControlledRotations(unittest.TestCase):
    """CQ-V252-05."""

    def test_controlled_rotations_match_qiskit(self):
        rng = np.random.default_rng(7)
        backend = NoisyDensityMatrixBackend()
        for name, qk_name in (("crx", "crx"), ("cry", "cry"), ("crz", "crz"), ("cu1", "cp")):
            for control, target in ((0, 1), (1, 0), (2, 0)):
                theta = float(rng.uniform(-3, 3))
                ins = [("h", [0], []), ("ry", [1], [0.7]), ("h", [2], []),
                       (name, [control, target], [theta]), ("h", [target], [])]
                qc = QuantumCircuit(3)
                qc.h(0)
                qc.ry(0.7, 1)
                qc.h(2)
                getattr(qc, qk_name)(theta, control, target)
                qc.h(target)
                ref = DensityMatrix(qc).probabilities_dict()
                res = backend.simulate(ins, shots=8, seed=1)
                with self.subTest(gate=name, control=control, target=target):
                    self.assertEqual(res.state, SimulationState.EXACT)
                    self.assertLess(_tv(res.probabilities, ref), 1e-10)


if __name__ == "__main__":
    unittest.main()
