"""Python side of the shared conformance corpus (T6-05 / W13).

The corpus ``web/tests/fixtures/shared_conformance.json`` is consumed by the browser tests
(WebAssembly f64 in Node and in the real page, WebGPU f32 when an adapter exists). This file is
the Python half: it checks that the committed fixture is what the generator produces, that
it still agrees with an independent Qiskit derivation, and that the CQ-HECS Python reference
paths (router, Paths A/B/C) agree with it on the declared common subset and refuse (rather than
fake) the features that are not common.

Scope statement: the browser engine is an independent statevector implementation, not Paths A-D;
agreement is claimed only for the cases listed in the corpus.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "web" / "tests" / "fixtures" / "shared_conformance.json"
GENERATOR = REPO_ROOT / "web" / "scripts" / "export_shared_conformance.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("export_shared_conformance", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CORPUS = json.loads(FIXTURE.read_text(encoding="utf-8"))
GEN = _load_generator()


def _dense(case) -> np.ndarray:
    probs = np.zeros(1 << case["num_qubits"])
    for index, p in case["probabilities_sparse"].items():
        probs[int(index)] = p
    return probs


class FixtureIntegrity(unittest.TestCase):
    def test_schema_and_declared_semantics(self):
        self.assertEqual(CORPUS["schema"], "hcs.conformance.shared.v1")
        for key in ("endianness", "count_key_order", "default_measurement", "phase_policy", "norm"):
            self.assertIn(key, CORPUS["semantics"])
        self.assertEqual(CORPUS["webgpu"]["precision"], "f32")
        self.assertGreaterEqual(len(CORPUS["cases"]), 20)

    def test_committed_fixture_is_what_the_generator_produces(self):
        fresh = json.dumps(GEN.build(), indent=2) + "\n"
        committed = FIXTURE.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(committed, fresh, "stale corpus: run python web/scripts/export_shared_conformance.py")

    def test_every_family_the_task_names_is_present(self):
        families = {case["family"] for case in CORPUS["cases"]}
        for needed in ("endianness", "measurement-map", "phase", "phase-policy", "operand-order", "gpu-range", "dynamic"):
            self.assertIn(needed, families)


class QiskitOracle(unittest.TestCase):
    """Re-derive every expectation from Qiskit, so the file is not trusted by construction."""

    def test_probabilities_amplitudes_norm_and_classical_map(self):
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector

        for case in CORPUS["cases"]:
            with self.subTest(case=case["name"]):
                circuit = QuantumCircuit.from_qasm_str(case["qasm"])
                unitary = QuantumCircuit(circuit.num_qubits)
                for inst in circuit.data:
                    if inst.operation.name not in ("measure", "barrier"):
                        unitary.append(inst.operation, [circuit.find_bit(q).index for q in inst.qubits])
                state = Statevector.from_instruction(unitary)
                probs = np.asarray(state.probabilities())
                self.assertLessEqual(abs(probs.sum() - 1), 1e-12)
                self.assertLessEqual(np.abs(probs - _dense(case)).max(), CORPUS["tolerance_f64"])
                if "amplitudes" in case:
                    amps = np.array([complex(re, im) for re, im in case["amplitudes"]])
                    self.assertLessEqual(np.abs(amps - np.asarray(state.data)).max(), CORPUS["tolerance_f64"])
                pairs = [tuple(pair) for pair in case["measurement_map"]]
                expected = GEN.classical_distribution(probs, case["num_qubits"], pairs, case["num_clbits"])
                self.assertEqual(set(expected), set(case["classical_distribution"]))
                for key, value in expected.items():
                    self.assertAlmostEqual(value, case["classical_distribution"][key], delta=1e-12)

    def test_endianness_is_not_reversible_by_accident(self):
        """Break test: reading the corpus big-endian must fail the endianness cases."""
        case = next(c for c in CORPUS["cases"] if c["name"] == "endianness-x-q0")
        probs = _dense(case)
        reversed_index = int(format(int(np.argmax(probs)), f"0{case['num_qubits']}b")[::-1], 2)
        self.assertNotEqual(reversed_index, int(np.argmax(probs)))
        self.assertEqual(int(np.argmax(probs)), 1)

    def test_global_phase_case_has_unit_probability(self):
        case = next(c for c in CORPUS["cases"] if c["name"] == "global-phase-only")
        self.assertEqual(case["probabilities_sparse"], {"0": 1.0})
        self.assertAlmostEqual(abs(complex(*case["amplitudes"][0])), 1.0, places=12)
        self.assertNotAlmostEqual(complex(*case["amplitudes"][0]).imag, 0.0, places=3)  # phase present, unobservable


class PythonReferencePaths(unittest.TestCase):
    """The four-path simulator against the corpus on the declared common subset."""

    SHOTS = 20_000

    def _run(self, case, path=None):
        from cqhecs.router import EntanglementAdaptiveRouter

        return EntanglementAdaptiveRouter().route_and_execute(
            case["qasm"], shots=self.SHOTS, seed=7, preferred_path=path
        )

    @staticmethod
    def _tv(counts, expected, shots):
        keys = set(counts) | set(expected)
        return 0.5 * sum(abs(counts.get(k, 0) / shots - expected.get(k, 0.0)) for k in keys)

    def test_supported_cases_agree_with_the_corpus(self):
        checked = 0
        for case in CORPUS["cases"]:
            if case["python"]["status"] != "SUPPORTED":
                continue
            support = len(case["classical_distribution"])
            if support > 64:
                continue  # empirical TV over a large support is dominated by sampling noise
            with self.subTest(case=case["name"]):
                result = self._run(case)
                counts = dict(result.counts)
                self.assertEqual(sum(counts.values()), self.SHOTS)
                if case["deterministic_counts"]:
                    self.assertEqual(counts, {next(iter(case["classical_distribution"])): self.SHOTS})
                else:
                    # 5 sigma of the worst coordinate at p = 1/2 is 0.0177; sum over <= 64 outcomes.
                    self.assertLessEqual(self._tv(counts, case["classical_distribution"], self.SHOTS), 0.03 + 0.002 * support)
                checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_path_c_dense_contraction_matches_probabilities(self):
        """Path C MPS contracted to a dense vector vs the corpus probabilities (<= 6 qubits)."""
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Operator

        from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain

        def chain_matrix(op: np.ndarray, k: int) -> np.ndarray:
            t = np.asarray(op, dtype=np.complex128).reshape((2,) * (2 * k))
            out = tuple(reversed(range(k)))
            inn = tuple(reversed(range(k, 2 * k)))
            return t.transpose(out + inn).reshape(1 << k, 1 << k)

        done = 0
        for case in CORPUS["cases"]:
            if case["python"]["status"] != "SUPPORTED" or case["num_qubits"] > 6:
                continue
            circuit = QuantumCircuit.from_qasm_str(case["qasm"])
            if any(len(inst.qubits) > 2 for inst in circuit.data if inst.operation.name != "measure"):
                continue  # the chain applies one- and two-qubit matrices only
            with self.subTest(case=case["name"]):
                n = circuit.num_qubits
                mps = ExactMPSTensorChain(n)
                for inst in circuit.data:
                    if inst.operation.name in ("measure", "barrier"):
                        continue
                    qs = [circuit.find_bit(q).index for q in inst.qubits]
                    matrix = Operator(inst.operation).data
                    if len(qs) == 1:
                        mps.apply_single_qubit_gate(qs[0], matrix)
                    else:
                        mps.apply_two_qubit_gate(qs[0], qs[1], chain_matrix(matrix, 2))
                vec = np.asarray(mps.to_statevector()).reshape((2,) * n).transpose(tuple(reversed(range(n)))).reshape(-1)
                probs = np.abs(vec) ** 2
                self.assertLessEqual(np.abs(probs - _dense(case)).max(), 1e-10)
                self.assertAlmostEqual(float(probs.sum()), 1.0, places=10)
                done += 1
        self.assertGreaterEqual(done, 12)

    def test_non_common_features_are_refused_not_faked(self):
        for name in ("measure-remap", "measure-partial", "measure-mid-circuit"):
            case = next(c for c in CORPUS["cases"] if c["name"] == name)
            with self.subTest(case=name):
                self.assertEqual(case["python"]["status"], "REFUSED")
                with self.assertRaises(Exception):
                    self._run(case)

    def test_recorded_python_status_matches_the_live_router(self):
        for case in CORPUS["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(GEN.python_status(case["qasm"])["status"], case["python"]["status"])


class Refusals(unittest.TestCase):
    def _refuses(self, text: str) -> bool:
        return GEN.python_status(text)["status"] == "REFUSED"

    def test_inputs_that_every_surface_must_refuse(self):
        for entry in CORPUS["refusals"]:
            with self.subTest(case=entry["name"]):
                self.assertTrue(self._refuses(entry["qasm"]))

    def test_repeated_operand_is_refused_C1_FIND_01(self):
        """C1-FIND-01 fixed: cqhecs refuses `cx q[0],q[0]` like Qiskit and the browser."""
        entry = next(e for e in CORPUS["refusals"] if e["name"] == "refuse-repeated-operand")
        self.assertTrue(self._refuses(entry["qasm"]))


if __name__ == "__main__":
    unittest.main()
