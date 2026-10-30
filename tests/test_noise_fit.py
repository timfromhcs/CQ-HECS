"""Tests for the per-qubit noise fit (EMULATOR_BUILD_PLAN W1, W3, W4, W5).

The measured ``r-io-7`` counts are committed under
``research/v3/evidence/openquantum``; tests read them offline.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cqhecs.noise_fit import (
    PerQubitModel,
    _calibration_status,
    dump_profile,
    evaluate_exploratory,
    fit_profile,
)
from cqhecs.openquantum_suite import FittedModel, build_suite, load_suite_run, simulate

REPO_ROOT = Path(__file__).resolve().parents[1]
RIGETTI = REPO_ROOT / "research" / "v3" / "evidence" / "openquantum" / "rigetti_cepheus-1-108q"

# Measured on rigetti:cepheus-1-108q (OQ-01 / OQ-02, 1000 shots each).
MEASURED_P01 = (0.070, 0.039, 0.003, 0.042, 0.011)
MEASURED_P10 = (0.531, 0.060, 0.059, 0.093, 0.077)


def _ghz5():
    return next(job for job in build_suite() if job.name == "ghz5")


class PerQubitReadoutTests(unittest.TestCase):
    """W3: the density-matrix path applies each qubit's own readout matrix."""

    def test_ghz5_matches_the_analytic_per_qubit_prediction(self):
        model = PerQubitModel(MEASURED_P01, MEASURED_P10, 0.0)
        simulated = simulate(_ghz5(), model.noise_model(_ghz5()))
        expected = np.zeros(32)
        for index in range(32):
            bits = [(index >> q) & 1 for q in range(5)]
            from_zero = np.prod([MEASURED_P01[q] if b else 1 - MEASURED_P01[q] for q, b in enumerate(bits)])
            from_one = np.prod([1 - MEASURED_P10[q] if b else MEASURED_P10[q] for q, b in enumerate(bits)])
            expected[index] = 0.5 * from_zero + 0.5 * from_one
        np.testing.assert_allclose(simulated, expected, atol=1e-12)
        # With P(0|1) = 0.531 on qubit 0, misreading it beats reading 11111.
        self.assertGreater(simulated[0b11110], simulated[0b11111])

    def test_per_qubit_model_differs_from_its_device_mean(self):
        per_qubit = PerQubitModel(MEASURED_P01, MEASURED_P10, 0.0)
        mean = FittedModel(float(np.mean(MEASURED_P01)), float(np.mean(MEASURED_P10)), 0.0,
                           MEASURED_P01, MEASURED_P10, 0.0, ())
        a = simulate(_ghz5(), per_qubit.noise_model(_ghz5()))
        b = simulate(_ghz5(), mean.noise_model(_ghz5()))
        self.assertGreater(0.5 * np.abs(a - b).sum(), 0.05)


_SHARED = {}


def _measured():
    """Fit and score once per test run; the fits dominate the runtime."""
    if not _SHARED:
        _SHARED["exploratory"] = evaluate_exploratory(RIGETTI, bootstrap_samples=500)
        _SHARED["profile"] = fit_profile(RIGETTI)[1]
    return _SHARED


class MeasuredProfileTests(unittest.TestCase):
    """W1, W4, W5 on the committed r-io-7 counts."""

    @classmethod
    def setUpClass(cls):
        cls.document = _measured()["profile"]

    def test_readout_reproduces_the_measured_probes(self):
        for row, p01, p10 in zip(self.document["readout"], MEASURED_P01, MEASURED_P10):
            self.assertAlmostEqual(row["p01"], p01, places=12)
            self.assertAlmostEqual(row["p10"], p10, places=12)
            self.assertAlmostEqual(row["p10_se"], np.sqrt(p10 * (1 - p10) / 1000), places=12)

    def test_profile_is_byte_identical_on_refit(self):
        # evaluate_exploratory fitted the same data independently.
        self.assertEqual(dump_profile(self.document), dump_profile(_measured()["exploratory"]["profile"]))

    def test_corrected_and_uncorrected_cx_are_both_reported(self):
        cx = self.document["cx_depolarizing"]
        self.assertLess(cx["readout_corrected"], cx["uncorrected"])
        self.assertIn("assumption", cx)

    def test_absent_calibration_is_explicit(self):
        self.assertEqual(self.document["provenance"]["calibration"], {"status": "absent", "files": {}})

    def test_status_is_exploratory(self):
        self.assertEqual(self.document["status"], "EXPLORATORY_POST_HOC")


class CalibrationStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(RIGETTI, self.tmp / "run", ignore=shutil.ignore_patterns("*.png", "*.csv", "*.md"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_snapshot_flips_the_status_to_present(self):
        self.assertEqual(_calibration_status(load_suite_run(self.tmp / "run"))["status"], "absent")
        (self.tmp / "run" / "OQ-01" / "calibration.json").write_text(json.dumps({"t1": {}}), "utf-8")
        status = _calibration_status(load_suite_run(self.tmp / "run"))
        self.assertEqual(status["status"], "present")
        self.assertIn("OQ-01", status["files"])


class ExploratoryEvaluationTests(unittest.TestCase):
    def test_measured_outcome_is_recorded_not_assumed(self):
        payload = _measured()["exploratory"]
        self.assertEqual(payload["status"], "EXPLORATORY_POST_HOC")
        self.assertEqual(payload["vs_ideal"]["n"], 20)
        self.assertEqual(payload["calibration"]["status"], "absent")
        # On r-io-7 the per-qubit transfer does not beat the frozen device-mean
        # model: the probe jobs and the GHZ jobs did not share a layout.
        self.assertNotEqual(payload["vs_m_fit"]["direction"], "M-FIT-2 better")


if __name__ == "__main__":
    unittest.main()
