"""
Real-calibration bridge (v3 plan, workstreams W1 and W2).

W1: IBM calibration snapshots import into non-synthetic schema-2.0 profiles
without clipping or dropping data (``tests/data/ibm_calibration``; see its
NOTICE.md). Expected values are read from the raw JSON in this file, not
through the importer.

W2: the relaxation-aware noise model equals Qiskit Aer's device model. Oracles:
closed forms for T1/T2 decay, ``qiskit_aer.noise.thermal_relaxation_error``,
``qiskit.quantum_info.average_gate_fidelity``, and - when qiskit-ibm-runtime is
installed - Aer's complete ``NoiseModel.from_backend`` pipeline.

Aer's density-matrix simulator drops noise terms with probability < 1e-10
(research/v3/EXECUTION_LOG.md, E-V3-02), so its output can lose up to a few
1e-9 of trace. Circuit-level parity therefore allows ``1e-12`` plus the trace
Aer itself reports missing; channel-level parity is exact to ``1e-12``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import unittest
import warnings
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Kraus, SuperOp, average_gate_fidelity
from qiskit_aer.noise import thermal_relaxation_error

from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.calibration_import import load_ibm_snapshot_files, profile_from_ibm_properties
from cqhecs.hardware_bridge import (
    BackendProfile,
    ComposedChannel,
    FakeHardwareBackend,
    InvalidNoiseModelError,
    InvalidProfileError,
    OutOfModelError,
    ThermalRelaxationChannel,
    TwoQubitDepolarizingChannel,
    TensorChannel,
    depolarizing_parameter_with_relaxation,
)
from cqhecs.result import ExecutionMode

DATA = Path(__file__).resolve().parent / "data" / "ibm_calibration"
HAVE_RUNTIME = importlib.util.find_spec("qiskit_ibm_runtime") is not None


def _snapshot(name, readout="asymmetric"):
    return load_ibm_snapshot_files(
        DATA / f"props_{name}.json", DATA / f"conf_{name}.json",
        provenance_uri=f"test-data:{name}", readout=readout,
    )


def _raw(name):
    return json.loads((DATA / f"props_{name}.json").read_text(encoding="utf-8"))


def _qubit_value(raw, qubit, field):
    for entry in raw["qubits"][qubit]:
        if entry["name"] == field:
            return entry["value"]
    return None


class TestFixtures(unittest.TestCase):
    def test_vendored_files_match_their_checksums(self):
        for line in (DATA / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split()
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), digest)


class TestImport(unittest.TestCase):
    """W1."""

    def test_manila_values_and_provenance(self):
        raw = _raw("manila")
        profile = _snapshot("manila")
        self.assertFalse(profile.is_synthetic)
        self.assertEqual(profile.schema_version, "2.0")
        self.assertEqual(profile.capture_timestamp, raw["last_update_date"])
        self.assertEqual(
            profile.source_sha256,
            hashlib.sha256((DATA / "props_manila.json").read_bytes()).hexdigest(),
        )
        self.assertEqual(profile.calibration_flags.get("non_operational", []), [])
        for q in range(5):
            self.assertEqual(profile.t1_us[q], _qubit_value(raw, q, "T1"))
            self.assertEqual(profile.t2_us[q], _qubit_value(raw, q, "T2"))
            # (P(1|0), P(0|1)) in CQ-HECS order.
            self.assertEqual(
                profile.readout_errors[q],
                (_qubit_value(raw, q, "prob_meas1_prep0"), _qubit_value(raw, q, "prob_meas0_prep1")),
            )
        for gate in raw["gates"]:
            if gate["gate"] in ("cx", "sx", "x", "id"):
                params = {p["name"]: p["value"] for p in gate["parameters"]}
                key = tuple(gate["qubits"])
                self.assertEqual(profile.gate_errors[gate["gate"]][key], params["gate_error"])
                self.assertEqual(profile.gate_durations_ns[gate["gate"]][key], params["gate_length"])

    def test_symmetric_readout_uses_readout_error(self):
        raw = _raw("manila")
        profile = _snapshot("manila", readout="symmetric")
        value = _qubit_value(raw, 0, "readout_error")
        self.assertEqual(profile.readout_errors[0], (value, value))

    def test_inconsistent_relaxation_is_flagged_not_clipped(self):
        raw = _raw("oslo")
        profile = _snapshot("oslo")
        t1, t2 = _qubit_value(raw, 6, "T1"), _qubit_value(raw, 6, "T2")
        self.assertGreater(t2, 2 * t1)  # the real fit violates the physical bound
        flag = profile.calibration_flags["relaxation_excluded"][6]
        self.assertEqual((flag["T1_us"], flag["T2_us"]), (t1, t2))
        self.assertNotIn(6, profile.t1_us)
        self.assertNotIn(6, profile.t2_us)

    def test_non_operational_gates_are_flagged(self):
        profile = _snapshot("algiers")
        flagged = {tuple(e["qubits"]) for e in profile.calibration_flags["non_operational"]}
        self.assertEqual(flagged, {(18, 15), (15, 18)})
        self.assertNotIn((15, 18), profile.gate_errors["cx"])
        for entry in profile.calibration_flags["non_operational"]:
            self.assertEqual(entry["gate_error"], 1.0)

    def test_round_trip_keeps_flags(self):
        profile = _snapshot("algiers")
        again = BackendProfile.from_dict(json.loads(json.dumps(profile.to_dict())))
        self.assertEqual(again.calibration_flags, profile.calibration_flags)
        self.assertEqual(again.source_sha256, profile.source_sha256)
        self.assertFalse(again.is_synthetic)

    def test_malformed_input_is_refused(self):
        raw = _raw("manila")
        conf = json.loads((DATA / "conf_manila.json").read_text())
        bad_unit = json.loads(json.dumps(raw))
        bad_unit["qubits"][0][0]["unit"] = "fortnights"
        bad_value = json.loads(json.dumps(raw))
        bad_value["qubits"][0][0]["value"] = float("nan")
        other_conf = dict(conf, backend_name="ibm_other")
        for props, cfg in ((bad_unit, conf), (bad_value, conf), (raw, other_conf)):
            with self.assertRaises(InvalidProfileError):
                profile_from_ibm_properties(props, cfg, provenance_uri="x")
        with self.assertRaises(InvalidProfileError):
            profile_from_ibm_properties(raw, conf, provenance_uri="x", readout="guess")

    def test_schema_1_profiles_cannot_carry_flags(self):
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="t", num_qubits=1, calibration_flags={"relaxation_excluded": {0: "x"}})


class TestOutOfModelRefusal(unittest.TestCase):
    def test_flagged_pair_is_refused(self):
        backend = FakeHardwareBackend(_snapshot("algiers"))
        with self.assertRaises(OutOfModelError):
            backend.run([("cx", [15, 18], []), ("measure", [15], [])], shots=8, seed=1)
        ok = backend.run([("x", [0], []), ("measure", [0], [])], shots=8, seed=1)
        self.assertEqual(ok.execution_mode, ExecutionMode.NOISY_CLASSICAL)
        self.assertFalse(ok.metadata["profile_is_synthetic"])

    def test_relaxation_excluded_qubit_only_matters_with_relaxation(self):
        profile = _snapshot("oslo")
        circuit = [("x", [6], []), ("measure", [6], [])]
        FakeHardwareBackend(profile).run(circuit, shots=8, seed=1)
        with self.assertRaises(OutOfModelError):
            FakeHardwareBackend(profile, relaxation=True).run(circuit, shots=8, seed=1)

    def test_ideal_mode_needs_no_calibration(self):
        backend = FakeHardwareBackend(_snapshot("algiers"))
        res = backend.run([("cx", [15, 18], [])], shots=8, seed=1,
                          execution_mode=ExecutionMode.IDEAL_CLASSICAL)
        # Not an OutOfModelError: the ideal mode uses no calibration. The
        # 19-qubit register exceeds the 10-qubit density-matrix ceiling, which
        # is reported as UNRESOLVED without counts.
        self.assertEqual(res.state.value, "UNRESOLVED")
        self.assertEqual(res.counts, {})


class TestThermalRelaxation(unittest.TestCase):
    """W2: channel definition."""

    def test_decay_matches_closed_form(self):
        t1, t2, t_ns = 80.0, 60.0, 400.0
        ch = ThermalRelaxationChannel(t1, t2, t_ns)
        plus_one = np.array([[0.5, 0.5], [0.5, 0.5]], dtype=complex)
        excited = np.array([[0, 0], [0, 1]], dtype=complex)
        out_plus = sum(k @ plus_one @ k.conj().T for k in ch.kraus_operators)
        out_exc = sum(k @ excited @ k.conj().T for k in ch.kraus_operators)
        t = t_ns * 1e-3
        self.assertAlmostEqual(out_exc[1, 1].real, math.exp(-t / t1), places=14)
        self.assertAlmostEqual(abs(out_plus[0, 1]), 0.5 * math.exp(-t / t2), places=14)

    def test_matches_aer_constructor(self):
        for t1, t2, t_ns in ((100.0, 50.0, 35.0), (80.0, 150.0, 660.0), (40.0, 80.0, 1000.0), (60.0, 60.0, 0.0)):
            with self.subTest(t1=t1, t2=t2, t=t_ns):
                ours = SuperOp(Kraus(ThermalRelaxationChannel(t1, t2, t_ns).kraus_operators)).data
                aer = SuperOp(thermal_relaxation_error(t1 * 1e3, t2 * 1e3, t_ns)).data
                self.assertLess(np.max(np.abs(ours - aer)), 1e-12)

    def test_invalid_parameters_are_refused(self):
        for args in ((10.0, 25.0, 5.0), (0.0, 1.0, 5.0), (10.0, 5.0, -1.0), (float("inf"), 5.0, 1.0)):
            with self.subTest(args=args):
                with self.assertRaises(InvalidNoiseModelError):
                    ThermalRelaxationChannel(*args)

    def test_composed_channel_has_reported_infidelity(self):
        relax = TensorChannel(ThermalRelaxationChannel(120.0, 90.0, 400.0),
                              ThermalRelaxationChannel(90.0, 150.0, 400.0))
        f_relax = float(average_gate_fidelity(Kraus(relax.kraus_operators)))
        r = 0.012
        p, zeroed = depolarizing_parameter_with_relaxation(r, 2, f_relax)
        self.assertFalse(zeroed)
        total = ComposedChannel(TwoQubitDepolarizingChannel(p), relax)
        self.assertAlmostEqual(1.0 - float(average_gate_fidelity(Kraus(total.kraus_operators))), r, places=12)

    def test_device_model_order_matches_aer(self):
        from qiskit_aer.noise import depolarizing_error

        profile = BackendProfile(
            name="t", num_qubits=1, t1_us={0: 30.0}, t2_us={0: 20.0},
            gate_errors={"x": {(0,): 0.1}}, gate_durations_ns={"x": {(0,): 200.0}},
        )
        channel = profile.to_noise_model(relaxation=True).channels_1q["x"][0][0]
        relax = thermal_relaxation_error(30e3, 20e3, 200.0)
        p, zeroed = depolarizing_parameter_with_relaxation(0.1, 1, float(average_gate_fidelity(relax)))
        self.assertFalse(zeroed)
        expected = SuperOp(depolarizing_error(p, 1)).compose(SuperOp(relax)).data
        self.assertLess(np.max(np.abs(SuperOp(Kraus(channel.kraus_operators)).data - expected)), 1e-12)

    def test_relaxation_beyond_reported_error_is_recorded(self):
        relax = ThermalRelaxationChannel(50.0, 30.0, 1000.0)
        f_relax = float(average_gate_fidelity(Kraus(relax.kraus_operators)))
        self.assertEqual(depolarizing_parameter_with_relaxation(1e-6, 1, f_relax), (0.0, True))
        profile = BackendProfile(
            name="t", num_qubits=1, t1_us={0: 50.0}, t2_us={0: 30.0},
            gate_errors={"x": {(0,): 1e-6}}, gate_durations_ns={"x": {(0,): 1000.0}},
        )
        model = profile.to_noise_model(relaxation=True)
        self.assertEqual(model.metadata["relaxation_exceeds_gate_error"], [["x", [0]]])

    def test_unflagged_missing_t1_is_refused(self):
        profile = BackendProfile(
            name="t", num_qubits=1, gate_errors={"x": {(0,): 1e-3}}, gate_durations_ns={"x": {(0,): 35.0}},
        )
        profile.to_noise_model()
        with self.assertRaises(InvalidNoiseModelError):
            profile.to_noise_model(relaxation=True)


@unittest.skipUnless(HAVE_RUNTIME, "qiskit-ibm-runtime not installed (needed for Aer's from_backend oracle)")
class TestAerDeviceModelParity(unittest.TestCase):
    """W2 against Aer's complete pipeline (NoiseModel.from_backend)."""

    BACKENDS = (("FakeManilaV2", "manila"), ("FakeQuitoV2", "quito"), ("FakeLagosV2", "lagos"))

    @classmethod
    def setUpClass(cls):
        from qiskit_aer.noise import NoiseModel
        from qiskit_ibm_runtime import fake_provider

        from cqhecs.calibration_import import load_qiskit_ibm_runtime_snapshot

        cls.models = {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for cls_name, name in cls.BACKENDS:
                backend = getattr(fake_provider, cls_name)()
                cls.models[name] = (
                    backend,
                    NoiseModel.from_backend(backend),
                    load_qiskit_ibm_runtime_snapshot(name, readout="symmetric"),
                )

    @staticmethod
    def _ours(channel, two_qubit):
        kraus = channel.kraus_operators
        if two_qubit:
            # Aer's first qarg is the least-significant tensor factor; ours the most.
            swap = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
            kraus = [swap @ k @ swap for k in kraus]
        return SuperOp(Kraus(kraus)).data

    def test_every_gate_channel_matches(self):
        for name, (_backend, aer_model, profile) in self.models.items():
            ours = profile.to_noise_model(relaxation=True)
            for gate, by_qubits in aer_model._local_quantum_errors.items():
                if gate == "reset":
                    continue  # reset is refused by CQ-HECS
                for qubits, error in by_qubits.items():
                    with self.subTest(backend=name, gate=gate, qubits=qubits):
                        if len(qubits) == 1:
                            channel = ours.channels_1q[gate][qubits[0]][0]
                        else:
                            channel = ours.channels_2q[gate][tuple(qubits)][0]
                        diff = np.max(np.abs(SuperOp(error).data - self._ours(channel, len(qubits) == 2)))
                        self.assertLess(diff, 1e-12)

    def test_random_basis_circuits_match_aer_density_matrix(self):
        from qiskit_aer import AerSimulator

        rng = np.random.default_rng(3003)
        for name, (backend, aer_model, profile) in self.models.items():
            n = backend.num_qubits
            model = profile.to_noise_model(relaxation=True)
            for trial in range(12):
                qc = QuantumCircuit(n)
                ins = [("barrier", list(range(n)), [])]
                for _ in range(int(rng.integers(3, 20))):
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
                        a, b = profile.coupling_map[int(rng.integers(len(profile.coupling_map)))]
                        qc.cx(a, b)
                        ins.append(("cx", [a, b], []))
                qc.save_density_matrix()
                rho = np.asarray(AerSimulator(method="density_matrix", noise_model=aer_model)
                                 .run(qc).result().data()["density_matrix"])
                probs = np.real(np.diag(rho))
                trace_loss = max(0.0, 1.0 - float(probs.sum()))
                assignment = np.array([[1.0]])
                for q in range(n - 1, -1, -1):
                    ro = aer_model._local_readout_errors.get((q,))
                    a = np.eye(2) if ro is None else np.asarray(ro.probabilities).T
                    assignment = np.kron(assignment, a)
                expected = assignment @ probs
                res = NoisyDensityMatrixBackend().simulate(ins, noise_model=model, shots=8, seed=1)
                got = np.zeros(1 << n)
                for bits, p in res.probabilities.items():
                    got[int(bits, 2)] = p
                with self.subTest(backend=name, trial=trial):
                    self.assertLess(0.5 * np.abs(got - expected).sum(), 1e-12 + trace_loss)

    def test_all_shipped_snapshots_import(self):
        from cqhecs.calibration_import import (
            available_qiskit_ibm_runtime_snapshots,
            load_qiskit_ibm_runtime_snapshot,
        )

        names = available_qiskit_ibm_runtime_snapshots()
        self.assertGreater(len(names), 0)
        for name in names:
            with self.subTest(snapshot=name):
                profile = load_qiskit_ibm_runtime_snapshot(name)
                self.assertFalse(profile.is_synthetic)
                profile.to_noise_model(relaxation=True)


if __name__ == "__main__":
    unittest.main()
