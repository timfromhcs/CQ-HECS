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


---

# V7 section (E3, 2026-11-22): test matrix for 7.0.0 (release candidate)

Append-only: the v4.0.0 matrix above is unchanged and historical. Candidate HEAD `38e799b`; the working tree at
writing has uncommitted Wave E edits, so a row marked "E3 re-run" ran on `38e799b` plus those edits.

Environment of the freeze run (integrator): Windows 11 Pro 10.0.26200, CPython 3.13.13 (pytest 9.2.0, hypothesis
6.170.14), Node 22.23.1, rustc/cargo 1.96.0, CMake 4.4.0, MSVC 19.44, Vulkan SDK 1.4.357, one AMD Radeon iGPU.
CI target is CPython 3.11 with `constraints/ci-py311.txt`; that lane was not run here.

Status values: `PASS`, `FAIL`, `NOT_RUN`, `BLOCKED`. Provenance: `E3 re-run` (executed by E3 in this task),
`freeze-file` (a raw log in the session scratchpad that E3 read; not in the repository), `integrator-recorded`
(`evidence/waveE_E2.md`), `wave` (a Wave A-D evidence file at its own SHA).

## V7.A Gates

| Layer | Command | Result | Provenance | Status |
|---|---|---|---|---|
| Version surfaces | `python scripts/check_version.py` | all surfaces report 7.0.0 | E3 re-run | PASS |
| Silent truncation | `python scripts/verify_no_silent_truncation.py` | no forbidden pattern | E3 re-run | PASS |
| QG doc consistency | `python scripts/qg_doc_consistency.py` | OK | E3 re-run | PASS |
| Doc and language consistency | `pytest tests/test_doc_consistency_v7.py tests/test_readme_languages.py -q` | 81 passed in 3.18 s | E3 re-run | PASS |
| Security scan with history | `python scripts/security_audit.py --history` | 0 secrets in tree, 0 in 343 scanned commits, 0 code findings, 41 workflow `uses:` entries, 0 unpinned | E3 re-run | PASS |
| Full Python suite | `pytest tests/` (Python 3.13.13) | 4269 passed, 134 skipped, 1 deselected, 0 failed, 711.68 s | freeze-file `freeze_pytest.txt`, integrator-recorded | PASS |
| Skip budget on that run | `python scripts/skip_budget.py --junitxml freeze_junit.xml --check` | FAILED: 134 skips against a budget of 105; `CQ_HECS_EXE not set` 6 > 4; unbudgeted reasons: 7x `cq_hecs executable not found (Vulkan build ...)`, 4x `native library cq_hecs.dll not found`, 9x `native library cq_hecs_core.dll not found`, 1x web/Playwright not installed, 1x `optional`, 1x `python-sat not installed`, 4x `qiskit-ibm-runtime not installed` | E3 re-run on the freeze junit file | FAIL |
| Mutation, in place | `python scripts/run_mutation_tests.py` | 95/95 killed (last lines of `mutation_freeze.txt`); the run is dated 07:42, after the `38e799b` commit | freeze-file, integrator-recorded | PASS |
| Web unit | `cd web && npm test` | 167 tests, 167 pass, 0 fail, 7.0 s | E3 re-run (tree at HEAD plus non-web edits) | PASS |
| Web build | `cd web && npm run build` | E3 attempt: `tsc` and Vite started, esbuild ended with `The service was stopped` (cause not diagnosed: a concurrent agent or the command timeout); the freeze log `freeze_web.txt` is also unusable (`tsc` not found because of the invocation, not the repo: `node_modules/.bin/tsc` exists) | E3 attempt inconclusive | NOT_RUN at the candidate by E3 |
| Playwright + axe | `npx playwright test` (chromium, mobile-360, mobile-390) | 128 passed, 1 skipped (WebGPU conformance, no adapter), 0 failed | integrator-recorded; C1 same figure on its tree | PASS (Chromium only) |
| Studio plan UI | `pytest tests/test_studio_plan_ui.py` plus `tests/studio_ui_e2e.mjs` | 6 passed; browser run axe critical+serious 0 | wave D4 at `6260495` | PASS |
| Native CTest, Vulkan ON | `ctest -C Release` (26 tests) | 26/26 | integrator-recorded; A2 and C2 same figure | PASS (one AMD iGPU, MSVC, Windows) |
| Native CTest, CPU-only | `ctest -C Release` with `-DCQ_ENABLE_VULKAN=OFF` (15 tests) | 15/15 | integrator-recorded | PASS |
| SPIR-V shaders | `python scripts/verify_vulkan_shaders.py` | not recorded for 7.0.0 | none | NOT_RUN |
| Lean | `lake build` in `formal/` | `Build completed successfully (8711 jobs)`, exit 0, Lean 4.33.1 | freeze-file `evidence/lean_freeze_build.txt` | PASS (specification lemmas only) |
| Lean axiom audit | `lake env lean scripts/PrintAxioms.lean` | 26 audited lemmas within `propext`, `Classical.choice`, `Quot.sound` | wave D5 at `c098971` | PASS |
| Lint and compile | `flake8 --select=E9,F cqhecs tests scripts python_bridge --count`; `compileall -q cqhecs python_bridge scripts` | 0 findings; compile exit 0 | E3 re-run (HEAD plus Wave E edits) | PASS |
| Wheel / sdist clean-venv | `python -m build`, install, smoke | built at `38e799b` per the integrator; smoke at an earlier base in C2 | integrator-recorded / wave C2 | PASS (build venv, non-admin, temp dir) |

## V7.B Targeted suites by wave (historical SHAs, not re-run)

| Suite | Result | Evidence |
|---|---|---|
| MCP, Studio, parity, schema, CLI (A1) | 203 passed, 14 skipped | `waveA_A1.md` |
| Native hardening pytest twins (A2) | 20 passed; `test_omniwave*` 490 passed; `test_native_cpu_only` 4 passed | `waveA_A2.md` |
| SAT family (A4) | 1314 passed, 58 skipped (19 files); separator 441 passed | `waveA_A4.md` |
| Spec correspondence (A5) | 66 + 269 passed | `waveA_A5.md` |
| Path B/C numerics (B1) | 44 + 94 passed, 1 skipped | `waveB_B1.md` |
| QG (B2, B3) | 261 passed; UI 45 + 34 passed; 14 Playwright | `waveB_B2.md`, `waveB_B3.md` |
| Noise governance (B4) | 15 new; 65 passed, 4 skipped | `waveB_B4.md` |
| Research prototypes (B5) | 85 passed | `waveB_B5.md` |
| Fuzz, property, resource (C5) | 205 passed, 14 xfailed at `51969fd`; xfails removed in D1/D2 | `waveC_C5.md`, `waveD_D2.md` |
| Security fixes (D2) | 182 passed; 798 passed, 15 skipped | `waveD_D2.md` |
| Native Vulkan refusal, release workflow lint (D3) | 7 passed; 16 passed | `waveD_D3.md` |

## V7.C NOT_RUN (never `PASS`)

Clang ASan/UBSan and any UBSan run on Windows (GCC-12 ASan+UBSan ran only on the hosted Linux job, V7.E; locally only MSVC ASan, 9 executables); macOS builds; Vulkan on any GPU other than one AMD iGPU (the lavapipe software ICD ran on the hosted Linux job only); WebGPU f32 beyond the partial E5 run (one AMD RDNA2 adapter, headless Chrome with unsafe flags, 20 cases, worst TV 7.8e-8, `RUN_PARTIAL`); Firefox and WebKit; screen
readers; a clean Windows machine or VM; Python 3.11 (the CI interpreter) and 3.12; the SPIR-V verification script for 7.0.0; the full suite under Python
3.14; `drat-trim`, `lrat-check`, `cake_lpr`; Comparator and nanoda for the Lean lemmas; `gitleaks`, `trufflehog`,
`cargo audit`, `pip-audit -r` over the manifest; sharpSAT/d4 and Pauli-propagation comparisons; any provider or
QPU call (none authorised); the release and nightly workflows on a hosted runner (package.yml and ci.yml ran once on the PR at `38e799b`, V7.E, and are red); the content and SHA of the Vercel preview (a Vercel status check reports success, nothing more); the production deployment; code signing; a published-asset download verification.

## V7.D Open finding from this matrix

The skip-budget gate fails on the freeze run. The skips are environmental (native build directory not exported,
optional extras absent), as `README.md` says, but `SKIP_BUDGET.json` still describes a 105-skip run and the gate
is a stated release condition (AGENTS_V7 21.1.2: no unexplained skip). Fix by running the gate with
`CQ_HECS_BUILD_DIR` set and `qiskit-ibm-runtime`/`python-sat` installed, or by a reasoned update of the budget
file owned by the integrator. Recorded as B-V7-11. E3 did not edit `SKIP_BUDGET.json`.

## V7.E Hosted CI on `38e799b` (read-only `gh` queries, 2026-11-22 08:38 UTC; detail in `evidence/waveE_E3.md`)

This is the only remote evidence for the candidate, and it is red. Provenance: `E3 hosted read`.

| Job (PR #55, head `38e799b`) | Result |
|---|---|
| Static checks and package smoke | PASS |
| Linux C++20 CPU-only | PASS |
| Linux ASan + UBSan native tests (gcc-12, `-fsanitize=address,undefined`) | PASS, 9/9 |
| Linux C++20 Vulkan: CTest on llvmpipe (software ICD) | PASS, 26/26 and 3/3 |
| Linux C++20 Vulkan: full Python suite (3.11) | FAIL: 5 failed, 4413 passed, 35 skipped |
| Python 3.12 / 3.13 / 3.14 compatibility | FAIL each (3.12: 4 failed, 4241 passed, 158 skipped) |
| Web emulator (WASM, unit, build, E2E) | PASS |
| Windows C++20 Vulkan and full Python suite | IN PROGRESS for about 2 h in "Full Python suite" (no result) |
| Wheel and sdist (build, inspect, clean-venv smoke) | FAIL: `studio_health_and_stop`, `OSError [Errno 98] Address already in use` |
| Windows onedir folder (PyInstaller) | PASS |
| Native cq-hecs-cpu and cq-hecs-vulkan (MSVC) | FAIL: CMake "Visual Studio 17 2022 could not find any instance" |
| SHA-256 manifest | SKIPPED (dependencies failed) |
| Vercel preview status | SUCCESS (not compared with the deployed SHA) |

The failing tests are `test_qg_replay` (manifest hash on Linux), two `test_sat_external_isolated` tests (Windows exit
status `0x40000409` against POSIX `9`), `test_web_shared_conformance` fixture integrity (Qiskit version string in the
committed fixture) and, in the 3.11 Vulkan lane, `test_native_cpu_only` (`undefined symbol: cq_core_build_capabilities`).
None of these appears on the Windows freeze run; they are platform or environment sensitive. Recorded as B-V7-15.
