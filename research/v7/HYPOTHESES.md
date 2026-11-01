# v4 hypotheses (preregistered before the deciding measurement)

Outcome vocabulary: SUPPORTED_IN_SCOPE, NOT_SUPPORTED, INCONCLUSIVE, DEFERRED.

## H4-ROUTE-01 -- cost-aware router beats fixed A->B->C->D
Status: **DEFERRED / not tested.** v4 ships the *explainable plan* only
(DECISIONS D-002); the router's selection is unchanged. No claim of better path
choice is made. A future test needs a held-out circuit-family suite with
measured regret.

## H4-SAT-01 -- variable elimination safely accelerates exact #SAT at bounded width

**Claim (scope).** For CNF formulas whose min-fill induced width is small,
`count_models(method="separator")` returns *exactly* the integer
`count_models(method="dpll")` returns, and is faster on declared low-width
families. On high-width formulas it refuses (`UNKNOWN`) or is bypassed, never
returning a wrong or partial count.

**Null / falsification.**
1. Correctness: any count mismatch against brute force (n <= 11) or the DPLL
   counter on the declared families falsifies the claim outright.
2. Soundness of refusal: any `COUNTED` result produced after a budget/deadline
   refusal falsifies it.
3. Speed (secondary, descriptive only): reported as median wall time; no
   asymptotic or general-speedup claim is made in either direction.

**Design.** Fixed seeds; families and parameters are fixed in
`scripts/sat_separator_benchmark.py` *before* it was run. The default method
stays `dpll`; `auto`'s width limit (`AUTO_SEPARATOR_MAX_WIDTH = 14`, i.e.
tables <= 2^15 entries) was chosen a priori and **not tuned on this benchmark**.
If it is changed after seeing these numbers, the benchmark becomes training data
and a new held-out set is required.

**Outcome.** See `FINDINGS.md` (filled after the run; raw data in
`evidence/sat_separator_bench.json`).
