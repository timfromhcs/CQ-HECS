"""
Result-contract regressions for the noisy density-matrix backend (v2.5.1).

Covers the defects recorded in research/v2_5_1/FINDINGS.md:

- CQ-V251-01: bitstrings were mirrored (qubit 0 rendered leftmost) and the
  readout assignment was applied to the mirrored bit.
- CQ-V251-02: terminal measurements were ignored (all qubits reported) and a
  mid-circuit measurement was silently dropped.
- CQ-V251-04: invalid ``shots``/``seed`` and missing gate parameters were
  accepted (bool/float shots, angle-less ``rx`` evaluated as identity).

The oracle is independent of the code under test: gates are applied by
``qiskit.quantum_info.DensityMatrix``, noise channels are built with
``qiskit_aer.noise`` constructors (not CQ-HECS Kraus operators), and the
readout assignment is computed bit by bit from its definition.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Kraus
from qiskit_aer.noise import (
    amplitude_damping_error,
    depolarizing_error,
    phase_damping_error,
)

from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.hardware_bridge import (
    AmplitudeDampingChannel,
    BackendProfile,
    DepolarizingChannel,
    InvalidProfileError,
    NoiseModel,
    PhaseDampingChannel,
    TwoQubitDepolarizingChannel,
)
from cqhecs.result import SimulationState

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Float64 evaluation of at most ~60 norm-<=1 operations on an 8x8 matrix
# accumulates O(1e-14) rounding; 1e-10 leaves four orders of headroom while
# still catching any mirrored bit (which moves O(0.1) probability mass).
ATOL = 1e-10

_ONE_Q = ["h", "x", "y", "s", "t", "sx", "rx", "ry", "rz", "u"]
_TWO_Q = ["cx", "cz", "swap", "cp"]


def _random_circuit(rng: np.random.Generator, n: int, depth: int) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    for _ in range(depth):
        if rng.random() < 0.6:
            name = _ONE_Q[rng.integers(len(_ONE_Q))]
            q = int(rng.integers(n))
            if name in ("rx", "ry", "rz"):
                getattr(qc, name)(float(rng.uniform(-np.pi, np.pi)), q)
            elif name == "u":
                qc.u(*(float(x) for x in rng.uniform(-np.pi, np.pi, 3)), q)
            else:
                getattr(qc, name)(q)
        else:
            name = _TWO_Q[rng.integers(len(_TWO_Q))]
            a, b = (int(x) for x in rng.choice(n, size=2, replace=False))
            if name == "cp":
                qc.cp(float(rng.uniform(-np.pi, np.pi)), a, b)
            else:
                getattr(qc, name)(a, b)
    return qc


def _oracle(qc: QuantumCircuit, ch1, ch2, readout, measured):
    """
    Independent reference distribution.

    ch1: {(gate, q): aer_error}; ch2: {(gate, (a, b)): aer_error}; readout:
    {q: (p01, p10)}; measured: qubit list (index 0 rendered rightmost) or None.
    """
    n = qc.num_qubits
    rho = DensityMatrix.from_label("0" * n)
    for inst in qc.data:
        op = inst.operation
        qargs = [qc.find_bit(q).index for q in inst.qubits]
        rho = rho.evolve(op, qargs=qargs)
        if len(qargs) == 1 and (op.name, qargs[0]) in ch1:
            rho = rho.evolve(Kraus(ch1[(op.name, qargs[0])]), qargs=qargs)
        if len(qargs) == 2 and (op.name, tuple(qargs)) in ch2:
            rho = rho.evolve(Kraus(ch2[(op.name, tuple(qargs))]), qargs=qargs)

    probs = np.real(np.diag(rho.data))  # Qiskit: qubit 0 is the LSB.
    noisy = np.zeros_like(probs)
    for true_idx, p_true in enumerate(probs):
        for meas_idx in range(len(probs)):
            weight = 1.0
            for q in range(n):
                t = (true_idx >> q) & 1
                m = (meas_idx >> q) & 1
                p01, p10 = readout.get(q, (0.0, 0.0))
                p_flip = p01 if t == 0 else p10
                weight *= p_flip if m != t else 1.0 - p_flip
            noisy[meas_idx] += weight * p_true

    keep = list(range(n)) if measured is None else measured
    out = {}
    for idx, p in enumerate(noisy):
        key = "".join(str((idx >> q) & 1) for q in reversed(keep))
        out[key] = out.get(key, 0.0) + float(p)
    return out


def _assert_same_distribution(test, got, want):
    for key in set(got) | set(want):
        test.assertAlmostEqual(got.get(key, 0.0), want.get(key, 0.0), delta=ATOL, msg=key)


class TestBitOrderAndMeasurement(unittest.TestCase):

    def setUp(self):
        self.backend = NoisyDensityMatrixBackend()

    def test_x_on_qubit0_renders_rightmost(self):
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.measure_all()
        res = self.backend.simulate(qc, shots=64)
        self.assertEqual(res.probabilities, {"01": 1.0})
        self.assertEqual(res.counts, {"01": 64})

    def test_readout_error_hits_the_named_qubit(self):
        # |q1 q0> = |10>; only qubit 1 has readout error.
        noise = NoiseModel()
        noise.set_readout_error(1, p01=0.0, p10=0.25)
        qc = QuantumCircuit(2)
        qc.x(1)
        res = self.backend.simulate(qc, noise_model=noise)
        self.assertAlmostEqual(res.probabilities["10"], 0.75, delta=ATOL)
        self.assertAlmostEqual(res.probabilities["00"], 0.25, delta=ATOL)
        self.assertEqual(set(res.probabilities), {"10", "00"})

    def test_partial_measurement_reports_measured_qubits_only(self):
        qc = QuantumCircuit(3, 2)
        qc.x(2)
        qc.h(1)
        qc.measure(0, 0)
        qc.measure(1, 1)
        res = self.backend.simulate(qc, shots=100)
        self.assertEqual(res.metadata["measured_qubits"], [0, 1])
        _assert_same_distribution(self, res.probabilities, {"00": 0.5, "10": 0.5})
        self.assertTrue(all(len(k) == 2 for k in res.counts))
        self.assertEqual(sum(res.counts.values()), 100)

    def test_mid_circuit_measurement_is_refused(self):
        res = self.backend.simulate([("h", [0], []), ("measure", [0], []), ("h", [0], [])])
        self.assertEqual(res.state, SimulationState.FAILED)
        self.assertIn("mid-circuit measurement", res.metadata["error"])
        self.assertFalse(res.counts)

    def test_measurement_followed_by_barrier_is_terminal(self):
        res = self.backend.simulate(
            [("x", [0], []), ("measure", [0], []), ("barrier", [0], [])], shots=8
        )
        self.assertEqual(res.state, SimulationState.EXACT)
        self.assertEqual(res.counts, {"1": 8})

    def test_reset_is_refused(self):
        qc = QuantumCircuit(1)
        qc.x(0)
        qc.reset(0)
        res = self.backend.simulate(qc)
        self.assertEqual(res.state, SimulationState.FAILED)


class TestArgumentValidation(unittest.TestCase):

    def setUp(self):
        self.backend = NoisyDensityMatrixBackend()

    def test_invalid_shots_rejected_before_parsing(self):
        for shots in (0, -1, True, 2.5, "8", None):
            with self.subTest(shots=shots), self.assertRaises(ValueError):
                self.backend.simulate("not a circuit", shots=shots)

    def test_invalid_seed_rejected(self):
        for seed in (-1, True, 1.0, "1", None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                self.backend.simulate([("h", [0], [])], seed=seed)

    def test_invalid_max_qubits_rejected(self):
        for value in (0, -3, True, 2.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                NoisyDensityMatrixBackend(max_qubits=value)

    def test_missing_or_extra_angle_is_refused_not_identity(self):
        for inst in ([("rx", [0], [])], [("rz", [0], [0.1, 0.2])], [("cp", [0, 1], [])]):
            with self.subTest(inst=inst):
                res = self.backend.simulate(inst)
                self.assertEqual(res.state, SimulationState.FAILED)
                self.assertIn("parameter", res.metadata["error"])

    def test_unsupported_gate_names_the_gate(self):
        res = self.backend.simulate([("crz", [0, 1], [0.3])])
        self.assertEqual(res.state, SimulationState.FAILED)
        self.assertIn("'crz'", res.metadata["error"])

    def test_same_seed_same_counts(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        a = self.backend.simulate(qc, shots=500, seed=7).counts
        b = self.backend.simulate(qc, shots=500, seed=7).counts
        self.assertEqual(a, b)


class TestDifferentialAgainstIndependentOracle(unittest.TestCase):
    """Exact (non-sampled) comparison on asymmetric random circuits."""

    def test_random_noisy_circuits_match_qiskit_density_matrix(self):
        rng = np.random.default_rng(20261030)
        backend = NoisyDensityMatrixBackend()
        for trial in range(25):
            n = 3
            qc = _random_circuit(rng, n, depth=14)

            cq = NoiseModel(name=f"trial_{trial}")
            ch1, ch2, readout = {}, {}, {}
            # Distinct per-qubit channels so a mirrored qubit index is visible.
            for q in range(n):
                p, g, lam = (float(x) for x in rng.uniform(0.0, 0.2, 3))
                cq.add_1q_channel("h", q, DepolarizingChannel(p))
                ch1[("h", q)] = depolarizing_error(p, 1)
                cq.add_1q_channel("x", q, AmplitudeDampingChannel(g))
                ch1[("x", q)] = amplitude_damping_error(g)
                cq.add_1q_channel("sx", q, PhaseDampingChannel(lam))
                ch1[("sx", q)] = phase_damping_error(lam)
                p01, p10 = (float(x) for x in rng.uniform(0.0, 0.15, 2))
                cq.set_readout_error(q, p01, p10)
                readout[q] = (p01, p10)
            for a in range(n):
                for b in range(n):
                    if a != b:
                        p2 = float(rng.uniform(0.0, 0.1))
                        cq.add_2q_channel("cx", (a, b), TwoQubitDepolarizingChannel(p2))
                        ch2[("cx", (a, b))] = depolarizing_error(p2, 2)

            measured = None
            if trial % 3 == 1:
                measured = [0, 2]
            elif trial % 3 == 2:
                measured = [1]
            circuit = qc
            if measured is not None:
                # The flat IR supports only the identity mapping q[i] -> c[i].
                circuit = QuantumCircuit(n, n)
                circuit.compose(qc, inplace=True)
                for q in measured:
                    circuit.measure(q, q)

            with self.subTest(trial=trial):
                res = backend.simulate(circuit, noise_model=cq, shots=256, seed=trial)
                self.assertEqual(res.state, SimulationState.CERTIFIED, res.metadata)
                want = _oracle(qc, ch1, ch2, readout, measured)
                _assert_same_distribution(self, res.probabilities, want)
                self.assertEqual(sum(res.counts.values()), 256)

    def test_ideal_circuits_match_qiskit_statevector_ordering(self):
        rng = np.random.default_rng(7)
        backend = NoisyDensityMatrixBackend()
        for trial in range(10):
            qc = _random_circuit(rng, 4, depth=12)
            with self.subTest(trial=trial):
                res = backend.simulate(qc)
                want = {
                    k: float(v)
                    for k, v in DensityMatrix(qc).probabilities_dict().items()
                }
                _assert_same_distribution(self, res.probabilities, want)


class TestProfileProvenance(unittest.TestCase):

    def test_non_synthetic_profile_requires_provenance(self):
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="claims_real", num_qubits=2, is_synthetic=False)
        with self.assertRaises(InvalidProfileError):
            BackendProfile(
                name="claims_real", num_qubits=2, is_synthetic=False,
                capture_timestamp="2026-01-01T00:00:00Z",
            )
        ok = BackendProfile(
            name="real", num_qubits=2, is_synthetic=False,
            capture_timestamp="2026-01-01T00:00:00Z",
            provenance_uri="sha256:" + "0" * 64,
        )
        self.assertFalse(ok.is_synthetic)

    def test_bool_qubit_count_rejected(self):
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="bool", num_qubits=True)


class TestCliProfileAgreesWithRouter(unittest.TestCase):
    """The same circuit must render identically on the router and --profile."""

    def _run(self, *args):
        env = dict(os.environ, PYTHONPATH=REPO_ROOT)
        proc = subprocess.run(
            [sys.executable, "-m", "cqhecs.cli", "--format", "json", *args],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
        )
        return proc

    def test_x_on_qubit0(self):
        import json
        import tempfile

        qasm = (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
            "x q[0];\nmeasure q -> c;\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x0.qasm")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(qasm)
            router = self._run("run", path, "--shots", "16")
            profile = self._run("run", path, "--profile", "fake_manila", "--no-noisy", "--shots", "16")
        self.assertEqual(router.returncode, 0, router.stderr)
        self.assertEqual(profile.returncode, 0, profile.stderr)
        self.assertEqual(json.loads(router.stdout)["result"]["counts"], {"01": 16})
        self.assertEqual(json.loads(profile.stdout)["result"]["counts"], {"01": 16})

    def test_unknown_profile_is_a_usage_error(self):
        proc = self._run("run", "name:bell", "--profile", "does_not_exist")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Unknown fake hardware profile", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
