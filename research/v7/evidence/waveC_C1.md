# Wave C / C1 evidence: W13 Web completion

Date 2026-11-22, branch release/v7-stable, Windows 11, Node (project toolchain), Chromium (Playwright bundled).
No git commit/add/stash/checkout/push. No QPU, no Open Quantum call, no credentials, version not bumped.

## Delivered

| Item | Files |
|---|---|
| (a) shared conformance corpus | `web/scripts/export_shared_conformance.py`, `web/tests/fixtures/shared_conformance.json` (21 circuits, 4 refusals), `tests/test_web_shared_conformance.py`, `web/tests/shared_conformance.test.ts`, `web/e2e/conformance.spec.ts`, `docs/CONFORMANCE.md` 2b |
| (b) Web column closed | `research/v7/FEATURE_COVERAGE.json` (13 web cells), `FEATURE_COVERAGE.md` (short form + C1 section), `tests/test_web_feature_coverage.py` |
| (c) states, import/export | `web/e2e/states.spec.ts`, `web/src/runcard_import.ts`, `web/tests/runcard_import.test.ts`, `web/src/main.ts` (worker-failure handling, import UI), `web/index.html`, `web/src/i18n.ts` (EN/DE/FR), `docs/WEB_ENGINES.md` |
| (d) visual regression | `web/e2e/visual.spec.ts`, 16 baselines `web/e2e/__snapshots__/visual.spec.ts/*-win32.png`, `web/playwright.config.ts` (`snapshotPathTemplate`) |
| (e) browser matrix | Chromium run; see NOT_RUN |

## Commands and results

- `python web/scripts/export_shared_conformance.py` -> wrote fixture, 21 cases; `--check` -> "shared conformance fixture is current".
- `python -m pytest tests/test_web_shared_conformance.py tests/test_web_feature_coverage.py tests/test_feature_coverage.py -q` -> 218 passed, 1 xfailed (the xfail is the open finding below).
- `python -m pytest tests/test_doc_consistency_v7.py -q` -> 63 passed.
- `cd web && npm test` -> 167 tests, 167 pass, 0 fail (baseline before this work: 105).
- `cd web && npm run build` -> `tsc --noEmit` clean, bundle size check passed, token contrast OK.
- `cd web && npx playwright test` (all projects: chromium, mobile-360, mobile-390) -> 128 passed, 1 skipped, 0 failed, 2.9 min. The skip is the WebGPU conformance run (NOT_RUN, below).

## Findings

- **C1-FIND-01 (CORRECTNESS, medium, OPEN, outside owned area):** `EntanglementAdaptiveRouter.route_and_execute` accepts the QASM
  `qreg q[2]; cx q[0],q[0];` and returns `EXACT` counts `{'00': 64}` on auto and on forced paths A, B and C. Qiskit and the browser refuse a repeated
  operand. Reproducer: `python -c "from cqhecs.router import EntanglementAdaptiveRouter as R; print(R().route_and_execute('OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncx q[0],q[0];\n',shots=64,seed=1).counts)"`.
  Recorded in the corpus as `known_divergence`; `tests/test_web_shared_conformance.py::Refusals::test_repeated_operand_is_refused_C1_FIND_01` is an
  `expectedFailure` that turns into an unexpected success when the parser is fixed. Not fixed here (cqhecs/ is not in the owned area).
- **Web defect fixed:** a worker that died or failed to load never answered, leaving the page busy or hanging boot. `src/main.ts` now remembers a worker
  `error` event (`failedWorkers`), settles `runOnce`/`ask` with a typed error, and restarts the worker. Covered by two e2e tests (boot, mid-run).
- **Stale cell corrected:** the first-cut QG Web cell said the QG Lab is Studio-only; the web app has `#/qg`. Cell is now PARTIAL with the remainder named.
- Non-common features (classical-bit remap, partial register, mid-circuit measurement) are refused by the Python router and executed by the browser; this is
  tabulated in `docs/CONFORMANCE.md` 2b and asserted from the Python side.

## Measured, with scope

- f32 *emulation* of the WGSL kernel (Math.fround, **not WebGPU**): worst max |dP| 2.2e-7, worst total variation 2.2e-7 over the 12-qubit-range cases; declared WebGPU
  tolerance is 5e-6 / 1e-5. Output at `web/test-results/shared_conformance_f32_emulation.json` (git-ignored, written by `npm test`).
- f64 core against the corpus: within 1e-12 (probabilities, norm), amplitudes within 1e-11 after removing one global phase.

## NOT RUN

- **WebGPU f32 conformance on a real adapter:** Chromium here exposes no WebGPU adapter (probe: `navigator.gpu` present but no adapter). The spec reports skipped and writes
  `web/e2e-results/webgpu_conformance.json` with `status: NOT_RUN`. No WebGPU deviation is claimed.
- **WebKit and Firefox:** only Chromium is installed (`ms-playwright` holds chromium and chromium_headless_shell only). Mobile projects are Chromium emulation.
- **Visual baselines on non-Windows platforms:** only `win32` committed; other platforms skip with a stated reason.
- Full Python pytest suite (targeted files only, per the task rules); Vercel preview/production E2E; physical phone.

## Notes for the integrator

- `web/package.json` version still says 5.0.0 (not touched; version bump is the integrator's).
- `web/.gitignore` gained `test-results/`.
- `tests/test_feature_coverage.py` (C3) still passes with the closed Web column.
