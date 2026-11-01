# Test matrix (v4.0.0 candidate)

Environment: Windows 11 Pro 10.0.26200, Python 3.13.13, Node 22.23.1, CMake 4.4.0
(Visual Studio generator), rustc 1.96.0, Vulkan SDK 1.4.357.0. All results are from
this working tree on the feature branch; raw logs in `evidence/`.

| Layer | Command | Result | Evidence |
|---|---|---|---|
| Baseline (v3.7.0 sources + in-flight plan wiring) | `pytest tests/` | 1964 passed, 13 skipped, 1 deselected | `evidence/baseline_pytest.txt` |
| Final Python | `pytest tests/ -rs` | **2503 passed**, 3 failed, 13 skipped, 1 deselected, 2251 subtests | `evidence/final_pytest.txt` |
| The 3 failures | stale pre-v4 native artifacts in the ignored top-level `build/` (`cq_hecs.dll`/`cq_hecs.exe` still 3.7.0) | rerun with `CQ_HECS_BUILD_DIR=build/v4/bin/Release` (fresh 4.0.0 build): `test_c_api`, `test_cli_powershell`, `test_exe_smoke` = 19 passed, 4 skipped (`CQ_HECS_EXE` unset) | this file |
| New unit/oracle tests | `test_execution_plan.py` 23, `test_sat_separator.py` 316, `test_path_d_pauli_observables.py` 203 | all pass | commits 67411cc, f3376b3, e7227f5 |
| Source mutation | `scripts/run_mutation_tests.py` | **60/60 killed** (54 inherited + 6 new) after replacing one *equivalent* mutant | `evidence/mutation_v4.txt` |
| Native | `cmake -B build/v4 ... && ctest -C Release` | **21/21** (rebuilt after the version bump) | `evidence/native_ctest.txt` |
| SPIR-V | `scripts/verify_vulkan_shaders.py` | 13/13 compiled and verified | session output |
| Web unit | `npm test` | 17/17 | `evidence/web_unit.txt` |
| Web build | `npm run build` | exit 0 | `evidence/web_build.txt` |
| Web e2e + axe | `npm run e2e` (local build, Chromium) | 13/13 | `evidence/web_e2e.txt` |
| Lint / hygiene | `flake8 --select=E9,F`, `verify_no_silent_truncation.py`, `check_version.py`, `git diff --check` | clean / PASS / 4.0.0 on all surfaces / clean | session output |
| Wheel | `pip wheel .` -> fresh venv install -> `cq-hecs version`, `analyze --explain`, `sat count --method auto` | PASS from a different cwd | session output |
| Selftest | `cq-hecs selftest --cases 4` | PASS | session output |

## NOT RUN (status `NOT RUN`, never `PASS`)

`python-sat`/CaDiCaL adapter tests (not installed); external DRAT/LRAT/`cake_lpr`
checkers (`CQ_DRAT_TRIM`, `CQ_LRAT_CHECK`, `CQ_CAKE_LPR` unset); Lean/Comparator/
nanoda; ASan/UBSan lanes; Linux/macOS builds; Playwright against a Vercel preview or
production; SBOM and SHA-256 manifest (`generate_sbom_and_checksums.py`, release-time);
Windows package (`package_release.ps1`); sharpSAT/d4 and PauliPropagation.jl
comparisons; `sat_propagation_benchmark.py`/`omniwave_benchmark.py` (unchanged code).
