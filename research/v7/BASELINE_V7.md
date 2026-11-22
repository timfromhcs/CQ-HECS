# BASELINE_V7.md — current baseline for the V7 mission (2026-11-21)

V7 §1.1 asks for a current `BASELINE.md`. The existing `BASELINE.md` (v4 record) and
`BASELINE_W0.md` (v5.0.0 W0 record) are **not overwritten** (V7 §17.2). This file records the
state V7 work starts from.

## Checkout

- Branch `agent/v6-rc`, base `origin/main` `25e16e5` (merge of PR #54), package version
  `5.0.0` (`python scripts/check_version.py`). Tags up to `v5.0.0` exist.
- `AGENTS_V7.md` adopted as the governing contract (committed on this branch; `DECISIONS.md` D-008).

## Environment (this session)

- Windows 11, Python 3.14.6 (pytest 9.1.1), Node 22.23.1, rustc/cargo 1.96.0.
- Prior W0 record: CMake 4.4.0, Vulkan SDK 1.4.357, Python 3.13.13.
- Not installed / not present: `python-sat` (optional `[sat]`), `lean`/`lake` (no Lean project),
  a real GPU run for end-to-end WebGPU/Vulkan claims.

## Gates (final state on this branch)

| Gate | Command | Result |
|---|---|---|
| Version | `python scripts/check_version.py` | PASS (5.0.0) |
| Truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS |
| QG docs | `python scripts/qg_doc_consistency.py` | PASS |
| Lint / compile | `flake8 --select=E9,F`, `compileall` | clean |
| Python suite | `pytest tests/ -q --junitxml=...` | **2899 passed, 105 skipped, 1 deselected** |
| Skip budget | `python scripts/skip_budget.py --junitxml ... --check` | OK (105 / 11 reasons) |
| Mutation | `python scripts/run_mutation_tests.py` | **64/64 killed** |
| Web unit + build | `cd web && npm test && npm run build` | 77/77; tsc + bundle budget + token contrast green |
| Web e2e | `cd web && npx playwright test` | 42/42 |
| Native CPU-only | `pytest tests/test_native_cpu_only.py` | 4/4 (configure+build+CTest, loader-free, capability) |

## What changed vs the v5.0.0 baseline

Wave 3 honesty fixes (D1–D12) and Wave 4 contracts/hardening; see `WAVE3_REPORT.md` and
`PLAN_COVERAGE.md`. No version bump yet (the bump is V7 W16 / V6 W10-01).

## Known blockers carried into V7

- **W4 (Lean):** no toolchain / no Lean project → NOT_RUN (toolchain install needs network).
- **W10/W14/W17/W18:** require maintainer authorization (provider spend, EXE signing, release).
- **W11 GPU claims:** no real-device end-to-end GPU benchmark in this environment.

## Addendum (A5, 2026-11-21): the 2899/105 vs 2896/109 delta is explained

The full suite on `release/v7-stable` (HEAD `6fe4f01`) was re-run once with `-rs --junitxml`
(2896 passed, 109 skipped, 1 deselected, 459 s) and its skip reasons were compared with
`SKIP_BUDGET.json` (105 / 11 reasons).

| Quantity | Baseline (`agent/v6-rc`) | `release/v7-stable` | Delta |
|---|---|---|---|
| passed | 2899 | 2896 | -3 |
| skipped | 105 | 109 | +4 |
| total collected | 3004 | 3005 | +1 |

- **+4 skips, -4 passes: environment, not a regression.** The four new skips are all
  `qiskit-ibm-runtime not installed (needed for Aer's from_backend oracle)`:
  `test_v3_calibration_bridge.py` lines 291, 306, 352 and `test_v3_noisy_expectation.py` line 292.
  `qiskit-ibm-runtime>=0.40.0` is a declared `[dev]` dependency. The `python` first on PATH in the
  later sessions is **3.13.13**, which lacks it; the baseline ran under **3.14.6**, which has
  `qiskit_ibm_runtime 0.51.0`. Re-running those two files with `py -3.14` gives 33 passed, 0 skipped.
- **+1 passed: a new test.** `tests/test_sha_bridge.py::test_oversized_body_is_consumed_before_the_413`
  was added by `2f0d362` (B-008). 2899 - 4 + 1 = 2896 and 105 + 4 = 109; the 3004 -> 3005 total change
  is that one test.
- No test was deleted, no assertion was weakened, and no other skip reason changed (the other
  ten reasons have identical counts to the budget).
- **Gate consequence.** `python scripts/skip_budget.py --junitxml ... --check` FAILS under 3.13.13
  with `unbudgeted skip reason (4x)`. That is the budget working as intended. Resolve by running the
  gate under the 3.14 interpreter (or installing `qiskit-ibm-runtime` into the 3.13 env), not by
  adding the reason to `SKIP_BUDGET.json`. `SKIP_BUDGET.json` was left unchanged.


## Addendum (E3, 2026-11-22): why the README says 95/95 and this file says 64/64

This file is a baseline: it records the state the V7 work **started** from on `agent/v6-rc` (base `25e16e5`,
version 5.0.0). It is history and is not rewritten. The numbers in the README verification table describe a later
commit and are not in conflict with it. Side by side:

| Quantity | This baseline (`agent/v6-rc`, 5.0.0) | Freeze record (`38e799b`, 7.0.0, integrator-recorded) | Why it differs |
|---|---|---|---|
| Mutation score | 64/64 killed | 95/95 killed, run in place (`mutation_freeze.txt`, last lines read by E3) | C5 added 31 behavioural mutants for the Wave A/B surfaces (service, MCP, Studio guard, calibration v3, MaxSAT, separator preflight, DIMACS/QASM limits). The meta test pins a floor (`>= 64`), not a literal, since D5. The harness never lost a mutant. |
| Python suite | 2899 passed, 105 skipped, 1 deselected | 4269 passed, 134 skipped, 1 deselected, 0 failed (`freeze_pytest.txt`, Python 3.13.13) | the collected count grew from 3,004 to 4,402 selected plus deselected (about 1,400 tests added by Waves A to D); skips rose by 29 (environmental, see below) |
| Web unit tests | 77/77 | 167/167 (E3 re-ran `npm test`: 167 pass) | conformance corpus, run-card import, states, QG logic |
| Playwright | 42/42 | 128 passed, 1 skipped (WebGPU, no adapter) | three projects (chromium, mobile-360, mobile-390), visual and state specs |
| Native | not recorded here (CPU-only pytest 4/4) | CTest 26/26 (Vulkan), 15/15 (CPU-only) | native hardening wave |

The README (EN, DE, FR) quotes the freeze column and labels it "freeze SHA `38e799b`", with the older figures in a
separate, labelled "Historical lane" table. Nobody should read 64/64 here as the current score, nor 95/95 as the
5.0.0 baseline.

Two cautions that belong with the addendum:

- The skip budget does not hold at the freeze. `skip_budget.py --check` against the freeze junit file FAILS (134
  skips against a budget of 105; seven unbudgeted reasons, `CQ_HECS_EXE not set` 6 against 4). The earlier A5
  addendum above explained 4 skips (`qiskit-ibm-runtime` absent on Python 3.13.13); the other new reasons are the
  native build directory not exported and the optional extras absent. Recorded as `B-V7-11` in `BLOCKERS.md`; the
  budget file was not widened.
- The README's "freeze SHA `38e799b`" is correct only while the release candidate is `38e799b`. After any further
  commit the SHA, the three READMEs, `waveE_E2.md` and `tests/test_doc_consistency_v7.py` must change together.

Final candidate SHA: `UNKNOWN` until the integrator freezes it (`RELEASE_CANDIDATE_AUDIT.md`).
