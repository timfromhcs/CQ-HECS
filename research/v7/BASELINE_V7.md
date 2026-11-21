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
