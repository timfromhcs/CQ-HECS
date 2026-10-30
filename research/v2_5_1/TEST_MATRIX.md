# CQ-HECS v2.5.1 Test Matrix

Baseline SHA: `a94ffb8`. Candidate: the commit on branch
`claude/beautiful-rubin-3hcoym` that adds this file (local runs below were made
on that working tree before committing; exact-SHA cloud results are listed in
§2 once they exist).

Environment: Linux x64, CPython 3.13.17, pinned `constraints/ci-py311.txt`,
GCC 13.3.0, CMake 3.28.3, Mesa llvmpipe (software Vulkan ICD).

## 1. Local gates

| Level | Gate | Command | Baseline | Candidate |
|---|---|---|---|---|
| L1 | Compile | `python -m compileall -q cqhecs tests scripts python_bridge` | — | PASS |
| L1 | Fatal lint | `flake8 cqhecs tests scripts python_bridge --count --select=E9,F` | — | PASS (0) |
| L1 | Versions | `python scripts/check_version.py` | PASS (2.5.0) | PASS (all 2.5.1) |
| L1 | Silent truncation | `python scripts/verify_no_silent_truncation.py` | — | PASS |
| L1 | Package | `python -m build`; `twine check` | — | PASS (wheel 150956 B, sdist 219846 B) |
| L1 | Clean-venv smoke | wheel in fresh venv: `version`, `doctor`, `profile list`, `--format json run name:bell [--profile fake_manila]` | — | PASS |
| L2 | Shaders | `python scripts/verify_vulkan_shaders.py` | 12/12 | 12/12 |
| L2 | CTest | `ctest --test-dir build --output-on-failure` (GCC Release) | 19/19 | 19/19 |
| L3 | Python suite | `CQ_HECS_REQUIRE_NATIVE=1 coverage run --branch --source=cqhecs -m pytest tests/ -q` | 452 passed | 470 passed, 0 skipped |
| L3 | Branch coverage | `coverage report --fail-under=70` | 84 % | 85 % (`noisy_density_matrix.py` 89 %) |
| L4 | Independent differential | `tests/test_noisy_density_matrix_contract.py` on v2.5.0 code | 60 failed / 10 passed | 18/18 tests pass |
| L5 | Mutation | `python scripts/run_mutation_tests.py` | 16/16 | 20/20 killed, baseline clean |
| L7 | Real QPU | — | NOT RUN (no authorization, no provider) | NOT RUN |
| L6 | Benchmarks | — | NOT RUN | NOT RUN (fix-only release, no performance claim) |

Published-artifact checks: v2.5.0 assets re-hashed (BASELINE.md §2); the
v2.5.0 wheel reproduces CQ-V251-01 in a clean venv.

## 2. Cloud gates (exact SHA)

Candidate SHA `777a66f73ec953f576151e16bcab7351398d4f32` (PR #15):

- push run https://github.com/timfromhcs/CQ-HECS/actions/runs/40981978372 — success
- pull_request run https://github.com/timfromhcs/CQ-HECS/actions/runs/40982014830 — success, 7/7 jobs:

| Job | Conclusion |
|---|---|
| Static checks & package smoke (Python 3.11) | success |
| Linux C++20, Vulkan & full Python suite (CTest, software-ICD dispatch, coverage, mutation gate) | success |
| Windows C++20, Vulkan & full Python suite (CTest, mutation gate) | success |
| Linux ASan + UBSan native tests | success |
| Python 3.12 / 3.13 / 3.14 compatibility (no native) | success ×3 |

This commit only adds the table above; it changes no code and is re-tested by
its own CI run.
