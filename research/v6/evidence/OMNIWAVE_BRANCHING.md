# OMNIWAVE branching heuristic (post-3.6.0)

**Date:** 2026-10-31
**Branch:** `agent/v3.7.0-omniwave-branching` from `origin/main` `5d2268f`
**Change:** `OmniwaveConfig.branch` = `auto | jw | bfs`.

## What changed

- `jw`: Jeroslow-Wang-style score over the clauses still open under the current
  propagated assignment; the wave's BFS order is the deterministic tie-break.
- `bfs`: the previous first-unassigned-in-BFS-order behavior.
- `auto`: `bfs` when `ProblemField.xor_view()` finds at least `n/4` exact parity
  rows (Tseitin/parity), `jw` otherwise. This keeps parity behavior unchanged
  while cutting pigeonhole/random trees.

## Quick suite (`omniwave_benchmark.py --quick`, same seeds)

| Family | Status | BFS ms (old) | Auto ms (new) | Speedup | Fronts old → new |
| :--- | :--- | ---: | ---: | ---: | ---: |
| random-20 SAT | SAT | 5.3 | 9.8 | 0.54× | 12 → 24 |
| random-20 UNSAT | UNSAT | 27.1 | 12.6 | **2.15×** | 69 → 19 |
| random-30 SAT | SAT | 11.2 | 12.7 | 0.88× | 46 → 23 |
| random-30 UNSAT | UNSAT | 162.9 | 37.6 | **4.33×** | 241 → 49 |
| planted-40 | SAT | 12.6 | 15.0 | 0.84× | 36 → 19 |
| parity-18 | UNSAT | 4052.6 | 4052.5 | 1.00× | 2047 → 2047 |
| pigeonhole-6/5 | UNSAT | 733.0 | 146.0 | **5.02×** | 777 → 239 |
| low-treewidth-40 | SAT | 7.5 | 12.2 | 0.62× | 17 → 32 |

Interpretation: the heuristic is a large win on UNSAT pigeonhole/random
instances and neutral on parity. Tiny SAT formulas pay a few milliseconds for
scoring, so `auto` is not a universal speedup. It is a structural branching
improvement, not a complexity claim.

## Full suite (`omniwave_benchmark.py`, same seeds)

| Family | Status | BFS ms (old) | Auto ms (new) | Speedup | Fronts old → new |
| :--- | :--- | ---: | ---: | ---: | ---: |
| random-30 UNSAT #1 | UNSAT | 269.4 | 35.9 | **7.51×** | 241 → 49 |
| random-30 UNSAT #2 | UNSAT | 101.5 | 37.1 | **2.73×** | 135 → 53 |
| random-40 UNSAT #1 | UNSAT | 114.6 | 30.5 | **3.75×** | 131 → 29 |
| random-40 UNSAT #2 | UNSAT | 265.9 | 33.4 | **7.96×** | 217 → 33 |
| random-50 UNSAT | UNSAT | 264.0 | 65.9 | **4.01×** | 227 → 57 |
| pigeonhole-6/5 | UNSAT | 2077.9 | 152.0 | **13.67×** | 777 → 239 |
| planted-120 | SAT | 12942.1 | 75.8 | **170.74×** | 19878 → 40 |
| parity-18 | UNSAT | 5313.3 | 4257.5 | 1.25× | 2047 → 2047 |
| random-50 SAT | SAT | 18.2 | 37.0 | 0.49× | 39 → 68 |
| low-treewidth-40 | SAT | 7.3 | 12.2 | 0.60× | 17 → 32 |

The large win on `planted-120` is a tree-size effect, not a scaling law. Some
small SAT instances regress because the score scan costs more than the saved
fronts; `--branch bfs` preserves the old behavior.

## Correctness

- `tests/test_omniwave.py`: 488 tests pass, including exhaustive/brute-force
  differential, all UNSAT proofs replay-checked, batch/GPU parity.
- New tests: JW < BFS front count on pigeonhole; auto uses BFS on a parity
  formula; invalid branch mode raises.
- The proof log and DRAT check are unchanged.

## Artifacts

- `research/v6/evidence/omniwave_benchmark_quick.json` (old baseline)
- `research/v6/evidence/omniwave_branching_auto_quick.json` (new)
- full-suite JSON: `research/v6/evidence/omniwave_branching_full.json`
