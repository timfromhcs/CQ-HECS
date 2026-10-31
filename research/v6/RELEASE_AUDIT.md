# v3.6.0 release audit

**Decision:** GO — released.
**Released:** 2026-10-31T09:35:24Z
**Source:** `cb0c4be41db5dd077a6d737a9c6f2800883d2153`
**Tag:** `v3.6.0` at the source commit
**Merge:** PR #39 → `db300c0ca38a6821bc6ca614971c555fc59c52d3`
**Release:** https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.6.0
**Production:** https://cq-hecs-web.vercel.app (bundle SHA `db300c0`, version 3.6.0)

## Gates

| Gate | Result |
| :--- | :--- |
| L0 repository/provenance | PASS |
| L1 version + compileall + lint | PASS, `3.6.0` on all surfaces; flake8 E9/F clean |
| L2 full pytest | PASS: 1964 passed, 9 skipped, 1 deselected, exit 0 |
| L2 optional python-sat | 44 tests pass; external exit defect F-09 recorded |
| L3 native build + CTest | PASS 21/21 |
| L4 SAT correctness/proof | PASS: differential, benchmark, DRAT/LRAT/CakeLPR |
| L5 counting prototype | PASS: 204 oracle cases, research-only |
| L6 mutation | PASS 54/54 (watched engine not yet mutated) |
| L7 shaders/Vulkan primitive | PASS 13/13; physical-device primitive parity |
| L8 web unit/build/E2E | PASS 17/17, build, 13/13 local and production |
| L9 Studio/CLI/MCP | PASS targeted tests |
| L10 security/supply chain | PASS secret scan, pip-audit, pinned actions, clean wheel |
| L11 CI on exact source SHA | PASS `41187883783` / `41187860625` |
| L11 merge-SHA CI | PASS `41189243074` |
| L11 Vercel Preview | Ready but auth-protected; unauthenticated E2E blocked |
| L11 Vercel Production | PASS 13/13 E2E against public production |
| L11 release assets | PASS: downloaded and independently hashed |

## Artifact policy

Per the release request, artifacts were built locally and uploaded manually.
The tag-triggered release workflow was disabled during publication so it would
not perform a second cloud build, then re-enabled.

## Assets

| Asset | SHA-256 |
| :--- | :--- |
| wheel | `a4bce3527887425367d500da49a270ba86a4fcf1b69cf02e95b9fb2f8490ad17` |
| sdist | `2560511b2dff273d81f452c7048439e29da43f38994288a76f31ba540683b78d` |
| Windows zip | `61a386829bcf26793fea75694b68668e08b1dc1f064c6849d586a541c2a79671` |
| SBOM | `7e235f858b336b1e0829427ca8991daa5c7ec538d0d20c14121a5cd7fb30240d` |
| release notes | `02ebd1d4c072d2cacf1e9a4d9f6083a2f98fb5f2453040dff002462151ec514f` |
| `sha256sums.txt` | `4fd8399bdded76d335b082e59db1fa1cf9a338e9700bb28913b9357624af22ea` |

## Residual risks

- Vercel Preview authentication blocks unauthenticated preview E2E.
- `python-sat`/CaDiCaL Windows/Python 3.14 exit defect (external).
- Watched engine absent from mutation targets.
- ETH artifacts are not peer-reviewed; only the pinned formal checks were run.
- No SAT Competition benchmark set.
