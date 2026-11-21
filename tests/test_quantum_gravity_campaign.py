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


FAKE_OQ = '''
import sys, json
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "quote":
    print(json.dumps({"preparation_id": "prep-1",
                      "selected": {"plan": "Public Plan", "priority": "Standard Queue", "total_cost": 1}}))
elif cmd == "submit":
    print(json.dumps({"job_id": "job-1", "status": "Created"}))
elif cmd == "wait":
    print("Completed")
elif cmd == "results":
    print(json.dumps({"status": "Completed"}))
else:
    print(json.dumps({}))
'''


def _make_set(tmp_path):
    setdir = tmp_path / "set"
    setdir.mkdir()
    (setdir / "c0.qasm").write_bytes(b"OPENQASM 2.0;\n")
    (setdir / "MANIFEST.json").write_text(
        json.dumps({"circuits": [{"circuit_id": "c0", "file": "c0.qasm", "qasm_sha256": "x"}]}),
        encoding="utf-8",
    )
    fake = tmp_path / "oq.py"
    fake.write_text(FAKE_OQ, encoding="utf-8")
    return setdir, fake


def test_quote_then_submit_with_fake_oq(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    setdir, fake = _make_set(tmp_path)
    code = module.main(["--campaign", str(campaign), "quote", "--backend", "rigetti:cepheus-1-108q",
                        "--set", str(setdir), "--shots", "1000", "--oq", str(fake)])
    assert code == 0
    ledger = json.loads((campaign / "QUOTE_LEDGER.json").read_text("utf-8"))
    assert ledger["quoted_total_credits"] == 1.0
    assert ledger["quotes"][0]["preparation_id"] == "prep-1"

    # submit without --yes is refused
    assert module.main(["--campaign", str(campaign), "submit", "--oq", str(fake)]) == 2
    # submit with --yes spends
    assert module.main(["--campaign", str(campaign), "submit", "--yes", "--oq", str(fake)]) == 0
    events = [json.loads(l) for l in (campaign / "JOB_LEDGER.jsonl").read_text("utf-8").splitlines() if l.strip()]
    assert any(e.get("event") == "submitted" and e["provider_job_id"] == "job-1" for e in events)


def test_submit_respects_budget(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    setdir, fake = _make_set(tmp_path)
    module.main(["--campaign", str(campaign), "quote", "--backend", "rigetti:cepheus-1-108q",
                 "--set", str(setdir), "--oq", str(fake)])
    assert module.main(["--campaign", str(campaign), "submit", "--yes", "--budget", "0", "--oq", str(fake)]) == 2


def test_collect_with_fake_oq(tmp_path):
    module = _load_module()
    campaign = tmp_path / "qg_2026"
    setdir, fake = _make_set(tmp_path)
    module.main(["--campaign", str(campaign), "quote", "--backend", "rigetti:cepheus-1-108q",
                 "--set", str(setdir), "--oq", str(fake)])
    module.main(["--campaign", str(campaign), "submit", "--yes", "--oq", str(fake)])
    assert module.main(["--campaign", str(campaign), "collect", "--oq", str(fake)]) == 0
    events = [json.loads(l) for l in (campaign / "JOB_LEDGER.jsonl").read_text("utf-8").splitlines() if l.strip()]
    assert any(e.get("event") == "collected" for e in events)
