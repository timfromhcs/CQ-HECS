# HCS SHA Forge — Findings

- **F-01 (process, mine):** a new test file overwrote an existing, unrelated test file of the same name. Detected through `git status`, restored from Git, renamed. Lesson: check the target path exists before writing; the Write tool's "updated" (vs "created") message is the signal.
- **F-02 (defect, fixed):** tab buttons had `role="tab"` without a `tablist` parent → axe `aria-required-parent` on every tab. Fixed in `forge.html`; E2E axe now clean on all five tabs.
- **F-03 (defect, fixed):** native `max=64` constraint blocked form submission so the localised "rounds" error never appeared. Fixed with `novalidate` and explicit validation.
- **F-04 (observation):** TypeScript 5.9 types `Uint8Array<ArrayBufferLike>` as not assignable to `BufferSource`; casts are limited to the Web Crypto call.
- **F-05 (observation):** the readable TS reference path ran ≈0.115 M compressions/s; the WebGPU path ≈4.6 M/s on one machine in one run. Not a claim (see H-WGPU-02).
- **F-06 (documentation conflict, unresolved):** the venue for the 37-step SHA-256 collision differs between the two ePrint abstracts (see `LITERATURE_MAP.md`).
- **F-07 (limitation):** no bundled WASM SHA module; the WASM tiers are reported unavailable rather than faked.
- **F-08 (defects, fixed):** the bridge crashed its handler on a negative or non-numeric `Content-Length`, blocked a thread forever on a truncated body, had no connection cap, printed tracebacks for aborted clients and forwarded every `GET /telemetry` straight to the miner. All fixed with regression tests (`tests/test_sha_bridge_adversarial.py`, 17 tests). Details in `E:\qCSHA\sha_forge_results\BREAKAGE_REPORT.md`.
- **F-09 (defect, fixed):** a 1 MB message froze the analyzer page for about 12 s. Input is now capped at 8 KiB with a localised error.
- **F-10 (observation):** hashrate on the stock firmware is unstable over an hour (240–425 GH/s, mean 325 vs expected 434) while temperature, power, ASIC error and heap are flat. Unexplained; see B-09.
- **F-11 (observation):** the unit runs from the `factory` partition. Backup and restore design must not assume the running app lives in `ota_0`/`ota_1`.
- **F-12 (process):** the operator asked for a flash; the safety gate of their own AGENTBUILD document (verified backup first) could not be met on this machine, so no flash was done. Recorded as B-03/B-04 rather than worked around.
