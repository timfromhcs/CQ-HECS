"""Finite SAT-oracle transfer and MPS-losslessness report checks."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVIDENCE = ROOT / "research/v4/evidence/pnp_sat_oracles"


def test_sat_oracles_transfer_and_are_honest_about_losslessness():
    summary = json.loads((EVIDENCE / "summary.json").read_text("utf-8"))
    assert summary["verdict"]["all_qpu_top_outcomes_are_models"] is True
    assert summary["verdict"]["transferable_top_outcome"] is True
    assert summary["verdict"]["exact_classical_emulation"] is True
    assert summary["verdict"]["all_mps_strictly_lossless"] is False
    assert len(summary["runs"]) >= 2
    for run in summary["runs"]:
        assert run["backend"] in ("ibm_fez", "ibm_marrakesh")
        for oracle in run["oracles"]:
            assert oracle["top_is_model"] is True
            assert oracle["dpll_status"] == "SAT"
            assert oracle["top_outcome"] in oracle["dpll_models"]
            assert 0.0 <= oracle["model_mass"] <= 1.0


def test_report_and_no_credentials():
    report = (EVIDENCE / "REPORT.md").read_text("utf-8")
    assert "Not a complexity result" in report
    assert "separate P from NP" in report
    for path in EVIDENCE.rglob("*"):
        if path.is_file():
            text = path.read_text("utf-8", errors="ignore")
            assert "apikey" not in text.lower()
            assert "Signature=" not in text
