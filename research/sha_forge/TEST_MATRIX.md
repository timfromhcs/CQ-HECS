# HCS SHA Forge — Test matrix

Statuses: `PASS`, `FAIL`, `NOT TESTED`, `BLOCKED`, `SIMULATED` (fake or emulated device, not hardware).
Environment: Windows 11, Python 3.13.13, Node v22.23.1, Chromium from the local Playwright install. 2026-11-01.

## Executed

| Gate | Result | Detail |
|---|---|---|
| Python, full suite `pytest tests` | PASS | 2499 passed, 109 skipped, 1 deselected, 0 failed (≈4 min). Skips are existing optional-dependency/hardware skips (e.g. optional SAT adapter, external proof tools); the number was not compared to the v4.0.0 baseline run, which was not re-run on `main` separately. |
| Python SHA tests | PASS | `test_sha_reference` 29, `test_sha_round_trace` 10, `test_sha_model` 6 |
| Python hardware policy | PASS (SIMULATED) | `test_hardware_policy` 28 |
| Python bridge | PASS (SIMULATED) | `test_sha_bridge` 16; pre-existing `test_hardware_bridge` 20 still passes |
| flake8 `E9,F` on new Python | PASS | after removing one unused import |
| `compileall` on new packages | PASS | |
| Web unit tests `npm test` | PASS | 33 passed (17 existing + 16 new incl. cross-language trace equality, backend fallback matrix, demo determinism) |
| `tsc --noEmit` | PASS | strict, includes `@webgpu/types` |
| `vite build` | PASS | two entries (`index.html`, `forge.html`) |
| Playwright + axe | PASS | 30 passed: 13 existing + 17 new (tabs, analyzer validation, export, demo has no cross-origin request, bridge unreachable, WebGPU-absent fallback, language, keyboard, axe ×5 tabs, no horizontal scroll at 360/768/1280/1920) |
| Manual browser run | PASS | analyzer, genesis check, WebGPU self-test and batch, bridge `--simulate` end-to-end (`CONNECTED_READ_ONLY`) |

## Not tested

| Gate | Status | Why |
|---|---|---|
| Anything on the physical `timsminer` (identity, 60-min baseline, telemetry, ASIC jobs) | NOT TESTED | no operator-approved device access (B-01) |
| WLAN backup route, backup/restore on a bench unit, OTA guards | NOT TESTED / BLOCKED | not implemented in firmware (B-03) |
| Research firmware, host-simulator ASIC job tests, QEMU/Unity | NOT TESTED / BLOCKED | not built (B-04); ESP-Miner untouched |
| WASM SIMD / scalar SHA modules | NOT TESTED | not implemented (B-05) |
| WebGPU on other browsers/adapters, device loss on real hardware | NOT TESTED | one Chromium/adapter only; loss/failure paths covered with mocks |
| Chrome/Edge Local Network Access with a LAN host | NOT TESTED | B-07 |
| Cross-implementation vs OpenSSL, secworks RTL | NOT TESTED | hashlib/node:crypto/Web Crypto used instead |
| Native C++ build + CTest, mutation suite, ESP-Miner CI | NOT RUN | unrelated to this change set; not re-run |
| Remote GitHub CI, Vercel preview | NOT RUN | nothing pushed (B-08) |
| SBOM, licence report, dependency audit | NOT RUN | |
| `sha256-research-framework` audit/replay | NOT RUN | B-06 |
