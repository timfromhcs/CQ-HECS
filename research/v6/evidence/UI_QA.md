# Web UI / accessibility QA (M10)

**Date:** 2026-10-31
**Build:** `web/` from this branch, `npm run build` (Vite 6.4.5, TypeScript 5.9.3)
**Runner:** `npm run e2e` (Playwright 1.64, Chromium, built-in `vite preview`)

## Result

13/13 E2E tests passed, including:

- every route renders and deep links survive a reload; console clean;
- EN/DE/FR switch;
- Bell run, provenance panel, JSON export download;
- WebGPU-unavailable fallback (WASM still runs);
- safe-limit refusal for an oversized circuit;
- SAT lab: checked UNSAT certificate, verified SAT model, exact #SAT count,
  and the new input/canonical SHA-256 line;
- no horizontal overflow at 360×800, 390×844, 768×1024, 1280×800, 1440×900,
  1920×1080;
- axe scan: no critical or serious violations on the main views.

## Screenshots retained

Representative captures are committed under `research/v6/evidence/screenshots/`:

- `mobile-360-home.png`
- `mobile-390-sat.png`
- `tablet-768-lab.png`
- `desktop-1280-home.png`
- `desktop-1440-guide.png`
- `desktop-1920-sat.png`

The full 24-shot matrix remains in the local `web/e2e-results/screenshots/`
directory and is uploaded as a CI artifact.

## Scope and non-claims

- The browser engine is its own WASM f64 / WebGPU f32 implementation, not the
  Python A–D router.
- WebGPU unavailable was tested as a fallback path; no physical-WebGPU
  performance claim is made here.
- axe is automated; it does not replace a manual screen-reader audit.
- The 360px nav row is horizontally scrollable by design; the test asserts that
  the page itself does not overflow.

## Commands

```powershell
cd web
npm test
npm run build
npm run e2e
```
