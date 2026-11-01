# HCS SHA Forge — Baseline (M0)

Recorded 2026-11-01 on the operator's Windows 11 machine. Everything here was observed, not assumed.

## Repositories

| Repository | Branch | HEAD | Tag | Worktree |
|---|---|---|---|---|
| `timfromhcs/CQ-HECS` | `main` (`origin/main` equal) | `423e389` | `v4.0.0` | clean at start |
| `timfromhcs/ESP-Miner` | `master` (`origin/master` equal) | `21f543c` | — | clean at start, **not modified** |
| `timfromhcs/sha256-research-framework` | — | — | — | **not cloned, not audited** (`NOT RUN`) |

Work branch in CQ-HECS: `feat/sha-forge-hardware-lab`, created from `423e389`. No push, no PR.
`git fetch --all` / `ls-remote` were not re-run in this session (`NOT RUN`); the remote refs shown are the cached ones from the last fetch.

## Toolchain observed

Python 3.13.13, Node v22.23.1, cargo 1.96.0, Vite 6.4.5, Playwright 1.64.1 (Chromium present).
Python test deps installed for this work: pytest, hypothesis, numpy, qiskit (declared project dependencies).

## Hardware baseline

| Item | State |
|---|---|
| Live `/api/system/info` read of `timsminer` | DONE — operator supplied the address; hostname, board, ASIC, firmware and partition recorded in `DEVICE_PROFILE.md` |
| 60-minute baseline at 30 s sampling | DONE on the stock firmware: 121 samples, 0 gaps (EVIDENCE_LEDGER E-11) |
| Running partition | `factory` (measured). Flash-encryption / secure-boot state: `NOT RUN` |
| WLAN app-image backup | `NOT RUN` |
| Any flash, OTA, restart, pool or frequency change | **none performed** |

The historical 430–433 GH/s figure is not a baseline (see AGENTBUILD §1.1). A fresh measurement on the exact unit is required first.

## Device scope (operator instruction, this session)

Only `timsminer` may be used. `blackharkminer` and `timminer2` are explicitly excluded. This is enforced in code
(`cqhecs/hardware/miner_capabilities.py`) and tests, not only documented.
The instruction "use blackhark data" is ambiguous and was **not** interpreted as permission to reuse the excluded
unit's identity, MAC/BSSID, wallet or pool user. See `BLOCKERS.md` B-02.

## Existing-document disagreements noted (not resolved by overwriting)

- `ESP-Miner/readme.md` records the v4.0.2-rc1 firmware on `timsminer` as flashed but not yet fully validated.
- `ESP-Miner/GEMINI.md` still lists "Device B … Hostname `blackharkminer`" as the physical device; older than the readme. Left untouched.
- A pre-existing `tests/test_hardware_bridge.py` (quantum hardware-aware bridge, unrelated) exists in CQ-HECS. An early draft of the SHA bridge tests overwrote it by mistake; it was restored from Git (`git checkout --`) and the SHA tests now live in `tests/test_sha_bridge.py`. No content was lost.
