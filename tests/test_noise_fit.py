"""Regression tests for the measured M-FIT-2 fit (research/v4 W1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cqhecs.noise_fit import evaluate_fit, fit_noise

ROOT = Path(__file__).parent.parent
EVIDENCE = ROOT / "research/v3/evidence/openquantum/rigetti_cepheus-1-108q"
ARTIFACT = ROOT / "research/v4/evidence/r-io-7/mfit2.json"


@pytest.fixture(scope="module")
def fit():
    return fit_noise(EVIDENCE)


def test_oq02_qubit0_is_not_installed_as_readout_error(fit):
    # OQ-02 reports 0.531 zeros on qubit 0, but OQ-03 and OQ-09 show it is an
    # X-gate anomaly, not a measurement error.
    assert fit.p10_observed[0] == pytest.approx(0.531)
    assert fit.p10[0] < 0.10
    assert 0 in fit.anomalous_qubits
    assert fit.x_bitflip[0] > 0.30
    assert fit.x_bitflip[1:] == pytest.approx((0.0, 0.0, 0.0, 0.0))


def test_fit_beats_frozen_mfit_on_fit_split(fit):
    assert fit.fit_tv < fit.mfit_tv
    assert fit.fit_tv < 0.15
    assert fit.mfit_tv > 0.22


def test_holdout_improves_post_hoc(fit):
    evaluation = evaluate_fit(fit, EVIDENCE, bootstrap_samples=200, seed=20261030)
    mfit = evaluation["models"]["M-FIT"]
    mfit2 = evaluation["models"]["M-FIT-2"]
    assert evaluation["status"] == "exploratory_post_hoc"
    assert mfit2["median_delta_tv"] < mfit["median_delta_tv"]
    assert mfit2["n_noisy_better"] >= mfit["n_noisy_better"]
    assert mfit2["ci95_high"] < 0.0


def test_model_is_deterministic_and_matches_artifact(fit):
    # Byte-identical within a platform; the committed artifact is matched
    # numerically so a different BLAS cannot fail the test at 1e-15.
    assert fit.to_json() == fit.to_json()
    artifact = json.loads(ARTIFACT.read_text("utf-8"))
    assert fit.p01 == pytest.approx(tuple(artifact["readout"]["p01"]), abs=1e-12)
    assert fit.p10 == pytest.approx(tuple(artifact["readout"]["p10"]), abs=1e-12)
    assert fit.x_bitflip == pytest.approx(tuple(artifact["x_bitflip"]), abs=1e-12)
    assert fit.cx_depolarizing == pytest.approx(artifact["cx_depolarizing"], abs=1e-12)
    assert fit.fit_tv == pytest.approx(artifact["fit"]["fit_tv"], abs=1e-9)
    assert fit.mfit_tv == pytest.approx(artifact["fit"]["mfit_fit_tv"], abs=1e-9)


def test_noise_model_uses_per_qubit_values(fit):
    from cqhecs.openquantum_suite import build_suite

    job = next(job for job in build_suite() if job.job_id == "OQ-09")
    model = fit.noise_model(job)
    assert model.readout_errors[0].p10 == pytest.approx(fit.p10[0])
    assert model.readout_errors[4].p10 == pytest.approx(fit.p10[4])
    assert model.readout_errors[0].p10 != pytest.approx(model.readout_errors[1].p10)


def test_backend_profile_is_valid_and_not_synthetic(fit):
    profile = fit.to_profile()
    assert profile.num_qubits == 5
    assert profile.is_synthetic is False
    assert profile.readout_errors[0][0] == pytest.approx(fit.p01[0])
    assert profile.readout_errors[0][1] == pytest.approx(fit.p10[0])
    assert profile.source_sha256 == fit.dataset_sha256


def test_artifact_files_agree(fit):
    base = ARTIFACT.parent
    evaluation = json.loads((base / "mfit2_evaluation.json").read_text("utf-8"))
    profile = json.loads((base / "profile.json").read_text("utf-8"))
    assert evaluation["dataset_sha256"] == fit.dataset_sha256
    assert profile["name"].startswith("M-FIT-2")
    assert profile["schema_version"] == "2.0"
