#!/usr/bin/env python3
"""
Collect and evaluate the r-qpu-pilot-1 IonQ run.

This is **not** the preregistered ``r-io-7`` suite. It is a five-job, 100-shot
pilot that spends the account's remaining 25 Spark credits (5 per job) to ask
one question: does the ``OQ-02`` qubit-0 anomaly reproduce on a different
vendor?

100 shots gives a binomial 95 % interval of roughly ±0.10 at p = 0.5, so the
pilot can separate "about half" from "about seven percent", and little else.
It cannot evaluate H-V3-8 and must not be used to fit or confirm a full noise
model.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "research/v4/evidence/openquantum_pilot/ionq_forte-1"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _job_id(folder: Path) -> Optional[str]:
    path = folder / "job.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text("utf-8"))
    return (payload.get("job") or {}).get("id") or payload.get("job_id")


def _counts(path: Path) -> Optional[Dict[str, int]]:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text("utf-8"))
    return {str(k).replace(" ", ""): int(v) for k, v in payload.items()} if payload else None


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _sanitize_job_json(path: Path) -> None:
    """Drop signed download URLs before evidence is committed."""
    if not path.is_file():
        return
    payload = json.loads(path.read_text("utf-8"))
    job = payload.get("job")
    if isinstance(job, dict):
        for key in ("input_data_url", "output_data_url", "calibration_data_url"):
            if job.get(key):
                job[key] = None
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--oq", default=str(ROOT / "oq.py"))
    parser.add_argument("--collect", action="store_true", help="Download completed jobs")
    args = parser.parse_args(argv)

    base = Path(args.dir)
    rows: list[Dict[str, Any]] = []
    for folder in sorted(path for path in base.glob("OQ-*") if path.is_dir()):
        job_id = _job_id(folder)
        if not job_id:
            continue
        status = None
        if args.collect:
            probe = _run([sys.executable, args.oq, "status", job_id, "--json"])
            if probe.returncode == 0:
                status = json.loads(probe.stdout).get("status")
            if status == "Completed":
                result = _run(
                    [sys.executable, args.oq, "results", job_id, "--out", str(folder), "--json"]
                )
                if result.returncode != 0:
                    print(f"{folder.name}: download failed: {result.stderr[:300]}", file=sys.stderr)
        job_path = folder / "job.json"
        payload = json.loads(job_path.read_text("utf-8")) if job_path.is_file() else {}
        counts = _counts(folder / "result.json")
        _sanitize_job_json(folder / "job.json")
        rows.append(
            {
                "job_id": folder.name,
                "provider_job_id": job_id,
                "status": status or (payload.get("job") or {}).get("status") or payload.get("status"),
                "shots": sum(counts.values()) if counts else None,
                "counts": counts,
            }
        )

    by_id = {row["job_id"]: row for row in rows}

    def p1(job: str, qubit: int = 0) -> Optional[Dict[str, Any]]:
        row = by_id.get(job)
        if not row or not row["counts"]:
            return None
        counts = row["counts"]
        n = len(next(iter(counts)))
        total = sum(counts.values())
        ones = sum(value for state, value in counts.items() if state[n - 1 - qubit] == "1")
        low, high = wilson(ones, total)
        return {"ones": ones, "shots": total, "p": ones / total, "ci95": [low, high]}

    anomaly: Dict[str, Any] = {
        "oq01_p1_q0": p1("OQ-01"),
        "oq02_p1_q0": p1("OQ-02"),
        "oq03_p1_q0": p1("OQ-03"),
        "oq09_p1_q0": p1("OQ-09"),
        "oq04_p1_q0": p1("OQ-04"),
    }
    verdict = "INCOMPLETE"
    oq03 = anomaly["oq03_p1_q0"]
    oq09 = anomaly["oq09_p1_q0"]
    oq01 = anomaly["oq01_p1_q0"]
    if oq03 and oq09 and oq01:
        low, high = oq03["ci95"]
        if low > 0.30 and oq09["ci95"][0] > 0.30:
            verdict = "ANOMALY_REPRODUCED"
        elif high < 0.20 and oq01["ci95"][1] < 0.20:
            verdict = "ANOMALY_NOT_REPRODUCED"
        else:
            verdict = "INCONCLUSIVE"

    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-qpu-pilot-1",
        "backend": "ionq:forte-1",
        "shots_per_job": 100,
        "credits_spent": 25,
        "jobs": rows,
        "qubit0": anomaly,
        "verdict": verdict,
        "interpretation": (
            "A 5-job, 100-shot pilot. It can distinguish a ~50 % X-gate flip from a "
            "~7 % readout error on qubit 0, and nothing finer. It does not test "
            "H-V3-8 and is not a confirmation of any full noise model."
        ),
    }
    (base / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps({k: summary[k] for k in ("dataset_id", "verdict", "qubit0")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
