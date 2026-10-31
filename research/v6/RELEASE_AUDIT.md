# v6 release audit

**Status:** NOT A RELEASE CANDIDATE (increment 1 only).
**Audited:** 2026-10-31.
**Branch:** `agent/v3.6.0-sat-core`, based on `origin/main` `33723dd`.
**Version:** still `3.5.0`; no tag, no GitHub release, no Vercel production action.

## What this increment contains

- Opt-in two-watched-literal SAT propagation with differential and benchmark
  evidence (`research/v6/evidence/sat_propagation_benchmark.json`).
- SAT contract `1.2` with original/canonical DIMACS digests and duplicate-literal
  normalization.
- Fixes for partial-assignment model checking, certificate budget composition, and
  a Windows Vulkan teardown abort.
- v6 research/state documents under `research/v6/`.

## Gates checked locally

| Gate | Status |
| :--- | :--- |
| L0 repository state | PASS |
| L1 version + compileall | PASS |
| L2 full pytest | PASS: 1758 passed, 6 skipped, 1 deselected, exit 0 (201.16 s) |
| L3 CTest | PASS 21/21 |
| L4 SAT differential/benchmark | PASS (finite suite) |
| L8 web unit/build | PASS (baseline; web code untouched) |
| L6 mutation | PASS 54/54 (watched engine not yet in the mutant list) |
| L7 physical GPU end-to-end | NOT RUN |
| L10 secret/dependency audit | TODO |
| L11 cloud/release | NOT RUN |

## Open blockers

- B-01 Lean/elan not installed.
- B-02 no formally verified proof checker.
- B-03 SAT Competition licensing.
- B-06 Vercel state not re-verified.
- B-07 Windows release artifact not re-downloaded here.

## Decision

No release. Merge/PR/preview/production require the remaining P0/P1 gates,
version decision, docs/claims audit, security audit, clean package install and an
explicit authorization. The current evidence supports only “increment tested
locally”, not “stable release”.
