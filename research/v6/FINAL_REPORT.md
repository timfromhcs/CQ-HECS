# CQ-HECS v3.7.0 final report

**Release:** `v3.7.0`, published 2026-10-31T10:36:11Z
**Tag / source commit:** `6c18ad7e90f4aa7287505c6353c8f8eba2b279d1`
**Feature commit / PR:** `1efa95f` / PR #41
**Previous stable:** `v3.6.0` (`cb0c4be`)
**Release URL:** https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.7.0
**Production:** https://cq-hecs-web.vercel.app (bundle source `6c18ad7`, version `3.7.0`)

## 1. What shipped

- OMNIWAVE `branch` policy: `auto | jw | bfs` in Python, CLI, MCP and Studio.
  `auto` uses Jeroslow-Wang on pigeonhole/random formulas and keeps BFS on
  parity-heavy formulas.
- Measured UNSAT reductions on the full suite: pigeonhole 777 → 239 fronts
  (13.67× wall), random-30/40 UNSAT 2.73–7.96×, planted-120 170× tree-size
  effect. Parity unchanged. Some small SAT cases regress; `--branch bfs` keeps
  the old behavior.
- Studio: branch selector, branch in live config/snapshot, final timeline sample
  for fast runs.
- Web SAT lab: downloadable JSON result with input/canonical SHA-256, engine and
  result.
- Version/docs/changelog/release notes updated to `3.7.0`.

## 2. Verification

- Python: **1968 passed, 9 skipped, 1 deselected**, exit 0.
- CTest: 21/21; mutation: 54/54.
- Web: 17/17 unit, 13/13 Playwright + axe locally and against Production.
- Exact feature-SHA CI: `41192014030` and `41192032308`, both success.
- Merge-SHA CI: `41192709602`, all jobs success.
- Release assets were downloaded again and match `sha256sums.txt`.
- Clean wheel install: version, selftest, OMNIWAVE `--branch jw` pass.

## 3. Assets

| Asset | SHA-256 |
| :--- | :--- |
| wheel | `07c561e647755d6806a1af6734f49b3146e13e7aa8c63066d65623bef5475a76` |
| sdist | `f45309f04ac94fe11896bfe853d818f0215ba519bca65765abade0996a97346b` |
| Windows zip | `3082c1863feb939c639032ccfadd70f34cd430aac6a8ff037754c92afa5ca7f0` |
| SBOM | `4353b94b63240e3b1b1f7fd872972c2e4bcaf35728a464308f89e0af16e35bf4` |

## 4. Limitations and non-claims

- OMNIWAVE remains experimental, not a CaDiCaL replacement or a complexity claim.
- The speedups are finite, machine-specific tree-size effects; small SAT cases
  can be slower.
- No new QPU job, physical-GPU end-to-end circuit claim, or ETH peer review.
- The watched engine and OMNIWAVE branch code are not yet dedicated mutation
  targets; they are covered by differential/front-count tests.
- P vs NP remains open. CQ-HECS has not proved `P = NP` or `P ≠ NP`.
