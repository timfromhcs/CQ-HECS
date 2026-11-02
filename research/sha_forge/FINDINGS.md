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

## F-13 (2026-11-02) - the hashrate swing is not caused by the research firmware

B-09 recorded a swing between 240 and 425 GH/s (mean 325, stdev 32) on the stock
image during the first 60-minute baseline, with an expected ~434 at 485 MHz /
1100 mV. The stock image has since been replaced twice; the device now runs
`v4.0.2-rc1-sha-research` with the **same** settings (485 MHz, 1100 mV, no limit
raised, no pool change).

A second read-only capture, 30 minutes at 30 s (61 samples, 0 gaps), while the
miner was mining normally:

| Metric | Stock capture (60 min) | Research firmware (30 min) |
|---|---|---|
| Samples | 121 | 61 |
| Mean hashrate | 325 GH/s | **333 GH/s** |
| Stdev | 32 | 29 |
| Range | 240-425 | **271-404** |
| Expected (485 MHz / 1100 mV) | ~434 | ~434 |
| Temperature | 64-65 C | 54-59 C |
| Power | not captured | 10.6-11.1 W |
| Shares accepted / rejected | 537 / 1 | **257 / 0** |

What this supports and what it does not:

- The swing is **not** an artefact of the research firmware: a different build,
  byte-for-byte different from the stock image, shows the same distribution at the
  same clock and voltage.
- The gap to the expected ~434 GH/s is a property of the device or its settings,
  not of the tooling; 0 rejected shares and 0 % ASIC error argue against a
  hardware fault on the share path.
- It does **not** explain the cause. Temperature in the second capture was 6-7 K
  lower (the unit was idle for a while before it), which could raise the clock
  ceiling rather than lower it, so thermal throttling is not an obvious
  explanation either.
- Nothing was tuned to chase it, and B-09 stays open as an observation.

Raw samples: `E:\qCSHA\sha_forge_results\baseline_research_fw\`
(`baseline_20261102T081809Z.jsonl` and its `.summary.json`). Reproduce the summary
with `python scripts/summarise_hashrate.py <capture.jsonl>`.
