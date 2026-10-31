# v6 status report — increment 1 (not a release)

**Date:** 2026-10-31
**Branch:** `agent/v3.6.0-sat-core`, based on `origin/main` `33723dd`
**Version:** unchanged at `3.5.0`
**Release status:** not a release candidate; no tag, GitHub release, PR, preview or
production deploy was created.

## 1. Verified baseline

- `origin/main` = `33723dd` (merge of PR #38), CI success `41178394449`.
- `v3.5.0` release is published with the asset digests recorded in
  `research/v5/RELEASE_AUDIT.md`; API metadata was re-read here.
- Local `main` was stale and was not used.
- Untracked user files `PLAN-v3.6.0.md` and `.claude/launch.json` were preserved.

## 2. Changes in this increment

### SAT propagation

- New `_WatchedDPLL` (`solve(..., propagation="watched")`, CLI
  `--engine watched`, Studio and MCP `engine=watched`), with the same decision
  order, polarity and pure-literal rule as the scan engine.
- The certificate path remains the independent scan-based `_CertifyingDPLL`.
- 134 targeted tests, including 120 random differential cases against brute force
  and the scan engine, pigeonhole certificate replay, edge cases, budgets and
  determinism.
- Full benchmark (6 families, 5 repeats) shows 1.04–1.74× scan/watched median
  speedups on this machine with identical decision counts and no verdict or
  certificate failures. Scope: finite, machine-specific.

### Correctness and contracts

- Fixed `CNF.is_satisfied`/`first_unsatisfied`: an unassigned variable is no
  longer treated as `False` (which could satisfy a negative literal).
- SAT contract `1.2`: `formula_original_sha256` next to the canonical
  `formula_sha256`; CLI/MCP/Studio summaries expose both.
- `parse_dimacs` normalizes repeated literals like the native parser; direct
  `CNF(...)` construction remains strict.
- The UNSAT certificate budget is capped by the remaining solve deadline.

### Native / GPU

- Root-caused a Windows `0xC0000409` abort at interpreter exit after
  `gpu.status()`.
- Added C ABI `cq_omniwave_shutdown()` and an `atexit` hook in
  `cqhecs.omniwave.gpu`; rebuilt the native library.
- New fresh-process regression test; `test_studio.py` now exits 0.

## 3. Evidence

- Full local pytest: **1758 passed, 6 skipped, 1 deselected** in 201.16 s, exit 0
  (Windows, Python 3.14.6; the 6 skips are the opt-in exe tests).
- CTest: 21/21 after the native rebuild; shaders 13/13; mutation 54/54 killed
  (the watched engine is not yet in the mutant list — see `TEST_MATRIX.md`).
- `research/v6/TEST_MATRIX.md` — commands and observed statuses.
- `research/v6/evidence/sat_propagation_benchmark.json` — raw benchmark.
- `research/v6/EVIDENCE_LEDGER.md` — claim → artifact mapping.
- `research/v6/BASELINE.md`, `FINDINGS.md`, `DECISIONS.md`, `TASKS.md`.

## 4. Open items / non-claims

- No formal verification of the DRAT/tree-resolution checkers; no Lean build.
- No SAT Competition benchmark set (licensing unresolved).
- No physical GPU end-to-end speedup claim; no live QPU job.
- No web contract-digest parity yet.
- No release authorization, version bump, package build or cloud action.
- P vs NP remains open; this increment does not bear on it.
