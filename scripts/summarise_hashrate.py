"""Summarise a hashrate capture and compare it with the recorded stock baseline.

Read-only: it reads a JSONL capture that `sha_forge_baseline.py` produced and
prints the numbers. It changes nothing on the device and nothing in a repository.

    python scripts/summarise_hashrate.py <capture.jsonl> [...]

The comparison baseline is the stock-firmware capture from 2026-11-01 (121
samples, 60 minutes): mean 325 GH/s, stdev 32, range 240-425, expected ~434 at
485 MHz / 1100 mV. Those numbers are quoted, not recomputed here - the raw stock
capture lives in a separate results folder.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

STOCK = {"samples": 121, "mean_ghs": 325.0, "stdev_ghs": 32.0, "min_ghs": 240.0, "max_ghs": 425.0}


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn last line from an interrupted capture is not a sample
    return rows


def summarise(path: Path) -> dict:
    rows = load(path)
    rates = [float(r["hashRate"]) for r in rows if isinstance(r.get("hashRate"), (int, float))]
    temps = [float(r["temp"]) for r in rows if isinstance(r.get("temp"), (int, float)) and r["temp"] > 0]
    freqs = {r.get("frequency") for r in rows}
    volts = {r.get("coreVoltage") for r in rows}
    rejected = rows[-1].get("sharesRejected") if rows else None
    accepted = rows[-1].get("sharesAccepted") if rows else None
    expected = rows[-1].get("expectedHashrate") if rows else None
    return {
        "file": path.name,
        "samples": len(rows),
        "version": rows[0].get("version") if rows else None,
        "window_s": None,
        "mean_ghs": round(statistics.fmean(rates), 1) if rates else None,
        "stdev_ghs": round(statistics.pstdev(rates), 1) if len(rates) > 1 else None,
        "min_ghs": round(min(rates), 1) if rates else None,
        "max_ghs": round(max(rates), 1) if rates else None,
        "mean_temp_c": round(statistics.fmean(temps), 1) if temps else None,
        "max_temp_c": round(max(temps), 1) if temps else None,
        "frequencies_mhz": sorted(f for f in freqs if f is not None),
        "core_voltages_mv": sorted(v for v in volts if v is not None),
        "expected_ghs": expected,
        "shares_accepted": accepted,
        "shares_rejected": rejected,
        "first_utc": rows[0].get("t_utc") if rows else None,
        "last_utc": rows[-1].get("t_utc") if rows else None,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for arg in argv[1:]:
        path = Path(arg)
        if not path.is_file():
            print(f"missing capture: {path}")
            continue
        s = summarise(path)
        print(json.dumps(s, indent=2, sort_keys=True))
        if s["mean_ghs"] is not None:
            print(
                f"  vs stock baseline: mean {s['mean_ghs']} vs {STOCK['mean_ghs']} "
                f"({s['mean_ghs'] - STOCK['mean_ghs']:+.1f} GH/s), "
                f"stdev {s['stdev_ghs']} vs {STOCK['stdev_ghs']}, "
                f"range {s['min_ghs']}-{s['max_ghs']} vs {STOCK['min_ghs']}-{STOCK['max_ghs']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
