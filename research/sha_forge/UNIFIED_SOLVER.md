# Unified solver - measurement record (2026-11-02)

Companion to `docs/UNIFIED_SOLVER.md`. This file is the record; the table there is a copy,
and `scripts/unified_solver_benchmark.py` regenerates both from the raw JSON.

## Run B - with CaDiCaL (2026-11-02, later the same day)

- Environment: Python 3.12.13, `python-sat 1.9.dev17` (CaDiCaL 1.9.5), Windows 11,
  AMD Ryzen 7 7735HS. A separate throw-away venv: `python-sat` does not build on this
  machine's default Python 3.14, and the project itself requires Python `<3.14`.
- Command: `python scripts/unified_solver_benchmark.py --out <dir> --timeout 30`
- Raw JSON: `E:\qCSHA\sha_forge_results\unified_cadical\unified_benchmark.json`
  (outside the repository).

| Instance | vars | watched | omniwave | cadical | scan | unified | fastest |
|---|---:|---|---|---|---|---|---|
| pigeonhole-7-6 | 42 | 0.186 | 0.992 | 0.214 | 0.372 | 0.189 (watched) | watched |
| pigeonhole-8-7 | 56 | 2.897 | 33.677 | 5.580 | 5.576 | 2.611 (watched) | watched |
| Tseitin 3x3 | 12 | 0.002 | 0.004 | 0.004 | 0.006 | 0.003 (watched) | watched |
| random 3-SAT 70/300 | 70 | 0.263 | 0.238 | 0.137 | 0.765 | 0.262 (watched) | cadical |
| SHA-256 W16 r8 | 6 673 | 0.157 | 0.330 | 0.054 | 0.554 | 0.209 (watched) | cadical |

- **0 disagreements.** Every engine that decided an instance agreed on the verdict.
- CaDiCaL's UNSAT answers were DRAT-checked by `cqhecs.drat` inside `solve_external`, so
  the column is not an unchecked label.
- The portfolio picked `watched` on all five because the declared order puts it first; it
  would have picked `cadical` on two families had CaDiCaL been asked first. Cost of the
  order on this set: 0.12 s and 0.16 s. See `docs/UNIFIED_SOLVER.md` for why the order is
  not swapped on the strength of one table.

## Run A - without CaDiCaL (earlier the same day)

- Environment: Python 3.14.6, no `python-sat`; the adapter reports `unavailable`.
- Raw JSON: `E:\qCSHA\sha_forge_results\unified\unified_benchmark.json`.

| Instance | vars | watched | omniwave | cadical | scan | unified |
|---|---:|---|---|---|---|---|
| pigeonhole-7-6 | 42 | 0.1 | 1.1 | unavailable | 0.3 | 0.14 (watched) |
| pigeonhole-8-7 | 56 | 1.3 | 26.8 | unavailable | 3.3 | 1.34 (watched) |
| Tseitin 3x3 | 12 | 0.0 | 0.0 | unavailable | 0.0 | 0.00 (watched) |
| random 3-SAT | 70 | 0.1 | 0.2 | unavailable | 0.4 | 0.14 (watched) |
| SHA-256 W=16 r=8 | 6 673 | 0.1 | 0.2 | unavailable | 0.4 | 0.10 (watched) |

## What these numbers do not show

- Nothing about industrial instances or SAT-competition workloads; the set is the project's
  own families.
- No claim that the portfolio beats CaDiCaL: on two of five families it is slower by
  design, because the order asks the built-in engine first.
- No claim about asymptotics from five instances. A different order is a hypothesis that
  needs a held-out benchmark and would be a schema-visible change.

## Reproduce

```bash
# Run A: any supported interpreter, no optional dependency
python scripts/unified_solver_benchmark.py --out <dir> --timeout 30

# Run B: a Python 3.12 environment with the optional extra
python -m venv .venv-sat
.venv-sat/Scripts/pip install -e . python-sat
.venv-sat/Scripts/python scripts/unified_solver_benchmark.py --out <dir> --timeout 30
```
