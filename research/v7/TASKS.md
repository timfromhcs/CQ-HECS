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

## AGENTS_V6.md Wave 4 (2026-11-21) — status

| ID | Task | Status |
|---|---|---|
| W4-01 | Threaded MCP execution + cancel contract | NOT STARTED |
| W4-02 | `isError` tool results + `-32602` for bad arguments | NOT STARTED |
| W4-03 | Shared service layer + `cq-hecs plan` + parity corpus | NOT STARTED |
| W4-04 | Publish JSON Schemas + OpenAPI 3.1 + `/api/v1` aliases | NOT STARTED |
| W4-05 | MCP protocol negotiation, annotations, outputSchema | NOT STARTED |
| W4-06 | `doctor` solver line + Studio token via env/file | NOT STARTED |
| W4-07 | `hcs.sat.count.v1` typed count contract | DONE |
| W4-08 | Separator width calibration | NOT STARTED |
| W4-09 | WebGPU device-loss handling | NOT STARTED |
| W4-10 | Run-card error scope | NOT STARTED |
| W4-11 | WASM base URL fix + hash check | NOT STARTED |
| W4-12 | Keyboard/touch composer | NOT STARTED |
| W4-13 | prefers-color-scheme + token contrast | NOT STARTED |
| W4-14 | Output-sink XSS + i18n key parity | NOT STARTED |
| W4-15 | Mobile viewport projects | NOT STARTED |
| W4-16 | Verify CPU-only core loader-free | NOT STARTED |
| W4-17 | VkResult checks + fault injection | NOT STARTED |
| W4-18 | C ABI hardening | NOT STARTED |
| W4-19 | Sanitizer lane | NOT STARTED |
| W4-20 | Skip budget | NOT STARTED |
| W4-21 | Mutation targets for QG/router/plan/scheduler | NOT STARTED |
| W4-22 | CI wiring | NOT STARTED |
| W4-23 | Version decision record | DONE (D-007: v6.0.0) |

## W3 / T6-03 status

DONE locally: CPU-only configure/build/CTest, loader-free binaries. OPEN: CI lane for `-DCQ_ENABLE_VULKAN=OFF`, C-ABI capability flag, CPU-vs-Vulkan differential tests (T6-04).
