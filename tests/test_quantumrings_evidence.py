"""The committed independent-oracle evidence must remain honest and key-free."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVIDENCE = ROOT / "research/v4/evidence/quantumrings/scarlet_quantum_rings"


def test_summary_is_complete_and_passes():
    summary = json.loads((EVIDENCE / "summary.json").read_text("utf-8"))
    assert summary["dataset_id"] == "r-qr-1"
    assert summary["aggregate"]["n"] >= 20
    assert summary["aggregate"]["verdict"] == "PASS"
    assert summary["aggregate"]["failed"] == 0
    ids = {row["circuit_id"] for row in summary["circuits"]}
    assert {"ghz2", "ghz10", "ghz64", "ghz100", "ghz128", "qft8"} <= ids
    for row in summary["circuits"]:
        assert row["qasm_sha256"]
        assert row["shots"] == 4096
        assert row["pass"] is True
        assert row["tv"] <= row["null_p99"]
        qasm = EVIDENCE / "qasm" / f"{row['circuit_id']}.qasm"
        assert qasm.is_file()
        assert hashlib.sha256(qasm.read_bytes()).hexdigest() == row["qasm_sha256"]


def test_no_credentials_in_evidence():
    pattern = re.compile(r"rings-\d+\.")
    for path in EVIDENCE.rglob("*"):
        if path.is_file():
            text = path.read_text("utf-8", errors="ignore")
            assert not pattern.search(text), f"credential-looking string in {path}"


def test_report_exists_and_states_the_non_claim():
    report = (EVIDENCE / "REPORT.md").read_text("utf-8")
    assert "independent QuantumRings cross-check" in report
    assert "not a QPU" in report
    assert "P = NP" in report
