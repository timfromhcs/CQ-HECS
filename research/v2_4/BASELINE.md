# Next-stable baseline (L0)

## Source and live repository

- Baseline locked: 2026-10-29 UTC.
- Local/default branch: `main`.
- Exact local and remote `main` SHA: `ba27bd1e7d814c79b7982ba3a9739f264f054520`.
- Latest stable tag/release: `v2.3.0`, pointing at the same SHA; published 2026-10-29T19:54:03Z, neither draft nor prerelease.
- Release: https://github.com/timfromhcs/CQ-HECS/releases/tag/v2.3.0
- Open pull requests at discovery: none. PR #12 was the latest merged PR.
- Branch protection API: `404 Branch not protected`; repository rulesets: empty list. This is an observation, not permission to push directly to `main`.
- Baseline CI on the exact SHA: https://github.com/timfromhcs/CQ-HECS/actions/runs/40943283508 — SUCCESS (Linux, Windows, Python compatibility, static/package, ASan/UBSan jobs).
- Baseline release pipeline on the exact SHA: https://github.com/timfromhcs/CQ-HECS/actions/runs/40944087829 — SUCCESS.
- Latest manually dispatched Nightly before discovery: https://github.com/timfromhcs/CQ-HECS/actions/runs/40934811223 — SUCCESS on ancestor `21eee7e6b2c9cd55d938c372299627d7f45b6b3c`; this is not evidence for a later source SHA.

## Pre-existing operator work

`git status --short --branch` initially reported only `M GEMINI.md` (`662` insertions, `917` deletions relative to `v2.3.0`). This is the operator-supplied mission document and is preserved without edits. No other modified, staged, or untracked source files were present initially. Generated baseline/build outputs are not source changes.

## Local environment

- OS: Windows 11, `Windows-11-10.0.26200-SP0`; working directory `D:\Quantum EMU\CQ-HECS`.
- Python: CPython 3.14.6, `C:\Program Files\Python314\python.exe`.
- NumPy 2.4.6; Qiskit 2.5.1; Qiskit Aer 0.17.2; Stim 1.16.0; pytest 9.1.1; Hypothesis 6.170.12; coverage 7.16.0.
- CMake 4.4.0; Ninja 1.13.2 available; configured generator/toolchain is the existing Visual Studio/MSBuild setup (MSBuild 17.14.40).
- Git 2.54.0.windows.1; GitHub CLI 2.97.0.
- Vulkan SDK 1.4.357.0; glslangValidator available. The baseline CTest includes `test_vulkan_compute_contract`; device class must be reported separately from shader compilation and is not inferred from the green test alone.
- Python native-required baseline used `CQ_HECS_REQUIRE_NATIVE=1` and loaded the locally built CPython 3.14 native extension.

## Baseline gate snapshot

All results below were executed locally against the baseline source before CQ-HECS source edits. See `TEST_MATRIX.md` and `evidence/` for commands/logs.

- Python: **PASS**, 377 passed in 64.85 s, none skipped in the native-required run.
- Branch coverage: **PASS**, 83% total (`--fail-under=70`); coverage test run 377 passed in 79.43 s.
- Native build and CTest: **PASS**, 19/19 tests, 18.94 s.
- Compileall, fatal flake8 rules, version consistency, silent-truncation audit: **PASS**; version surfaces report 2.3.0.
- Vulkan shader source/SPIR-V verification: **PASS**, 12/12 shaders, zero reported warnings/errors. This does not establish end-to-end simulator GPU acceleration.
- Mutation harness: **PASS**, unmutated 12/12 checks first, then 12/12 mutants killed. Limited to the harness's declared source patches.
- Wheel/sdist build and Twine metadata checks: **PASS** for 2.3.0 artifacts. This baseline build is not a new release candidate.

## OpenAI Math upstream snapshot

- Repository `openai/math`, exact `main` SHA at discovery: `7ef5c0cc5ca4b0e072b7a050fca09ab24bc6fa3a` (commit date 2026-10-26T21:18:03Z).
- Pinned README reports 721 manuscripts in 373 families and approximately 42% of top-line results formalized. These are upstream-reported catalogue counts, not independent proof counts.
- Previous local snapshot (`research/v2_1/openai_math/UPSTREAM_SNAPSHOT.md`) was SHA `1581d4cbdd69a0faf34b2089614fe2a814316a6a`, 719 manuscripts and 372 families: observed delta **+2 manuscripts, +1 family** using the same upstream headline-count definitions.
- Upstream explicitly labels the material raw research data at differing verification stages. Formalization of a neighbouring result is not treated as verification of an implementation or every headline claim.

## Version decision

**NOT YET DECIDED.** `v2.4.0` requires at least one validated backward-compatible feature. A correctness-only result will use the appropriate patch version instead. No version surface has been changed.
