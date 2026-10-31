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
| L1 | `python scripts/check_version.py` | 3.6.0 everywhere | `Version consistency OK` | <1 s | PASS |
| L1 | `python -m compileall -q cqhecs tests scripts python_bridge` | no syntax error | exit 0 | <1 s | PASS |
| L2 | `python -m pytest tests/ -q` (baseline) | no regression | 1617 passed, 6 skipped, 1 deselected in 190.44 s; process exit was the F-05 crash | PASS (counts) |
| L2 | `python -m pytest tests/ -q` (final, no optional python-sat) | no regression | **1964 passed, 9 skipped, 1 deselected** in 248.62 s, exit 0 (`.local/v36/pytest-360c.log`) | PASS |
| L3 | `ctest --test-dir build -C Release --output-on-failure` | 21/21 | 21/21 passed | 153.25 s | PASS |
| L8 | `cd web && npm test` | all pass | 17/17 | 5.1 s | PASS |
| L8 | `cd web && npm run build` | tsc + vite build | built successfully | 1.5 s | PASS |
| L7 | physical Vulkan primitive dispatch | CPU parity | OMNIWAVE BCP on AMD Radeon iGPU, CPU-verified; no end-to-end simulator claim | PASS (primitive) |
| L4 | external LRAT/CakeLPR | verified checker | CakeLPR `s VERIFIED UNSAT` on the committed LRAT vector | PASS |
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
| L2 | full `pytest` after changes | no regression | 1964 passed, 9 skipped, 1 deselected, exit 0 | PASS |

## Classification of failures

- `correctness`: wrong verdict, unverified model, unchecked UNSAT presented as
  certified, or an unsound predicate.
- `build`: compile/link/package failure.
- `performance`: regression outside the preregistered threshold.
- `UI`: dead control, wrong status label, overflow or a11y failure.
- `security`: secret, unsafe endpoint, resource exhaustion.
- `docs`: claim not backed by code/test/evidence.
- `research`: hypothesis result, including negative results.

## v3.6.0 final local gates

| Gate | Command | Observed | Status |
| :--- | :--- | :--- | :--- |
| L2 | `python -m pytest tests/ -q` (no optional python-sat) | 1964 passed, 9 skipped, 1 deselected, exit 0 | PASS |
| L2 | `python -m pytest tests/test_sat_external.py -q` (python-sat installed) | 44 passed; process exit `0xC0000409` (F-09, external CaDiCaL) | PASS tests / external exit defect |
| L8 | `cd web && npm test` | 17/17 | PASS |
| L8 | `cd web && npm run build` | tsc + Vite | PASS |
| L8 | `cd web && npm run e2e` | 13/13 Playwright + axe | PASS |
| L3 | CTest | 21/21 | PASS |
| L7 | `python scripts/verify_vulkan_shaders.py` | 13/13 | PASS |
| L6 | `python scripts/run_mutation_tests.py` | 54/54 killed | PASS |
| L10 | `pip-audit -r requirements.txt` | no known vulnerabilities | PASS |
| L10 | secret pattern scan | no matches in tracked files | PASS |
| L11 | wheel/sdist + clean venv | twine PASS; CLI/SAT watched smoke PASS | PASS |
| M5 | CakeLPR / lrat-check / drat-trim | LRAT and DRAT accepted | PASS |
| M5 | Lean 4.33.1 `lake build` + `PrintAxioms` | 9768 jobs; three standard axioms | PASS |
| M5 | Comparator + nanoda | running/recorded in `evidence/COMPARATOR_ETH.md` | see file |

## v3.6.0 release verification

| Gate | Command / source | Observed | Status |
| :--- | :--- | :--- | :--- |
| Exact source CI | `gh pr checks 39` | 8/8 jobs + Vercel pass on `cb0c4be` | PASS |
| Merge-SHA CI | `gh run watch 41189243074` | all jobs success on `db300c0` | PASS |
| Vercel Preview | preview URL | Ready, but Vercel Authentication blocks unauthenticated E2E | BLOCKED |
| Vercel Production | `E2E_BASE_URL=https://cq-hecs-web.vercel.app npm run e2e` | 13/13 pass; bundle reports `3.6.0` / `db300c0` | PASS |
| Release assets | `gh release download v3.6.0` + SHA-256 | all hashes match `sha256sums.txt` | PASS |
| Clean release wheel | fresh venv from downloaded wheel | version 3.6.0, selftest PASS | PASS |
| Lean build | `lake build` | 9768 jobs, standard axioms | PASS |
| Comparator + nanoda | `comparator-check.sh` | `Your solution is okay!`; nanoda accepts | PASS |
| External proof | drat-trim / lrat-check / cake_lpr | DRAT and LRAT verified; CakeML `VERIFIED UNSAT` | PASS |

## v3.7.0 release verification

| Gate | Command / source | Observed | Status |
| :--- | :--- | :--- | :--- |
| Full pytest | `python -m pytest tests/ -q` | 1968 passed, 9 skipped, 1 deselected, exit 0 | PASS |
| OMNIWAVE branch tests | `tests/test_omniwave.py` | 488 passed; JW vs BFS front counts | PASS |
| CTest | `ctest --test-dir build -C Release` | 21/21 | PASS |
| Mutation | `scripts/run_mutation_tests.py` | 54/54 | PASS |
| Web | `npm test`, `npm run build`, `npm run e2e` | 17/17, build, 13/13 | PASS |
| Feature-SHA CI | `gh pr checks 41` | both CI run sets success | PASS |
| Merge-SHA CI | `gh run watch 41192709602` | all jobs success | PASS |
| Production E2E | `E2E_BASE_URL=https://cq-hecs-web.vercel.app npm run e2e` | 13/13; bundle 3.7.0 / 6c18ad7 | PASS |
| Release assets | `gh release download v3.7.0` + SHA-256 | all match `sha256sums.txt` | PASS |
| Clean wheel | fresh venv from downloaded wheel | version/selftest/OMNIWAVE branch PASS | PASS |
