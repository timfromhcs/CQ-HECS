# v4 task board

Status vocabulary: PROPOSED, IN_PROGRESS, SUPPORTED_IN_SCOPE, NOT_SUPPORTED,
INCONCLUSIVE, BLOCKED, DEFERRED, REJECTED, NOT STARTED.

Scope decision (see DECISIONS.md D-001): ship a *small, verified* v4 -- the
explainable `ExecutionPlan` plus exact bounded-width separator #SAT -- and
record everything else honestly as not promoted.

| ID | Milestone | Status |
|---|---|---|
| M0 | Safe repo state, branch from verified origin/main | DONE |
| M1 | Baseline reproduction (Python gates) | DONE (native/web/mutation NOT RUN yet) |
| M2 | Source/literature audit | IN_PROGRESS (literature map: prior art for planned features only) |
| M3 | Result schema / contracts | PARTIAL: additive fields only (plan_check, count backend, per-observable bounds); no field changed meaning |
| M4 | Explainable ExecutionPlan (Python/CLI/MCP/Studio API) | SUPPORTED_IN_SCOPE (Python+CLI+MCP+Studio API); Studio *UI panel* NOT STARTED |
| M5 | Path D native X/Y/Z observables + per-observable bounds | SUPPORTED_IN_SCOPE (see HYPOTHESES H4-PAULI-01 for scope: not a new capability, a tighter and single-pass one) |
| M6 | Path C graph-aware ordering | DEFERRED |
| M7 | Noise calibration schema v3 | DEFERRED |
| M8 | Browser/Python/native conformance corpus | NOT STARTED |
| M9 | Native/GPU correctness+performance | NOT STARTED (Vulkan toolchain unverified) |
| M10 | Exact separator #SAT backend | SUPPORTED_IN_SCOPE (opt-in `method="separator"` or `"auto"`; default stays dpll) |
| M11 | CNF-to-XOR with witness | DEFERRED |
| M12 | Optional CDCL | DEFERRED |
| M13 | OMNIWAVE v4 experiments | DEFERRED |
| M14 | Formal verification | DEFERRED |
| M15 | UX/docs/provenance | PARTIAL: docs, migration notes and provenance fields done; Studio/Web UI panels for the plan NOT STARTED |
| M16 | Hardening/security | NOT STARTED |
| M17 | Local release-candidate gates | DONE (SBOM/checksums and Windows package are release-time steps, NOT RUN) |
| M18 | Remote CI/preview loop | IN_PROGRESS |
| M19 | Release decision | NOT STARTED -- publishing requires explicit user authorization |

## AGENTS_V6.md Wave 3 (2026-11-21) — status

Base `25e16e5` (v5.0.0), branch `agent/v6-rc`. Detail in `WAVE3_REPORT.md`.

| ID | Task | Status |
|---|---|---|
| W3-01 | Path A shot truncation (D1) | DONE |
| W3-02 | Path B hygiene / parser parity (D10) | NOT STARTED |
| W3-03 | Path C "exact" label audit (D12) | DONE (audit: not reproduced; see FINDINGS F-004) |
| W3-04 | Path B vs dense measurement | DONE (dense dominates; FINDINGS F-005) |
| W3-05 | Runner ledger fail-closed + net spend (D2) | DONE |
| W3-06 | Uncalibrated-gate policy (D4) | DONE |
| W3-07 | Deterministic synthetic profile (D4) | DONE |
| W3-08 | Frozen SAT baseline | DONE |
| W3-09 | `certified` / `proof_level` (D3) | DONE |
| W3-10 | Deadline covers proof checking | DONE (both engines bound the proof check by the remaining deadline) |
| W3-11 | python-sat child-process isolation | NOT RUN (no python-sat) |
| W3-12 | Shared web noise predicate (D5) | DONE |
| W3-13 | Forge axe tags | DONE (wcag22aa added; forge axe 5/5, full e2e 42/42) |
| W3-14 | Rust toolchain pin | DONE (pin added; wasm rebuild-hash check NOT RUN) |
| W3-15 | MCP input bounds (D7) | DONE |
| W3-16 | llms.txt refresh | DONE |
| W3-17 | Pinned build constraints | DONE |
| W3-18 | Version surfaces / SECURITY.md | DONE |
| W3-19 | Ledger/baseline reconciliation (D11) | DONE (mutant count; baseline numbers in WAVE3_REPORT) |
| W3-20 | Licence register | DONE (all externals UNVERIFIED until opened) |
| W3-21 | QG board reconciliation (D9) | DONE |

Waves 4–11: NOT STARTED.

## V7 (AGENTS_V7.md)

`AGENTS_V7.md` is the governing contract (see `DECISIONS.md` D-008). This branch's V6 Wave-3/4
work maps into V7 waves; the full mapping (V7 waves W0–W18, V6 backlog T6-01..T6-13, V6 Wave-3/4
tasks, PLAN.md) is in `research/v7/PLAN_COVERAGE.md`, and the cross-surface capability matrix is
`research/v7/FEATURE_COVERAGE.md` + `.json`. Work now follows V7's wave order; Web (W13) and
Windows EXE (W14) are hard gates.

## AGENTS_V6.md Wave 4 (2026-11-21) — status

| ID | Task | Status |
|---|---|---|
| W4-01 | Threaded MCP execution + cancel contract | NOT STARTED |
| W4-02 | `isError` tool results + `-32602` for bad arguments | DONE |
| W4-03 | Shared service layer + `cq-hecs plan` + parity corpus | NOT STARTED |
| W4-04 | Publish JSON Schemas + OpenAPI 3.1 + `/api/v1` aliases | PARTIAL: ExecutionPlan schema published + validated; OpenAPI/aliases deferred |
| W4-05 | MCP protocol negotiation, annotations, outputSchema | NOT STARTED |
| W4-06 | `doctor` solver line + Studio token via env/file | DONE |
| W4-07 | `hcs.sat.count.v1` typed count contract | DONE |
| W4-08 | Separator width calibration | NOT STARTED |
| W4-09 | WebGPU device-loss handling | NOT STARTED |
| W4-10 | Run-card error scope | DONE (browser card + schema `error_scope`; Python parity deferred to W4-03) |
| W4-11 | WASM base URL fix + hash check | DONE (base-aware URL; served-core SHA-256 in engine info) |
| W4-12 | Keyboard/touch composer | NOT STARTED |
| W4-13 | prefers-color-scheme + token contrast | DONE (OS default + toggle first-click fix; contrast gate in build) |
| W4-14 | Output-sink XSS + i18n key parity | PARTIAL: i18n parity test added; forge has a hostile-text XSS e2e; main-page XSS assertion deferred |
| W4-15 | Mobile viewport projects | NOT STARTED |
| W4-16 | Verify CPU-only core loader-free | DONE (test_native_cpu_only 4: build, CTest, no Vulkan loader, capability) |
| W4-17 | VkResult checks + fault injection | NOT STARTED |
| W4-18 | C ABI hardening | NOT STARTED |
| W4-19 | Sanitizer lane | NOT STARTED |
| W4-20 | Skip budget | DONE (105 skips / 11 reasons; `skip_budget.py --check`) |
| W4-21 | Mutation targets for QG/router/plan/scheduler | DONE (QG x2, router, scheduler; plan already covered) |
| W4-22 | CI wiring | DONE (qg_doc_consistency gate; skip-budget lane report on Linux+Windows) |
| W4-23 | Version decision record | DONE (D-007: v6.0.0) |

## W3 / T6-03 status

DONE locally: CPU-only configure/build/CTest, loader-free binaries. OPEN: CI lane for `-DCQ_ENABLE_VULKAN=OFF`, C-ABI capability flag, CPU-vs-Vulkan differential tests (T6-04).

## Wave A (V7 plan, 2026-11-21) — status (evidence: research/v7/evidence/waveA_A1..A5.md)

| ID | Task | Status |
|---|---|---|
| W4-01 | Threaded MCP execution + cancel | DONE (compute abandoned, not stopped; documented) |
| W4-03 | Shared service layer, `cq-hecs plan`, parity corpus | DONE (`analyze --explain` migrated onto the service in Wave C / C3) |
| W4-04 | OpenAPI 3.1 + `/api/v1` | DONE (openapi_spec_validator NOT RUN) |
| W4-05 | MCP negotiation/annotations/outputSchema | DONE (2025-06-18 only) |
| W4-08 | Separator width calibration | DONE (preflight -> UNKNOWN) |
| W4-09 | WebGPU device-loss + WASM fallback | DONE (real GPU loss NOT RUN) |
| W4-12 | Keyboard/touch composer | DONE |
| W4-14 | Main-page XSS assertion | DONE |
| W4-15 | Mobile viewport projects | DONE (Chromium emulation only) |
| W4-17 | VkResult checks + fault injection | DONE |
| W4-18 | C ABI hardening | DONE |
| W4-19 | Sanitizer lane | PARTIAL (MSVC ASan ran; GCC/Clang ASan+UBSan NOT RUN) |
| W3-11 | python-sat child isolation | DONE (3.13; 3.14 NOT RUN) |
| T6-04 | CPU vs Vulkan BCP differential | PARTIAL (AMD hardware only; software ICD/Linux NOT RUN) |
| T6-06 | Low-memory/WebGPU-absent tests | DONE |
| W5 | Lean Path A invariant + Pauli rules; Path A/D spec tests | DONE at specification level (not refinement) |
| — | MaxSAT typed contract + CLI wiring | DONE |
| — | LRAT / drat-trim / cake_lpr lanes | NOT RUN (no checkers installed) |
| — | Baseline delta 2896/109 vs 2899/105 | EXPLAINED: 4 skips from missing qiskit-ibm-runtime on PATH Python 3.13 |

## Wave B (V7 plan, 2026-11-21, committed) - status

Evidence: `research/v7/evidence/waveB_B1..B5.md`.

| ID | Task | Status |
|---|---|---|
| W6 | Paths B/C error-story metadata, SVD instrumentation, tiny-reference tests | DONE (B1; n > 7 dense Path C comparison NOT RUN) |
| W8 | QG model audit: competing BMV models, SYK Trotter oracle, Z2 leakage, offline replay | DONE (B2; model quantities only) |
| T6-01 | QG ExecutionPlan parity | DONE: envelope (B2) + CLI/MCP/Studio wiring and four-surface parity test (C3) |
| T6-02 | QG Lab UI in Web and Studio | DONE (B3); Studio `qg.js` plan panel NOT added (see FEATURE_COVERAGE) |
| W10 | Calibration schema v3, FIT/EVAL enforcement, channel checks | DONE (B4); CLI/Studio/MCP wiring DONE in C3 |
| W7 | Research Paths E/F/G prototypes, preregistration, negative results | DONE as RESEARCH_ONLY (B5); router unchanged; nothing promoted |

## Wave C (V7 plan, 2026-11-22) - status

Evidence: `research/v7/evidence/waveC_<id>.md` (each owner writes its own). Only C3 and C4 are recorded
here; the others are tracked by the integrator.

| ID | Task | Status |
|---|---|---|
| C3 / W12 / T6-01 | QG plan envelope via CLI `qg plan`, MCP `cqhecs_qg_plan`, Studio `/api/qg/v1/experiments/plan`, one service, parity test (dict + digest) | DONE (`tests/test_qg_surface_parity.py`, 49 tests) |
| C3 / W12 | `analyze --explain` migrated onto `service.analysis_document` | DONE (`tests/test_service_w12.py`) |
| C3 / W12 | calibration v3 policy `refuse|warn|ideal` in the noisy-run path; label + freshness shown in CLI, Studio, MCP; v1/v2 files unchanged | DONE (`tests/test_calibration_surfaces.py`, 16 tests; synthetic profile only, no measured v3 record exists) |
| C3 / QGRAVITY 9.1-9.2 | local API routes and MCP tools completed (experiments, backends, evidence/{id}, exports/{id}, compare, model_validate, export); paid Open Quantum routes/tools exist as separate typed refusals | DONE for local; paid paths UNAVAILABLE by design (authorisation, quote id, 25-Spark ledger live only in the runner script) |
| C3 / W12 | FEATURE_COVERAGE non-Web `TODO_VERIFY` cells resolved; test fails on any empty cell | DONE (`tests/test_feature_coverage.py`); 11 Windows EXE cells are PARTIAL with NOT_RUN, closed by W14 |
| C3 | Studio diagnostics route + MCP `cqhecs_doctor` on `service.doctor_report` | DONE |
| C4 / W15 | Documentation matches code and evidence | see `waveC_C4.md` |

### Open items recorded by C3

- Studio UI has no plan panel (no caller of `/api/plan`); needs a change in `cqhecs/studio/static` (UI owner).
- `scripts/build_exe.ps1` smoke has no analyze/plan/qg/doctor/calibration step; the opt-in `tests/test_exe_smoke.py`
  now has them but no EXE was built or run (W14).
- Calibration `ideal` and `warn` behave identically inside `FakeHardwareBackend` (both run uncovered gates
  noiselessly and report them); they differ only in the warning text. `hardware_bridge.py` was not changed.
- MaxSAT has no MCP tool or Studio route.


## Waves C, D and E (V7 plan, 2026-11-22) - status at the freeze (E3)

Evidence: `research/v7/evidence/waveC_C1..C5.md`, `waveD_D1..D5.md`, `waveE_E2.md`, `waveE_E3.md`. Commits: `d56c5cc`,
`f4dc089`, `133ae64`, `440e367`, `51969fd`, `c655e92`, `c631cf8`, `f912160`, `6260495`, `c098971`, `38e799b`.
Wave E is in progress: only E2 (docs) and E3 (this record) have evidence files when this was written.

| ID | Task | Status |
|---|---|---|
| C1 / W13 | Shared web/Python conformance corpus (21 circuits, 4 refusals), run-card import, state/visual specs, feature matrix web column | DONE (Chromium only; WebGPU on a real adapter, Firefox, WebKit NOT_RUN) |
| C2 / W14 / T6-07 | Reproducible wheel/sdist, onedir EXE, native CPU/Vulkan zips, CycloneDX SBOMs, manifest, `package.yml` | DONE locally; rebuilt for `38e799b` by the integrator; clean-machine install and a hosted run NOT_RUN |
| C3 / W12 | QG plan on four surfaces, `analyze --explain` on the service, calibration v3 policy | DONE (see Wave C table above) |
| C4 / W15 | Docs match code and evidence | DONE for the pinned statements (63 tests); full claim audit in `CLAIM_AUDIT.md` (E3 section) |
| C5 / W15 | Fuzz, property, resource tests; mutation targets to 95; security audit | DONE (181 targeted tests re-run by E3, 0 xfail; mutation 95/95 in place at the freeze, integrator-recorded) |
| D1 | Repeated gate operands refused at the shared layer (C1-FIND-01); `eval` removed from `python_bridge` (SEC-M2) | DONE |
| D2 | SEC-M1, SEC-L1..L5, P-01 | DONE |
| D3 | Typed Vulkan refusal (P-03), `/Brepro` reproducible MSVC binaries (P-06), release asset policy (P-07), legacy script (P-08) | DONE; the workflows are linted, NOT run |
| D4 | Studio ExecutionPlan panel, real-browser axe and keyboard test | DONE |
| D5 | Mutation count pin, Python 3.14 lane report, Lean L-RESULT-01, audit skeletons | DONE; Python 3.14 whole suite NOT_RUN |
| E2 | Documentation freeze numbers | DONE (integrator figures recorded; E2 did not re-run) |
| E3 | Research record to the freeze state (this task) | DONE: ledger, matrix, blockers, security, licences, claims, packaging, baseline addendum, candidate audit, final report draft |
| E1, E4, E5 | other Wave E tasks | NOT_RUN by E3; their evidence files did not exist at writing (E4 owns the rollback section of `FINAL_REPORT.md` and the release workflow edits) |

Not promoted in V7 (kept as research or deferred): Paths E, F, G (`RESEARCH_ONLY`, B5); Path C graph-aware ordering
(M6 DEFERRED); CNF-to-XOR with a witness (M11 DEFERRED); optional CDCL (M12 DEFERRED); the learned router
(H4-ROUTE-01 DEFERRED); a Studio plan i18n and Studio `qg.js` plan panel (English only).

Open release conditions that block `STABLE`: see `BLOCKERS.md` B-V7-09, B-V7-11, B-V7-12, B-V7-13, B-V7-14 and the
`NOT_RUN`/`FAIL` rows of `RELEASE_CANDIDATE_AUDIT.md`.
