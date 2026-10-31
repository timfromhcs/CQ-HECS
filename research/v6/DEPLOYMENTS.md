# v6 deployments and cloud state

Verified after the v3.6.0 release.

| Surface | Version / SHA | Status | Evidence |
| :--- | :--- | :--- | :--- |
| Source commit | `cb0c4be41db5dd077a6d737a9c6f2800883d2153` | tagged `v3.6.0`; exact artifacts built from it | `git rev-parse`, release target |
| PR #39 | head `cb0c4be`, base `33723dd` | merged | https://github.com/timfromhcs/CQ-HECS/pull/39 |
| Merge commit / `origin/main` | `db300c0ca38a6821bc6ca614971c555fc59c52d3` | exact-SHA CI `41189243074` success | `gh run watch` |
| Required CI on source SHA | `41187883783` (pull_request), `41187860625` (push) | both success | `gh run list` |
| GitHub Release `v3.6.0` | tag `cb0c4be` | published 2026-10-31T09:35:24Z, not draft/prerelease | https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.6.0 |
| Vercel Preview (PR #39) | deployment `8b9DbQxWC8Bu5LYU1ZH5cpkdqVwc` | Ready, but protected by Vercel Authentication; unauthenticated Playwright cannot access it | Vercel comment / login page |
| Vercel Production | bundle source `db300c0`, version `3.6.0` | E2E 13/13 against https://cq-hecs-web.vercel.app | bundle grep + Playwright |
| Release workflow | re-enabled after manual asset upload | disabled only during publication to avoid a second cloud build | `gh workflow list --all` |

## Release assets (independently downloaded and hashed)

| Asset | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `cqhecs-3.6.0-py3-none-any.whl` | 304,489 | `a4bce3527887425367d500da49a270ba86a4fcf1b69cf02e95b9fb2f8490ad17` |
| `cqhecs-3.6.0-windows-x64.zip` | 77,383,523 | `61a386829bcf26793fea75694b68668e08b1dc1f064c6849d586a541c2a79671` |
| `cqhecs-3.6.0.tar.gz` | 440,828 | `2560511b2dff273d81f452c7048439e29da43f38994288a76f31ba540683b78d` |
| `cqhecs-sbom.spdx.json` | 1,770 | `7e235f858b336b1e0829427ca8991daa5c7ec538d0d20c14121a5cd7fb30240d` |
| `RELEASE_NOTES_v3.6.0.md` | 7,034 | `02ebd1d4c072d2cacf1e9a4d9f6083a2f98fb5f2453040dff002462151ec514f` |
| `sha256sums.txt` | 460 | `4fd8399bdded76d335b082e59db1fa1cf9a338e9700bb28913b9357624af22ea` |

The downloaded hashes match the uploaded `sha256sums.txt` and GitHub asset
digests. `audit/release_tracking.json` is a local generated record; the release's
authoritative manifest is the published `sha256sums.txt`.
