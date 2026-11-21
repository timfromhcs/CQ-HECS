"""D2 (W3-05): the campaign ledger guard must fail closed and net spends correctly.

Before this change the guard summed only ``submitted`` events, so the real campaign
ledger (27 submitted, 2 refunded) read as 27 > 25 and would have refused every future
submit; malformed lines were skipped silently, which could hide a spend event. These
tests pin the net-spend rule and the fail-closed parse against the real ledger and
against hand-built fixtures.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import run_qg_openquantum_campaign as runner  # noqa: E402  (script module under scripts/)


def _write(tmp_path: Path, lines) -> Path:
    ledger = tmp_path / "JOB_LEDGER.jsonl"
    ledger.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return tmp_path


def _submitted(job="j1", prep="p1", credits=1.0):
    return {"event": "submitted", "provider_job_id": job, "preparation_id": prep, "quoted_credits": credits}


def _refunded(job="j1", credits=1.0, status="confirmed"):
    return {"event": "refunded", "provider_job_id": job, "refunded_credits": credits, "refund_status": status}


# ------------------------------------------------------------------ real ledger

def test_the_real_campaign_ledger_nets_to_25_of_25_credits():
    summary = runner._ledger_summary(REPO / "research" / "qg_2026")
    assert summary["gross_submitted_credits"] == 27.0
    assert summary["refunded_credits"] == 2.0
    assert summary["net_spent_credits"] == 25.0
    assert runner._load_ledger_spend(REPO / "research" / "qg_2026") == 25.0


# --------------------------------------------------------------- fail-closed

def test_a_corrupt_line_aborts_instead_of_being_skipped(tmp_path):
    ledger = tmp_path / "JOB_LEDGER.jsonl"
    ledger.write_text(json.dumps(_submitted()) + "\n{not json\n", encoding="utf-8")
    with pytest.raises(runner.LedgerError, match="invalid JSON"):
        runner._ledger_summary(tmp_path)


def test_an_unknown_event_is_rejected(tmp_path):
    _write(tmp_path, [{"event": "teleported"}])
    with pytest.raises(runner.LedgerError, match="unknown or missing event"):
        runner._ledger_summary(tmp_path)


def test_a_submitted_event_needs_a_provider_job_id(tmp_path):
    _write(tmp_path, [{"event": "submitted", "preparation_id": "p1", "quoted_credits": 1.0}])
    with pytest.raises(runner.LedgerError, match="provider_job_id"):
        runner._ledger_summary(tmp_path)


def test_a_non_numeric_credit_aborts(tmp_path):
    _write(tmp_path, [{"event": "submitted", "provider_job_id": "j1", "preparation_id": "p1", "quoted_credits": "one"}])
    with pytest.raises(runner.LedgerError, match="quoted_credits"):
        runner._ledger_summary(tmp_path)


def test_a_refund_for_an_unknown_job_is_rejected(tmp_path):
    _write(tmp_path, [_submitted(job="j1"), _refunded(job="does-not-exist")])
    with pytest.raises(runner.LedgerError, match="unknown job"):
        runner._ledger_summary(tmp_path)


# ----------------------------------------------------------------- net spend

def test_a_failed_job_without_a_refund_still_counts_as_spent(tmp_path):
    _write(tmp_path, [_submitted(credits=3.0), {"event": "failed", "provider_job_id": "j1"}])
    assert runner._ledger_summary(tmp_path)["net_spent_credits"] == 3.0


def test_a_confirmed_refund_is_subtracted(tmp_path):
    _write(tmp_path, [_submitted(credits=3.0), _refunded(credits=3.0)])
    assert runner._ledger_summary(tmp_path)["net_spent_credits"] == 0.0


def test_a_refund_never_exceeds_the_job_quoted_credits(tmp_path):
    _write(tmp_path, [_submitted(job="j1", credits=1.0), _refunded(job="j1", credits=5.0)])
    summary = runner._ledger_summary(tmp_path)
    assert summary["refunded_credits"] == 1.0
    assert summary["net_spent_credits"] == 0.0


def test_an_unconfirmed_refund_is_not_subtracted(tmp_path):
    _write(tmp_path, [_submitted(credits=2.0), _refunded(credits=2.0, status="pending")])
    summary = runner._ledger_summary(tmp_path)
    assert summary["refunded_credits"] == 0.0
    assert summary["refund_unconfirmed_credits"] == 2.0
    assert summary["net_spent_credits"] == 2.0


def test_an_unresolved_submit_intent_counts_as_spent(tmp_path):
    _write(tmp_path, [{"event": "submit_intent", "preparation_id": "p1", "quoted_credits": 1.5}])
    summary = runner._ledger_summary(tmp_path)
    assert summary["unresolved_credits"] == 1.5
    assert summary["net_spent_credits"] == 1.5


def test_an_intent_resolved_by_a_later_submit_is_not_double_counted(tmp_path):
    _write(tmp_path, [
        {"event": "submit_intent", "preparation_id": "p1", "quoted_credits": 1.0},
        _submitted(job="j1", prep="p1", credits=1.0),
    ])
    summary = runner._ledger_summary(tmp_path)
    assert summary["unresolved_credits"] == 0.0
    assert summary["net_spent_credits"] == 1.0


def test_a_missing_ledger_is_zero_spend(tmp_path):
    assert runner._ledger_summary(tmp_path)["net_spent_credits"] == 0.0


def test_main_reports_a_corrupt_ledger_with_exit_code_3(monkeypatch, capsys):
    def boom(args):
        raise runner.LedgerError("JOB_LEDGER.jsonl:1: invalid JSON")

    monkeypatch.setattr(runner, "cmd_validate", boom)
    code = runner.main(["validate"])
    assert code == 3
    document = json.loads(capsys.readouterr().out)
    assert document["status"] == "FAILED"
    assert document["code"] == "QG_LEDGER_CORRUPT"

