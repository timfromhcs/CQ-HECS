# HCS SHA Forge — Findings

- **F-01 (process, mine):** a new test file overwrote an existing, unrelated test file of the same name. Detected through `git status`, restored from Git, renamed. Lesson: check the target path exists before writing; the Write tool's "updated" (vs "created") message is the signal.
- **F-02 (defect, fixed):** tab buttons had `role="tab"` without a `tablist` parent → axe `aria-required-parent` on every tab. Fixed in `forge.html`; E2E axe now clean on all five tabs.
- **F-03 (defect, fixed):** native `max=64` constraint blocked form submission so the localised "rounds" error never appeared. Fixed with `novalidate` and explicit validation.
- **F-04 (observation):** TypeScript 5.9 types `Uint8Array<ArrayBufferLike>` as not assignable to `BufferSource`; casts are limited to the Web Crypto call.
- **F-05 (observation):** the readable TS reference path ran ≈0.115 M compressions/s; the WebGPU path ≈4.6 M/s on one machine in one run. Not a claim (see H-WGPU-02).
- **F-06 (documentation conflict, unresolved):** the venue for the 37-step SHA-256 collision differs between the two ePrint abstracts (see `LITERATURE_MAP.md`).
- **F-07 (limitation):** no bundled WASM SHA module; the WASM tiers are reported unavailable rather than faked.
