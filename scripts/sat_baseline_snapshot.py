#!/usr/bin/env python3
"""
Frozen SAT timing snapshot (W3-08).

Records, per engine and per fixed-seed formula, the verdict, the proof label and the
wall time of the SAT stack *as it is at the checkout it runs on*. Run it before a SAT
change to freeze the "pre" numbers and again afterwards to compare.

    python scripts/sat_baseline_snapshot.py
    python scripts/sat_baseline_snapshot.py --out research/v7/evidence/SAT_BASELINE_pre_R0.json
    python scripts/sat_baseline_snapshot.py --with-tests

Honesty rules:

* Engines are called through ``cqhecs.unified._attempt`` so the snapshot sees what the
  portfolio sees. An engine that is not installed is recorded ``NOT_RUN`` with a
  reason, never as a pass or as a zero time.
* Timings are for this machine and this Python build. Nothing here is an asymptotic
  or a competitive claim.
* The snapshot keeps raw per-repeat timings, the median, the git SHA and whether the
  worktree was dirty, so a later run can be compared without re-deriving anything.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from cqhecs import __version__  # noqa: E402
from cqhecs import unified  # noqa: E402
from cqhecs.sat import random_3sat  # noqa: E402
from sat_propagation_benchmark import pigeonhole, planted_3sat, tseitin_grid  # noqa: E402

SCHEMA = "hcs.sat.baseline_snapshot.v1"
DEFAULT_OUT = ROOT / "research" / "v7" / "evidence" / "SAT_BASELINE_pre_R0.json"
ENGINES = ("watched", "omniwave", "cadical", "scan")
FOCUSED_TESTS = (
    "tests/test_unified_solver.py",
    "tests/test_drat.py",
    "tests/test_sat_external.py",
)


def suite():
    """Fixed seeds; small enough to finish in seconds on every engine."""
    return [
        ("random-3sat-30-sat-side", random_3sat(30, 100, seed=2601), 20.0),
        ("planted-30", planted_3sat(30, 110, seed=2602), 20.0),
        ("pigeonhole-5-4", pigeonhole(4), 20.0),
        ("pigeonhole-6-5", pigeonhole(5), 30.0),
        ("tseitin-3x3", tseitin_grid(3, 3, seed=2603), 20.0),
    ]


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {type(exc).__name__}"


def measure_engine(engine: str, formula, timeout: float, repeat: int) -> Dict[str, Any]:
    if engine == "cadical":
        from cqhecs import sat_external

        if not sat_external.available():
            return {"engine": engine, "state": "NOT_RUN", "reason": "python-sat is not installed"}
    runs: List[Dict[str, Any]] = []
    for _ in range(repeat):
        started = time.perf_counter()
        attempt, _result = unified._attempt(engine, formula, timeout)
        wall = time.perf_counter() - started
        runs.append({"status": attempt.status, "proof": attempt.proof, "wall_seconds": round(wall, 6), "reason": attempt.reason})
    walls = [run["wall_seconds"] for run in runs]
    return {
        "engine": engine,
        "state": "RUN",
        "statuses": sorted({run["status"] for run in runs}),
        "proof_labels": sorted({str(run["proof"]) for run in runs}),
        "median_wall_seconds": round(statistics.median(walls), 6),
        "min_wall_seconds": min(walls),
        "max_wall_seconds": max(walls),
        "runs": runs,
    }


def focused_test_counts() -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pytest", *FOCUSED_TESTS, "-q", "-rs", "-p", "no:cacheprovider"]
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()][-1:]
    return {
        "command": " ".join(cmd[1:]),
        "returncode": proc.returncode,
        "summary": tail[0] if tail else "",
        "wall_seconds": round(time.perf_counter() - started, 2),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON report path")
    parser.add_argument("--repeat", type=int, default=3, help="timed repetitions per engine")
    parser.add_argument("--with-tests", action="store_true", help="also record the focused SAT test counts")
    args = parser.parse_args(argv)

    report: Dict[str, Any] = {
        "schema": SCHEMA,
        "cqhecs_version": __version__,
        "git_sha": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "worktree_dirty_files": [line for line in _git("status", "--short").splitlines() if line],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "repeat": args.repeat,
        "engines_requested": list(ENGINES),
        "note": "Pre-change timing baseline. Timings are for this machine only; no asymptotic or competitive claim.",
        "formulas": [],
    }
    for name, formula, timeout in suite():
        entry: Dict[str, Any] = {
            "name": name,
            "num_vars": formula.num_vars,
            "num_clauses": len(formula.clauses),
            "sha256": formula.sha256,
            "timeout_seconds": timeout,
            "engines": [measure_engine(engine, formula, timeout, args.repeat) for engine in ENGINES],
        }
        report["formulas"].append(entry)
        print(f"{name}: " + ", ".join(
            f"{e['engine']}={e['median_wall_seconds']:.3f}s/{'|'.join(e['statuses'])}" if e["state"] == "RUN" else f"{e['engine']}=NOT_RUN"
            for e in entry["engines"]
        ))
    if args.with_tests:
        report["focused_tests"] = focused_test_counts()
        print("focused tests:", report["focused_tests"]["summary"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
