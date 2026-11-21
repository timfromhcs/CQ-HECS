"""Campaign runner tests: offline generate/validate, secret-safe doctor gating."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_qg_openquantum_campaign.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("qg_campaign_module", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_generate_then_validate(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    assert module.main(["--campaign", str(campaign), "generate"]) == 0
    assert (campaign / "qasm" / "CIRCUIT_MANIFEST.json").is_file()
    assert (campaign / "MODEL_MANIFEST.json").is_file()
    assert module.main(["--campaign", str(campaign), "validate"]) == 0


def test_validate_detects_tampering(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    assert module.main(["--campaign", str(campaign), "generate"]) == 0
    manifest = json.loads((campaign / "qasm" / "CIRCUIT_MANIFEST.json").read_text("utf-8"))
    victim = campaign / "qasm" / manifest["circuits"][0]["qasm_file"]
    victim.write_text(victim.read_text("utf-8") + "// tampered\n", encoding="utf-8")
    assert module.main(["--campaign", str(campaign), "validate"]) == 1


def test_validate_without_generate_fails(tmp_path):
    module = _load_module()
    campaign = tmp_path / "empty"
    assert module.main(["--campaign", str(campaign), "validate"]) == 1


def test_doctor_without_credentials_is_blocked(monkeypatch):
    module = _load_module()
    monkeypatch.delenv("OPENQUANTUM_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENQUANTUM_CLIENT_SECRET", raising=False)
    assert module.main(["doctor"]) == 2


def test_report_writes_file(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    assert module.main(["--campaign", str(campaign), "report"]) == 0
    report = json.loads((campaign / "reports" / "campaign_report.json").read_text("utf-8"))
    assert report["campaign_id"] == "qg-2026-01"
    assert report["submitted_credits"] == 0.0


def test_quote_and_submit_are_gated_without_credentials(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    assert module.main(["--campaign", str(campaign), "quote", "--backend", "qr:sim"]) == 2
    assert module.main(["--campaign", str(campaign), "submit"]) == 2
