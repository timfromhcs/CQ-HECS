"""Integrity and reproducibility of the committed 10,000-shot IBM evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cqhecs.openquantum_suite import build_suite, evaluate_suite

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "research" / "v4" / "evidence" / "ibm_10k"
BACKENDS = ("ibm_fez", "ibm_kingston", "ibm_marrakesh")


def _load(path: Path):
    return json.loads(path.read_text("utf-8"))


@pytest.mark.parametrize("backend", BACKENDS)
def test_every_job_has_pinned_digest_and_ten_thousand_shots(backend):
    folder = EVIDENCE / backend
    suite = build_suite()
    provider_ids = set()
    for job in suite:
        job_dir = folder / job.job_id
        meta = _load(job_dir / "job.json")
        counts = _load(job_dir / "result.json")
        qasm_digest = hashlib.sha256((job_dir / "circuit.qasm").read_bytes()).hexdigest()
        assert meta["metadata"]["qasm_sha256"] == qasm_digest
        assert meta["metadata"]["job_id"] == job.job_id
        assert meta["job"]["backend"] == backend
        assert meta["job"]["status"] == "Completed"
        assert meta["shots"] == 10000
        assert sum(counts.values()) == 10000
        assert all(len(key) == job.num_qubits for key in counts)
        provider_ids.add(meta["job"]["id"])
    assert all(provider_ids)


@pytest.mark.parametrize("backend", BACKENDS)
def test_committed_verdicts_and_bit_order(backend):
    evaluation = _load(EVIDENCE / backend / "h_v3_8_evaluation.json")
    assert evaluation["backend"] == backend
    assert evaluation["bit_order"]["little_endian"] is True
    assert evaluation["bit_order"]["mode"] == "00001"
    aggregate = evaluation["aggregate"]
    assert aggregate["verdict"] == "SUPPORTED"
    assert aggregate["n_eval"] == 20
    assert aggregate["ci95_high"] < 0
    exploratory = _load(EVIDENCE / backend / "m_fit_2_exploratory.json")
    assert exploratory["status"] == "EXPLORATORY_POST_HOC"
    summary = _load(EVIDENCE / "summary_evaluation.json")
    row = next(item for item in summary["backends"] if item["backend"] == backend)
    assert row["h_v3_8"]["median_delta_tv"] == aggregate["median_delta_tv"]


def test_evaluation_reproduces_from_counts():
    # The median is bootstrap-independent; a short bootstrap keeps this fast.
    backend = "ibm_kingston"
    committed = _load(EVIDENCE / backend / "h_v3_8_evaluation.json")["aggregate"]
    fresh = evaluate_suite(EVIDENCE / backend, bootstrap_samples=200)["aggregate"]
    assert fresh["median_delta_tv"] == pytest.approx(committed["median_delta_tv"], abs=1e-12)
    assert fresh["n_noisy_better"] == committed["n_noisy_better"]
