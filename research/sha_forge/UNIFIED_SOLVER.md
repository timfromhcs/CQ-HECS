# Unified solver - measurement record (2026-11-02)

Companion to `docs/UNIFIED_SOLVER.md`. This file is the record; the table there is a
copy, and `scripts/unified_solver_benchmark.py` regenerates both from the raw JSON in
`E:\qCSHA\sha_forge_results\unified\unified_benchmark.json`.

## What was measured

Five instances, every engine asked separately with a 12 s budget, then the portfolio
with the same budget. `waves=1, workers=1` for OMNIWAVE, `python-sat` **not installed**
on this machine, so the CaDiCaL column is the unavailable path.

| Instance | vars | clauses | watched | omniwave | cadical | scan | unified |
|---|---:|---:|---|---|---|---|---|
| pigeonhole-7-6 | 42 | 133 | UNSAT 0.1 s | UNSAT 1.1 s | unavailable | UNSAT 0.3 s | UNSAT (watched) 0.14 s |
| pigeonhole-8-7 | 56 | 204 | UNSAT 1.3 s | UNSAT 26.8 s | unavailable | UNSAT 3.3 s | UNSAT (watched) 1.34 s |
| Tseitin 3x3 | 12 | 81 | UNSAT 0.0 s | UNSAT 0.0 s | unavailable | UNSAT 0.0 s | UNSAT (watched) 0.00 s |
| random 3-SAT | 70 | 300 | UNSAT 0.1 s | UNSAT 0.2 s | unavailable | UNSAT 0.4 s | UNSAT (watched) 0.14 s |
| SHA-256 W=16 r=8 | 6 673 | 22 929 | SAT 0.1 s | SAT 0.2 s | unavailable | SAT 0.4 s | SAT (watched) 0.10 s |

## What the numbers say

- **Zero disagreements.** Four independent implementations, five instances, same
  verdicts. A disagreement would be a hard failure of the run, not a preference.
- **The portfolio picks the right engine here**, because the watched engine wins every
  row; the cost of finding that out is one attempt, 0.00-0.04 s.
- **OMNIWAVE is the slowest on this set** (26.8 s on pigeonhole-8-7 against 1.3 s), which
  is consistent with F-16: its strength is exhaustive coverage with a checked proof, not
  speed.
- **CaDiCaL is reported unavailable, not skipped.** That is deliberate: a silent
  fallback would make the record claim an engine ran when it did not.

## What this does not show

- Nothing about performance against CaDiCaL: it is not installed here. The docs say so
  and the table will grow a column, not change a claim, once it is.
- Nothing about large industrial instances. The set is small on purpose: it compares
  engines on the project's own families, not on a SAT-competition benchmark.
- No claim that the portfolio is faster than the best engine - it is a contract and an
  evidence record first, and it always costs at least one attempt.

## Reproduce

```bash
cd E:/qCSHA/CQ-HECS
$env:PYTHONPATH="."
python scripts/unified_solver_benchmark.py --out <results dir> --timeout 12
```
