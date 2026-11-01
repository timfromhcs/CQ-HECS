# HCS SHA Forge — Test matrix

Statuses: `PASS`, `FAIL`, `NOT TESTED`, `BLOCKED`, `SIMULATED` (fake or emulated device, not hardware).
Environment: Windows 11, Python 3.13.13, Node v22.23.1, Chromium from the local Playwright install. 2026-11-01.
Full logs: `E:\qCSHA\sha_forge_results\tests\`.

## Executed

| Gate | Result | Detail |
|---|---|---|
| Python, full suite `pytest tests` | PASS | **2570 passed, 109 skipped, 1 deselected, 0 failed** (4 min 45 s). Skips are existing optional-dependency/hardware skips. |
| SHA reference, trace, model | PASS | `test_sha_reference` 29, `test_sha_round_trace` 10, `test_sha_model` 6 |
| Hardware policy | PASS (SIMULATED) | `test_hardware_policy` 28 |
| Bridge, functional | PASS (SIMULATED) | `test_sha_bridge` 16; pre-existing `test_hardware_bridge` 20 unchanged and passing |
| Bridge, adversarial | PASS | `test_sha_bridge_adversarial` 17 (bad `Content-Length`, truncated body, idle sockets, aborted clients, read throttling, garbage) |
| Fuzz / property | PASS | `test_sha_fuzz` 41 (Hypothesis vs `hashlib`, tampered traces, nonce replay, junk identity/telemetry, image truncation and byte flips, restore-target abuse, state-machine random walks) |
| Result bundle | PASS | `test_sha_results` 13 (no identifiers or secrets, gaps stay gaps, malformed lines counted) |
| CI static gates | PASS | `compileall`, `flake8 --select=E9,F` (0), `check_version.py` (all surfaces 4.0.0), `verify_no_silent_truncation.py` |
| Web unit tests `npm test` | PASS | 33 passed (17 existing + 16 new) |
| `tsc --noEmit`, `vite build` | PASS | two entries |
| Playwright + axe | PASS | **40 passed**: 13 existing + 27 new (tabs, validation, export, demo makes no cross-origin request, bridge unreachable, WebGPU-absent fallback, language, keyboard, axe on 5 tabs, no horizontal scroll at 360/768/1280/1920, 8 break tests, measured baseline section, evidence export) |
| Hardware, read-only | MEASURED | identity read and a 60-minute baseline on the stock firmware (EVIDENCE_LEDGER E-09, E-11) |

## Not tested

| Gate | Status | Why |
|---|---|---|
| Flash, OTA, research firmware, restore, ASIC job path | NOT TESTED / BLOCKED | B-03, B-04: no verified restore artifact, no USB access, no ESP-IDF; research firmware does not exist |
| WLAN backup route, backup/restore on a bench unit | NOT TESTED / BLOCKED | not implemented in firmware |
| Flash-encryption / secure-boot state | NOT TESTED | B-01 |
| Any write, malformed request or load against the physical unit | NOT TESTED (deliberate) | a crash of the only unit is not an acceptable test |
| WASM SIMD / scalar SHA modules | NOT TESTED | B-05 |
| WebGPU on other browsers/adapters; Chrome Local Network Access with a LAN host | NOT TESTED | B-07 |
| Native C++ build + CTest, mutation suite, Windows/Linux CI matrix locally | NOT RUN locally | unrelated code paths; remote CI result recorded in EXECUTION_LOG |
| SBOM, licence report, dependency audit | NOT RUN | |
| `sha256-research-framework` audit/replay | NOT RUN | B-06 |
