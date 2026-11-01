# HCS SHA Forge — Evidence ledger

Trust levels: `MEASURED` (run here, output seen), `REPRODUCED_HERE`, `SOURCE_CLAIM` (read, not reproduced), `SIMULATED`, `NOT_RUN`.

| ID | Claim | Level | Evidence |
|---|---|---|---|
| E-01 | Python SHA-256 reference equals NIST/CAVS vectors, `hashlib` (lengths 0–1000, 300 random messages) and prime-root derived constants | REPRODUCED_HERE | `tests/test_sha_reference.py` (29 tests) |
| E-02 | All 64 rounds satisfy the T1/T2/register-shift equations; replay rejects tampering | REPRODUCED_HERE | `tests/test_sha_round_trace.py` (10 tests) |
| E-03 | TS trace equals Python trace for "abc" (64 and 20 rounds), genesis SHA-256d and a 2-block message | REPRODUCED_HERE | `web/tests/forge.test.ts` against `web/tests/fixtures/sha_traces.json` |
| E-04 | Genesis header SHA-256d = `000000000019d6…e26f` in Python, TS and the browser UI | REPRODUCED_HERE | tests + browser run |
| E-05 | WebGPU kernel self-test passed and matched CPU on 64 blocks of a 65 536 batch (one Chromium/adapter) | MEASURED (single environment) | in-app browser run; browser/adapter versions not recorded |
| E-06 | Bridge fails closed (identity, origin, token, method, size, rate, read-only) | SIMULATED device | `tests/test_sha_bridge.py` (16), `tests/test_hardware_policy.py` (28) |
| E-07 | Bridge reachable from the page only after the connect click; unreachable state is explicit; demo makes no cross-origin request | MEASURED | `web/e2e/forge.spec.ts`, manual run with `--simulate` |
| E-08 | ePrint 2026/232 and 2026/1120 abstracts say what the snapshot says | SOURCE_CLAIM | fetched 2026-11-01, PDFs unread |
| E-09 | `timsminer` identity (hostname, board 201, BM1366, firmware `v4.0.2-rc1-timsminer`, running partition `factory`) | MEASURED | one read-only GET 2026-11-01 |
| E-11 | 60-minute read-only baseline on the **stock** firmware: 121 samples at 30 s, 0 gaps, uptime monotonic, reset reason unchanged; hashrate 240.5–425.2 GH/s (mean 325.1, stdev 32.3), temperature 64–65 °C, power 11.37–11.64 W, RSSI -61…-56 dBm, free heap 7.88–7.90 MB, 536 shares accepted / 1 rejected | MEASURED | raw data in `E:\qCSHA\sha_forge_results\baseline\`; public bundle `web/public/forge/baseline_results.json` (schema `hcs.sha.forge.baseline.v1`, identifier-free, checked by `cqhecs.hardware.results.assert_public_safe`) |
| E-12 | Bridge, SHA, policy and UI survive adversarial and fuzz inputs after the F-08/F-09 fixes | REPRODUCED_HERE | `tests/test_sha_bridge_adversarial.py` (17), `tests/test_sha_fuzz.py` (41), Playwright break tests (8) |
| E-13 | Flash-encryption / secure-boot state, backup, restore, any research firmware, any ASIC-job measurement | NOT_RUN | B-01, B-03, B-04 |
| E-10 | Any ASIC-returned nonce re-verified | NOT_RUN | blocker B-04 |

The ASIC throughput of any unit has **not** been measured here. Historical GH/s figures in the ESP-Miner repo are not evidence for this work.
