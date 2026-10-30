"""Integrity checks for the external IBM Quantum run (r-io-7 on ibm_fez)."""

from __future__ import annotations

import json
from pathlib import Path

from cqhecs.openquantum_suite import check_bit_order, load_suite_run

ROOT = Path(__file__).parent.parent
IBM = ROOT / "research/v4/evidence/ibm/ibm_fez"


def test_ibm_run_has_all_jobs_and_the_expected_bit_order():
    run = load_suite_run(IBM)
    assert len(run.counts) == 25
    assert run.backend == "ibm_fez"
    order = check_bit_order(run)
    assert order["little_endian"] is True
    assert order["mode"] == "00001"


def test_ibm_frozen_and_corrected_evaluations_are_recorded():
    frozen = json.loads((IBM / "h_v3_8_evaluation.json").read_text("utf-8"))
    assert frozen["aggregate"]["verdict"] == "SUPPORTED"
    assert frozen["aggregate"]["n_eval"] == 20
    assert frozen["aggregate"]["median_delta_tv"] < 0
    assert frozen["aggregate"]["ci95_high"] < 0

    corrected = json.loads((IBM / "m_fit_2_exploratory.json").read_text("utf-8"))
    assert corrected["profile"]["anomalies"] == []
    assert corrected["vs_ideal"]["direction"] == "M-FIT-2 better"
    assert corrected["vs_m_fit"]["direction"] == "M-FIT-2 worse"


def test_ibm_summary_has_no_credentials_or_signed_urls():
    summary = json.loads((IBM / "summary.json").read_text("utf-8"))
    assert summary["dataset_id"] == "r-ibm-1"
    assert summary["backend"] == "ibm_fez"
    assert summary["job_id"] == "dbidem5ep8hs73ankcvg"
    assert summary["shots"] == 1000
    assert len(summary["fixed_chain"]) == 5
    for path in IBM.rglob("*"):
        if path.is_file():
            text = path.read_text("utf-8", errors="ignore")
            assert "apikey" not in text.lower()
            assert "Signature=" not in text
