"""Finite P-vs-NP emulability check: every universal probe is exact and the QPU agrees."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVIDENCE = ROOT / "research/v4/evidence/pnp_emulability"


def test_every_universal_probe_matches_an_independent_statevector():
    summary = json.loads((EVIDENCE / "summary.json").read_text("utf-8"))
    assert summary["verdict"] == "EXACTLY_EMULABLE_AND_QPU_CONSISTENT"
    assert len(summary["exact_emulation"]) == 8
    for row in summary["exact_emulation"]:
        assert row["exact_classically_emulable"] is True
        assert abs(row["normalisation"] - 1.0) < 1e-12
        assert row["cqhecs_vs_qiskit_statevector_tv"] < 1e-12


def test_qpu_runs_and_sat_probe_are_recorded():
    summary = json.loads((EVIDENCE / "summary.json").read_text("utf-8"))
    assert len(summary["qpu_runs"]) >= 3
    assert summary["sat"]["dpll_status"] == "SAT"
    assert summary["sat"]["dpll_model"] == "100"
    assert summary["sat"]["model_verified"] is True
    assert all(item["sat_top"] == "100" for item in summary["sat"]["qpu"])
    assert "not decide" in summary["non_claim"] or "does not decide" in summary["non_claim"]


def test_report_and_no_credentials():
    report = (EVIDENCE / "REPORT.md").read_text("utf-8")
    assert "not a complexity result" in report
    assert "O(4^n)" in report
    for path in EVIDENCE.rglob("*"):
        if path.is_file():
            text = path.read_text("utf-8", errors="ignore")
            assert "apikey" not in text.lower()
            assert "Signature=" not in text
