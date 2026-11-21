# Execution log

| When (2026-11-01) | Step | Result |
|---|---|---|
| M0 | `git fetch`; branch `agent/v4.0.0-foundation` from `origin/main` 78b970f | OK; user's untracked files preserved |
| M1 | version/truncation/compile/flake8 gates; full pytest | PASS; 1964 passed, 13 skipped (see BASELINE caveats) |
| M4 | ExecutionPlan + router/CLI/MCP/Studio wiring; 23 tests | commit 67411cc, pushed |
| M10 | `cqhecs/sat_separator.py`, `count_models(method=...)`; 316 tests | done |
| M10 | benchmark `sat_separator_bench.json` | 0 mismatches; see FINDINGS F-001 |
| M10 | DPLL counter RecursionError (F-002) | regression test red -> fixed -> green |
| M5 | `PauliObservable`, `evaluate_pauli_observables`, `expectation.py` single native pass; 203 oracle tests | done |
| M15/M17 | version 4.0.0 on all surfaces; README/CHANGELOG/RELEASE_NOTES/MIGRATION_V4/ARCHITECTURE; native, web, mutation, wheel gates | done locally (see TEST_MATRIX) |

## Wave 3 (AGENTS_V6.md) — honesty fixes, 2026-11-21

Base `25e16e5` (v5.0.0), branch `agent/v6-rc`. Full detail: `WAVE3_REPORT.md`.

| Step | Task | Result |
|---|---|---|
| W0 | baseline on 25e16e5 | 2814 passed / 109 skipped; web 61/61; CTest 21/21 (prior agent) |
| T6-03 | native CPU-only build `-DCQ_ENABLE_VULKAN=OFF` + CI lane | committed (prior agent) |
| f16dbb5 | W3-12 / D5 shared web noise predicate | web 71/71, build green |
| 722b7be | W3-09 / D3 `certified` + `proof_level`; rejected proof ≠ checked | test_unified_solver +6 |
| a3f5ab4 | W3-06/W3-07 / D4 uncovered gates; synthetic profile digest | test_uncovered_gates 12 |
| 659885e | W3-01 / D1 Path A shot truncation removed | test_path_a_shots 5 |
| 70a145e | W3-05 / D2 fail-closed ledger + net spend | test_runner_ledger 14; ledger = 25.0/25 |
| 85887b7 | W3-08 / W3-17 SAT baseline + build constraints | script reproduces |
| 8ea4ad6 | W3-15 / D7 MCP input bounds | test_mcp_server +4 |
| fad5efb | W3-18 / D8 SECURITY.md + classifiers + version check | check_version PASS |
| b14f617 | W3-19 / D11 mutant count fixed + guarded | mutation 60/60; meta meta-test 5 passed |
| 9d9a720 | W3-02 / D10 Path B dropped mass + Path A parser dedup | test_path_b_hygiene 3, test_parser_parity 2 |
| (this commit) | W3-03 / D12 audit; W3-04 Path B vs dense | FINDINGS F-004/F-005; PATHB_DOMINANCE.json |
| (this commit) | W3-20 licence register; W3-21 QG board reconciliation | qg_doc_consistency.py PASS; qg tests 102 passed |
| (this commit) | W3-16 llms.txt; W3-14 Rust pin | test_llms_txt 4 passed |
| (this commit) | W3-10 proof deadline; W3-13 Forge axe wcag22aa | test_unified_deadline 6; Playwright e2e 42/42 |
| full gate | `pytest tests/ -q` | 2878 passed, 105 skipped, 1 deselected (clean run) |

## Wave 4 (AGENTS_V6.md) — contracts and hardening, 2026-11-21

| Step | Task | Result |
|---|---|---|
| f2908e3 | W4-07 `hcs.sat.count.v1`; W4-23 version decision v6.0.0 | test_sat_count_contract 4 |
| 0b202be | W4-02 MCP `isError` + `-32602` | test_mcp_server 15 |
| 699ece3 | W4-06 doctor solver line + Studio token env/file | test_doctor_and_token 5 |
| (this commit) | W4-21 QG/router mutation targets | mutation 63/63 killed |

Note (W4-21): the W3-10 proof-deadline change made the existing OMNIWAVE mutant
"accepts an undecided proof check" survive, because a zero proof budget now short-circuits
before the mutated line. The check now uses a tiny positive budget so it still exercises
the undecided branch; the mutant is killed again. Recorded because it shows the mutation
suite doing its job across waves.
| deferred | W3-10 deadline; W3-02/03/04/11/13/14/16/18/19/20/21; web e2e | see WAVE3_REPORT / BLOCKERS |
| W0 (2026-11-21) | AGENTS_V6 baseline on 25e16e5 | PASS: 2814 passed/109 skipped; web 61/61; CTest 21/21 (see BASELINE_W0.md) |
| W3 / T6-03 (2026-11-21) | `-DCQ_ENABLE_VULKAN=OFF` CPU-only native build | PASS: new `tests/test_native_cpu_only.py` red->green (configure, build, CTest, no binary contains the Vulkan loader name; detector positive-controlled: Vulkan-build binaries match). Vulkan build still CTest 21/21. CPU build runs 15 CPU-pure tests; Vulkan targets excluded, not stubbed. NOT YET: CPU/Vulkan differential tests (T6-04), capability reporting in C ABI, CI lane. |
| W3 cont. (2026-11-21) | CI lane `linux-native-cpu-only` (no libvulkan installed), `cq_core_build_capabilities()` C ABI | PASS locally: CPU build reports vulkan_linked=false, Vulkan build true; Vulkan CTest 21/21; CI lane not yet run remotely |
