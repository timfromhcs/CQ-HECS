# v6/v7 deployments and cloud state

Verified after the v3.7.0 release.

| Surface | Version / SHA | Status | Evidence |
| :--- | :--- | :--- | :--- |
| Source commit (v3.7.0) | `1efa95f` feature commit; tree identical to merge | tagged `v3.7.0` via merge commit | `git ls-remote` |
| PR #41 | head `1efa95f`, base `5d2268f` | merged | https://github.com/timfromhcs/CQ-HECS/pull/41 |
| Merge commit / `origin/main` | `6c18ad7e90f4aa7287505c6353c8f8eba2b279d1` | exact-SHA CI `41192709602` success | `gh run watch` |
| Required CI on feature SHA | `41192014030` (push), `41192032308` (pull_request) | both success | `gh run list` |
| GitHub Release `v3.7.0` | tag `6c18ad7` | published 2026-10-31T10:36:11Z, not draft/prerelease | https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.7.0 |
| Vercel Production | bundle source `6c18ad7`, version `3.7.0` | E2E 13/13 against https://cq-hecs-web.vercel.app | bundle grep + Playwright |
| Release workflow | re-enabled after manual asset upload | disabled only during publication to avoid a second cloud build | `gh workflow list --all` |

## v3.7.0 release assets (independently downloaded and hashed)

| Asset | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `cqhecs-3.7.0-py3-none-any.whl` | 305,682 | `07c561e647755d6806a1af6734f49b3146e13e7aa8c63066d65623bef5475a76` |
| `cqhecs-3.7.0-windows-x64.zip` | 77,384,651 | `3082c1863feb939c639032ccfadd70f34cd430aac6a8ff037754c92afa5ca7f0` |
| `cqhecs-3.7.0.tar.gz` | 442,558 | `f45309f04ac94fe11896bfe853d818f0215ba519bca65765abade0996a97346b` |
| `cqhecs-sbom.spdx.json` | 1,770 | `4353b94b63240e3b1b1f7fd872972c2e4bcaf35728a464308f89e0af16e35bf4` |
| `RELEASE_NOTES_v3.7.0.md` | 3,930 | `6c19335d4633cadd7dce0c1c480cd1d55c635d7b6dcb177c9c2400f1eed613b0` |
| `sha256sums.txt` | 460 | `34c6299f4292f8a6dd51b6d59d5134f712a944d23a64521de57675e7d26d27d7` |

## Previous release (v3.6.0)

Source `cb0c4be`, merge `db300c0`, release assets:
wheel `a4bce352...`, sdist `2560511b...`, Windows zip `61a38682...`,
SBOM `7e235f85...`. Full details remain in the v3.6 release notes and
`research/v6/evidence/`.
