# HCS SHA Forge — Final report (this run)

**Verdict: PARTIAL.** Software, break testing, UI and read-only hardware measurement are done and green locally. The operator-requested **flash was not performed**: the verified-backup gate (AGENTBUILD §6) cannot be met on this machine and the research firmware does not exist yet (B-03, B-04).

## 1. Branch and commits

| Repo | Branch | State |
|---|---|---|
| CQ-HECS | `dev/sha-forge-hardware-lab` (local name `feat/sha-forge-hardware-lab`, from `423e389`, tag v4.0.0) | commits listed in `git log`; pushed as the dev branch, see EXECUTION_LOG for the remote CI result on the exact head SHA |
| ESP-Miner | none | unchanged (`21f543c`) |
| sha256-research-framework | none | not touched |

## 2. What was built

- `cqhecs/sha`: FIPS 180-4 reference, 64-round traces (`hcs.sha.trace.v1`, `SOFTWARE_REPLAY`), replay that rejects tampering, nonce candidate replay, typed result contract.
- `cqhecs/hardware`: state machine, timsminer-only allowlist (`blackharkminer`, `timminer2` excluded), telemetry normaliser, backup manifest and restore preview, loopback read-only bridge (hardened by break testing), secret-free result bundle builder.
- `web/forge.html`: Round Analyzer, Miner Lab with a **MEASURED** baseline section kept apart from the **DEMO** fixture, backend probe with WebGPU u32 kernel, Evidence export, EN/DE/FR.
- `scripts/sha_forge_baseline.py` (read-only capture, identity checked per sample) and `scripts/sha_forge_publish_results.py`.
- Results live outside both repositories in `E:\qCSHA\sha_forge_results\` (raw capture, logs, breakage report). Only the identifier-free bundle `web/public/forge/baseline_results.json` is in the repo.

## 3. Hardware: what happened and what did not

| Item | Result |
|---|---|
| Identity read of `timsminer` | done: hostname `timsminer`, board 201, BM1366, `v4.0.2-rc1-timsminer`, running partition `factory` |
| 60-minute baseline, stock firmware | done: 121 samples, 0 gaps; hashrate 240.5–425.2 GH/s (mean 325.1) at 485 MHz / 1100 mV, 64–65 °C, 11.4 W, 0 % ASIC error, 536 accepted / 1 rejected |
| Pool, worker, wallet | unchanged (operator decision) |
| Flash, OTA, restart, restore | **none**, see B-03/B-04 |
| Writes, malformed requests or load against the unit | none (deliberate) |

The miner is in the same firmware state as before this run.

## 4. Break testing

7 real defects found and fixed with regression tests (bridge: bad `Content-Length`, stalled body, connection exhaustion, aborted clients, unthrottled device reads, HTML error pages; analyzer: 1 MB input froze the page). Details: `E:\qCSHA\sha_forge_results\BREAKAGE_REPORT.md`.

## 5. Tests (see TEST_MATRIX.md)

Python 2570 passed / 109 skipped / 0 failed; web unit 33; Playwright 40; CI static gates pass. Not run locally: native CTest, mutation suite, SBOM and licence report.

## 6. Limits and next steps

- To flash: attach `timsminer` by USB (or point to the private backup), approve installing ESP-IDF v6.0.2, then build stock, verify the hash, create the research profile, test restore first.
- WASM SHA module (B-05), Chrome Local Network Access check (B-07), research sprint (B-06) remain open.
- Hashrate instability on the stock firmware (B-09) is unexplained.

## Definition-of-done check (AGENTBUILD §16)

Done: SHA reference vs independent oracles; reproducible 64-round trace; no false round-access claim; bridge loopback-only, paired, allowlisted, schema-validated and break-tested; demo deterministic and labelled; measured data separated and identifier-free; no secrets committed.
Not done: three-repo audit, ASIC candidate verification on real data, research mode, WLAN backup/restore, restored-firmware validation, WASM/WebGPU parity beyond one browser, SBOM/licence gates.
