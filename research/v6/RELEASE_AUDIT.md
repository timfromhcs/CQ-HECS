# v3.7.0 release audit

**Decision:** GO — released.
**Released:** 2026-10-31T10:36:11Z
**Source:** `6c18ad7e90f4aa7287505c6353c8f8eba2b279d1` (merge of PR #41)
**Feature commit:** `1efa95f`
**Tag:** `v3.7.0`
**Release:** https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.7.0
**Production:** https://cq-hecs-web.vercel.app (bundle `6c18ad7`, version 3.7.0)

## Gates

| Gate | Result |
| :--- | :--- |
| L0 repository/provenance | PASS |
| L1 version + compileall + lint | PASS, 3.7.0 on all surfaces |
| L2 full pytest | PASS: 1968 passed, 9 skipped, 1 deselected, exit 0 |
| L3 native build + CTest | PASS 21/21 |
| L4 SAT/proof | PASS: differential, DRAT/LRAT/CakeLPR |
| L6 mutation | PASS 54/54 |
| L7 shaders/GPU primitive | PASS 13/13; primitive parity |
| L8 web unit/build/E2E | PASS 17/17, build, 13/13 local + production |
| L9 Studio/CLI/MCP | PASS targeted tests incl. branch policy |
| L10 security/supply chain | PASS prior scan/audit; no new secrets |
| L11 feature-SHA CI | PASS `41192014030`, `41192032308` |
| L11 merge-SHA CI | PASS `41192709602` |
| L11 release assets | PASS: downloaded and independently hashed |

## Artifact policy

Built locally and uploaded manually. The tag-triggered release workflow was
disabled during publication to avoid a second cloud build, then re-enabled.

## Assets

| Asset | SHA-256 |
| :--- | :--- |
| wheel | `07c561e647755d6806a1af6734f49b3146e13e7aa8c63066d65623bef5475a76` |
| sdist | `f45309f04ac94fe11896bfe853d818f0215ba519bca65765abade0996a97346b` |
| Windows zip | `3082c1863feb939c639032ccfadd70f34cd430aac6a8ff037754c92afa5ca7f0` |
| SBOM | `4353b94b63240e3b1b1f7fd872972c2e4bcaf35728a464308f89e0af16e35bf4` |

## Residual risks

- OMNIWAVE speedups are finite tree-size effects; small SAT regressions remain.
- No dedicated mutation targets for the new branch policy.
- Vercel Preview remains auth-protected; Production was tested instead.
- No new QPU/GPU end-to-end work in this release.
