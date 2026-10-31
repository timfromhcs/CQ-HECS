# CQ-HECS v6 baseline (M0/M1)

**Captured:** 2026-10-31 (Europe/Berlin), before any v3.6 implementation commit.
**Repository:** local checkout of `github.com/timfromhcs/CQ-HECS` (`origin` = `github.com/timfromhcs/CQ-HECS`)
**Work branch:** `agent/v3.6.0-sat-core`, cut from verified `origin/main`
**Plan:** root `PLAN-v3.6.0.md` (supplied plan; pointer in `research/v6/PLAN.md`)

## 1. Exact Git state

| Item | Value |
| :--- | :--- |
| `origin/main` at capture | `33723dda200428d50f0923fa7bccb7726ff88e47` (`Merge pull request #38: v3.5.0 audit`) |
| Local `main` | `488a05c` — stale, 41 commits behind `origin/main`; not used |
| Audit branch | `agent/v3.5.0-audit` = `09467af`; its tree is identical to `origin/main` |
| `v3.5.0` tag | `725d2c35615b9ccf6f7fdc77cf0992bbc890b66c` (`Merge pull request #37: v3.5.0`) |
| Version | `3.5.0` on every checked surface (`python scripts/check_version.py` OK) |
| Worktree before changes | clean except untracked `PLAN-v3.6.0.md` and `.claude/launch.json` |
| Ignored local credentials | `sdk-key-*.json`, `oq.py`, `.local/`, `quantumrings.conf` (all matched by `.gitignore`) |
| CI on `origin/main` | `success` — run `41178394449` (CI), `41178394448` (release no-op) |
| Release | `v3.5.0` published, not draft, 2026-10-31T06:39:49Z |

The audit branch predates the PR #38 merge; because `origin/main` is that merge of the
same tree, the effective baseline tree is unchanged. No user file was reset, cleaned or
overwritten.

## 2. Release artifact check (API metadata)

`gh release view v3.5.0` reports:

| Asset | Bytes | GitHub SHA-256 |
| :--- | ---: | :--- |
| `cqhecs-3.5.0-py3-none-any.whl` | 298,903 | `0bbd84ac…46c94` |
| `cqhecs-3.5.0-windows-x64.zip` | 77,376,589 | `f0ddbeb5…6627a` |
| `cqhecs-3.5.0.tar.gz` | 426,591 | `349e4394…46a05` |
| `cqhecs-sbom.spdx.json` | 1,717 | `cc58efb1…28b67e` |
| `RELEASE_NOTES_v3.5.0.md` | 10,368 | `0ac3a135…8b0ab` |
| `sha256sums.txt` | 360 | `fe51e63e…3a45f6` |

`research/v5/RELEASE_AUDIT.md` records an independent download and recomputation of these
digests. This v6 session did not re-download the 77 MB Windows archive; it re-read the
release metadata and the prior audit. Full asset re-download remains an M12/M14 gate.

## 3. Toolchains on this machine

| Tool | State |
| :--- | :--- |
| OS / CPU | Windows 11 (10.0.26200), AMD Ryzen 7 7735HS, 8 cores / 16 threads |
| Python | 3.14.6, pytest 9.1.1, Hypothesis, coverage, python-sat |
| C++ / CMake | CMake 4.4.0, existing `build/` Release tree |
| Rust | 1.96.0, `wasm32-unknown-unknown` |
| Node / npm | 22.23.1 / 10.9.8 |
| Lean / elan | **not installed** → ETH Lean builds remain `NOT RUN` (B-01) |
| cake_lpr / LRAT-Catcher | **not installed** (B-02) |
| Git / GitHub CLI | authenticated as `timfromhcs`; read/write available |

## 4. Baseline gate results (fresh local runs)

| Gate | Command | Result |
| :--- | :--- | :--- |
| L0 | `git status`, `git log`, `git remote`, `git tag` | PASS (captured above) |
| L1 | `python scripts/check_version.py` | PASS, `3.5.0` on all surfaces |
| L1 | `python -m compileall -q cqhecs tests scripts python_bridge` | PASS (exit 0) |
| L2 | `python -m pytest tests/ -q` | **1617 passed, 6 skipped, 1 deselected** in 190.44 s (log `.local/baseline/pytest-baseline.log`); wrapper reported exit 1, to be rechecked |
| L3 | `ctest --test-dir build -C Release` | **21/21 PASS** in 65.42 s |
| L8 | `cd web && npm test` | **16/16 PASS** |
| L8 | `cd web && npm run build` | PASS (`tsc --noEmit` + Vite build) |
| L7 | Vulkan/WebGPU device run | `NOT RUN` in this session (CTest contract only) |
| L4 | External LRAT/CakeLPR check | `NOT RUN` (B-02) |
| L6 | Mutation suite | `NOT RUN` in this session (CI reports 54/54) |

Linux CI reports 1669 passed / 4 skipped; Windows reports 1573 passed / 50 skipped.
Those are CI observations, not copies of this local run.

## 5. Existing v3.5.0 scope that must not be rebuilt

SAT certification metadata, optional CaDiCaL, in-repo DRAT checker, exact `count_models`,
browser tree-resolution certificates, Blackwell/ETH claim audit, design system, web
provenance export, Playwright/axe CI, and the experimental OMNIWAVE engine. v3.6 work
starts from their contracts and defects.

## 6. Baseline defects found (status in this branch)

1. **Partial-assignment model check (fixed).** `CNF.is_satisfied({})`
   treated an unassigned *negative* literal as true (`False == False`), so a partial
   assignment could appear to satisfy a clause. Regression test added in
   `tests/test_sat_watched.py`.
2. **Original DIMACS bytes were not retained (fixed).** `CNF` now carries
   `original_sha256`; SAT contract `1.2` exposes `formula_original_sha256` next to
   the canonical `formula_sha256`.
3. **Duplicate literals were rejected by Python but accepted by native (fixed).**
   `parse_dimacs` normalizes repeated literals; direct `CNF(...)` stays strict.
4. **Certificate budget could extend the solve deadline (fixed).** The certificate
   budget is capped by the remaining solve deadline; no time left means
   `UNSAT` with `certified=False`.
5. **Windows Vulkan teardown abort (fixed).** `gpu.status()` could terminate the
   process with `0xC0000409` at DLL unload. New `cq_omniwave_shutdown()` + `atexit`
   hook; regression test runs the probe in a fresh process.
6. **No independent mathematical review of the ETH artifacts.** `CLAIMED_REFUTED`
   stays scoped to the source claims; Lean/comparator/nanoda are `NOT RUN`.
7. **Credentials.** The Open Quantum and IBM keys from earlier runs are reported
   valid by the v5 audit and must be rotated by the owner. The ignored local key
   file is not tracked and must never be staged.
8. **`cloudbuild.yaml`** remains `UNVERIFIED_LEGACY`, not a release path.
