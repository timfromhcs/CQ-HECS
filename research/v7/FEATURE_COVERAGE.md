# FEATURE_COVERAGE.md — cross-surface capability matrix (V7 §16.1)

Created 2026-11-21 on branch `agent/v6-rc`. Machine-readable source: `FEATURE_COVERAGE.json`.
Statuses: `DONE`, `PARTIAL`, `NOT_APPLICABLE`, `UNAVAILABLE`, `TODO_VERIFY`. Every cell names a
route/command/tool/source. **A `TODO_VERIFY` cell must be resolved with evidence before W13/W14
close; an empty cell blocks release.** This is a first cut; the integrator maintains it.

| Capability | Python/API | CLI | MCP | Studio | Web | Windows EXE | Native/HW |
|---|---|---|---|---|---|---|---|
| Circuit input + execution | `cqhecs.router.run`/backends | `run`/`analyze`/`verify`/`expect`/`selftest` | `cqhecs_run`/`_analyze`/`_plan` | `StudioState.simulate` | composer + WASM f64 / WebGPU f32 | TODO_VERIFY (build_exe onedir) | CPU-only core (W4-16) |
| Paths A–D and router | `router`, `execution_plan` | `analyze`, `run --path` | `cqhecs_plan` | TODO_VERIFY plan panel | N/A (own engine) | TODO_VERIFY | PARTIAL (A/C native) |
| Research Paths E/F/G | not shipped | N/A | N/A | N/A | N/A | N/A | N/A |
| SAT | `sat`, `unified`, `sat_external` | `sat solve` | `cqhecs_sat_solve` | SAT lab | PARTIAL (TS `sat.ts`) | TODO_VERIFY | PARTIAL (OMNIWAVE BCP) |
| #SAT / MaxSAT | `count_models` (`hcs.sat.count.v1`), `maxsat` | `sat count`/`sat maxsat` | `cqhecs_sat_count` | count via `/api/sat` | PARTIAL | TODO_VERIFY | N/A |
| Noise / device profiles | `hardware_bridge`, `noise_fit` | `profile`, `devices`, `fit` | `cqhecs_devices`/`_hardware` | Noise lab | PARTIAL (no creds) | TODO_VERIFY | PARTIAL |
| QG BMV/SYK/Z2 | `quantum_gravity` (BMV exact) | PARTIAL `qg catalog/preview/run-local` | PARTIAL `cqhecs_qg_*` | PARTIAL (verify) | N/A (Studio-hosted) | TODO_VERIFY | DONE (prior QPU evidence) |
| QG QPU / hardware | runner script (fail-closed) | N/A | N/A | PARTIAL status | UNAVAILABLE (no creds) | UNAVAILABLE | DONE (evidence display) |
| Native CPU / Vulkan | PARTIAL optional binding | `doctor`/`backend` | PARTIAL | TODO_VERIFY | N/A (WebGPU ≠ Vulkan) | TODO_VERIFY | PARTIAL (CPU verified) |
| Formal Lean assurance | N/A (W4 not started) | N/A | N/A | N/A | N/A | N/A | N/A |
| Reproducibility / evidence | `hcs.run.v2` | `--format json` | digests in results | PARTIAL evidence | DONE run card + `error_scope` | TODO_VERIFY | PARTIAL |
| Studio / MCP / API | `studio`, `mcp_server` | `studio`/`mcp` | 11 tools (isError, bounds) | loopback + token | PARTIAL links | TODO_VERIFY | N/A |
| Learn / docs / a11y | N/A | `--help` + `docs/` | N/A | PARTIAL i18n | DONE EN/DE/FR + axe | TODO_VERIFY | N/A |

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
