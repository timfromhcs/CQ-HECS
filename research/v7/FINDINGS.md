# v4 findings

## F-001 H4-SAT-01: variable elimination #SAT -- SUPPORTED_IN_SCOPE (correctness), descriptive speed
Raw data: `evidence/sat_separator_bench.json` (script
`scripts/sat_separator_benchmark.py`, 3 repeats, 30 s timeout, fixed seeds,
Python 3.13.13, Windows 11, single process). Environment fields are in the JSON.

**Correctness:** 0 mismatches across 11 families x 3 methods. Test oracles:
`tests/test_sat_separator.py` -- all 3,000+ formulas with <= 3 clauses over 3
variables (exhaustive), 300 random formulas vs brute force and the DPLL counter,
tautology/duplicate/free-variable/empty-clause edge cases, >2^53 counts as
decimal strings, budget and deadline refusals (`UNKNOWN`, never partial), and a
deliberately broken join that the oracle catches.

**Speed (median wall ms; C = counted, U = UNKNOWN):**

| Family | width | dpll | separator | auto |
|---|---:|---:|---:|---:|
| chain-200 | 1 | 77.6 C | 4.6 C | 4.5 C |
| chain-2000 | 1 | 19157 U | 365 C | 365 C |
| grid-3x25 | 3 | 1107 C | 2.6 C | 2.6 C |
| grid-4x20 | 4 | 2046 C | 3.7 C | 3.6 C |
| grid-5x12 | 5 | 464 C | 3.0 C | 3.0 C |
| banded-n80-w8 | 7 | 2736 C | 7.0 C | 6.9 C |
| banded-n120-w10 | 7 | 30025 U (timeout) | 13.2 C | 13.1 C |
| banded-n60-w14 | 11 | 185 C | 13.9 C | 13.8 C |
| random3sat-n24-r4.26 | 17 | 3.1 C | 67.7 C | 4.8 C |
| random3sat-n32-r3.0 | 21 | 23.3 C | 396.5 C | 26.6 C |
| random3sat-n40-r4.26 | 27 | 25.3 C | 232 U (table budget) | 32.6 C |

Reading: on bounded-width structured families variable elimination is
orders of magnitude faster; on high-width random 3-SAT it is slower or refuses,
and `auto` avoids that loss at a planning cost of 1.5-7 ms. This is a finite
benchmark on synthetic families; it establishes **no** asymptotic or general
speedup claim and says nothing about industrial instances. The default method
therefore stays `dpll`; `auto` is opt-in. The `auto` width limit (14) was fixed
before this run and not tuned on it (see HYPOTHESES.md).

## F-002 Latent defect fixed: DPLL `count_models` crashed on deep formulas (CORRECTNESS/RESOURCE)
Found by this benchmark. Reproducer: `count_models(CNF chain of 2000 vars)` raised
an uncaught `RecursionError` in v3.7.0 instead of a typed result. Regression
test `test_dpll_counter_refuses_deep_recursion_instead_of_crashing` failed before
the fix. The counter now returns `UNKNOWN` with an explicit note (no count
claimed). Severity: medium (no wrong answer, but an unhandled exception in a
public API and MCP/Studio surface).
