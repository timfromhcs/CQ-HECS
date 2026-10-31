#!/usr/bin/env python3
"""
Watched-literal vs clause-scan propagation benchmark.

Both engines use the same decision variable, polarity, pure-literal rule and
node budget. The only intended difference is the propagation data structure,
so this script can test H-SAT-01 without mixing in a second heuristic change.

    python scripts/sat_propagation_benchmark.py
    python scripts/sat_propagation_benchmark.py --quick
    python scripts/sat_propagation_benchmark.py --out research/v6/evidence/sat_propagation.json

The script exits non-zero if the engines disagree on a verdict, if a reported
model fails the original CNF, or if an UNSAT result lacks a checked
tree-resolution certificate in the verification pass.

Nothing here is an asymptotic claim. Timings are for this machine and this
Python build; medians over repeated runs are reported instead of a single
sample. The certificate path is intentionally excluded from the timed loop
(it is produced by a separate scan-based search) and checked separately.
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
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cqhecs import __version__  # noqa: E402
from cqhecs.sat import CNF, SAT, UNSAT, check_refutation, random_3sat, solve  # noqa: E402


def pigeonhole(holes: int) -> CNF:
    """``holes + 1`` pigeons into ``holes`` holes: always UNSAT."""
    pigeons = holes + 1

    def var(pigeon: int, hole: int) -> int:
        return pigeon * holes + hole + 1

    clauses: List[Tuple[int, ...]] = []
    for pigeon in range(pigeons):
        clauses.append(tuple(var(pigeon, hole) for hole in range(holes)))
    for hole in range(holes):
        for first in range(pigeons):
            for second in range(first + 1, pigeons):
                clauses.append((-var(first, hole), -var(second, hole)))
    return CNF(pigeons * holes, tuple(clauses), source=f"pigeonhole({pigeons},{holes})")


def planted_3sat(num_vars: int, num_clauses: int, seed: int) -> CNF:
    rng = random.Random(seed)
    hidden = {var: rng.random() < 0.5 for var in range(1, num_vars + 1)}
    clauses: List[Tuple[int, ...]] = []
    while len(clauses) < num_clauses:
        variables = rng.sample(range(1, num_vars + 1), 3)
        clause = tuple(var if rng.random() < 0.5 else -var for var in variables)
        if any((literal > 0) == hidden[abs(literal)] for literal in clause):
            clauses.append(clause)
    return CNF(num_vars, tuple(clauses), source=f"planted(n={num_vars},m={num_clauses},seed={seed})")


def tseitin_grid(rows: int, cols: int, seed: int) -> CNF:
    """Tseitin parity formula on a grid with odd total charge: always UNSAT."""
    rng = random.Random(seed)
    edges: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = {}
    incident: Dict[Tuple[int, int], List[int]] = {}

    def edge(first, second):
        key = (min(first, second), max(first, second))
        if key not in edges:
            edges[key] = len(edges) + 1
        return edges[key]

    for row in range(rows):
        for col in range(cols):
            for neighbour in ((row + 1, col), (row, col + 1)):
                if neighbour[0] >= rows or neighbour[1] >= cols:
                    continue
                number = edge((row, col), neighbour)
                incident.setdefault((row, col), []).append(number)
                incident.setdefault(neighbour, []).append(number)
    charge = {vertex: rng.random() < 0.5 for vertex in sorted(incident)}
    if sum(charge.values()) % 2 == 0:
        first = min(charge)
        charge[first] = not charge[first]

    def forbid(assignment: Tuple[int, ...], value: bool) -> Tuple[int, ...]:
        return tuple(-literal if value else literal for literal in assignment)

    clauses: List[Tuple[int, ...]] = []
    for vertex, edge_numbers in incident.items():
        alternatives = []
        for mask in range(1 << len(edge_numbers)):
            parity = bin(mask).count("1") % 2
            if (parity == 1) != charge[vertex]:
                alternatives.append(tuple(edge_numbers[i] if (mask >> i) & 1 else -edge_numbers[i] for i in range(len(edge_numbers))))
        for alternative in alternatives:
            clauses.append(forbid(alternative, True))
    return CNF(len(edges), tuple(clauses), source=f"tseitin({rows}x{cols},seed={seed})")


def families(quick: bool) -> List[Tuple[str, CNF, float]]:
    """``(family, formula, timeout)`` with fixed seeds; timeout generous on purpose."""
    if quick:
        return [
            ("random-3sat-40", random_3sat(40, 170, seed=2601), 10.0),
            ("planted-40", planted_3sat(40, 160, seed=2602), 10.0),
            ("pigeonhole-6-5", pigeonhole(5), 10.0),
            ("tseitin-4x4", tseitin_grid(4, 4, seed=2603), 10.0),
        ]
    return [
        ("random-3sat-70", random_3sat(70, 298, seed=2601), 30.0),
        ("random-3sat-90", random_3sat(90, 384, seed=2604), 30.0),
        ("planted-70", planted_3sat(70, 280, seed=2602), 30.0),
        ("pigeonhole-7-6", pigeonhole(6), 30.0),
        ("pigeonhole-8-7", pigeonhole(7), 30.0),
        ("tseitin-4x5", tseitin_grid(4, 5, seed=2603), 30.0),
    ]


def measure(formula: CNF, propagation: str, timeout: float, repeat: int) -> Dict[str, object]:
    samples: List[Dict[str, object]] = []
    for _ in range(repeat):
        started = time.perf_counter()
        result = solve(formula, timeout_seconds=timeout, certify=False, propagation=propagation)
        wall_ms = (time.perf_counter() - started) * 1000.0
        samples.append(
            {
                "status": result.status,
                "elapsed_ms": result.elapsed_ms,
                "wall_ms": wall_ms,
                "decisions": result.decisions,
                "propagations": result.propagations,
                "conflicts": result.conflicts,
                "nodes": result.nodes,
                "max_depth": result.max_depth,
                "note": result.note,
                "model_verified": result.model_verified,
                "assignment": result.assignment,
            }
        )
    times = sorted(float(sample["elapsed_ms"]) for sample in samples)
    walls = sorted(float(sample["wall_ms"]) for sample in samples)
    last = samples[-1]
    return {
        "status": last["status"],
        "model_verified": last["model_verified"],
        "assignment": last["assignment"],
        "decisions": last["decisions"],
        "propagations": last["propagations"],
        "conflicts": last["conflicts"],
        "nodes": last["nodes"],
        "max_depth": last["max_depth"],
        "note": last["note"],
        "elapsed_ms_median": statistics.median(times),
        "elapsed_ms_min": times[0],
        "elapsed_ms_p95": times[max(0, int(round(0.95 * (len(times) - 1))))],
        "wall_ms_median": statistics.median(walls),
        "samples": len(samples),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="CI-sized suite")
    parser.add_argument("--repeat", type=int, default=3, help="timed repetitions per engine")
    parser.add_argument("--out", default=None, help="write the JSON report here")
    parser.add_argument("--no-certify", action="store_true", help="skip the separate certificate check")
    args = parser.parse_args(argv)
    if args.repeat <= 0:
        parser.error("--repeat must be > 0")

    rows = []
    failures = []
    for family, formula, timeout in families(args.quick):
        scan = measure(formula, "scan", timeout, args.repeat)
        watched = measure(formula, "watched", timeout, args.repeat)
        if scan["status"] != watched["status"]:
            failures.append(f"{family}: status {scan['status']} != {watched['status']}")
        if watched["status"] == SAT and watched["assignment"] is not None:
            if not formula.is_satisfied(watched["assignment"]):
                failures.append(f"{family}: watched model fails the original CNF")
        if scan["status"] == SAT and scan["assignment"] is not None:
            if not formula.is_satisfied(scan["assignment"]):
                failures.append(f"{family}: scan model fails the original CNF")
        certificate = None
        if not args.no_certify and watched["status"] == UNSAT:
            certified = solve(formula, timeout_seconds=timeout, propagation="watched")
            if certified.status != UNSAT or not certified.certified or certified.certificate is None:
                failures.append(f"{family}: UNSAT without a checked certificate")
            elif not check_refutation(formula.clauses, certified.certificate):
                failures.append(f"{family}: certificate failed independent replay")
            else:
                certificate = {"checked": True, "steps": len(certified.certificate), "engine": certified.engine}
        ratio = None
        if watched["elapsed_ms_median"] > 0:
            ratio = scan["elapsed_ms_median"] / watched["elapsed_ms_median"]
        rows.append(
            {
                "family": family,
                "num_vars": formula.num_vars,
                "num_clauses": formula.num_clauses,
                "sha256": formula.sha256,
                "timeout_seconds": timeout,
                "scan": {key: value for key, value in scan.items() if key != "assignment"},
                "watched": {key: value for key, value in watched.items() if key != "assignment"},
                "scan_over_watched_speedup": ratio,
                "certificate": certificate,
            }
        )

    report = {
        "schema_version": "1.0",
        "project_version": __version__,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "method": (
            "same solver, decision order, polarity and pure-literal rule; "
            "propagation=scan vs propagation=watched; certify=False for timing; "
            "separate checked certificate pass for UNSAT"
        ),
        "rows": rows,
        "failures": failures,
        "non_claims": [
            "Finite measurements on one machine are not an asymptotic complexity claim.",
            "A speedup on one family is not a universal SAT performance claim.",
            "Tree-resolution certificates are checked by cqhecs.sat.check_refutation; that checker is independent of the search but not formally verified.",
        ],
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", "utf-8")
    else:
        print(text)
    if failures:
        print("FAILED: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
