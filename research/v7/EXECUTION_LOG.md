# Execution log

| When (2026-11-01) | Step | Result |
|---|---|---|
| M0 | `git fetch`; branch `agent/v4.0.0-foundation` from `origin/main` 78b970f | OK; user's untracked files preserved |
| M1 | version/truncation/compile/flake8 gates; full pytest | PASS; 1964 passed, 13 skipped (see BASELINE caveats) |
| M4 | ExecutionPlan + router/CLI/MCP/Studio wiring; 23 tests | commit 67411cc, pushed |
| M10 | `cqhecs/sat_separator.py`, `count_models(method=...)`; 316 tests | done |
| M10 | benchmark `sat_separator_bench.json` | 0 mismatches; see FINDINGS F-001 |
| M10 | DPLL counter RecursionError (F-002) | regression test red -> fixed -> green |
