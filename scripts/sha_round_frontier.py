"""Measure the reduced-round SHA frontier: how far a preimage search actually gets.

This produces the table that `research/sha_forge/SAT_SHA.md` quotes, so the numbers
in the document can be regenerated instead of remembered. It is a measurement, not a
benchmark protocol: one machine, one repetition per cell, stated budget.

    python scripts/sha_round_frontier.py --out E:/qCSHA/sha_forge_results/frontier

Cells:

* **preimage, toy width** - `W = 8` and `W = 16`, one free message word, the output
  state asserted to the reference value of the block. This is a real search: the
  free word is unknown to the solver. A toy width is not SHA-256; it exists so the
  answer can also be found by exhaustive enumeration.
* **preimage, full width** - `W = 32`, one free word, rounds where the system is
  still over-determined. Above that the instance is not decidable in the budget and
  the cell says UNRESOLVED, which is a result.
* **verification, full width** - `W = 32`, all 1024 message bits fixed, 64 rounds.
  Cheap by construction; included as the control.

Every UNKNOWN is recorded with the budget it was given, so "it did not finish" is
never written as "it is hard".
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cqhecs import sat  # noqa: E402
from cqhecs.sha import preimage_sat as ps  # noqa: E402

BLOCK = bytes((i * 37 + 11) & 0xFF for i in range(64))


def solve_cell(instance, timeout: float, propagation: str = "watched") -> dict:
    cnf = instance.to_cnf()
    started = time.perf_counter()
    # Watched-literal propagation is the default here because it was measured to be
    # 8.7x - 16.1x faster than the scan engine on exactly these instances, with
    # identical verdicts (SAT_SHA.md section 9). The flag stays so the comparison can
    # be repeated.
    result = sat.solve(cnf, timeout_seconds=timeout, certify=False, propagation=propagation)
    elapsed = time.perf_counter() - started
    return {
        "status": result.status,
        "seconds": round(elapsed, 2),
        "node_budget_note": (result.note or "")[:120],
        "vars": instance.num_vars,
        "clauses": instance.num_clauses,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per cell")
    parser.add_argument("--max-rounds-toy", type=int, default=24)
    parser.add_argument("--max-rounds-full", type=int, default=16)
    parser.add_argument("--propagation", default="watched", choices=("scan", "watched"))
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"block": BLOCK.hex(), "timeout_s": args.timeout, "propagation": args.propagation, "cells": []}

    for width in (8, 16):
        for rounds in range(2, args.max_rounds_toy + 1, 2):
            instance = ps.build_partial_preimage_instance(BLOCK, rounds, [0], width=width)
            cell = {"kind": "preimage", "width": width, "rounds": rounds, "free_words": [0]}
            cell.update(solve_cell(instance, args.timeout, args.propagation))
            report["cells"].append(cell)
            print(f"W={width:<2} preimage r={rounds:<2} {cell['status']:<8} {cell['seconds']:>6.2f}s  "
                  f"({cell['vars']} vars / {cell['clauses']} clauses)")

    for rounds in range(1, args.max_rounds_full + 1):
        instance = ps.build_partial_preimage_instance(BLOCK, rounds, [0])
        cell = {"kind": "preimage", "width": 32, "rounds": rounds, "free_words": [0]}
        cell.update(solve_cell(instance, args.timeout))
        report["cells"].append(cell)
        print(f"W=32 preimage r={rounds:<2} {cell['status']:<8} {cell['seconds']:>6.2f}s")

    instance = ps.build_verification_instance(BLOCK, 64)
    cell = {"kind": "verification", "width": 32, "rounds": 64, "free_words": []}
    cell.update(solve_cell(instance, args.timeout))
    report["cells"].append(cell)
    print(f"W=32 verify   r=64 {cell['status']:<8} {cell['seconds']:>6.2f}s")

    (out / "frontier.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten: {out / 'frontier.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
