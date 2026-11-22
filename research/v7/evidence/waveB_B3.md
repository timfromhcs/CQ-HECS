# Wave B / B3 - T6-02 Quantum Gravity Lab UI (web + Studio)

Status: SUPPORTED_IN_SCOPE for the UI surfaces below. No QPU job, no Open Quantum call, no credentials, no spend.

## State found
- Web app (`web/src/qg*.ts`, route `#/qg`, 8 workspaces, EN/DE/FR) already present and passing.
- Studio had `/api/qg/v1/*` routes but no UI; `qg.js` was listed in `_STATIC_FILES` with no file behind it.
- `cqhecs/studio/app.py` had a syntax error (line 903: `b"\r\n"` written as literal CR LF). Fixed (escape sequences restored). Root cause: file write mangled escapes; one repair cycle.

## Changes (owned area only)
- `cqhecs/studio/static/qg.js` (new), `index.html` (nav 08 + `view-qg` + script), `app.js` (TITLES.qg, lazy mount hook), `style.css` (QG rules).
- `cqhecs/studio/app.py`: only the syntax repair above.
- `tests/test_quantum_gravity_studio_ui.py` (new, 3 tests): assets served, no credential/provider path/innerHTML/eval, every tab has a panel; only `/api/qg/v1/` calls.
- `docs/DESIGN_SYSTEM.md`: Quantum Gravity Lab section.

## Commands and results
- `python -m pytest tests/test_quantum_gravity_studio_ui.py tests/test_quantum_gravity_studio.py tests/test_studio.py tests/test_studio_security.py -q` -> 45 passed
- `python -m pytest tests/test_quantum_gravity_studio_ui.py tests/test_quantum_gravity_studio.py tests/test_qg_replay.py tests/test_qg_execution_plan.py -q` -> 34 passed
- `cd web && npm test` -> 105 pass / 0 fail; `npx tsc --noEmit` ok; `npm run build` ok (bundle budget, token contrast)
- `npx playwright test e2e/qg.spec.ts --project=chromium` -> 14 passed
- `npx playwright test e2e/app.spec.ts e2e/mobile.spec.ts` -> 35 passed
- Studio real-browser smoke (ad hoc Playwright script, scratchpad, not committed): all 8 tabs at 1280 and 360 px; axe critical/serious = 0 on `#view-qg`; no console errors; Run disabled until assumptions confirmed; result, SHA-256 preview, typed refusal, 13-row scan table + SVG, 10 evidence rows. One 360 px overflow (long hash on Circuit tab) found and fixed with `overflow-wrap` in style.css; re-run clean.

## NOT RUN
- Studio browser smoke is not a committed Playwright spec (Studio has no e2e harness); covered by pytest static checks only.
- Studio i18n: English only (existing Studio convention); EN/DE/FR parity covers the web app.
- Studio keyboard tab pattern verified by code and smoke click path, not by an arrow-key assertion.
- Full pytest suite, native, WebGPU hardware: not run (out of scope).

## Limits
Charts show recorded QPU correlators with shot-noise bars only; toy model; no gravity measurement claim. Studio `preview` takes theta only (local phases are web-only).
