# Wave A, agent A3: web (W4-09, W4-12, W4-14 remainder, W4-15, T6-06)

Worktree branch release/v7-stable. Nothing committed by this agent.

## Commands and results

| Command (cd web) | Result |
|---|---|
| `npx tsc --noEmit` | clean |
| `npm test` | 91 tests, 91 pass, 0 fail (new file `tests/fallback.test.ts`; the i18n parity test still passes with 9 new keys per language) |
| `npm run build` | bundle budget passed (8 files), token contrast OK |
| `npx playwright test` | 63 passed, 0 failed, about 1.2 min |

Playwright counts: desktop project `chromium` runs `app.spec.ts` and `forge.spec.ts`; the new
projects `mobile-360` and `mobile-390` run only `e2e/mobile.spec.ts` (7 tests each).

## Defects found by the new tests and fixed (root cause, fix)

1. Phone width 360, `#/compare`: 13 px horizontal overflow from the device-profile table.
   Fix: table wrapped in a focusable scroll region (`.table-wrap`, `role=region`).
2. Phone width 360, `#/guide`: axe `scrollable-region-focusable` on a code block.
   Fix: guide `pre` blocks get `tabindex=0`.
3. Own regression caught before it shipped: re-rendering the composer on focus swallowed the
   mouse click (the SVG was replaced between mousedown and mouseup). Fix: the cursor is always
   drawn and shown by CSS `:focus-visible`; no render on focus.
4. Touch long-press erase placed the gate straight back (the release became a click on the
   emptied cell). Fix: that one click is swallowed.
5. Latent: `splice(indexOf(p), 1)` with a missing gate would remove the last gate; the erase
   path now checks the index.

## What was added

- `web/src/fallback.ts`, `gpu.ts` (device.lost race, `GpuLossError`, `isLost`),
  `engine.worker.ts` (WebGPU run falls back to WASM, labelled), `protocol.ts` (`fallback`,
  `gpu-failed`), `main.ts` (chip, provenance line, run-card limit, option disabled).
- `web/src/composer_nav.ts`, `composer.ts` (keyboard cursor, live region, long press), CSS.
- `web/e2e/mobile.spec.ts`, config projects, main-page XSS test, keyboard composer tests,
  cancellation, low-memory and memory-API-absent tests in `e2e/app.spec.ts`.
- Docs: `docs/WEB_ENGINES.md` (three new sections).

## NOT RUN / limits

- No real GPU loss was exercised: the machine reports "No available adapters" in headless
  Chromium, so WebGPU fallback is covered by a fake device (unit) only. The worker path that
  calls `runWithFallback` has no browser-level test, because an init script does not reach a
  Worker global.
- Mobile projects are Chromium emulation (Pixel 7 profile with a custom viewport), not WebKit
  or a physical phone. Long press uses CDP touch events.
- Screen-reader behaviour of the live region was not tested with a real reader; axe passes.
- `docs/CONFORMANCE.md` and `docs/WEBGPU_WASM_BACKENDS.md` were not changed (no claim there
  changed).
- Full Python suite not run (out of scope).
