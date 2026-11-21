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

`10/10 checks passed` against the production deployment of commit `e7e5c1e`
(`https://cq-hecs-web.vercel.app`), **anonymously, without `--via-cli`**.

Earlier the same check needed `vercel curl`, because the project was behind Vercel
Deployment Protection: an anonymous request got Vercel's login page (HTTP 200). On explicit
operator request that protection was disabled for this project on 2026-11-02
(`ssoProtection: null`), and the check now observes the real application over the public
alias. The script still detects a protection page and exits with code 3 if it ever appears
again, instead of blaming the application.

The public alias is `https://cq-hecs-web.vercel.app`; `cq-hecs-web-hcsmediacorp.vercel.app`
and `cq-hecs-web-git-main-hcsmediacorp.vercel.app` serve the same build.

### First-visit weight

The entry chunk is `main-*.js` at **104.1 KB raw (39.0 KB gzip)**. The editor is **not**
part of it: `src/main.ts` imports `./editor` dynamically in `ensureEditor()`, so the
`editor-*.js` chunk (502.4 KB raw / 169.2 KB gzip, CodeMirror) is fetched only when the
code lab opens. A Playwright test asserts exactly that: no editor request on `/` and
`#/lab`, and one after `#/code`.

## Reproducible run cards

`#/lab` → *Export* writes `cqhecs-run-<timestamp>.json` with schema
`cqhecs.web.run/1.1`:

| Field | Meaning |
|---|---|
| `app_version`, `source_revision` | version from `scripts/version.py` and the build's commit |
| `input.qasm`, `input.shots`, `input.engine`, `input.noise` | what was run |
| `input.seed` | the sampling seed, chosen by the UI so the card can be replayed |
| `input_digest` | SHA-256 over the exact QASM text in `input.qasm` |
| `engine.kind`, `engine.precision` | `wasm`/`f64` or `webgpu`/`f32` |
| `result` | counts, exact probabilities, amplitudes, Bloch vectors, elapsed time |
| `limitations` | the same non-claim the UI shows |

The Playwright test recomputes the digest in Node, asserts `engine.precision` is `f64` for
a WASM run, and asserts the file contains no bridge URL, BSSID, wallet or token string.

## WebGPU failure handling and fallback (W4-09)

The WebGPU engine is an optional f32 accelerator. `web/src/gpu.ts` races every await on the
device against `device.lost`, so a lost device raises a typed `GpuLossError` instead of
hanging, and a lost engine refuses later runs at once. `web/src/fallback.ts` decides what
happens next:

- A device loss or a GPU error (validation, out of memory) repeats the run on the exact WASM
  f64 core. The result carries `fallback = { from, to, kind, reason }`.
- The fallback is labelled everywhere: a result chip, a line in "What ran", and an extra
  entry in the exported run card's `limits`. The card's `engine.kind` is `wasm` and
  `input.engine_requested` stays `webgpu`, so the swap is visible in the file.
- A deliberate cancellation never falls back. If the fallback also fails, the error names
  both causes and no partial result is produced.
- After a failure the WebGPU option is switched off until the page reloads.

Tests: `web/tests/fallback.test.ts` drives `gpu.ts` through a fake device (loss during a run,
out-of-memory, healthy, adapter missing) and the policy functions. Not covered: a real GPU
loss; no CI lane has a GPU, so the fake device models only what `gpu.ts` calls.

## Resource-limit tests (T6-06)

`fallback.test.ts` covers the low-memory policy (0.25 GiB reported RAM gives 22 qubits;
memory API absent assumes 2 GiB on mobile and 4 GiB on desktop), no WASM core, no WebGPU, and
a failed allocation (`init(30)` returns false and the core stays usable). `e2e/app.spec.ts`
covers a 0.25 GiB device refusing a 24-qubit circuit, a missing memory API, and worker
cancellation: Stop terminates a long 24-qubit run, shows "cancelled", and the next run works
on a fresh worker.

## Composer input (W4-12) and phone viewports (W4-15)

The composer grid is one tab stop. Arrow keys, Home, End, PageUp and PageDown move a cursor
(`composer_nav.ts`, bounded by the grid and 64 columns), Enter or Space places the selected
gate, Delete or Backspace removes the gate under the cursor, Escape cancels a half-placed
multi-qubit gate. Changes are announced in a polite live region. On touch, a tap places a
gate and a long press (550 ms without movement) removes one; the release after a long press
is swallowed so it cannot place a gate back.

Playwright runs `e2e/mobile.spec.ts` in two extra projects, `mobile-360` and `mobile-390`
(Chromium device emulation, touch on). They check horizontal overflow on every route, a
24 x 24 CSS px minimum target size (WCAG 2.2 AA 2.5.8) in the lab, a tapped Bell run, the
touch composer, and axe at phone width. This is emulation, not a physical phone; WebKit and
Firefox are not run.

The main-page output sinks (SAT result, code error, share link, `lang` and route in the URL)
have a hostile-text test in `e2e/app.spec.ts`: no handler attributes, injected images,
dialogs or `window` side effects may appear.

## What is not claimed

- No speed comparison between WebGPU and WASM is published; that needs a measurement with
  transfer and validation time separated, and it is work package W6 of
  `PLAN_HORIZON_6_WEB.md`.
- No claim that the browser engine equals the Python engine beyond the corpus above.
- No claim about widths that the memory guard refuses.
