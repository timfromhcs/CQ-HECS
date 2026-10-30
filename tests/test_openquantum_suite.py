"""Tests for the preregistered Open Quantum suite (``r-io-7``, v3 W4).

The counts used below are *synthetic*: they are sampled from a known M-FIT
model to check that ingest, fit and evaluation recover what was put in. They
are never written outside a temporary directory and are not evidence.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from qiskit import qasm2
from qiskit.quantum_info import Statevector

from cqhecs.openquantum_suite import (
    FittedModel,
    build_suite,
    check_bit_order,
    evaluate_suite,
    load_suite_run,
    simulate,
    suite_manifest,
)
from cqhecs.reference import DatasetNotAvailableError, IntegrityError

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = REPO_ROOT / "research" / "v3" / "openquantum_suite"
RUNNER = REPO_ROOT / "scripts" / "run_openquantum_suite.py"

TRUE_P = 0.04
TRUE_P01 = 0.02
TRUE_P10 = 0.05


def _write_synthetic_run(root: Path, *, shots: int = 4000, seed: int = 7, reverse: bool = False) -> None:
    rng = np.random.default_rng(seed)
    truth = FittedModel(TRUE_P01, TRUE_P10, TRUE_P, (TRUE_P01,) * 5, (TRUE_P10,) * 5, 0.0, ())
    for job in build_suite():
        probabilities = simulate(job, truth.noise_model(job))
        probabilities = probabilities / probabilities.sum()
        draws = rng.multinomial(shots, probabilities)
        counts = {}
        for index, count in enumerate(draws):
            if count:
                key = format(index, f"0{job.num_qubits}b")
                counts[key[::-1] if reverse else key] = int(count)
        folder = root / job.job_id
        folder.mkdir(parents=True)
        (folder / "circuit.qasm").write_bytes(job.qasm.encode("ascii"))
        (folder / "result.json").write_text(json.dumps({"counts": counts}), "utf-8")
        (folder / "job.json").write_text(
            json.dumps({"job": {"id": f"synthetic-{job.job_id}"}, "quote": {"backend": "synthetic:test"}}),
            "utf-8",
        )


class SuiteDefinitionTests(unittest.TestCase):
    def test_shape_and_split(self):
        jobs = build_suite()
        self.assertEqual(len(jobs), 25)
        self.assertEqual(sum(job.split == "FIT" for job in jobs), 5)
        self.assertEqual(sum(job.split == "EVAL" for job in jobs), 20)
        self.assertEqual(len({job.sha256 for job in jobs}), 24)  # ghz5 and its repeat share a circuit
        self.assertTrue(all(job.num_qubits <= 5 for job in jobs))

    def test_generation_is_deterministic(self):
        self.assertEqual([j.sha256 for j in build_suite()], [j.sha256 for j in build_suite()])

    def test_committed_files_match_the_generator(self):
        manifest = json.loads((SUITE_DIR / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest, suite_manifest())
        for job, entry in zip(build_suite(), manifest["jobs"]):
            self.assertEqual((SUITE_DIR / entry["qasm_file"]).read_text("ascii"), job.qasm)

    def test_ideal_distribution_matches_qiskit(self):
        for job in build_suite():
            circuit = qasm2.loads(job.qasm, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
            circuit.remove_final_measurements()
            expected = Statevector(circuit).probabilities()
            np.testing.assert_allclose(simulate(job, None), expected, atol=1e-12, err_msg=job.name)

    def test_deterministic_jobs_have_their_documented_outcome(self):
        expected = {
            "bitorder_q0_5": "00001", "qpe3_t": "1001", "qpe3_s": "1010", "qft4_roundtrip": "1010",
            "mirror4_d10": "0000", "mirror4_d20": "0000", "mirror4_d40": "0000",
            "grover2_mark11": "11", "bv4_1011": "01011", "dj3_balanced": "0111",
        }
        for job in build_suite():
            if job.name in expected:
                probabilities = simulate(job, None)
                self.assertAlmostEqual(probabilities[int(expected[job.name], 2)], 1.0, places=12, msg=job.name)


class IngestAndEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_results_are_refused_not_filled(self):
        with self.assertRaises(DatasetNotAvailableError):
            load_suite_run(self.tmp / "absent")
        self.tmp.joinpath("empty").mkdir()
        with self.assertRaises(DatasetNotAvailableError):
            load_suite_run(self.tmp / "empty")

    def test_fit_recovers_the_generating_model(self):
        _write_synthetic_run(self.tmp)
        payload = evaluate_suite(self.tmp, bootstrap_samples=500)
        model = payload["model"]
        self.assertAlmostEqual(model["cx_depolarizing"], TRUE_P, delta=0.01)
        self.assertAlmostEqual(model["p01_mean"], TRUE_P01, delta=0.01)
        self.assertAlmostEqual(model["p10_mean"], TRUE_P10, delta=0.01)
        self.assertEqual(payload["aggregate"]["n_eval"], 20)
        self.assertTrue(payload["aggregate"]["complete"])
        self.assertEqual(payload["aggregate"]["verdict"], "SUPPORTED")
        self.assertEqual(payload["backend"], "synthetic:test")

    def test_fit_uses_only_the_fit_split(self):
        _write_synthetic_run(self.tmp)
        before = evaluate_suite(self.tmp, bootstrap_samples=200)["model"]
        eval_job = next(job for job in build_suite() if job.split == "EVAL")
        (self.tmp / eval_job.job_id / "result.json").write_text(
            json.dumps({"counts": {"1" * eval_job.num_qubits: 4000}}), "utf-8"
        )
        after = evaluate_suite(self.tmp, bootstrap_samples=200)["model"]
        self.assertEqual(before, after)

    def test_tampered_circuit_is_an_integrity_error(self):
        _write_synthetic_run(self.tmp)
        (self.tmp / "OQ-06" / "circuit.qasm").write_text("OPENQASM 2.0;\n", "ascii")
        with self.assertRaises(IntegrityError):
            load_suite_run(self.tmp)

    def test_crlf_copy_of_a_preregistered_circuit_is_accepted(self):
        _write_synthetic_run(self.tmp)
        qasm = self.tmp / "OQ-06" / "circuit.qasm"
        qasm.write_bytes(qasm.read_bytes().replace(b"\n", b"\r\n"))
        self.assertIn("OQ-06", load_suite_run(self.tmp).counts)

    def test_wrong_width_is_an_integrity_error(self):
        _write_synthetic_run(self.tmp)
        (self.tmp / "OQ-06" / "result.json").write_text(json.dumps({"counts": {"000": 10}}), "utf-8")
        with self.assertRaises(IntegrityError):
            load_suite_run(self.tmp)

    def test_reversed_bit_order_stops_the_evaluation(self):
        _write_synthetic_run(self.tmp, reverse=True)
        run = load_suite_run(self.tmp)
        self.assertFalse(check_bit_order(run)["little_endian"])
        with self.assertRaises(IntegrityError):
            evaluate_suite(self.tmp, bootstrap_samples=100)

    def test_incomplete_eval_split_is_labelled(self):
        _write_synthetic_run(self.tmp)
        shutil.rmtree(self.tmp / "OQ-25")
        payload = evaluate_suite(self.tmp, bootstrap_samples=200)
        self.assertFalse(payload["aggregate"]["complete"])
        self.assertIn("incomplete: 19/20", payload["aggregate"]["verdict"])

    def test_missing_fit_job_is_refused(self):
        _write_synthetic_run(self.tmp)
        shutil.rmtree(self.tmp / "OQ-04")
        with self.assertRaises(DatasetNotAvailableError):
            evaluate_suite(self.tmp, bootstrap_samples=100)


class RunnerSpendGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        state_dir = self.tmp / "test_backend"
        state_dir.mkdir()
        (state_dir / "suite_state.json").write_text(
            json.dumps({"backend": "test:backend", "quoted_total": 12.5,
                        "jobs": {"OQ-01": {"preparation_id": "p", "quoted_credits": 0.5}}}),
            "utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra: str) -> int:
        import importlib.util

        spec = importlib.util.spec_from_file_location("run_openquantum_suite", RUNNER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.main(["--runs-dir", str(self.tmp), "--oq", "/nonexistent/oq.py",
                            "submit", "-b", "test:backend", *extra])

    def test_submit_without_yes_spends_nothing(self):
        self.assertEqual(self._run("--budget", "100"), 2)

    def test_submit_over_budget_spends_nothing(self):
        self.assertEqual(self._run("--budget", "10", "--yes"), 2)


if __name__ == "__main__":
    unittest.main()
