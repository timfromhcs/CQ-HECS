"""Public measurement bundle built from a raw baseline capture.

Only whitelisted, non-identifying numeric fields survive. `assert_public_safe` is the last gate: any bundle that
contains an address, MAC, wallet-like string, credential-like key or pool/Wi-Fi field is refused.
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

SCHEMA = "hcs.sha.forge.baseline.v1"

# raw field -> public field
SERIES = {
    "hashRate": "hashrate_ghs", "temp": "temperature_c", "vrTemp": "vr_temperature_c", "power": "power_w",
    "wifiRSSI": "wifi_rssi_dbm", "freeHeap": "free_heap_bytes", "frequency": "frequency_mhz",
    "coreVoltage": "core_voltage_mv", "errorPercentage": "asic_error_percent",
}

_FORBIDDEN_KEYS = re.compile(r"(stratum|wallet|pass(word)?|secret|token|ssid|mac|bssid|ipv4|ipv6|ip_?addr|pool|worker|user)", re.I)
_FORBIDDEN_VALUES = (
    re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b"),                    # IPv4
    re.compile(r"\b[0-9a-f]{2}([:-][0-9a-f]{2}){5}\b", re.I),     # MAC
    re.compile(r"\b(dgb1|bc1|tb1|ltc1|bitcoincash:|q[a-z0-9]{30,})[a-z0-9]{20,}\b", re.I),  # bech32 / wallet-like
)


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + "/" + str(k), str(k), None
            yield from _walk(v, path + "/" + str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, None, obj


def assert_public_safe(bundle: dict) -> None:
    for path, key, value in _walk(bundle):
        if key is not None and _FORBIDDEN_KEYS.search(key):
            raise ValueError(f"forbidden key in public bundle: {path}")
        if value is not None and any(p.search(value) for p in _FORBIDDEN_VALUES):
            raise ValueError(f"identifier-like value in public bundle at {path}")


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf") else None


def _stat(values):
    v = [x for x in values if x is not None]
    if not v:
        return None
    return {"n": len(v), "min": min(v), "max": max(v), "mean": round(statistics.fmean(v), 3),
            "stdev": round(statistics.pstdev(v), 3)}


def build_public_baseline(jsonl_path, interval_s: float) -> dict:
    rows, malformed = [], 0
    for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            malformed += 1
            continue
        if not isinstance(row, dict):
            malformed += 1
            continue
        rows.append(row)

    identity_bad = any("identity_error" in r for r in rows)
    good = [r for r in rows if "gap" not in r and "identity_error" not in r]
    samples = []
    for r in rows:
        if "identity_error" in r:
            continue
        t_s = int(r.get("i", len(samples)) * interval_s)
        s = {"t_s": t_s, "t_utc": r.get("t_utc") if isinstance(r.get("t_utc"), str) and re.fullmatch(r"[0-9T:\-]+Z", r["t_utc"]) else None}
        for raw_key, pub in SERIES.items():
            s[pub] = None if "gap" in r else _num(r.get(raw_key))
        samples.append(s)

    def delta(key):
        v = [r[key] for r in good if isinstance(r.get(key), int)]
        return v[-1] - v[0] if len(v) >= 2 else None

    firmware = sorted({str(r.get("version")) for r in good if r.get("version")})
    bundle = {
        "schema": SCHEMA,
        "source": "MEASURED",
        "mode": "STOCK_FIRMWARE_READ_ONLY",
        "note": "Physical node timsminer, stock firmware, read-only polling. Not a research-firmware or ASIC-job measurement.",
        "device_label": "timsminer",
        "asic": "BM1366",
        "firmware": firmware,
        "running_partitions": sorted({str(r.get("runningPartition")) for r in good if r.get("runningPartition")}),
        "interval_s": interval_s,
        "verdict": "IDENTITY_MISMATCH" if identity_bad else ("NO_DATA" if not good else "OK"),
        "samples": samples,
        "summary": {
            "samples": len(good),
            "gaps": sum(1 for r in rows if "gap" in r),
            "malformed_lines": malformed,
            "reset_reasons": sorted({str(r.get("resetReason")) for r in good if r.get("resetReason")}),
            "hashrate_ghs": _stat([_num(r.get("hashRate")) for r in good]),
            "temperature_c": _stat([_num(r.get("temp")) for r in good]),
            "power_w": _stat([_num(r.get("power")) for r in good]),
            "free_heap_bytes": _stat([_num(r.get("freeHeap")) for r in good]),
            "min_free_heap_bytes": _stat([_num(r.get("minFreeHeap")) for r in good]),
            "shares_accepted_delta": delta("sharesAccepted"),
            "shares_rejected_delta": delta("sharesRejected"),
            "uptime_monotonic": all(
                b["uptimeSeconds"] >= a["uptimeSeconds"]
                for a, b in zip(good, good[1:])
                if isinstance(a.get("uptimeSeconds"), int) and isinstance(b.get("uptimeSeconds"), int)
            ),
        },
    }
    assert_public_safe(bundle)
    return bundle
