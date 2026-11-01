"""Public result bundle: derived from raw captures, never carries identifiers or secrets."""
import json

import pytest

from cqhecs.hardware import results


def _raw(tmp_path, n=5, gap_at=(2,), extra=None):
    rows = []
    for i in range(n):
        row = {"i": i, "t_utc": f"2026-11-01T20:{i:02d}:00Z"}
        if i in gap_at:
            row["gap"] = "TimeoutError"
        else:
            row.update({"version": "v4.0.2-rc1-timsminer", "runningPartition": "factory", "ASICModel": "BM1366",
                        "boardVersion": "201", "frequency": 485, "coreVoltage": 1100, "hashRate": 340.0 + i,
                        "temp": 65, "vrTemp": 0, "power": 11.5, "wifiRSSI": -57, "freeHeap": 7000000,
                        "sharesAccepted": 100 + i, "sharesRejected": 1, "uptimeSeconds": 1000 + 30 * i,
                        "resetReason": "Software reset via esp_restart", "errorPercentage": 0})
            if extra:
                row.update(extra)
        rows.append(row)
    p = tmp_path / "baseline.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_bundle_shape_and_gaps_stay_gaps(tmp_path):
    b = results.build_public_baseline(_raw(tmp_path), interval_s=30)
    assert b["schema"] == "hcs.sha.forge.baseline.v1"
    assert b["source"] == "MEASURED" and b["mode"] == "STOCK_FIRMWARE_READ_ONLY"
    assert len(b["samples"]) == 5
    assert b["samples"][2]["hashrate_ghs"] is None   # never interpolated
    assert b["summary"]["gaps"] == 1 and b["summary"]["samples"] == 4
    assert b["summary"]["hashrate_ghs"]["min"] == 340.0 and b["summary"]["hashrate_ghs"]["max"] == 344.0
    assert b["summary"]["shares_accepted_delta"] == 4


def test_no_identifiers_or_secrets_leave_the_machine(tmp_path):
    p = _raw(tmp_path, extra={"stratumUser": "WALLET.worker", "wifiPass": "PSK", "macAddr": "AA:BB:CC:DD:EE:FF",
                              "ipv4": "192.168.1.9", "ssid": "HomeNet"})
    b = results.build_public_baseline(p, interval_s=30)
    blob = json.dumps(b)
    for bad in ("WALLET", "PSK", "AA:BB:CC", "192.168", "HomeNet", "stratum", "macAddr", "ssid"):
        assert bad not in blob
    results.assert_public_safe(b)


@pytest.mark.parametrize("poison", [
    {"x": "192.168.50.20"}, {"x": "02:11:22:33:44:55"}, {"stratumUser": "a"}, {"nested": {"wallet": "dgb1qabc"}},
    {"x": "dgb1q" + "a" * 38}, {"x": "bc1q" + "a" * 38}, {"list": ["10.0.0.1"]}, {"password": "x"},
])
def test_public_safety_check_rejects_poisoned_bundles(poison):
    with pytest.raises(ValueError):
        results.assert_public_safe({"schema": "hcs.sha.forge.baseline.v1", **poison})


def test_empty_or_all_gap_capture_is_reported_not_faked(tmp_path):
    p = _raw(tmp_path, n=3, gap_at=(0, 1, 2))
    b = results.build_public_baseline(p, interval_s=30)
    assert b["summary"]["samples"] == 0 and b["summary"]["hashrate_ghs"] is None
    assert b["verdict"] == "NO_DATA"


def test_identity_error_row_marks_bundle_invalid(tmp_path):
    p = _raw(tmp_path)
    with p.open("a", encoding="utf-8") as f:
        f.write("\n" + json.dumps({"i": 9, "t_utc": "x", "identity_error": "MAC mismatch"}))
    b = results.build_public_baseline(p, interval_s=30)
    assert b["verdict"] == "IDENTITY_MISMATCH"


def test_malformed_lines_are_skipped_but_counted(tmp_path):
    p = _raw(tmp_path)
    with p.open("a", encoding="utf-8") as f:
        f.write("\n{not json\n[]\n")
    b = results.build_public_baseline(p, interval_s=30)
    assert b["summary"]["malformed_lines"] == 2
