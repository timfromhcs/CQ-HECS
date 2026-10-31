# CQ-HECS v3.6.0 final report

**Release:** `v3.6.0`, published 2026-10-31T09:35:24Z
**Tag / source commit:** `cb0c4be41db5dd077a6d737a9c6f2800883d2153`
**PR / merge commit:** PR #39 → `db300c0ca38a6821bc6ca614971c555fc59c52d3`
**Previous stable:** `v3.5.0` (`725d2c3`)
**Release URL:** https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.6.0
**Production:** https://cq-hecs-web.vercel.app (bundle source `db300c0`, version `3.6.0`)

## 1. What shipped

- Opt-in two-watched-literal DPLL: `solve(..., propagation="watched")`,
  `cq-hecs sat solve --engine watched`, Studio and MCP.
- SAT contract 1.2 with original/canonical DIMACS digests.
- Correct partial-assignment model predicate; repeated-literal normalization;
  certificate deadline cap.
- Windows Vulkan teardown fix (`cq_omniwave_shutdown` + `atexit`).
- Web SAT input/canonical SHA-256 and browser normalization parity.
- External DRAT/LRAT/CakeLPR proof evidence.
- Lean 4.33.1 build + Comparator + nanoda evidence.
- Research-only separator/bucket-elimination counter.
- Docs, changelog, release notes and security policy updated to 3.6.0.

## 2. Local gates (final code)

- Python (without optional python-sat): **1964 passed, 9 skipped, 1 deselected**,
  248.62 s, exit 0.
- Optional python-sat/CaDiCaL: 44 tests pass; the Windows/Python 3.14.6 CaDiCaL
  build exits `0xC0000409` after completion (external F-09).
- CTest 21/21; shaders 13/13; mutation 54/54.
- Web 17/17 unit, 13/13 Playwright + axe locally and 13/13 against production.
- Clean wheel install: version, selftest, `sat solve --engine watched` pass.
- Lean: 9768-job build, standard axioms, Comparator `Your solution is okay!`,
  nanoda accepts.
- Secret scan: no matches; `pip-audit -r requirements.txt`: no known
  vulnerabilities; actions pinned by SHA.

## 3. CI and deployment

- Exact source SHA CI: runs `41187883783` (PR) and `41187860625` (push), success.
- Merge SHA CI: run `41189243074`, all jobs success.
- Release assets uploaded manually from local builds; release workflow was
  disabled during publication to avoid a second cloud build, then re-enabled.
- GitHub release: published, six assets, tag `v3.6.0` at the source SHA.
- Vercel Preview was Ready but is protected by Vercel Authentication; the
  unauthenticated Playwright run cannot pass it. Production is public and passed
  all 13 E2E/axe tests with source SHA `db300c0`.

## 4. Release assets

| Asset | SHA-256 |
| :--- | :--- |
| wheel | `a4bce3527887425367d500da49a270ba86a4fcf1b69cf02e95b9fb2f8490ad17` |
| sdist | `2560511b2dff273d81f452c7048439e29da43f38994288a76f31ba540683b78d` |
| Windows zip | `61a386829bcf26793fea75694b68668e08b1dc1f064c6849d586a541c2a79671` |
| SBOM | `7e235f858b336b1e0829427ca8991daa5c7ec538d0d20c14121a5cd7fb30240d` |

All were downloaded again and independently hashed; they match the release
manifest.

## 5. Known limitations

- No peer review of the OpenAI/Anthropic ETH artifacts; the project reproduced
  the pinned Lean build/Comparator checks but did not prove the paper.
- No SAT Competition 2026 benchmark subset (licence/SHA still unresolved).
- No physical GPU end-to-end circuit-simulation claim; primitive dispatch only.
- No live QPU job in this release.
- `python-sat`/CaDiCaL exit defect on Windows/Python 3.14.6 (F-09).
- Vercel Preview is auth-protected; preview E2E requires a bypass token.
- The watched engine is not yet in the mutation mutant list.

## 6. Non-claims

P vs NP remains open. CQ-HECS has not proved `P = NP` or `P ≠ NP`. The ETH/SETH
sources are *claimed* refutations; this project reproduced their pinned Lean
checks, not an independent mathematical proof. No universal SAT speedup, GPU
acceleration, or QPU capability is claimed.
