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

