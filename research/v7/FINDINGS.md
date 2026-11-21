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

## F-003 H4-PAULI-01: native X/Y/Z observables -- SUPPORTED_IN_SCOPE
All 203 oracle tests pass. 150 randomized truncated circuits (>= 50 with a
non-zero bound) never exceeded their own certified bound; 120 untruncated random
circuits agree with Qiskit to 1e-9; every single-qubit gate x letter and every
two-qubit Pauli x {cx, cz, swap} entry matches to 1e-12; the Y-phase mutation is
caught. In 60 random truncated circuits the per-observable maximum was strictly
below the shared-sum bound in more than 10 (asserted), i.e. the new bounds are
tighter, never looser, by construction. `expectation_values(method="sparse_pauli")`
now runs once instead of once per basis-rotation pattern; its reported
`error_bound` per value is the observable's own bound (previously the group
total). Callers that read the old looser number get a smaller, still valid one.

## F-004 Path C "exact" label audit (D12, W3-03) — NOT REPRODUCED
The reported defect (Path C claims `exact=True`/`error_bound=0.0` while discarding
nonzero Schmidt values below the relative 1e-13 floor) is **not a defect at the Python
surfaces**. The code already: (a) keeps `error_bound=0.0` as "no deliberate budget
approximation"; (b) leaves `numerical_error_bound=None` with
`metadata["numerical_error_bound_reason"]` containing "not derived" (it does not compose
the per-SVD discarded mass into a state-norm bound it cannot derive); and (c) reports the
discarded mass only as `metadata["discarded_spectral_mass_diagnostic"]`. Existing tests
pin all three: `tests/test_correctness_contracts.py` (the discarded-mass test asserts
`numerical_error_bound is None`, the reason string, and that the diagnostic is never
presented as a bound). CLI and Studio serialise `result.to_dict()` and `metadata`, so the
diagnostic is visible there too. Remaining (not W3-03): the Studio/Web **UI copy** that
renders a result state should state the qualifier in plain language — deferred to the
Wave 7 provenance UI. Recorded as an audit, not a fix.

## F-005 Path B vs a plain dense statevector (P1-04/W3-04) — dense dominates
Raw data: `evidence/PATHB_DOMINANCE.json` (`scripts/bench_path_b_vs_dense.py --quick`,
3 repeats, 2000 shots, fixed seed, Qiskit `Statevector` as the dense baseline; git SHA,
Python and OS are in the JSON). Median wall seconds, ratio = Path B / dense:

| n | T | branches | dense (s) | Path B (s) | ratio |
|--:|--:|--:|--:|--:|--:|
| 8 | 0 | 1 | 0.0005 | 0.0013 | 2.7x |
| 8 | 8 | 256 | 0.0006 | 0.0373 | 57.7x |
| 12 | 0 | 1 | 0.0012 | 0.0024 | 2.0x |
| 12 | 4 | 16 | 0.0013 | 0.0168 | 12.6x |
| 12 | 8 | 256 | 0.0014 | 0.2524 | 181.2x |

Reading: on every measured case Path B is slower than a plain dense statevector, by 2x at
T=0 up to ~181x at T=8. Path B is a branch decomposition that contracts onto a dense
statevector and carries none of the sparse-extent advantage that would justify a
stabilizer-rank method. This is a finite measurement on this machine, not an asymptotic
claim. It is the input to the P1-04 decision (relabel Path B honestly as a low-T dense
branch-sum method and re-order the router under H4-ROUTE-01). No router change is made in
Wave 3; the decision is recorded in `DECISIONS.md`.
