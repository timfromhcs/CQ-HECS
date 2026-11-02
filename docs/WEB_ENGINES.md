# Web engines, delivery and the conformance corpus

What the browser version actually is, what was measured, and what it does not claim.

## The three engines

| Engine | Language | Precision | Where it runs | What it is for |
|---|---|---|---|---|
| `wasm` | Rust → `wasm32-unknown-unknown` (`web/wasm/src/lib.rs`) | f64 | worker thread, `web/src/core.ts` | the exact path: amplitudes, probabilities, Bloch vectors, seeded sampling |
| `webgpu` | WGSL compute (`web/src/gpu.ts`, `web/src/forge/gpu_sha.ts`) | f32 | GPU via the browser's WebGPU | the fast path, used only when an adapter exists and the width fits |
| `cpu` | TypeScript (`web/src/forge/sha.ts`, SAT lab) | exact integer | main thread | fallback and reference for the SHA-256 workbench |

The browser engine is **not** the Python engine. It is an independent implementation; the
only honest statement is that the two agree on a declared common corpus.

## Precision contract

WGSL has no `f64`. The WebGPU path rounds every amplitude to f32, which is about
`1e-7` relative per operation, and the error accumulates over the circuit. Therefore:

- the WebGPU engine may be used for **display and exploration**;
- the **reported exact probabilities and exported run cards come from the WASM f64 path**
  unless the page explicitly labels the result as the f32 GPU path;
- a run is never described as "exact" when the GPU path produced it;
- when no adapter is available, or the device is lost, the page falls back to WASM and
  says so (Playwright covers both cases).

## Conformance corpus

`scripts/export_web_conformance.py` writes `web/tests/fixtures/quantum_conformance.json`
and `web/tests/conformance.test.ts` replays it through the WebAssembly core.

- The reference is a dense NumPy statevector written from the same 2×2 matrices, not the
  Python simulator, so a defect in the browser core shows up as a mismatch.
- The file states the semantics it depends on: qubit `q` is bit `q` of the basis index,
  `ctrl` is a bitmask with `0` meaning no control, matrices are row-major
  `[re00, im00, re01, im01, re10, im10, re11, im11]`.
- Amplitudes are compared, not only probabilities: a uniform distribution hides a phase
  error.
- Tolerance: `1e-12`. Six cases: Bell, GHZ-3, phase interference, a `u3` rotation, a
  controlled phase and a control-direction check.
- One test deliberately breaks a matrix entry and asserts the comparison fails, so the
  corpus cannot pass vacuously.

Regenerate after changing the corpus:

```bash
python scripts/export_web_conformance.py   # Python, from the repository root
cd web && npm test                          # 8 conformance assertions among the suite
```

## Bundle budget

Measured on 2026-11-02, gzip level 9, from `web/dist`:

| Asset class | Transferred | Budget | Note |
|---|---:|---:|---|
| JavaScript total | 233.5 KB | 270 KB | the editor chunk alone is 169.2 KB (CodeMirror) |
| WebAssembly core | 15.0 KB | 18 KB | 35.5 KB uncompressed |
| CSS total | 6.6 KB | 8 KB | — |

`npm run build` runs `scripts/check_bundle_budget.mjs` and fails when a budget is
exceeded. Raising a budget is a decision that needs a reason in the commit message.

## Delivery check (Vercel)

`npm run verify:deploy -- <base-url>` observes the deployed build:

```bash
cd web
npm run verify:deploy -- https://cq-hecs-3au7h073x-hcsmediacorp.vercel.app --via-cli
```

It checks the app shell, a hash route, the three security headers from `vercel.json`, the
wasm MIME type and cache policy, that the wasm body really is wasm, and the transport
sizes.

### Result on 2026-11-02

`10/10 checks passed` against the production deployment of commit `1d38df2`
(`https://cq-hecs-3au7h073x-hcsmediacorp.vercel.app`), observed through `vercel curl`.

**Important caveat, and a finding:** that deployment is protected by Vercel Deployment
Protection. An anonymous request gets Vercel's login page (HTTP 200, `Log in to Vercel`),
which is why the check has to go through the CLI. The script detects that page and exits
with code 3 instead of reporting the app as broken. A bypassed request proves the build is
correct; it does **not** prove the URL is public. Whether the demo should be public is an
owner decision, not something an agent changes on its own.

## What is not claimed

- No speed comparison between WebGPU and WASM is published; that needs a measurement with
  transfer and validation time separated, and it is work package W6 of
  `PLAN_HORIZON_6_WEB.md`.
- No claim that the browser engine equals the Python engine beyond the corpus above.
- No claim about widths that the memory guard refuses.
