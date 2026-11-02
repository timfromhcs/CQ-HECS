"""Measure OMNIWAVE where its nogood store actually matters.

The general benchmark (`omniwave_benchmark.py --quick`) runs instances that finish in
milliseconds, which is the wrong instrument for a change to learnt-clause management:
a formula has to produce thousands of refuted antecedents before an unbounded nogood
list costs anything. This script therefore runs the families from
`AGENT_PLAN_OMNIWAVE.md` §3, sized so each instance takes seconds rather than
milliseconds, and prints the counters that the change is supposed to move.

    python scripts/omniwave_efficiency.py --out E:/qCSHA/sha_forge_results/omniwave_before
    # ... change the engine ...
    python scripts/omniwave_efficiency.py --out E:/qCSHA/sha_forge_results/omniwave_after

Every row reports the verdict, the wall time and the engine counters. A run is only
comparable if the verdict is identical, so the script prints a warning per row when the
verdict is UNKNOWN (nothing is being claimed about those), and it never sums times
across verdicts.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import Dict, List, Tuple

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cqhecs.omniwave import OmniwaveEngine, OmniwaveConfig  # noqa: E402
from cqhecs.sat import CNF  # noqa: E402


def pigeonhole(pigeons: int, holes: int) -> CNF:
    def var(p: int, h: int) -> int:
        return p * holes + h + 1

    clauses: List[Tuple[int, ...]] = [tuple(var(p, h) for h in range(holes)) for p in range(pigeons)]
    for h in range(holes):
        for p1 in range(pigeons):
            for p2 in range(p1 + 1, pigeons):
                clauses.append((-var(p1, h), -var(p2, h)))
    return CNF(num_vars=pigeons * holes, clauses=tuple(clauses), source=f"pigeonhole-{pigeons}-{holes}")


def tseitin_grid(rows: int, cols: int, seed: int = 7) -> CNF:
    """Parity constraints on the edges of a grid: UNSAT when the charges are odd."""
    state = seed

    def edge(a, b):
        nonlocal state
        if a > b:
            a, b = b, a
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return (a, b, state)

    variables: Dict[Tuple[int, int], int] = {}
    counter = 0
    for r in range(rows):
        for c in range(cols):
            for nbr in ((r + 1, c), (r, c + 1)):
                if nbr[0] < rows and nbr[1] < cols:
                    counter += 1
                    variables[(r, c, nbr[0], nbr[1])] = counter
    clauses: List[Tuple[int, ...]] = []
    for r in range(rows):
        for c in range(cols):
            incident = [var for key, var in variables.items() if (key[0], key[1]) == (r, c) or (key[2], key[3]) == (r, c)]
            if not incident:
                continue
            # Odd parity on every vertex: encode "an odd number of incident edges is true".
            # For 2 incident edges that is XOR; for 3 or 4 the full parity clauses below.
            for mask in range(1 << len(incident)):
                if bin(mask).count("1") % 2 == 0:  # forbid even parity
                    clause = tuple(-incident[i] if (mask >> i) & 1 else incident[i] for i in range(len(incident)))
                    clauses.append(clause)
    return CNF(num_vars=counter, clauses=tuple(clauses), source=f"tseitin-{rows}x{cols}")


def random_3sat(n: int, m: int, seed: int) -> CNF:
    state = seed

    def nxt() -> int:
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return state

    clauses = []
    for _ in range(m):
        picked = set()
        while len(picked) < 3:
            picked.add(nxt() % n + 1)
        signs = [1 if (nxt() >> 5) & 1 else -1 for _ in range(3)]
        clauses.append(tuple(sorted(lit * sign for lit, sign in zip(sorted(picked), signs))))
    return CNF(num_vars=n, clauses=tuple(clauses), source=f"random-{n}-{m}-{seed}")


def sha_instance(width: int, rounds: int) -> CNF:
    from cqhecs.sha import preimage_sat as ps

    block = bytes((i * 37 + 11) & 0xFF for i in range(64))
    return ps.build_partial_preimage_instance(block, rounds, [0], width=width).to_cnf()


def families() -> List[Tuple[str, CNF]]:
    return [
        ("pigeonhole", pigeonhole(8, 7)),
        ("pigeonhole", pigeonhole(9, 8)),
        ("parity", tseitin_grid(3, 3)),
        ("parity", tseitin_grid(4, 3)),
        ("random", random_3sat(70, 300, 20261102)),
        ("random", random_3sat(60, 260, 20261103)),
        ("sha", sha_instance(16, 8)),
    ]


def measure(formula: CNF, timeout: float, config: OmniwaveConfig, want_proof: bool) -> Dict[str, object]:
    engine = OmniwaveEngine(formula, config)
    started = time.perf_counter()
    result = engine.run()
    elapsed = time.perf_counter() - started
    snapshot = engine.snapshot()
    # The DRAT check is part of "did it actually prove anything", not an extra.
    # UNSAT is only returned when the engine covered the space *and* the DRAT check
    # accepted the proof, so the verdict itself carries the proof status; the note
    # says which one it was.
    proof_status = None
    if want_proof and result.status == "UNSAT":
        proof_status = "checked" if "DRAT" in (result.note or "") or "proof" in (result.note or "").lower() else "see note"
    return {
        "status": result.status,
        "seconds": round(elapsed, 3),
        "fronts": snapshot.get("fronts_created"),
        "processed": snapshot.get("fronts_processed"),
        "splits": snapshot.get("splits"),
        "conflicts": snapshot.get("conflicts"),
        "nogoods": snapshot.get("shared_nogoods"),
        "lemmas": snapshot.get("proof_lemmas"),
        "queue_peak": snapshot.get("queue"),
        "proof": proof_status,
        "note": (result.note or "")[:120],
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--waves", type=int, default=2)
    parser.add_argument("--max-nogoods", type=int, default=0, help="0 keeps the engine default")
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for family, formula in families():
        config = OmniwaveConfig(waves=args.waves, workers=1, timeout_seconds=args.timeout, check_proof=True)
        if args.max_nogoods:
            config = OmniwaveConfig(
                waves=args.waves, workers=1, timeout_seconds=args.timeout, check_proof=True, max_nogoods=args.max_nogoods
            )
        row = {"family": family, "source": formula.source, "vars": formula.num_vars, "clauses": len(formula.clauses)}
        try:
            row.update(measure(formula, args.timeout, config, want_proof=True))
        except Exception as exc:  # noqa: BLE001 - a broken engine must show up as a row, not a traceback
            row.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
        rows.append(row)
        print(
            f"{family:<12} {formula.source:<24} {row['status']:<8} {row.get('seconds', 0):>7.2f}s "
            f"fronts={row.get('fronts')} nogoods={row.get('nogoods')} lemmas={row.get('lemmas')} "
            f"proof={row.get('proof') or '-'}"
        )

    (out / "omniwave_efficiency.json").write_text(json.dumps({"config": vars(args), "rows": rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten: {out / 'omniwave_efficiency.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
