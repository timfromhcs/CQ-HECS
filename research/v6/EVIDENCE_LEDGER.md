# v6 evidence ledger

Raw evidence is referenced by path and digest where available. Local `.local/`
logs are scratch; committed evidence belongs under `research/v6/evidence/`.

| ID | Claim | Artifact | SHA-256 / result | Verified by |
| :--- | :--- | :--- | :--- | :--- |
| E-001 | `origin/main` is `33723dd` and CI success | `gh run list`, `git rev-parse` | run `41178394449` success | lead, 2026-10-31 |
| E-002 | v3.5.0 release assets have the recorded digests | `gh release view v3.5.0 --json assets` | 6 assets; see `BASELINE.md` | lead + v5 audit |
| E-003 | Baseline pytest | `.local/baseline/pytest-baseline.log` | 1617 passed, 6 skipped, 1 deselected, 190.44 s | lead |
| E-004 | Baseline CTest | `.local/baseline/ctest-baseline.log` | 21/21 passed, 65.42 s | lead |
| E-005 | Baseline web unit tests | `.local/baseline/web-test-baseline.log` | 16/16 passed | lead |
| E-006 | Baseline web build | `.local/baseline/web-build-baseline.log` | tsc + Vite build OK | lead |
| E-007 | Partial-assignment defect | `tests/test_sat_watched.py` | regression passes; old predicate returned True | lead |
| E-008 | Watched engine differential | `tests/test_sat_watched.py` | 134/134 pass | lead |
| E-009 | Exhaustive 3-var check | scratch generator | 27,405 formulas, no mismatch | lead |
| E-010 | Quick propagation benchmark | `.local/baseline/sat-propagation-quick.json` | 4 families, 0 failures | lead |
| E-011 | Full propagation benchmark | `research/v6/evidence/sat_propagation_benchmark.json` | 6 families, 0 failures, 5 repeats, 1.04–1.74× scan/watched | lead |
| E-012 | CLI watched engine contract | `tests/test_cli_contract.py` | 33/33 pass, `engine=dpll-watched` | lead |
| E-013 | Studio watched engine contract | `tests/test_studio.py` | 16/16 pass, clean exit | lead |
| E-014 | Vulkan exit crash fixed | `tests/test_omniwave_gpu_shutdown.py`, `src/cq_hecs_api.cpp`, `cqhecs/omniwave/gpu.py` | fresh process exit 0; CTest 21/21 after rebuild | lead |
| E-015 | SAT contract 1.2 + duplicate normalization | `tests/test_sat_soundness.py`, `tests/test_cli_contract.py` | original/canonical digests distinct; parser normalizes `1 1 0` | lead |
| E-016 | Full suite after changes | `.local/v36/pytest-final3.log` | 1758 passed, 6 skipped, 1 deselected, 201.16 s, exit 0 | lead |
| E-017 | Shader verification after native rebuild | `.local/v36/shaders.log` | 13/13 compiled and validated | lead |
| E-018 | Source mutation suite | `.local/v36/mutation.log` | 54/54 killed, exit 0 (watched engine not yet in the mutant list) | lead |

## Evidence rules

- A hash is not a proof of correctness; it binds the artifact to a claim.
- Timing evidence includes machine, Python version, seeds and repeat count.
- `NOT RUN`, `BLOCKED` and `UNKNOWN` are recorded explicitly.
- Do not commit logs that contain credentials, tokens or private paths.
