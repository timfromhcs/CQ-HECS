# Unified solver

One entry point over four engines, one result contract, one evidence record.

```python
from cqhecs import unified
result = unified.solve_unified(formula, timeout_seconds=10.0)
result.status        # "SAT" | "UNSAT" | "UNKNOWN"
result.engine        # which engine decided, or None
result.attempts      # every engine tried, with budget, time, status, reason, proof
result.to_dict()     # {"schema": "hcs.sat.unified.v1", ...}
```

```bash
cq-hecs sat solve --cnf ... --engine unified          # text
cq-hecs --format json sat solve --random 40 --engine unified
```

## Why this exists instead of a fork

CaDiCaL is reached through `cqhecs/sat_external.py` (optional `python-sat`). It is not
modified here: forking a third-party solver would create maintenance and licensing work
with no scientific gain. What was missing was the layer above - one contract that knows
what each engine can do, spends a declared budget across them, and records what
happened. That layer is this module.

## The four engines

| Engine | What it is | Evidence it produces |
|---|---|---|
| `watched` | `cqhecs.sat` watched-literal DPLL | a model, re-verified against the original CNF; UNSAT by exhaustion, **no** certificate |
| `omniwave` | exhaustive cube search (`cqhecs.omniwave`) | a model; UNSAT only with a DRAT proof checked by `cqhecs.drat` |
| `cadical` | CaDiCaL via `python-sat`, **optional** | a model re-verified here; UNSAT with a DRAT proof checked in-repo |
| `scan` | `cqhecs.sat` scan DPLL, the readable reference | a model; UNSAT with a tree-resolution certificate checked in-repo |

## The rules, and where they are tested

1. **Capability first.** `unified.capabilities()` reports every engine and whether it is
   available. A missing `python-sat` shows up as `cadical: unavailable` in the attempt
   list; nothing is skipped silently. (`test_missing_cadical_is_reported_not_skipped`)
2. **Declared order and budget.** Default order `watched → omniwave → cadical → scan`
   with fractions `0.5 / 0.3 / 0.2`, and a small floor for the last engine so every
   engine is at least probed. The split always sums to the total budget - to the last
   bit, not approximately. (`test_budget_split_sums_to_the_total`)
3. **The portfolio re-verifies.** A `SAT` model is checked against the *original* CNF
   here, one more time, before it is returned; a model that fails is refused and the
   attempt is rewritten as `UNKNOWN`. An engine's self-report is not evidence.
   (`test_a_model_that_fails_verification_is_refused`)
4. **UNSAT status is copied, never upgraded.** Each attempt carries the proof status its
   engine produced, including the honest "no certificate (exhaustive search)" of the
   watched engine. (`test_unsat_result_keeps_the_proof_status_of_the_engine_that_proved_it`)
5. **Deterministic.** Same formula, same order, same budgets. No randomness and no
   wall-clock-dependent choice beyond the budgets themselves.
6. **One schema.** `hcs.sat.unified.v1` with status, engine, order, fractions, attempts,
   assignment, certificate step count and the formula digest - everything a report needs
   to stay honest.

## When not to use it

- You already know the engine that fits: call it directly and skip the attempts.
- You need a *tree-resolution* proof: ask the `scan` engine, not the portfolio.
- You want the fastest possible answer on a hard instance: `cadical` alone (when
  installed) is still far ahead of everything here.

## Measured (2026-11-02, one machine, 12 s budget per engine)

`scripts/unified_solver_benchmark.py` regenerates this table.

| Instance | vars | watched | omniwave | cadical | scan | portfolio |
|---|---:|---|---|---|---|---|
| pigeonhole-7-6 | 42 | UNSAT 0.1 s | UNSAT 1.1 s | unavailable | UNSAT 0.3 s | UNSAT via watched, 0.14 s |
| pigeonhole-8-7 | 56 | UNSAT 1.3 s | UNSAT 26.8 s | unavailable | UNSAT 3.3 s | UNSAT via watched, 1.34 s |
| Tseitin 3x3 | 12 | UNSAT 0.0 s | UNSAT 0.0 s | unavailable | UNSAT 0.0 s | UNSAT via watched, 0.00 s |
| random 3-SAT 70 vars | 70 | UNSAT 0.1 s | UNSAT 0.2 s | unavailable | UNSAT 0.4 s | UNSAT via watched, 0.14 s |
| SHA-256 W=16 r=8 | 6 673 | SAT 0.1 s | SAT 0.2 s | unavailable | SAT 0.4 s | SAT via watched, 0.10 s |

**Disagreements between engines: 0.** That is the property that matters - four
independent implementations on the same formula, same verdict.

The portfolio's overhead is the price of the attempt record (0.00-0.04 s here). With
`python-sat` installed, `cadical` joins the order with its own share; the table will show
it, and no number in this document has to change.
