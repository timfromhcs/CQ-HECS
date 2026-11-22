# Wave D / D4 - Studio ExecutionPlan panel

Status: SUPPORTED_IN_SCOPE (Studio UI). No QPU, Open Quantum, credentials or spend. Version not bumped. Nothing committed.

## Changes (owned area only)
- `cqhecs/studio/static/index.html`: `#plan-panel` in the Circuit lab (button, live result region, state tag).
- `cqhecs/studio/static/app.js`: `runPlan`/`renderPlan` (POST `/api/plan` via the shared bearer `api()` helper). Shows selected path, selection reason, per-candidate capable/chosen/blockers/policy notes (why rejected), peak memory and work labelled ESTIMATE, known hard limits, unsupported operations, input/normalized/plan digests. Typed states: idle, empty source, refused (plan.refusal code + message, role=alert), error (server 4xx, role=alert), plan ready. textContent only.
- `cqhecs/studio/static/style.css`: panel rules (overflow-wrap, focus ring).
- `tests/test_studio_plan_ui.py` (new, 6 tests), `tests/studio_ui_e2e.mjs` (new): static checks (only `/api/plan`, no innerHTML/eval/storage/credential words/token use, no secret patterns, native button, focusable region), 401/403 without bearer token, and a real headless Chromium run (Playwright + axe from web/node_modules, loopback server with per-launch token; not the user's browser): 1280 and 360 px empty/plan/refusal/error/empty-source states, axe critical+serious = 0 on `#plan-panel` and `#view-circuit`, no horizontal overflow, keyboard Enter on the Plan button, no page errors.
- Keyboard arrow-key tab assertion (left NOT_RUN by B3) is now implemented in the same script on the QG tablist: ArrowRight/ArrowLeft/Home/End, wrap-around, roving tabindex, aria-selected, tabpanel labelledby. Passed.
- `docs/STUDIO.md`, `research/v7/FEATURE_COVERAGE.json` and `.md`: Studio plan cell PARTIAL -> DONE (evidence above).

## Deviation
A separate `plan.js` was not created: static files are served from the `_STATIC_FILES` allow-list in `cqhecs/studio/app.py`, outside this task's owned area, so the code lives in `app.js`.

## Results
- `python -m pytest tests/test_studio_plan_ui.py -q` -> 6 passed (first browser run failed on axe `Please use browser.newContext()`: script bug, fixed in one cycle).
- `python -m pytest tests/test_studio_plan_ui.py tests/test_quantum_gravity_studio_ui.py tests/test_studio.py tests/test_studio_security.py -q` -> 46 passed.

## NOT RUN
- Firefox/WebKit; full pytest suite; screen-reader manual testing; axe on views other than the circuit view and QG tablist page; Studio i18n (English only, existing convention).
