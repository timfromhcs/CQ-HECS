# Evidence ledger (v4.0.0)

Each shipped claim maps to code, a test or measurement, and a trust label. Labels
follow AGENTS.md section 4.4; nothing here is "formally verified".

| ID | Claim | Code | Evidence | Label / status |
|---|---|---|---|---|
| E-01 | The plan is built without allocating a backend | `cqhecs/execution_plan.py` | `test_dry_run_allocates_no_backend` (all four backend constructors and `execute` poisoned) | tested |
| E-02 | Plan selection equals the router's; capability comes only from the manifest | `execution_plan.py`, `router.py` | `test_plan_matches_router_selection_and_manifest` over 5 circuit families | tested |
| E-03 | Forced incapable path is refused, never rerouted | `_plan_from_props` | `test_forced_unsupported_path_...`, mutant "ExecutionPlan reroutes a forced incapable path" killed | tested + mutation |
| E-04 | Python, CLI, MCP and Studio return the same plan JSON | `cli.py`, `mcp_server.py`, `studio/app.py` | `test_cli_mcp_studio_return_the_python_plan` | tested |
| E-05 | Plan estimates are heuristics | `_estimate_path` | `estimate_quality="heuristic"`, saturation test | documented limitation |
| E-06 | `count_models(method="separator")` returns the exact count | `cqhecs/sat_separator.py` | 3,000+ exhaustive 3-variable formulas, 300 random vs brute force + DPLL, 3 mutants killed | tested + mutation (exact counting; no proof object is produced) |
| E-07 | Budget/deadline refusals never return a partial count | `count_by_elimination`, `count_models` | `test_table_budget_returns_unknown_...`, `test_deadline_returns_unknown` | tested |
| E-08 | Separator is faster on bounded-width families and slower on high-width random 3-SAT | `scripts/sat_separator_benchmark.py` | `evidence/sat_separator_bench.json` (3 repeats, 11 families, one machine) | measured, finite, no general claim |
| E-09 | DPLL counter no longer raises `RecursionError` | `sat.py:_count_models_dpll` | `test_dpll_counter_refuses_deep_recursion_instead_of_crashing` (red before fix) | tested |
| E-10 | Path D native X/Y/Z values equal Qiskit within 1e-9 (untruncated) | `path_d_sparse_pauli.py` | 120 random circuits, exhaustive 1-/2-qubit tables | tested vs independent oracle |
| E-11 | Each observable's true error <= its own bound | `evaluate_pauli_observables` | 150 truncated circuits (>50 with nonzero bound), mutant "bound never accumulates" killed | tested + mutation (float64 roundoff not in the bound) |
| E-12 | Y phase is correct | `pauli_observable_from_ops` | table tests + mutant "Y loses its phase" killed | tested |
| E-13 | Native C++ core and shaders unaffected | `src/`, `shaders/` | CTest 21/21, 13/13 SPIR-V | tested (Windows only) |
| E-14 | Web app unaffected | `web/` | 17/17 unit, 13/13 Playwright + axe (local) | tested |

## Claims explicitly NOT made

No claim of a complexity improvement; no comparison with external counters or
Pauli-propagation tools; no formal verification; no GPU/Vulkan end-to-end claim; no
statement about real QPU hardware; the plan's estimates are not guarantees; no
statement about any ETH/SETH/P-vs-NP question.
