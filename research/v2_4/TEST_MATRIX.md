# Test matrix and evidence ledger

Statuses are actual outcomes, not intended outcomes. Baseline source SHA: `ba27bd1e7d814c79b7982ba3a9739f264f054520`. Local platform: Windows 11 / CPython 3.14.6 / MSVC, except cloud rows.

| Phase | Gate | Exact command / URL | Status | Result and evidence |
|---|---|---|---|---|
| L0 | Live repository | `git status --short --branch`; `git rev-parse HEAD`; GitHub repo/release/PR/run APIs | PASS | Local=remote `main` at baseline SHA; v2.3.0; no open PRs; `BASELINE.md`. |
| L0 | Worktree inventory | `git status --porcelain=v1 --untracked-files=all`; `git diff --numstat` | PASS | Only pre-existing `GEMINI.md` modification; preserved. |
| L1 | Python compile | `python -m compileall -q cqhecs tests scripts python_bridge` | PASS | Exit 0; `evidence/baseline_compileall.log`. |
| L1 | Fatal Python lint | `python -m flake8 cqhecs tests scripts python_bridge --select=E9,F63,F7,F82` | PASS | Exit 0; `evidence/baseline_flake8.log`. |
| L1 | Version surfaces | `python scripts/check_version.py` | PASS | All report 2.3.0; `evidence/baseline_check_version.log`. |
| L1 | Silent-truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS | `evidence/baseline_no_silent_truncation.log`. |
| L1 | Full Python/native-required | `$env:CQ_HECS_REQUIRE_NATIVE='1'; python -m pytest tests/ -q` | PASS | 377 passed, 64.85 s; `evidence/baseline_pytest.log`. |
| L1 | Branch coverage | `$env:CQ_HECS_REQUIRE_NATIVE='1'; python -m coverage run --branch --source=cqhecs -m pytest tests/ -q`; `python -m coverage report -m --fail-under=70` | PASS | 377 passed; 83% total; `evidence/baseline_coverage_*.log`. |
| L1 | Native configure | `cmake -B build -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON` | PASS | Vulkan SDK 1.4.357 found; `evidence/baseline_cmake_configure.log`. |
| L1 | Native build | `cmake --build build --config Release --parallel` | PASS | `evidence/baseline_cmake_build.log`. |
| L1 | CTest | `ctest --test-dir build -C Release --output-on-failure` | PASS | 19/19, 18.94 s; `evidence/baseline_ctest.log`. Includes primitive Vulkan contract only. |
| L1 | Shader validation | `python scripts/verify_vulkan_shaders.py` | PASS | 12/12 compiled/verified; `evidence/baseline_vulkan_shaders.log`. |
| L1 | Mutation | `python scripts/run_mutation_tests.py` | PASS | Baseline checks 12/12; mutants killed 12/12; `evidence/baseline_mutation.log`. |
| L1 | Package | `python -m build`; `python -m twine check dist/*` | PASS | Wheel and sdist metadata pass; `evidence/baseline_build_package.log`, `baseline_twine.log`. |
| L1 | Clean wheel CLI/JSON smoke | Current repository clean-environment smoke procedure | NOT RUN | Baseline package smoke still required before candidate push. |
| L1 | Benchmark smoke/schema | Current repository benchmark smoke procedure | NOT RUN | Must generate fresh raw output; stored historical JSON is not reused as current evidence. |
| L0 | Baseline GitHub CI | https://github.com/timfromhcs/CQ-HECS/actions/runs/40943283508 | PASS | Exact baseline SHA; all reported jobs successful. |
| L0 | Baseline Nightly | https://github.com/timfromhcs/CQ-HECS/actions/runs/40934811223 | PASS (ANCESTOR SHA) | Exact head `21eee7e6b2c9cd55d938c372299627d7f45b6b3c`; not claimed for baseline/final SHA. |
| L0 | Baseline Release | https://github.com/timfromhcs/CQ-HECS/actions/runs/40944087829 | PASS | Exact baseline SHA; release assets enumerated in `RELEASE_AUDIT.md`. |
| L0 | Physical GPU end-to-end | No documented physical-device full-simulator validation run executed | NOT RUN | No physical-GPU or end-to-end acceleration claim. |
| L0 | Real quantum hardware | Not authorized/required | NOT RUN | Classical emulation only; no hardware result claimed. |

## Candidate gates (source commit `112895a` + documentation, version 2.4.0)

Baseline rows above are for `ba27bd1`; the rows below are fresh runs on the candidate. Platform: Windows 11 / CPython 3.14.6 / MSVC 19.44 / Vulkan SDK 1.4.357. Raw logs in `evidence/candidate_*.log`.

| Phase | Gate | Status | Result |
|---|---|---|---|
| L2 | compileall | PASS | exit 0 |
| L2 | `flake8 --select=E9,F` on `cqhecs python_bridge scripts tests` | PASS | 0 findings (CI now enforces the full `F` set) |
| L2 | `check_version.py` | PASS | all surfaces 2.4.0 |
| L2 | silent-truncation audit | PASS | |
| L2 | pytest, `CQ_HECS_REQUIRE_NATIVE=1` | PASS | **420 passed**, 77.4 s (baseline 377) |
| L2 | branch coverage | PASS | **85 %** (threshold 70) |
| L2 | CTest (Release) | PASS | 19/19 |
| L2 | Vulkan shader validation | PASS | 12/12 (compile/SPIR-V evidence only) |
| L2 | mutation gate | PASS | **14/14 killed** (baseline 12) |
| L2 | wheel + sdist, `twine check` | PASS | `cqhecs-2.4.0` |
| L2 | clean-venv wheel smoke (`version`, `expect`, `run`) | PASS | Bell `YY = -1` via stabilizer; Toffoli adder `1111` |
| L2 | `benchmark smoke` schema | PASS | schema 1.0, version 2.4.0 (timings are not a performance claim) |
| L3 | GitHub CI on the pushed head | see `RELEASE_AUDIT.md` | filled after the run |
| L3 | Nightly on the branch | see `RELEASE_AUDIT.md` | filled after the run |
| - | Physical GPU end-to-end | NOT RUN | |
| - | Real quantum hardware | NOT RUN | |
| - | Web research | BLOCKED | search tool unavailable this session |
