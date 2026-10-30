"""
Noisy Pauli expectation values (v3 plan, workstream W8).

Oracles are independent of the code under test:

* Qiskit Aer's density-matrix simulator with channels built by Aer's own
  constructors (``depolarizing_error``, ``amplitude_damping_error``,
  ``thermal_relaxation_error``, ``ReadoutError``), and readout applied from
  Aer's assignment probabilities;
* when qiskit-ibm-runtime is installed, Aer's complete device pipeline
  ``NoiseModel.from_backend(FakeManilaV2/FakeLagosV2)`` on real calibration.

Aer's simulator drops noise terms with probability < 1e-10 and may lose a few
1e-9 of trace (research/v3/EXECUTION_LOG.md, E-V3-02); comparisons allow
``1e-12`` plus that reported loss.
"""

from __future__ import annotations

import importlib.util
import unittest
import warnings

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel as AerNoiseModel
from qiskit_aer.noise import (
    ReadoutError,
    amplitude_damping_error,
    depolarizing_error,
    thermal_relaxation_error,
)

from cqhecs.expectation import ExpectationError, expectation_values
from cqhecs.hardware_bridge import (
    AmplitudeDampingChannel,
    BackendProfile,
    ComposedChannel,
    DepolarizingChannel,
    FakeHardwareBackend,
    NoiseModel,
    OutOfModelError,
    TensorChannel,
    ThermalRelaxationChannel,
    TwoQubitDepolarizingChannel,
)
from cqhecs.noisy_expectation import (
    heisenberg_matrix_1q,
    heisenberg_matrix_2q,
    noisy_expectation_values,
)

HAVE_RUNTIME = importlib.util.find_spec("qiskit_ibm_runtime") is not None
N = 3


def _models():
    """The same noise in CQ-HECS and in Aer (each built by its own code)."""
    ours = NoiseModel(name="test")
    aer = AerNoiseModel()
    for q, (p, gamma) in enumerate(((0.03, 0.05), (0.01, 0.12), (0.05, 0.02))):
        ours.add_1q_channel("sx", q, ComposedChannel(DepolarizingChannel(p), AmplitudeDampingChannel(gamma)))
        aer.add_quantum_error(depolarizing_error(p, 1).compose(amplitude_damping_error(gamma)), "sx", [q])
        ours.add_1q_channel("x", q, ThermalRelaxationChannel(50.0, 40.0, 300.0 * (q + 1)))
        aer.add_quantum_error(thermal_relaxation_error(50e3, 40e3, 300.0 * (q + 1)), "x", [q])
        p01, p10 = 0.02 + 0.01 * q, 0.05 - 0.01 * q
        ours.set_readout_error(q, p01, p10)
        aer.add_readout_error(ReadoutError([[1 - p01, p01], [p10, 1 - p10]]), [q])
    for a, b, p in ((0, 1, 0.04), (1, 2, 0.08)):
        ours.add_2q_channel("cx", (a, b), TwoQubitDepolarizingChannel(p))
        aer.add_quantum_error(depolarizing_error(p, 2), "cx", [a, b])
    # An asymmetric two-qubit channel: damping only on the control (first operand).
    ours.add_2q_channel("cx", (2, 1), TensorChannel(AmplitudeDampingChannel(0.2), DepolarizingChannel(0.0)))
    # Qiskit's a.tensor(b) puts b on the first qarg, so the damping goes last.
    aer.add_quantum_error(depolarizing_error(0.0, 1).tensor(amplitude_damping_error(0.2)), "cx", [2, 1])
    return ours, aer


def _random_circuit(rng, n, depth, edges):
    qc = QuantumCircuit(n)
    ins = [("barrier", list(range(n)), [])]
    for _ in range(depth):
        r = rng.random()
        if r < 0.3:
            q = int(rng.integers(n))
            qc.sx(q)
            ins.append(("sx", [q], []))
        elif r < 0.45:
            q = int(rng.integers(n))
            qc.x(q)
            ins.append(("x", [q], []))
        elif r < 0.65:
            q, theta = int(rng.integers(n)), float(rng.uniform(-3, 3))
            qc.rz(theta, q)
            ins.append(("rz", [q], [theta]))
        else:
            a, b = edges[int(rng.integers(len(edges)))]
            qc.cx(a, b)
            ins.append(("cx", [a, b], []))
    return qc, ins


def _aer_value(qc, aer_model, label, n):
    """``<label>`` with readout, from Aer's density matrix and Aer's assignment matrices."""
    circ = qc.copy()
    circ.save_density_matrix()
    rho = np.asarray(AerSimulator(method="density_matrix", noise_model=aer_model)
                     .run(circ).result().data()["density_matrix"])
    terms = [(SparsePauliOp("I" * n), 1.0)]
    for pos, letter in enumerate(label):  # leftmost character is qubit n-1
        q = n - 1 - pos
        if letter == "I":
            continue
        ro = aer_model._local_readout_errors.get((q,))
        probs = np.eye(2) if ro is None else np.asarray(ro.probabilities)
        p01, p10 = probs[0, 1], probs[1, 0]
        factor = ["I"] * n
        factor[pos] = letter
        nxt = []
        for op, c in terms:
            nxt.append((op.compose(SparsePauliOp("".join(factor))), c * (1 - p01 - p10)))
            nxt.append((op, c * (p10 - p01)))
        terms = nxt
    value = sum(c * np.trace(rho @ op.to_matrix()).real for op, c in terms)
    return float(value), max(0.0, 1.0 - float(np.trace(rho).real))


def _labels(rng, n, count):
    return ["".join(rng.choice(list("IXYZ"), size=n)) for _ in range(count)]


def _cq(label):
    """Qiskit label (qubit 0 rightmost) -> CQ-HECS Pauli string."""
    n = len(label)
    return "".join(f"{letter}[{n - 1 - pos}]" for pos, letter in enumerate(label) if letter != "I") or "I"


class TestAgainstAerChannels(unittest.TestCase):
    """Both engines against Aer with independently constructed channels."""

    def test_random_circuits_both_methods(self):
        ours, aer = _models()
        rng = np.random.default_rng(808)
        edges = [(0, 1), (1, 2), (2, 1)]
        for trial in range(15):
            qc, ins = _random_circuit(rng, N, int(rng.integers(4, 18)), edges)
            labels = _labels(rng, N, 5)
            names = {f"o{i}": _cq(lbl) for i, lbl in enumerate(labels)}
            dm = noisy_expectation_values(ins, names, ours, method="density_matrix")
            pp = noisy_expectation_values(ins, names, ours, method="pauli_propagation",
                                          prune_threshold=0.0, max_pauli_terms=10 ** 6)
            self.assertEqual(pp.error_bound, 0.0)
            for i, lbl in enumerate(labels):
                ref, loss = _aer_value(qc, aer, lbl, N)
                with self.subTest(trial=trial, label=lbl):
                    self.assertLess(abs(dm.values[f"o{i}"] - ref), 1e-12 + loss)
                    self.assertLess(abs(pp.values[f"o{i}"] - ref), 1e-12 + loss)

    def test_readout_can_be_switched_off(self):
        ours, aer = _models()
        aer_no_ro = AerNoiseModel()
        for name, by_q in aer._local_quantum_errors.items():
            for qubits, err in by_q.items():
                aer_no_ro.add_quantum_error(err, name, list(qubits))
        qc, ins = _random_circuit(np.random.default_rng(1), N, 12, [(0, 1), (1, 2)])
        res = noisy_expectation_values(ins, ["Y[2]Z[0]"], ours, readout=False)
        ref, loss = _aer_value(qc, aer_no_ro, "YIZ", N)
        self.assertLess(abs(res.values["Y[2]Z[0]"] - ref), 1e-12 + loss)
        self.assertFalse(res.metadata["readout_applied"])


class TestCertifiedTruncation(unittest.TestCase):
    def test_truncated_values_stay_within_their_bound(self):
        ours, _aer = _models()
        rng = np.random.default_rng(99)
        checked = 0
        for trial in range(25):
            _qc, ins = _random_circuit(rng, N, 25, [(0, 1), (1, 2), (2, 1)])
            names = {f"o{i}": _cq(lbl) for i, lbl in enumerate(_labels(rng, N, 4))}
            exact = noisy_expectation_values(ins, names, ours, method="density_matrix")
            cut = noisy_expectation_values(ins, names, ours, method="pauli_propagation",
                                           prune_threshold=0.02, max_pauli_terms=8, error_tolerance=1.0)
            for key in names:
                if cut.values[key] is None:
                    continue
                checked += 1
                with self.subTest(trial=trial, observable=names[key]):
                    self.assertLessEqual(abs(cut.values[key] - exact.values[key]), cut.error_bound + 1e-12)
        self.assertGreater(checked, 50)

    def test_bound_above_tolerance_is_unresolved(self):
        ours, _aer = _models()
        _qc, ins = _random_circuit(np.random.default_rng(4), N, 30, [(0, 1), (1, 2)])
        res = noisy_expectation_values(ins, ["X[0]X[1]", "Z[2]"], ours, method="pauli_propagation",
                                       prune_threshold=0.2, max_pauli_terms=2, error_tolerance=1e-6)
        if res.error_bound > 1e-6:
            self.assertTrue(res.unresolved)
            self.assertIn(None, res.values.values())

    def test_heisenberg_maps_are_unital(self):
        # N^dag(I) = I for every CPTP channel: column 0 is e_0.
        for ch in (AmplitudeDampingChannel(0.3), ThermalRelaxationChannel(30.0, 50.0, 400.0)):
            col = heisenberg_matrix_1q(ch.kraus_operators)[:, 0]
            np.testing.assert_allclose(col, np.eye(4)[:, 0], atol=1e-14)
        two = TensorChannel(AmplitudeDampingChannel(0.3), ThermalRelaxationChannel(30.0, 50.0, 400.0))
        np.testing.assert_allclose(heisenberg_matrix_2q(two.kraus_operators)[:, 0], np.eye(16)[:, 0], atol=1e-14)


class TestScaleAndConsistency(unittest.TestCase):
    def test_no_noise_matches_dense_engine(self):
        rng = np.random.default_rng(12)
        n = 12
        ins = [("barrier", list(range(n)), [])]
        for _ in range(60):
            if rng.random() < 0.5:
                q = int(rng.integers(n))
                ins.append((str(rng.choice(["sx", "x", "h", "t"])), [q], []))
            else:
                a = int(rng.integers(n - 1))
                ins.append(("cx", [a, a + 1], []))
        obs = ["Z[0]", "X[3]Y[4]", "Z[5]Z[6]Z[7]"]
        dense = expectation_values(ins, obs, method="dense")
        pp = noisy_expectation_values(ins, obs, NoiseModel(), method="pauli_propagation",
                                      prune_threshold=0.0, max_pauli_terms=10 ** 6)
        for o in obs:
            self.assertAlmostEqual(pp.values[o], dense.values[o], places=12)

    def test_wide_noisy_circuit_runs_with_a_bound(self):
        n = 40
        model = NoiseModel(name="chain")
        for q in range(n):
            model.add_1q_channel("sx", q, ThermalRelaxationChannel(100.0, 80.0, 35.0))
            model.set_readout_error(q, 0.01, 0.02)
        for q in range(n - 1):
            model.add_2q_channel("cx", (q, q + 1), TwoQubitDepolarizingChannel(0.01))
        ins = []
        for _layer in range(4):
            ins += [("sx", [q], []) for q in range(n)]
            ins += [("cx", [q, q + 1], []) for q in range(0, n - 1, 2)]
            ins += [("rz", [q], [0.3]) for q in range(n)]
        res = noisy_expectation_values(ins, ["Z[20]", "Z[19]Z[20]"], model, prune_threshold=1e-6)
        self.assertEqual(res.method, "noisy_pauli_propagation")
        self.assertFalse(res.exact)
        self.assertLessEqual(res.error_bound, 0.01)
        for value in res.values.values():
            self.assertTrue(-1.0 <= value <= 1.0)


class TestContract(unittest.TestCase):
    def test_invalid_arguments(self):
        ins = [("h", [0], [])]
        for kwargs in ({"method": "magic"}, {"error_tolerance": 0}, {"max_pauli_terms": 0},
                       {"prune_threshold": float("nan")}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ExpectationError):
                    noisy_expectation_values(ins, ["Z[0]"], NoiseModel(), **kwargs)
        with self.assertRaises(ExpectationError):
            noisy_expectation_values(ins, ["Z[0]"], None)

    def test_dynamic_operations_are_refused(self):
        for ins in ([("measure", [0], []), ("x", [0], [])], [("reset", [0], [])]):
            with self.subTest(ins=ins):
                with self.assertRaises(ExpectationError):
                    noisy_expectation_values(ins, ["Z[0]"], NoiseModel())

    def test_density_matrix_width_limit(self):
        ins = [("h", [q], []) for q in range(4)]
        with self.assertRaises(ExpectationError):
            noisy_expectation_values(ins, ["Z[0]"], NoiseModel(), method="density_matrix", dm_max_qubits=3)

    def test_fake_backend_checks_calibration_flags(self):
        profile = BackendProfile(
            name="t", num_qubits=2, schema_version="2.0", coupling_map=[(0, 1)],
            calibration_flags={"non_operational": [{"gate": "cx", "qubits": [0, 1], "gate_error": 1.0}]},
        )
        backend = FakeHardwareBackend(profile)
        with self.assertRaises(OutOfModelError):
            backend.expectation_values([("cx", [0, 1], [])], ["Z[0]"])
        res = backend.expectation_values([("x", [1], [])], ["Z[1]"])
        self.assertEqual(res.metadata["execution_mode"], "NOISY_CLASSICAL")
        self.assertFalse(res.metadata["is_real_hardware"])


@unittest.skipUnless(HAVE_RUNTIME, "qiskit-ibm-runtime not installed (needed for Aer's from_backend oracle)")
class TestAerDevicePipeline(unittest.TestCase):
    def test_real_calibration_matches_aer_from_backend(self):
        from qiskit_ibm_runtime.fake_provider import FakeLagosV2, FakeManilaV2

        from cqhecs.calibration_import import load_qiskit_ibm_runtime_snapshot

        rng = np.random.default_rng(2052)
        for fake, name in ((FakeManilaV2, "manila"), (FakeLagosV2, "lagos")):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                device = fake()
                aer = AerNoiseModel.from_backend(device)
            profile = load_qiskit_ibm_runtime_snapshot(name, readout="symmetric")
            model = profile.to_noise_model(relaxation=True)
            n = device.num_qubits
            for trial in range(5):
                qc, ins = _random_circuit(rng, n, int(rng.integers(5, 20)), profile.coupling_map)
                labels = _labels(rng, n, 3)
                names = {f"o{i}": _cq(lbl) for i, lbl in enumerate(labels)}
                dm = noisy_expectation_values(ins, names, model, method="density_matrix")
                pp = noisy_expectation_values(ins, names, model, method="pauli_propagation",
                                              prune_threshold=0.0, max_pauli_terms=10 ** 6)
                for i, lbl in enumerate(labels):
                    ref, loss = _aer_value(qc, aer, lbl, n)
                    with self.subTest(backend=name, trial=trial, label=lbl):
                        self.assertLess(abs(dm.values[f"o{i}"] - ref), 1e-12 + loss)
                        self.assertLess(abs(pp.values[f"o{i}"] - ref), 1e-12 + loss)


if __name__ == "__main__":
    unittest.main()
