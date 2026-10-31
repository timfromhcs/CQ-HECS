# v5 baseline (M0)

**Captured:** 2026-10-30, before any change for the next release.

| Item | Value |
| :--- | :--- |
| Repository | `D:/Quantum EMU/CQ-HECS` (`origin` = github.com/timfromhcs/CQ-HECS) |
| Baseline SHA | `dd669602f34aa685e7de3870e89537d1357293d7` = `origin/main` (merge of PR #36) |
| Latest tags | `v3.4.0` → `0ce73f8`, `v3.3.0`, `v3.2.0`, `v3.1.0`, `v3.0.0` |
| Version | `3.4.0` on every surface (`scripts/check_version.py` OK) |
| Work branch | `agent/v3.5.0`, cut from the baseline SHA |
| Dirty state at start | untracked `PLAN.md` (the mission document, kept and committed) and `.claude/launch.json` (local preview config, left untracked) |
| CI on the baseline SHA | `ci.yml` success, `release.yml` success (no-op: tag exists) |
| Open PRs | none |

## Gate evidence carried over (same tree as `v3.4.0` plus the audit doc)

The figures come from `research/v3_4_0/RELEASE_AUDIT.md`. They are measurements on the
tagged tree and are not re-claimed here.

- Linux CI lane: 698 passed, 4 skipped (opt-in exe tests), 1 slow gate deselected;
  branch coverage 83 %; CTest 21/21; source mutation 44/44.
- Web: `npm test` 14/14; production deployment from `0ce73f8`.
- Local Windows: 690 passed, 5 skipped (4 opt-in exe tests; `tests/test_sat_certificates.py`
  needed `python-sat`, which is now installed locally as the pinned `1.9.dev17`).

## Toolchains on this machine

| Tool | State |
| :--- | :--- |
| Python | 3.14.6 (`py -3.14`): pytest, qiskit, PyInstaller, python-sat 1.9.dev17 |
| C++ | MSVC via CMake, `build/` Release, CTest 21/21 |
| Rust | 1.96.0, target `wasm32-unknown-unknown` |
| Node | 22.23.1 / npm 10.9.8 |
| Lean / elan | **not installed**, so the OpenAI and Anthropic Lean builds are `NOT RUN` here |
| drat-trim / cake_lpr | **not installed**; replaced by an in-repo DRAT checker (see DECISIONS.md D-02) |

## Other pipelines

- `cloudbuild.yaml` (Google Cloud Build) is still in the tree. No trigger, IAM binding
  or recent run is visible from this machine. It is **not** the release path: releases come only from
  `.github/workflows/release.yml`. It is kept unchanged and marked `UNVERIFIED_LEGACY`
  in `TASKS.md` (T-M0-05).
- Vercel project `cq-hecs-web` (team hcsmediagroup) is linked to this repository,
  with `web/` as its root. PRs get preview deployments, and `main` deploys to production.

## Historical documents

`GEMINI.md` and `GEMINI_HANDOFF.md` describe the v3.0.0 mission and the v3.2.0 handoff.
Both are superseded (v3.2.0, v3.3.0 and v3.4.0 have shipped since). They are kept for history and
carry a banner that points here (T-M1-03).
