"""W4-08: measure predicted vs observed separator table sizes (deterministic).

Usage: python scripts/sat_separator_calibration.py [--out FILE]
Writes raw JSON rows: family, n, induced_width, predicted_table_bound, observed max_table.
Observed peak must never exceed the predicted bound; the script exits 1 if it does.
"""
from __future__ import annotations

import argparse
import json
import sys

from cqhecs import sat_separator as sep
from cqhecs.sat import AUTO_SEPARATOR_MAX_WIDTH, random_3sat


def families():
    for n in (8, 12, 16, 20):
        yield "chain", n, [(i, i + 1) for i in range(1, n)]
    for n in (8, 10, 12):
        yield "clique2", n, [(i, j) for i in range(1, n + 1) for j in range(i + 1, n + 1)]
    for seed in range(8):
        for n, ratio in ((12, 2.0), (16, 3.0), (20, 4.0)):
            yield f"random3sat_s{seed}_r{ratio}", n, random_3sat(n, int(n * ratio), seed=seed).clauses


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    rows, bad = [], 0
    for name, n, clauses in families():
        got = sep.count_by_elimination(n, clauses, max_table_entries=10**8)
        row = {"family": name, "n": n, "status": got["status"],
               "induced_width": got.get("induced_width"),
               "predicted_table_bound": got.get("predicted_table_bound"),
               "observed_max_table": got.get("max_table")}
        if got["status"] == sep.COUNTED and row["observed_max_table"] > row["predicted_table_bound"]:
            bad += 1
        rows.append(row)
    out = {"auto_separator_max_width": AUTO_SEPARATOR_MAX_WIDTH,
           "bound_at_auto_width": sep.predicted_table_bound(AUTO_SEPARATOR_MAX_WIDTH),
           "violations": bad, "rows": rows}
    text = json.dumps(out, indent=1)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
