# CQ-HECS Release Notes

**Version:** 3.7.0
**Release date:** 2026-10-31
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to `dist/RELEASE_NOTES_v3.7.0.md`,
> prepends the exact source commit and required CI run, and appends the SHA256
> values of the final assets.

---

## 0. What v3.7.0 adds

`v3.7.0` is an additive minor release focused on the experimental OMNIWAVE
engine and the product surfaces that expose it.

1. **Structure-aware OMNIWAVE branching.** `branch="auto"` uses a
   Jeroslow-Wang score over open clauses on pigeonhole/random formulas and keeps
   the BFS order on parity-heavy formulas. Pigeonhole fronts fall 777 → 239
   (13.7× wall on the full suite); random-30/40 UNSAT fronts fall 135–241 → 29–53.
   Some small SAT cases regress because scoring costs more than the saved fronts;
   `--branch bfs` preserves the previous behavior. No verdict or proof change.

2. **Branch policy everywhere.** Python `OmniwaveConfig.branch`, CLI
   `--branch auto|jw|bfs`, MCP `branch`, and the Studio OMNIWAVE selector. The
   live config and snapshot report the selected policy.

3. **Studio OMNIWAVE polish.** Runs that finish between tick boundaries now
   always leave a final timeline sample, so the chart is never empty on fast
   instances.

4. **Web SAT provenance.** The SAT lab can download the full result as JSON
   (input/canonical SHA-256, engine, counts/model, diagnostics) in addition to
   the existing on-screen evidence line.

5. **Version and docs.** All surfaces report `3.7.0`; the README, changelog,
   API reference and Studio guide describe the branch policy and its limits.

## 1. Evidence

Local candidate (Windows 11, AMD Ryzen 7 7735HS, Python 3.14.6):

- Python: **1968 passed, 9 skipped, 1 deselected**, exit 0.
- CTest: 21/21.
- Mutation: 54/54 killed (OMNIWAVE branch code is covered by
  differential/front-count tests, not yet by a dedicated mutant).
- Web: 17/17 unit, 13/13 Playwright + axe.
- OMNIWAVE quick/full raw data:
  `research/v6/evidence/omniwave_branching_auto_quick.json` and
  `omniwave_branching_full.json`; summary in
  `research/v6/evidence/OMNIWAVE_BRANCHING.md`.

## 2. Honest limits

- OMNIWAVE remains experimental; it is not a CaDiCaL replacement and no
  complexity/ETH/P-vs-NP claim follows from these measurements.
- The UNSAT speedup is a tree-size effect on the measured families; small SAT
  instances can be slower.
- The old BFS behavior remains available with `--branch bfs`.
- No new QPU job, no physical-GPU end-to-end circuit claim, no peer review of
  the ETH artifacts.

## 3. Upgrade notes

- New optional field: `OmniwaveConfig.branch` (default `auto`); existing callers
  are unaffected.
- New CLI flag: `cq-hecs sat solve --engine omniwave --branch auto|jw|bfs`.
- Studio API accepts `branch` in `/api/omniwave/start`.
- No public result field or command was removed.

## 4. Historical releases

- `v3.6.0` added watched-literal SAT propagation, SAT contract 1.2, external
  DRAT/LRAT/CakeLPR evidence and the Windows Vulkan teardown fix.
- `v3.5.0` introduced proof-carrying SAT, exact #SAT, the ETH audit, web E2E and
  the experimental OMNIWAVE engine.
- Older notes remain in `CHANGELOG.md` and the GitHub release history.
