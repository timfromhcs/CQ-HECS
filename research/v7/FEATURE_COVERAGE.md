# FEATURE_COVERAGE.md — cross-surface capability matrix (V7 §16.1)

Created 2026-11-21 on branch `agent/v6-rc`. Machine-readable source: `FEATURE_COVERAGE.json`.
Statuses: `DONE`, `PARTIAL`, `NOT_APPLICABLE`, `UNAVAILABLE`, `TODO_VERIFY`. Every cell names a
route/command/tool/source. **A `TODO_VERIFY` cell must be resolved with evidence before W13/W14
close; an empty cell blocks release.** This is a first cut; the integrator maintains it.

| Capability | Python/API | CLI | MCP | Studio | Web | Windows EXE | Native/HW |
|---|---|---|---|---|---|---|---|
| Circuit input + execution | `cqhecs.router.run`/backends | `run`/`analyze`/`verify`/`expect`/`selftest` | `cqhecs_run`/`_analyze`/`_plan` | `StudioState.simulate` | DONE composer/code lab, WASM f64 + WebGPU f32; shared corpus (WebGPU NOT_RUN without adapter) | TODO_VERIFY (build_exe onedir) | CPU-only core (W4-16) |
| Paths A–D and router | `router`, `execution_plan` | `analyze`, `run --path` | `cqhecs_plan` | DONE plan panel (Circuit lab, test_studio_plan_ui.py) | NOT_APPLICABLE own engines, never labelled A–D | TODO_VERIFY | PARTIAL (A/C native) |
| Research Paths E/F/G | not shipped | N/A | N/A | N/A | NOT_APPLICABLE not promoted | N/A | N/A |
| SAT | `sat`, `unified`, `sat_external` | `sat solve` | `cqhecs_sat_solve` | SAT lab | DONE browser DPLL + certificates; CaDiCaL/OMNIWAVE/DRAT UNAVAILABLE | TODO_VERIFY | PARTIAL (OMNIWAVE BCP) |
| #SAT / MaxSAT | `count_models` (`hcs.sat.count.v1`), `maxsat` | `sat count`/`sat maxsat` | `cqhecs_sat_count` | count via `/api/sat` | DONE #SAT BigInt exact; MaxSAT NOT_APPLICABLE | TODO_VERIFY | N/A |
| Noise / device profiles | `hardware_bridge`, `noise_fit` | `profile`, `devices`, `fit` | `cqhecs_devices`/`_hardware` | Noise lab | PARTIAL labelled profiles; schema v3 N/A; provider UNAVAILABLE | TODO_VERIFY | PARTIAL |
| QG BMV/SYK/Z2 | `quantum_gravity` (BMV exact) | PARTIAL `qg catalog/preview/run-local` | PARTIAL `cqhecs_qg_*` | PARTIAL (verify) | PARTIAL `#/qg` BMV toy model + evidence; SYK/Z2 N/A as executors | TODO_VERIFY | DONE (prior QPU evidence) |
| QG QPU / hardware | runner script (fail-closed) | N/A | N/A | PARTIAL status | UNAVAILABLE no credentials, typed refusal | UNAVAILABLE | DONE (evidence display) |
| Native CPU / Vulkan | PARTIAL optional binding | `doctor`/`backend` | PARTIAL | TODO_VERIFY | NOT_APPLICABLE WebGPU is not Vulkan | TODO_VERIFY | PARTIAL (CPU verified) |
| Formal Lean assurance | N/A (W4 not started) | N/A | N/A | N/A | NOT_APPLICABLE nothing shipped | N/A | N/A |
| Reproducibility / evidence | `hcs.run.v2` | `--format json` | digests in results | PARTIAL evidence | DONE run card export + import | TODO_VERIFY | PARTIAL |
| Studio / MCP / API | `studio`, `mcp_server` | `studio`/`mcp` | 11 tools (isError, bounds) | loopback + token | NOT_APPLICABLE loopback services; bridge refuses non-loopback | TODO_VERIFY | N/A |
| Learn / docs / a11y | N/A | `--help` + `docs/` | N/A | PARTIAL i18n | DONE EN/DE/FR, axe, 16 visual baselines (win32) | TODO_VERIFY | N/A |

## Parity rules and limitations (V7 §16.1)

- **Browser engines are not Python Paths A–D.** The browser runs its own WASM f64 / WebGPU f32
  statevector. Do not claim identical engines; state the exact common subset and tolerances.
- **WebGPU, Vulkan and CPU native are distinct surfaces**, not synonyms. The browser does not
  expose Vulkan.
- **SAT:** list supported engines and proof formats per surface; UNKNOWN is never UNSAT.
- **#SAT/MaxSAT:** no LIMIT/timeout may be reported as an exact count or optimum.
- **Noise:** the browser must never embed provider credentials.
- **QG:** a toy model does not measure gravity; a QPU campaign is never initiated by a page load
  or EXE startup; no provider tokens in the browser bundle or packaged files.
- **Lean:** a formal specification does not imply implementation refinement; display the exact
  level/scope (none shipped yet).
- **Studio/MCP/API:** MCP is stdio by default; Studio stays loopback-only and token-protected.

## Why the `TODO_VERIFY` / `UNAVAILABLE` cells are not "deferrals"

They are honest gaps to be closed with evidence in V7 W12/W13/W14. An `UNAVAILABLE` row carries a
technical reason (e.g. a browser cannot hold provider credentials) and needs a visible
explanation and integrator sign-off; it cannot be used to defer a feasible planned feature.

## Wave C / C3 (W12) resolution of the non-Web cells

`FEATURE_COVERAGE.json` is authoritative for the cell text; the table above is the original first cut
and is not rewritten here (the Web column is owned by another agent). `tests/test_feature_coverage.py`
fails on an empty cell, an unknown status, or any `TODO_VERIFY` outside the Web column.

- **Windows EXE (all 11 applicable rows):** `PARTIAL`, each with the exact smoke that exists and
  `NOT_RUN`. No EXE was built or run in this worktree; W14 closes these. Gaps named per row: the
  `build_exe.ps1` smoke has no analyze/plan/qg/doctor/calibration step (they are now in the opt-in
  `tests/test_exe_smoke.py`).
- **Studio plan panel:** `DONE`. Circuit lab `Plan circuit` calls `POST /api/plan` and renders the
  selected path, rejected-candidate reasons, ESTIMATE-labelled resources, digests and typed
  refusal/error/empty states. Evidence: `tests/test_studio_plan_ui.py` (6 tests incl. real Chromium,
  axe critical/serious 0 at 1280 and 360 px) and `evidence/waveD_D4.md`. Still English only.
- **Studio native diagnostics:** `DONE` (`GET /api/diagnostics`); MCP gained `cqhecs_doctor`.
- **Research Paths E/F/G (Python):** `NOT_APPLICABLE`: prototypes only, asserted absent from the package
  and the router.
- **QG routes/tools:** CLI, MCP and Studio now share `cqhecs.service.qg_*`; Open Quantum quote, submit,
  status, results exist as separate typed refusals (`UNAVAILABLE`) and write no ledger.
- **MaxSAT:** `PARTIAL` on MCP and Studio (no tool/route); `DONE` on Python and CLI.
- **Studio i18n:** `PARTIAL`, English only.

## Wave C / C1 (W13) resolution of the Web column

`FEATURE_COVERAGE.json` is authoritative; the table above shows the short form. All 13 Web cells are
closed (no `TODO_VERIFY`), each cell cites real files, and `tests/test_web_feature_coverage.py` fails on
an unknown status, a missing cited path, a `NOT_APPLICABLE`/`UNAVAILABLE` cell without a reason, or a
`PARTIAL` cell that does not name what is missing.

- **Shared conformance corpus (T6-05):** `web/tests/fixtures/shared_conformance.json`, generated by
  `web/scripts/export_shared_conformance.py`; Python (`tests/test_web_shared_conformance.py`), browser
  WASM f64 in Node and in the page, WebGPU f32 in the page when an adapter exists. **WebGPU: NOT_RUN** in
  this environment (no adapter); the f32 deviation is bounded only by a labelled emulation. See
  `docs/CONFORMANCE.md` section 2b.
- **TODO_VERIFY resolved:** `#SAT` exactness (BigInt, `web/tests/core.test.ts`, 3*2^198 on 200 variables).
- **Stale first-cut cell corrected:** QG Lab is *not* Studio-only; `#/qg` exists in the web app (BMV toy
  model, evidence ledger), so the cell is `PARTIAL` with the remainder named.
- **Found while building the corpus (not fixed, outside the web area):** C1-FIND-01, the Python router
  accepts `cx q[0],q[0]` and returns `EXACT` on paths A/B/C (Qiskit and the browser refuse it).
- **NOT_RUN:** WebGPU conformance on a real adapter; WebKit and Firefox; visual baselines on non-Windows
  platforms.
