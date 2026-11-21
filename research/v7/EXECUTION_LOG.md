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
| W0 (2026-11-21) | AGENTS_V6 baseline on 25e16e5 | PASS: 2814 passed/109 skipped; web 61/61; CTest 21/21 (see BASELINE_W0.md) |
| W3 / T6-03 (2026-11-21) | `-DCQ_ENABLE_VULKAN=OFF` CPU-only native build | PASS: new `tests/test_native_cpu_only.py` red->green (configure, build, CTest, no binary contains the Vulkan loader name; detector positive-controlled: Vulkan-build binaries match). Vulkan build still CTest 21/21. CPU build runs 15 CPU-pure tests; Vulkan targets excluded, not stubbed. NOT YET: CPU/Vulkan differential tests (T6-04), capability reporting in C ABI, CI lane. |
