# v6 hypotheses

Status values: `PROPOSED`, `PREREGISTERED`, `IN_PROGRESS`, `SUPPORTED_IN_SCOPE`,
`NOT_SUPPORTED`, `REJECTED`, `INCONCLUSIVE`, `BLOCKED`, `DEFERRED`.

A hypothesis is not “proved” by a finite benchmark. Every entry names its null
hypothesis, oracle and stop rule.

## H-SAT-01 — Two-watched literals reduce propagation work

**Status:** SUPPORTED_IN_SCOPE (result recorded 2026-10-31; scope is this machine,
six fixed families, n ≤ 90, 5 repetitions)
**Owner:** lead engineer

**Claim:** on a preregistered family set, two-watched-literal propagation reduces
clause visits and/or wall time relative to the existing full-clause scan while
preserving every SAT/UNSAT/UNKNOWN verdict and every checked certificate.

**Null hypothesis:** watch maintenance and initialization cost erase the benefit;
the watched engine is not measurably faster on at least two of the preregistered
families, or it regresses wall time by more than 10 % on any family.

**Scope:** built-in DPLL only. Same variable choice (Jeroslow–Wang), same polarity
order (True then False), same pure-literal rule, same node/time budget. No CDCL,
restarts, learning, preprocessing or changed heuristics in this ablation.

**Families (fixed seeds):**
- random 3-SAT at ratio 4.26, 70 and 90 variables;
- planted 3-SAT, 70 variables, hidden assignment;
- pigeonhole 7/6 and 8/7 (UNSAT);
- Tseitin grid 6×6 (UNSAT, parity-heavy);
- quick subset: 40-variable random/planted, pigeonhole 6/5, Tseitin 4×4.

**Metrics:** wall and solver milliseconds (median, min, p95), decisions,
propagations, conflicts, nodes, peak memory (not yet instrumented), certificate
replay success.

**Oracle:** brute force for n ≤ 7; the existing scan engine as a differential
reference; `check_refutation` for every UNSAT certificate; SAT models checked
against the original CNF.

**Acceptance threshold:** zero verdict or model disagreements; every UNSAT has a
replayed certificate in the verification pass; a repeatable median improvement on
at least two families without a >10 % median regression on any family. Report
family-specific results even if the overall claim fails.

**Falsification:** any disagreement, any unchecked UNSAT presented as certified,
or no family with a repeatable improvement.

**Stop rule:** the benchmark is rerun at most three times after a defect fix; if
the result remains mixed, ship the engine as opt-in and record `NOT_SUPPORTED` for
the universal claim.

**Evidence:** `scripts/sat_propagation_benchmark.py`,
`research/v6/evidence/sat_propagation_benchmark.json`, `tests/test_sat_watched.py`.

**Observed result (2026-10-31, Windows 11, Ryzen 7 7735HS, Python 3.14.6):**

| Family | Status | Scan median ms | Watched median ms | Scan/watched | Decision nodes |
| :--- | :--- | ---: | ---: | ---: | ---: |
| random-3sat-70 | SAT | 136.84 | 83.50 | 1.64× | 246 |
| random-3sat-90 | UNSAT | 677.60 | 389.74 | 1.74× | 885 |
| planted-70 | SAT | 7.99 | 7.68 | 1.04× | 14 |
| pigeonhole-7-6 | UNSAT | 131.29 | 120.69 | 1.09× | 1,439 |
| pigeonhole-8-7 | UNSAT | 1,292.15 | 1,153.07 | 1.12× | 10,079 |
| tseitin-4x5 | UNSAT | 985.56 | 652.92 | 1.51× | 8,191 |

All verdicts agreed, all SAT models passed the original CNF, and all four UNSAT
families had certificates replayed by `check_refutation`. Decision counts were
identical, as intended by the controlled design. The result supports the claim
only for this finite suite; it does not establish asymptotic behavior or a
universal speedup. Small families gain little because initialization dominates.

## H-SAT-02 — Incremental propagation improves repeated queries

**Status:** PROPOSED. Requires a session API; not part of the first increment.

## H-SAT-03 — A small CDCL subset outperforms project DPLL on some hard families

**Status:** DEFERRED until H-SAT-01 and the proof-checker audit pass. No code yet.

## H-SAT-05 — Certified GF(2) preprocessing resolves parity-heavy CNFs

**Status:** PROPOSED. The v3.5 OMNIWAVE report found parity wins on Tseitin, but
the extraction soundness and certificate replay are not yet audited for a
production path.

## H-SAT-06 — Separator DP provides exact counts for low-width formulas

**Status:** PROPOSED. Requires an exact-count oracle and `UNKNOWN` on width growth.

## H-UX-01 — Provenance-first results improve interpretability

**Status:** PROPOSED. Any change must name a task and a measurable misinterpretation
rate; “looks clearer” is not evidence.
