# v6 test matrix

Every row records the exact command, environment, observed result and status.
`NOT RUN` is not `PASS`. Logs under `.local/` are local scratch and are not
committed; committed evidence goes under `research/v6/evidence/`.

Environment: Windows 11 10.0.26200, AMD Ryzen 7 7735HS (8C/16T), Python 3.14.6,
CMake 4.4.0, Node 22.23.1, Rust 1.96.0.

## Baseline (before v3.6 code changes)

| Gate | Command | Expected | Observed | Duration | Status |
| :--- | :--- | :--- | :--- | ---: | :--- |
| L0 | `git status --short --branch` | user files preserved | only `PLAN-v3.6.0.md`, `.claude/launch.json` untracked | — | PASS |
| L1 | `python scripts/check_version.py` | 3.5.0 everywhere | `Version consistency OK` | <1 s | PASS |
| L1 | `python -m compileall -q cqhecs tests scripts python_bridge` | no syntax error | exit 0 | <1 s | PASS |
| L2 | `python -m pytest tests/ -q` (baseline) | no regression | 1617 passed, 6 skipped, 1 deselected in 190.44 s; process exit was the F-05 crash | PASS (counts) |
| L2 | `python -m pytest tests/ -q` (after changes) | no regression | **1758 passed, 6 skipped, 1 deselected** in 201.16 s, exit 0 (`.local/v36/pytest-final3.log`) | PASS |
| L3 | `ctest --test-dir build -C Release --output-on-failure` | 21/21 | 21/21 passed | 65.42 s | PASS |
| L8 | `cd web && npm test` | all pass | 16/16 | 5.1 s | PASS |
| L8 | `cd web && npm run build` | tsc + vite build | built successfully | 1.5 s | PASS |
| L7 | physical Vulkan/WebGPU dispatch | device-specific result | not attempted | — | NOT RUN |
| L4 | external LRAT/CakeLPR | verified checker | not installed | — | BLOCKED (B-02) |
| L6 | mutation suite | ≥ CI history | 54/54 killed, exit 0 | PASS |
| L6 | watched-engine mutants | new mutation targets | not yet added to the harness | TODO |

## v3.6 increment 1 (SAT propagation + predicate fix)

| Gate | Command | Expected | Observed | Status |
| :--- | :--- | :--- | :--- | :--- |
| L2 | `python -m pytest tests/test_sat_watched.py -q` | all pass | 134 passed in 1.08 s | PASS |
| L4 | exhaustive 3-var formulas, 0–4 clauses (27,405 formulas) | scan = watched = brute force | no mismatch | PASS (scratch, reproducible) |
| L4 | `scripts/sat_propagation_benchmark.py --quick --repeat 3` | no disagreement, certificates valid | 4 families, 0 failures | PASS (quick) |
| L4 | full `sat_propagation_benchmark.py --repeat 5` | family table | 6 families, 0 failures, 5 samples each | PASS |
| L9 | `python -m pytest tests/test_cli_contract.py -q` | 33 pass | 33 passed | PASS |
| L9 | `python -m pytest tests/test_studio.py -q` | all pass, clean exit | 16 passed, exit 0 | PASS |
| L7 | `python -m pytest tests/test_omniwave_gpu_shutdown.py -q` | clean process exit | 1 passed, exit 0 | PASS |
| L2 | full `pytest` after changes | no regression | 1758 passed, 6 skipped, 1 deselected, exit 0 | PASS |

## Classification of failures

- `correctness`: wrong verdict, unverified model, unchecked UNSAT presented as
  certified, or an unsound predicate.
- `build`: compile/link/package failure.
- `performance`: regression outside the preregistered threshold.
- `UI`: dead control, wrong status label, overflow or a11y failure.
- `security`: secret, unsafe endpoint, resource exhaustion.
- `docs`: claim not backed by code/test/evidence.
- `research`: hypothesis result, including negative results.
