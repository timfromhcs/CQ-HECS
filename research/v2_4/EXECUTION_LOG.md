# Execution log

Append-only chronological record. Times UTC; source SHA is explicit where relevant.

## 2026-10-29 — L0 live discovery

- Read the complete operator-modified `GEMINI.md`; preserved it and all historical audit directories.
- Initial worktree: `main...origin/main`, only `M GEMINI.md`; HEAD and remote `main` both `ba27bd1e7d814c79b7982ba3a9739f264f054520`.
- GitHub CLI already authenticated as `timfromhcs`; no credential value was written to repository files or commands. Existing authentication was used.
- Live release v2.3.0 and its five assets enumerated. No open PRs. Branch protection returned 404 and rulesets returned `[]`; mission still requires a focused branch and PR.
- Latest exact-SHA CI and Release runs are green. Latest green manual Nightly belongs to an ancestor SHA and is labelled accordingly.
- OpenAI Math pinned at `7ef5c0cc5ca4b0e072b7a050fca09ab24bc6fa3a`; README/history/CONTENTS/formalization catalogue retrieved. Recursive Git tree response was truncated, so it is not used to claim a complete independent file count.

## 2026-10-29 — L1 baseline gates

- PASS: compileall, fatal flake8, version, silent-truncation audit.
- PASS: native-required pytest, 377 tests in 64.85 s.
- PASS: branch coverage, 83%, threshold 70; all 377 tests passed.
- PASS: Release native configure/build and CTest, 19/19.
- PASS: 12 Vulkan shader validations. This is compile/SPIR-V evidence, not full simulator GPU evidence.
- PASS: mutation baseline 12/12 checks followed by 12/12 killed mutants.
- PASS: wheel/sdist build and Twine check.
- Raw logs saved under `research/v2_4/evidence/`; details and exact commands in `TEST_MATRIX.md`.

## 2026-10-29 — P0 investigation started

- H0 result-metric composition and H1 MPS numerical-rank semantics are under source/executable investigation before feature work.
- No source fix, version bump, branch, commit, push, merge, tag, or release has yet been performed.

## 2026-10-29 - continuation (second agent)

- Found the predecessor's uncommitted H0/H1 work on `main` (tests 381 passed, one lint failure from an unused `contract_metadata_keys`). Preserved and completed it.
- Randomised differential fuzzing of Paths A/B/C against Qiskit: no mismatches.
- Added exact lowerings (r, iswap, dcx, ecr, cu3, cu, csx, c3x, c4x), `cqhecs/backends/dense_reference.py`, `cqhecs/expectation.py`, `cq-hecs expect`, 14-mutant gate, confidence-bound tests, README example fix.
- Found and fixed: README error example (`AttributeError`), Path D idle-top-qubit width.
- Web search unavailable; GitHub API used for repository metadata; OpenAI Math head unchanged.
- Version 2.4.0 on every surface. Candidate gates: see `TEST_MATRIX.md`.
