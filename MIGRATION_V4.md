# Migrating from v3.7.0 to v4.0.0

v4.0.0 removes nothing. Every v3.7.0 call keeps working; the changes below are
additive except for the three *behavior* notes in section 2. (Under strict
semantic versioning these changes alone would be a minor release; the major
number marks the new public contracts -- the `ExecutionPlan` schema, the
`count_models(method=...)` contract and per-observable Path D bounds -- and was
requested for this release line.)

## 1. New (opt-in)

| Surface | v4 addition |
|---|---|
| Python | `cqhecs.execution_plan.build_execution_plan(circuit, forced_path=, require_counts=, max_memory_bytes=)`, `EntanglementAdaptiveRouter.plan(...)`. Schema `cqhecs.execution_plan/1`. |
| Python | Routed results carry `metadata["plan_check"]` (planned vs actual path, elapsed time). Observation only; it never changes later routing. |
| CLI | `cq-hecs analyze CIRCUIT --explain [--force-path P] [--require-counts] [--max-memory-mb N]` adds a `plan` object to the JSON payload and a text explanation. Without these flags the output is unchanged. |
| MCP | New tool `cqhecs_plan`. `cqhecs_sat_count` accepts `method`. |
| Studio API | `POST /api/plan`; `POST /api/sat/count` accepts `method`. |
| Python | `count_models(formula, ..., method="dpll"\|"separator"\|"auto", separator_max_table_entries=500000)`. The default is `"dpll"`, i.e. the v3.7.0 algorithm. |
| CLI | `cq-hecs sat count --method dpll\|separator\|auto`. |
| Python | `PauliObservable`, `pauli_observable_from_ops`, `SparsePauliDynamicsSimulator.evaluate_pauli_observables`, `PathDSparsePauliBackend.evaluate_paulis`; `PathDSparsePauliBackend.execute(observables=["X[0]Y[1]", ...])`. |

Example:

```bash
cq-hecs --format json analyze name:ghz8 --explain
cq-hecs sat count formula.cnf --method auto
```

```python
from cqhecs.execution_plan import build_execution_plan
plan = build_execution_plan(qasm_text)        # no backend is allocated
plan.selected_path, plan.refusal, plan.candidate_paths
```

## 2. Behavior notes

1. **`count_models` no longer raises `RecursionError`.** A deep formula (for
   example a 2000-variable implication chain) used to crash the DPLL counter with
   an uncaught exception. It now returns `status="UNKNOWN"`, `count=None` with a
   note. Callers that caught `RecursionError` should switch to checking `status`.
2. **Path D bounds from `expectation_values(method="sparse_pauli")` are
   per-observable.** Each value previously carried the *total* bound of its
   Path D run; it now carries its own (smaller or equal, still certified). An
   observable that exceeds the tolerance is `None`/unresolved without
   invalidating the others. `metadata["sparse_pauli_runs"]` is now `1` (one
   native pass) instead of one per basis-rotation pattern.
3. **`count_models` results gain fields**: `backend` (`"dpll"` or
   `"separator"`), and for the separator backend `induced_width` and
   `max_table`. Existing fields are unchanged. With `method="auto"` a refused
   elimination attempt is recorded under `auto_separator`.

## 3. Unchanged, by design

* Routing order and capability rules (A -> B -> C -> D); the plan reports the
  router's choice and does not introduce a second policy.
* The default `count_models` method, the default OMNIWAVE branch policy, all
  proof/certificate semantics, the real-hardware refusal boundary.
* `SimulationResult` field meanings.

## 4. What the plan is and is not

`estimated_peak_memory_bytes` and `estimated_work_units` are conservative
*heuristics* derived from qubit count, gate count, T-count and 1D cut crossings.
They are not guarantees and do not model backend swap routing or scratch I/O. A
`max_memory_bytes` budget turns an overshoot of the *selected* path into a typed
`RESOURCE_BUDGET` refusal; it never silently selects a different path.

## 5. Not part of v4.0.0

Graph-aware Path C ordering, noise calibration schema v3, CNF-to-XOR witnesses,
an optional CDCL engine, OMNIWAVE scheduling experiments, browser/native
conformance corpus and Lean formalization were evaluated for scope and
**deferred**; see `research/v7/DECISIONS.md` and `TASKS.md`. Nothing in the
release claims them.
