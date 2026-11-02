# Backend detection: WebGPU, WebAssembly, CPU

`web/src/forge/backends.ts` probes in this order and records why each alternative was rejected:

| Order | Backend | Chosen when | Status in this build |
|---|---|---|---|
| 1 | `WEBGPU` | `navigator.gpu`, adapter and device acquired, WGSL compiles, **self-test equals the CPU reference** (64 and 20 rounds) | implemented; passed in the in-app Chromium |
| 2 | `WASM_SIMD` | SIMD supported **and** a bundled SHA module has a SIMD variant that passes its self-test | **not implemented** — no module bundled (blocker B-05) |
| 3 | `WASM_SCALAR` | bundled scalar module passes its self-test | **not implemented** |
| 4 | `BROWSER_CPU` | TypeScript reference matches known answers | implemented |
| — | `LOCAL_NATIVE` | bridge connected and advertises a native backend | probe only; no native SHA backend ships |
| — | `ASIC_BM1366` | bridge confirms the allowlisted unit **and** a supported job type | never selected as a software fallback; no job type is exposed |
| last | `DEMO_SIMULATED` | everything else failed | always labelled |

A failed shader compile, device loss, thrown error or self-test mismatch falls back visibly with the reason shown in the table.

## Kernel

`web/src/forge/gpu_sha.ts` compresses one 64-byte block per invocation with `u32` arithmetic only (no `f32`), standard IV, 0–64 rounds.
Dispatch is bounded to 65 536 blocks; sizes and rounds are validated before allocation; buffers are destroyed after each batch.
The kernel is **a SHA-256 compression microbenchmark**, not an SHA-256d mining kernel and not ASIC-equivalent.

## Benchmarks

Reported unit: SHA-256 compressions/s (1 block, standard IV, 64 rounds). ASIC GH/s is a different unit and is never plotted on the same axis
without a documented conversion. One run on one machine is an observation, not a result (see `research/sha_forge/HYPOTHESES.md` H-WGPU-02).
