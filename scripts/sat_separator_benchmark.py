#!/usr/bin/env python3
"""
Benchmark exact #SAT backends: DPLL counting vs variable elimination (H4-SAT-01).

Families, sizes and seeds are fixed below. Every row records both backends'
counts and flags a mismatch; the script exits non-zero if any pair of COUNTED
results disagrees. Timeouts and UNKNOWN results are reported, not dropped.

    python scripts/sat_separator_benchmark.py --out research/v7/evidence/sat_separator_bench.json
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cqhecs.sat import CNF, count_models, random_3sat  # noqa: E402

Clauses = Tuple[Tuple[int, ...], ...]


def chain(n: int) -> CNF:
    return CNF(n, tuple((i, i + 1) for i in range(1, n)), source=f"chain:{n}")


def grid_xorish(rows: int, cols: int) -> CNF:
    """rows x cols grid; each edge forbids both endpoints being true."""
    def var(r: int, c: int) -> int:
        return r * cols + c + 1

    clauses: List[Tuple[int, ...]] = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                clauses.append((-var(r, c), -var(r, c + 1)))
            if r + 1 < rows:
                clauses.append((-var(r, c), -var(r + 1, c)))
    return CNF(rows * cols, tuple(clauses), source=f"grid:{rows}x{cols}")


def banded(n: int, window: int, ratio: float, seed: int) -> CNF:
    """Random 3-clauses whose variables lie in a sliding window (bounded width)."""
    rng = random.Random(seed)
    clauses: List[Tuple[int, ...]] = []
    for _ in range(int(ratio * n)):
        start = rng.randint(1, max(1, n - window + 1))
        vs = rng.sample(range(start, min(n, start + window - 1) + 1), 3)
        clauses.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    return CNF(n, tuple(clauses), source=f"banded:n={n}:w={window}:r={ratio}:seed={seed}")


FAMILIES: Dict[str, Callable[[], CNF]] = {
    "chain-200": lambda: chain(200),
    "chain-2000": lambda: chain(2000),
    "grid-3x25": lambda: grid_xorish(3, 25),
    "grid-4x20": lambda: grid_xorish(4, 20),
    "grid-5x12": lambda: grid_xorish(5, 12),
    "banded-n80-w8": lambda: banded(80, 8, 2.0, seed=11),
    "banded-n120-w10": lambda: banded(120, 10, 2.0, seed=12),
    "banded-n60-w14": lambda: banded(60, 14, 2.5, seed=13),
    "random3sat-n24-r4.26": lambda: random_3sat(24, 102, seed=21),
    "random3sat-n32-r3.0": lambda: random_3sat(32, 96, seed=22),
    "random3sat-n40-r4.26": lambda: random_3sat(40, 170, seed=23),
}


def timed(formula: CNF, method: str, timeout: float, repeat: int) -> Dict[str, object]:
    walls: List[float] = []
    last: Dict[str, object] = {}
    for _ in range(repeat):
        start = time.perf_counter()
        last = count_models(formula, timeout_seconds=timeout, method=method)
        walls.append((time.perf_counter() - start) * 1000.0)
    return {
        "status": last["status"],
        "count": last["count"],
        "backend": last.get("backend"),
        "induced_width": last.get("induced_width"),
        "max_table": last.get("max_table"),
        "median_ms": statistics.median(walls),
        "min_ms": min(walls),
        "max_ms": max(walls),
        "repeats": repeat,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    rows = []
    mismatches = 0
    for name, build in FAMILIES.items():
        formula = build()
        row: Dict[str, object] = {
            "family": name,
            "num_vars": formula.num_vars,
            "num_clauses": formula.num_clauses,
            "formula_sha256": formula.sha256,
        }
        for method in ("dpll", "separator", "auto"):
            row[method] = timed(formula, method, args.timeout, args.repeat)
        counted = {
            m: row[m]["count"] for m in ("dpll", "separator", "auto")
            if row[m]["status"] == "COUNTED"
        }
        row["counts_agree"] = len(set(counted.values())) <= 1
        if not row["counts_agree"]:
            mismatches += 1
        rows.append(row)
        print(
            f"{name:24s} n={formula.num_vars:5d} m={formula.num_clauses:5d} "
            + "  ".join(
                f"{m}={row[m]['status'][0]}:{row[m]['median_ms']:9.1f}ms"
                for m in ("dpll", "separator", "auto")
            )
            + f"  width={row['separator']['induced_width']}"
            + ("" if row["counts_agree"] else "  *** MISMATCH ***")
        )

    report = {
        "benchmark": "sat_separator",
        "hypothesis": "H4-SAT-01",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "repeat": args.repeat,
        "timeout_seconds": args.timeout,
        "mismatches": mismatches,
        "rows": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
