"""Measure the unified solver against its individual engines.

One row per instance, one column per engine, plus the portfolio. The point is not to
show the portfolio is fastest - it usually is not, because it pays for the attempts it
does not need - but to show three things that a table can show and prose cannot:

1. every engine that decides an instance agrees on the verdict,
2. the portfolio's overhead is bounded and visible (attempt count, total time),
3. the optional backend is reported as unavailable instead of being skipped.

    python scripts/unified_solver_benchmark.py --out E:/qCSHA/sha_forge_results/unified
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import Dict, List

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cqhecs import sat, sat_external, unified  # noqa: E402
from omniwave_efficiency import pigeonhole, random_3sat, sha_instance, tseitin_grid  # noqa: E402

ENGINES = ("watched", "omniwave", "cadical", "scan")


def families() -> List[tuple]:
    return [
        ("pigeonhole-7-6", pigeonhole(7, 6)),
        ("pigeonhole-8-7", pigeonhole(8, 7)),
        ("tseitin-3x3", tseitin_grid(3, 3)),
        ("random-70-300", random_3sat(70, 300, 20261102)),
        ("sha-W16-r8", sha_instance(16, 8)),
    ]


def run_engine(engine: str, formula, budget: float) -> Dict[str, object]:
    started = time.perf_counter()
    try:
        if engine == "omniwave":
            from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine

            result = OmniwaveEngine(formula, OmniwaveConfig(waves=1, workers=1, timeout_seconds=budget)).run()
        elif engine == "cadical":
            if not sat_external.available():
                return {"status": "unavailable", "seconds": 0.0}
            result = sat_external.solve_external(formula, timeout_seconds=budget, check_proof=True)
        elif engine == "watched":
            result = sat.solve(formula, timeout_seconds=budget, certify=False, propagation="watched")
        else:
            result = sat.solve(formula, timeout_seconds=budget, certify=True)
        return {"status": result.status, "seconds": round(time.perf_counter() - started, 3)}
    except Exception as exc:  # noqa: BLE001 - a broken engine is a row, not a crash
        return {"status": "error", "seconds": round(time.perf_counter() - started, 3), "error": f"{type(exc).__name__}: {exc}"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=15.0, help="budget per engine and instance")
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    disagreements = 0

    print(f"{'instance':<16}{'vars':>6} " + "".join(f"{name:>12}" for name in ENGINES) + f"{'unified':>16}")
    for name, formula in families():
        row: Dict[str, object] = {"instance": name, "vars": formula.num_vars, "clauses": len(formula.clauses), "engines": {}}
        verdicts = {}
        for engine in ENGINES:
            outcome = run_engine(engine, formula, args.timeout)
            row["engines"][engine] = outcome
            if outcome["status"] in (sat.SAT, sat.UNSAT):
                verdicts[engine] = outcome["status"]
        started = time.perf_counter()
        document = unified.solve_unified(formula, timeout_seconds=args.timeout)
        unified_seconds = round(time.perf_counter() - started, 3)
        row["unified"] = {
            "status": document.status,
            "engine": document.engine,
            "seconds": unified_seconds,
            "attempts": [attempt.to_dict() for attempt in document.attempts],
        }
        distinct = set(verdicts.values())
        if len(distinct) > 1:
            disagreements += 1
        rows.append(row)
        cells = "".join(
            f"{str(row['engines'][engine]['status'])[:4]:>8}{row['engines'][engine]['seconds']:>4.1f}"
            for engine in ENGINES
        )
        print(f"{name:<16}{formula.num_vars:>6} {cells}   {document.status:>6}/{str(document.engine or '-'):<9} {unified_seconds:>5.2f}s")

    summary = {
        "engines": list(ENGINES),
        "cadical_available": sat_external.available(),
        "instances": len(rows),
        "disagreements": disagreements,
        "rows": rows,
    }
    (out / "unified_benchmark.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\ndisagreements between engines: {disagreements}")
    print(f"written: {out / 'unified_benchmark.json'}")
    return 0 if disagreements == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
