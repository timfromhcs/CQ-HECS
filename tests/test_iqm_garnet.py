"""Integrity and reproducibility of the r-iqm-1 run (r-io-7 suite on IQM Garnet)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cqhecs.openquantum_suite import build_suite, evaluate_suite

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "research" / "v3" / "evidence" / "openquantum" / "iqm_garnet"
MANIFEST = ROOT / "research" / "v3" / "openquantum_suite" / "manifest.json"


def _load(path: Path):
    return json.loads(path.read_text("utf-8"))


def test_preregistration_precedes_the_run():
    prereg = (ROOT / "research" / "v4" / "PREREG_IQM_GARNET.md").read_text("utf-8")
    assert "500 per circuit" in prereg and "before" in prereg


def test_every_job_matches_the_pinned_manifest_and_budget():
    manifest = {job["job_id"]: job for job in _load(MANIFEST)["jobs"]}
    state = _load(RUN / "suite_state.json")
    assert state["backend"] == "iqm:garnet"
    assert state["quoted_total"] == 25.0
    provider_ids = set()
    for job in build_suite():
        entry = state["jobs"][job.job_id]
        folder = RUN / job.job_id
        digest = hashlib.sha256((folder / "circuit.qasm").read_bytes()).hexdigest()
        assert digest == manifest[job.job_id]["qasm_sha256"] == entry["qasm_sha256"]
        assert entry["shots"] == 500 and entry["quoted_credits"] == 1.0
        assert entry["status"] == "Completed"
        counts = _load(folder / "result.json")
        assert sum(counts.values()) == 500
        assert all(len(k) == job.num_qubits for k in counts)
        assert _load(folder / "job.json")["job"]["id"] == entry["provider_job_id"]
        provider_ids.add(entry["provider_job_id"])
    assert len(provider_ids) == 25


def test_no_signed_urls_or_credentials_in_the_evidence():
    for path in RUN.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".md", ".csv", ".qasm"):
            text = path.read_text("utf-8", "ignore")
            assert "Signature=" not in text and "client_secret" not in text, path


def test_committed_verdict_and_bit_order():
    evaluation = _load(RUN / "h_v3_8_evaluation.json")
    assert evaluation["bit_order"]["mode"] == "00001"
    agg = evaluation["aggregate"]
    assert agg["verdict"] == "SUPPORTED"
    assert agg["n_eval"] == 20 and agg["n_noisy_better"] == 16
    assert agg["ci95_high"] < 0
    assert _load(RUN / "m_fit_2_exploratory.json")["status"] == "EXPLORATORY_POST_HOC"


@pytest.mark.parametrize("bootstrap", [200])
def test_evaluation_reproduces_from_counts(bootstrap):
    committed = _load(RUN / "h_v3_8_evaluation.json")["aggregate"]
    fresh = evaluate_suite(RUN, bootstrap_samples=bootstrap)["aggregate"]
    assert fresh["median_delta_tv"] == pytest.approx(committed["median_delta_tv"], abs=1e-12)
    assert fresh["n_noisy_better"] == committed["n_noisy_better"]
