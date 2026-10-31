#!/usr/bin/env python3
"""
OMNIWAVE benchmark: DPLL vs CaDiCaL vs OMNIWAVE (scalar / batch / vulkan) on
five instance families, plus the algebraic views (GF(2), tensor counting).

    python scripts/omniwave_benchmark.py                      # default suite
    python scripts/omniwave_benchmark.py --quick              # CI-sized
    python scripts/omniwave_benchmark.py --out research/v5/evidence/omniwave_benchmark.json

Every instance is generated from a fixed seed, so the JSON is reproducible up to
timing. The script fails (exit 1) if two engines that both decided an instance
disagree, or if any UNSAT lacks a checked certificate: the benchmark is also a
correctness gate.

Measured per engine: status, certification, wall time, work (DPLL nodes or
OMNIWAVE fronts), proof lemmas, time spent re-checking the proof, and peak
traced Python memory for the run (tracemalloc; it slows every engine alike and
does not see native memory). Nothing here is a speedup claim: OMNIWAVE worker
threads share the GIL, and the Vulkan path verifies each GPU pass on the CPU.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cqhecs import __version__  # noqa: E402
from cqhecs.drat import check_drat  # noqa: E402
from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine  # noqa: E402
from cqhecs.omniwave import gpu  # noqa: E402
from cqhecs.omniwave.field import ProblemField, TableTooLarge  # noqa: E402
from cqhecs.sat import CNF, count_models, load_dimacs, random_3sat, solve  # noqa: E402

# ------------------------------------------------------------------ families


def planted_3sat(n: int, m: int, seed: int) -> CNF:
    """Random 3-SAT that keeps only clauses satisfied by a hidden assignment (always SAT)."""
    rng = random.Random(seed)
    hidden = {v: rng.random() < 0.5 for v in range(1, n + 1)}
    clauses: List[Tuple[int, ...]] = []
    while len(clauses) < m:
        vs = rng.sample(range(1, n + 1), 3)
        clause = tuple(v if rng.random() < 0.5 else -v for v in vs)
        if any((lit > 0) == hidden[abs(lit)] for lit in clause):
            clauses.append(clause)
    return CNF(n, tuple(clauses), source=f"planted_3sat(n={n},m={m},seed={seed})")


def tseitin_torus(rows: int, cols: int, seed: int) -> CNF:
    """Tseitin parity formula on a rows x cols torus with odd total charge (always UNSAT)."""
    rng = random.Random(seed)
    edges: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = {}

    def edge(a, b):
        key = (min(a, b), max(a, b))
        if key not in edges:
            edges[key] = len(edges) + 1
        return edges[key]

    incident: Dict[Tuple[int, int], List[int]] = {}
    for r in range(rows):
        for c in range(cols):
            for nb in (((r + 1) % rows, c), (r, (c + 1) % cols)):
                e = edge((r, c), nb)
                incident.setdefault((r, c), []).append(e)
                incident.setdefault(nb, []).append(e)
    vertices = sorted(incident)
    charge = {v: rng.random() < 0.5 for v in vertices}
    if sum(charge.values()) % 2 == 0:  # make the total odd, hence UNSAT
        charge[vertices[0]] = not charge[vertices[0]]
    clauses = []
    for v in vertices:
        es = sorted(set(incident[v]))
        for mask in range(1 << len(es)):
            # Forbid every assignment of the incident edges whose parity differs from the charge.
            parity = bin(mask).count("1") % 2
            if parity != charge[v]:
                clauses.append(tuple(-e if mask >> i & 1 else e for i, e in enumerate(es)))
    return CNF(len(edges), tuple(clauses), source=f"tseitin_torus({rows}x{cols},seed={seed})")


def banded_3sat(n: int, m: int, width: int, seed: int) -> CNF:
    """Random 3-clauses inside a sliding window of `width` variables: pathwidth < width."""
    rng = random.Random(seed)
    clauses = []
    for _ in range(m):
        start = rng.randint(1, n - width + 1)
        vs = rng.sample(range(start, start + width), 3)
        clauses.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    return CNF(n, tuple(clauses), source=f"banded_3sat(n={n},m={m},w={width},seed={seed})")


def suite(quick: bool) -> List[Tuple[str, CNF]]:
    out: List[Tuple[str, CNF]] = []
    sizes = (20, 30) if quick else (20, 30, 40, 50)
    for n in sizes:
        for s in range(2 if quick else 3):
            out.append(("random", random_3sat(n, int(round(4.26 * n)), seed=1000 + 17 * n + s)))
    for n in ((40,) if quick else (40, 80, 120)):
        out.append(("planted", planted_3sat(n, int(round(4.26 * n)), seed=2000 + n)))
    for rows, cols in (((3, 3),) if quick else ((3, 3), (3, 4), (4, 4))):
        out.append(("parity", tseitin_torus(rows, cols, seed=3000 + rows * cols)))
    out.append(("pigeonhole", load_dimacs(ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf")))
    for n in ((40,) if quick else (40, 80)):
        out.append(("low-treewidth", banded_3sat(n, int(2.5 * n), 6, seed=4000 + n)))
    return out


# ------------------------------------------------------------------ engines


def measured(fn: Callable[[], Dict[str, object]]) -> Dict[str, object]:
    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        row = fn()
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    row["wall_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    row["peak_traced_kib"] = round(peak / 1024.0, 1)
    return row


def run_dpll(formula: CNF, timeout: float) -> Dict[str, object]:
    r = solve(formula, timeout_seconds=timeout)
    return {"status": r.status, "certification": r.certification, "work": r.nodes, "proof_lemmas": None,
            "note": r.note}


def run_cadical(formula: CNF, timeout: float) -> Dict[str, object]:
    from cqhecs.sat_external import solve_external

    r = solve_external(formula, timeout_seconds=timeout)
    return {"status": r.status, "certification": r.certification, "work": r.decisions, "proof_lemmas": None,
            "note": r.note}


def run_omniwave(formula: CNF, timeout: float, bcp: str, waves: int, workers: int) -> Dict[str, object]:
    engine = OmniwaveEngine(formula, OmniwaveConfig(
        waves=waves, workers=workers, timeout_seconds=timeout, bcp=bcp, max_fronts=5_000_000,
    ))
    r = engine.run()
    snap = engine.snapshot()
    row: Dict[str, object] = {
        "status": r.status, "certification": r.certification, "work": snap["fronts_processed"],
        "proof_lemmas": snap["proof_lemmas"], "shared_nogoods": snap["shared_nogoods"],
        "duplicates_skipped": snap["duplicates_skipped"], "coverage": snap["covered"], "note": r.note,
    }
    if r.status == "UNSAT":
        t0 = time.perf_counter()
        check = check_drat(formula.clauses, engine.proof(), timeout_seconds=120)
        row["proof_recheck_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        row["proof_recheck_valid"] = check.valid
    return row


def algebraic_views(family: str, formula: CNF, timeout: float) -> Dict[str, object]:
    view: Dict[str, object] = {}
    field = ProblemField(formula)
    if family == "parity":
        t0 = time.perf_counter()
        xor = field.xor_view()
        view["gf2_rows"] = len(xor.rows)
        view["gf2_solutions"] = xor.count_solutions() if len(xor.rows) else None
        view["gf2_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    if family == "low-treewidth":
        t0 = time.perf_counter()
        try:
            view["tensor_count"] = str(field.tensor_count(order=list(range(1, formula.num_vars + 1))))
        except TableTooLarge as exc:
            view["tensor_count"] = f"table too large: {exc}"
        view["tensor_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        t0 = time.perf_counter()
        counted = count_models(formula, timeout_seconds=timeout)
        view["sharpsat_count"] = counted.get("count")
        view["sharpsat_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    return view


# ------------------------------------------------------------------ ablation

ABLATION_CONFIGS = (
    ("1 wave, no sharing", dict(waves=1, workers=1, share_max_len=0)),
    ("1 wave, sharing <= 8", dict(waves=1, workers=1, share_max_len=8)),
    ("4 waves, no sharing", dict(waves=4, workers=1, share_max_len=0)),
    ("4 waves, sharing <= 8", dict(waves=4, workers=1, share_max_len=8)),
    ("4 waves, 2 workers, sharing <= 8", dict(waves=4, workers=2, share_max_len=8)),
)


def ablation(timeout: float) -> Dict[str, object]:
    """H1: do waves and nogood sharing reduce the fronts OMNIWAVE must process?
    H2: how far do exact separator signatures compress the left-side states?"""
    instances = [("pigeonhole", load_dimacs(ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf")),
                 ("parity", tseitin_torus(3, 3, seed=3009))]
    for n in (30, 40):
        for s in range(3):
            formula = random_3sat(n, int(round(4.26 * n)), seed=1000 + 17 * n + s)
            instances.append(("random", formula))
    h1 = []
    for family, formula in instances:
        row: Dict[str, object] = {"family": family, "source": formula.source, "configs": {}}
        for label, cfg in ABLATION_CONFIGS:
            engine = OmniwaveEngine(formula, OmniwaveConfig(timeout_seconds=timeout, max_fronts=5_000_000, **cfg))
            t0 = time.perf_counter()
            r = engine.run()
            snap = engine.snapshot()
            row["configs"][label] = {
                "status": r.status, "certification": r.certification,
                "fronts": snap["fronts_processed"], "shared_nogoods": snap["shared_nogoods"],
                "ms": round((time.perf_counter() - t0) * 1000.0, 1),
            }
        h1.append(row)
        print(f"ablation {formula.source}: " + "  ".join(
            f"[{k}] {v['status']}/{v['fronts']}" for k, v in row["configs"].items()), flush=True)
    from cqhecs.omniwave.boundary import compression_report, separator_count

    h2 = []
    for seed in range(5):
        formula = banded_3sat(24, 60, 5, seed=5000 + seed)
        left, sep = list(range(1, 13)), list(range(13, 18))
        report = compression_report(formula.num_vars, formula.clauses, left, sep)
        report["source"] = formula.source
        report["separator_count"] = str(separator_count(formula.num_vars, formula.clauses, left, sep))
        report["sharpsat_count"] = count_models(formula, timeout_seconds=timeout).get("count")
        h2.append(report)
        print(f"compression {formula.source}: {report['consistent_left_states']} states -> "
              f"{report['distinct_signatures']} signatures", flush=True)
    return {"h1_work_by_config": h1, "h2_signature_compression": h2}


# ------------------------------------------------------------------ main


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="small CI-sized suite")
    parser.add_argument("--timeout", type=float, default=20.0, help="per engine and instance, seconds")
    parser.add_argument("--waves", type=int, default=4)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--out", default=None, help="write the JSON report here")
    parser.add_argument("--ablation", action="store_true",
                        help="run only the H1/H2 ablation (waves, sharing, separator compression)")
    args = parser.parse_args(argv)

    if args.ablation:
        result = ablation(args.timeout)
        failures = []
        for row in result["h1_work_by_config"]:
            decided = {r["status"] for r in row["configs"].values() if r["status"] != "UNKNOWN"}
            if len(decided) > 1:
                failures.append(f"{row['source']}: configurations disagree")
        for rep in result["h2_signature_compression"]:
            if rep["sharpsat_count"] is not None and rep["sharpsat_count"] != rep["separator_count"]:
                failures.append(f"{rep['source']}: separator count != #SAT")
        result.update({"schema_version": "1.0", "cqhecs_version": __version__, "failures": failures,
                       "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2) + "\n", "utf-8")
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1 if failures else 0

    try:
        from cqhecs import sat_external

        cadical = sat_external.available()
    except ImportError:
        cadical = False
    gpu_status = gpu.status()
    engines: List[Tuple[str, Callable[[CNF], Dict[str, object]]]] = [
        ("dpll", lambda f: run_dpll(f, args.timeout)),
    ]
    if cadical:
        engines.append(("cadical", lambda f: run_cadical(f, args.timeout)))
    for bcp in ("scalar", "batch") + (("vulkan",) if gpu_status.get("available") else ()):
        engines.append((f"omniwave-{bcp}", lambda f, b=bcp: run_omniwave(f, args.timeout, b, args.waves, args.workers)))

    rows = []
    failures = []
    for family, formula in suite(args.quick):
        entry: Dict[str, object] = {
            "family": family, "source": formula.source, "num_vars": formula.num_vars,
            "num_clauses": formula.num_clauses, "sha256": formula.sha256, "engines": {},
        }
        for name, fn in engines:
            row = measured(lambda: fn(formula))
            entry["engines"][name] = row
            if row["status"] == "UNSAT" and row["certification"] not in ("TREE_RESOLUTION_CHECKED", "DRAT_CHECKED"):
                failures.append(f"{formula.source}: {name} UNSAT without a checked certificate")
            if row.get("proof_recheck_valid") is False:
                failures.append(f"{formula.source}: {name} proof failed the re-check")
        decided = {n: r["status"] for n, r in entry["engines"].items() if r["status"] in ("SAT", "UNSAT")}
        if len(set(decided.values())) > 1:
            failures.append(f"{formula.source}: engines disagree {decided}")
        if family == "planted" and "UNSAT" in decided.values():
            failures.append(f"{formula.source}: planted (satisfiable) instance reported UNSAT")
        if family in ("parity", "pigeonhole") and "SAT" in decided.values():
            failures.append(f"{formula.source}: unsatisfiable instance reported SAT")
        entry["algebraic"] = algebraic_views(family, formula, args.timeout)
        alg = entry["algebraic"]
        if "sharpsat_count" in alg and alg["sharpsat_count"] is not None and not str(alg["tensor_count"]).startswith("table"):
            if alg["sharpsat_count"] != alg["tensor_count"]:
                failures.append(f"{formula.source}: tensor count {alg['tensor_count']} != #SAT {alg['sharpsat_count']}")
        if family == "parity" and alg.get("gf2_solutions") not in (None, 0):
            failures.append(f"{formula.source}: GF(2) view finds solutions of an odd-charge Tseitin formula")
        rows.append(entry)
        short = {"SAT": "S", "UNSAT": "U", "UNKNOWN": "?"}
        summary = "  ".join(f"{n}={short[r['status']]}/{r['wall_ms']:.0f}ms" for n, r in entry["engines"].items())
        print(f"{family:14s} {formula.num_vars:4d}v {formula.num_clauses:5d}c  {summary}", flush=True)

    report = {
        "schema_version": "1.0",
        "cqhecs_version": __version__,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": {"platform": platform.platform(), "python": platform.python_version(),
                    "processor": platform.processor()},
        "settings": {"quick": args.quick, "timeout_seconds": args.timeout, "waves": args.waves,
                     "workers": args.workers},
        "backends": {"cadical": cadical, "gpu": gpu_status},
        "instances": rows,
        "failures": failures,
        "non_claims": [
            "Timings are one run on one machine; they are not a speedup claim.",
            "OMNIWAVE worker threads share the Python GIL.",
            "The Vulkan path checks every GPU pass against the CPU reference, so it measures "
            "correctness of the kernel, not GPU acceleration.",
            "No complexity statement (P vs NP, ETH) follows from these numbers.",
        ],
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
        print(f"wrote {out}")
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
