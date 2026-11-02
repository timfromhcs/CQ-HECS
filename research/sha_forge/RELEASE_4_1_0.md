# Release readiness: 4.1.0 (solo)

Written 2026-11-02. This is a **readiness record**, not a published release: tagging
and publishing need the operator. It states exactly what would ship, what is
measured, and what is not supported, so the decision can be made without reading the
whole branch.

## What "solo" means here

One version of CQ-HECS in which the SHA Forge works on its own: the host reference,
the device client, the firmware profile, the campaign and evaluation scripts, the
SAT/reduced-round experiments and the web page — with the matching firmware build
profile. No external service, no account, no network beyond a local miner if one is
present.

## Components in this release candidate

| Area | What ships | Evidence |
|---|---|---|
| SHA reference | `cqhecs/sha` (FIPS 180-4, traces, replay, SHA-256d) | KAT, randomized cross-checks, replay that rejects tampering |
| Device | `cqhecs/hardware` (profile pinning, research client), `scripts/sha_forge_firmware.py`, `scripts/verify_firmware_trace.py` | 32 tests; device traces accepted by `replay()` |
| Device campaign | `scripts/device_research_campaign.py`, `scripts/evaluate_device_traces.py` | 8/8 blocks, 512 rounds re-derived, host C cross-check |
| Research | `cqhecs/sha/preimage_sat.py`, `scripts/sha_round_frontier.py` | 32 tests; frontier table in `SAT_SHA.md` §8 |
| Web | Forge page with scalar SHA-256 WASM, WebGPU kernel with CPU oracle | 39 unit, 41 Playwright, axe |
| Firmware | ESP-Miner branch `feat/timsminer-sha-research-mode` (`07de7e4`) | host tests 84 + 115 + 83 assertions; CI green; flashed over USB and **OTA** |
| Records | `FIRMWARE.md`, `FIRMWARE_BUILD.md`, `DEVICE_RESEARCH.md`, `SAT_SHA.md`, `P_VS_NP_BOUNDARY.md`, `FINDINGS.md`, `BLOCKERS.md` | each states what was read, run or refused |

## Measured, with the numbers that would go into release notes

- Device: 8 blocks, 512 rounds, all accepted by the independent replay **and** by a
  host build of the same C source; digests match the Python reference.
- OTA: `POST /api/system/OTA` → HTTP 200 in 23.2 s, device came back on `ota_0`,
  mining resumed by itself at 393-524 GH/s.
- Reduced-round frontier: preimage with one free word finishes through 16 rounds at
  W=8/16/32 and stops at 17-18 with a 10 s budget; 64-round *verification* takes
  0.99 s because every message bit is fixed.
- Engine choice: watched propagation is 8.6x-16.1x faster than the scan reference on
  these CNFs with identical verdicts.
- OMNIWAVE: 6.5x-8x slower than DPLL on the same instances (same verdicts); it stays
  in the pipeline for the UNSAT side, where its DRAT log is checked in-repo.
- Hashrate: 240-425 GH/s on stock, 271-404 GH/s on the research build at the same
  clock and voltage; cause of the gap to ~434 still unknown (B-09).

## Not supported, and stated as such

- No full SHA-256 break, no 64-round preimage, no collision at any round.
- No ASIC-internal state: the BM1366 returns nonces, and the research surface says
  `asic_access: none`.
- No P vs NP claim; `P_VS_NP_BOUNDARY.md` explains why the experiments here cannot
  produce one.
- No automatic OTA rollback (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE` is off) and no
  OTA authentication beyond the network-range check.
- The browser cannot reach the miner directly (measured, B-07): the loopback bridge is
  required.

## What the release still needs from the operator

1. A decision to tag (the version bump is not in this branch; it is a release
   action, not a code change to sneak in).
2. Confirmation that the ESP-Miner branch should be merged into its own `master`, or
   kept as a branch with the per-device image built locally.
3. Nothing else: local gates and the exact-SHA CI run are recorded in the PRs.

## Deliberately not done in this horizon

- The web panel that would show the device campaign next to the demo fixtures. It is
  UI work with i18n, axe and Playwright obligations, and doing it half-way would put
  an unverified control in front of a user. The data file and the report exist; the
  panel does not.
- A version bump to 4.1.0. See above: it belongs with the tag.
