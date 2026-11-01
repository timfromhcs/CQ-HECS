"""Read-only baseline capture for the allowlisted miner (HCS SHA Forge, AGENTBUILD 10.5).

Polls only GET /api/system/info of ONE exact host, verifies the identity against a local profile on every
sample and stops at the first mismatch. Writes non-secret telemetry fields as JSON lines outside the repo.
It never writes to the device and never stores pool users, wallet data, SSID or addresses.

    python scripts/sha_forge_baseline.py --host <exact-host> --profile <profile.json> --out <dir> [--minutes 60]
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from cqhecs.hardware import miner_capabilities as caps
from cqhecs.hardware.bridge import HttpDeviceClient

FIELDS = (
    "version", "runningPartition", "ASICModel", "boardVersion", "frequency", "actualFrequency", "coreVoltage",
    "coreVoltageActual", "hashRate", "hashRate_1m", "hashRate_10m", "hashRate_1h", "expectedHashrate",
    "errorPercentage", "sharesAccepted", "sharesRejected", "sharesRejectedStale", "notifyDropped",
    "temp", "temp2", "vrTemp", "fanspeed", "fanrpm", "power", "voltage", "current", "wifiRSSI", "wifiStatus",
    "freeHeap", "freeHeapInternal", "freeHeapSpiram", "minFreeHeap", "uptimeSeconds", "resetReason",
    "isUsingFallbackStratum", "miningPaused", "overheat_mode",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=30.0)
    args = ap.parse_args()

    profile = caps.DeviceProfile.load(args.profile)
    client = HttpDeviceClient(args.host, timeout=8.0)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"baseline_{stamp}.jsonl"
    total = int(args.minutes * 60 / args.interval) + 1
    rows, gaps = [], 0
    with path.open("w", encoding="utf-8") as fh:
        for i in range(total):
            t0 = time.monotonic()
            row = {"i": i, "t_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            try:
                info = client.get_info()
            except Exception as e:  # a missing sample stays a gap, never interpolated
                row["gap"] = type(e).__name__
                gaps += 1
            else:
                ident = caps.check_identity(info, profile)
                if not ident.ok:
                    row["identity_error"] = ident.reason
                    fh.write(json.dumps(row) + "\n")
                    print("IDENTITY MISMATCH, stopping:", ident.reason)
                    return 2
                row.update({k: info.get(k) for k in FIELDS})
                rows.append(row)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            time.sleep(max(0.0, args.interval - (time.monotonic() - t0)))

    def stat(key):
        v = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return {"n": len(v), "min": min(v), "max": max(v), "mean": round(statistics.fmean(v), 3)} if v else None

    summary = {
        "file": path.name, "samples": len(rows), "gaps": gaps, "interval_s": args.interval,
        "versions": sorted({str(r.get("version")) for r in rows}),
        "partitions": sorted({str(r.get("runningPartition")) for r in rows}),
        "reset_reasons": sorted({str(r.get("resetReason")) for r in rows}),
        "uptime_monotonic": all(b["uptimeSeconds"] >= a["uptimeSeconds"] for a, b in zip(rows, rows[1:])
                                if isinstance(a.get("uptimeSeconds"), int) and isinstance(b.get("uptimeSeconds"), int)),
        "hashRate": stat("hashRate"), "temp": stat("temp"), "vrTemp": stat("vrTemp"), "power": stat("power"),
        "wifiRSSI": stat("wifiRSSI"), "freeHeap": stat("freeHeap"), "minFreeHeap": stat("minFreeHeap"),
        "shares_accepted_delta": (rows[-1]["sharesAccepted"] - rows[0]["sharesAccepted"]) if rows else None,
        "shares_rejected_delta": (rows[-1]["sharesRejected"] - rows[0]["sharesRejected"]) if rows else None,
    }
    (out / f"baseline_{stamp}.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
