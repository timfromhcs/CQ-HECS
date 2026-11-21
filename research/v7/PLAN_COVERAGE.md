# PLAN_COVERAGE.md — every plan item mapped to a V7 wave (V7 §1.1, §19.0)

Created 2026-11-21 on branch `agent/v6-rc` (base `25e16e5`, v5.0.0). This file is the
required inventory mapping every valid item in `AGENTS_V6.md`, `PLAN.md` and this branch's own
work to a **V7 wave/task/status/owner/gate**, plus the V6 backlog carry-forward. Nothing is
silently dropped or renamed (V7 §19.0).

Status vocabulary: `DONE`, `PARTIAL`, `IN_PROGRESS`, `NOT_STARTED`, `DEFERRED`, `NOT_RUN`,
`BLOCKED`, `REJECTED`. Owner codes: `I` integrator, `Q` quantum paths, `N` noise/hardware,
`G` QG, `S` SAT/proof, `X` native, `W` web, `U` UI, `A` API/MCP, `R` release, `V` verification.

Guiding rule: V7 supersedes the *execution order*; where it conflicts with V6/PLAN the stricter
correctness/security/release condition wins (recorded in `DECISIONS.md` D-008).

---

## 1. V7 waves W0–W18

| Wave | Scope | Status | Evidence / next gate |
|---|---|---|---|
| W0 | Repository inventory, baseline, protection | **PARTIAL** | baseline reproduced (`WAVE3_REPORT.md`, junit 2899 passed / 105 skipped); baseline as `BASELINE_W0.md`; source-tree map as `SOURCE_TREE_MAP.md`; a V7 §1.1 `BASELINE.md` refresh still owed |
| W1 | Claim/interface/architecture freeze | **PARTIAL** | additive contracts (D-007, D-008); ExecutionPlan schema + `hcs.run.v2` error_scope published; `CLAIM_AUDIT.md` first cut + feature matrix; DE/FR/ARCHITECTURE/docs claim audit owed |
| W2 | Research and SOTA replication | **NOT_STARTED** | `LITERATURE_MAP.md` (V6) exists; V7 `CLAIM_AUDIT.md` (first cut done), `QUANTUM_SIMULATION_RESEARCH.md`, `SAT_PROOF_REVIEW.md`, `NOISE_QEC_RESEARCH.md` owed |
| W3 | Test harness and evidence ledger | **PARTIAL** | skip budget (`SKIP_BUDGET.json`), mutation 64/64, ExecutionPlan schema contract, QG doc-consistency gate, `evidence/` ledgers done; unified fixture/digest policy + cross-surface conformance fixtures owed |
| W4 | Lean formal workspace | **NOT_RUN** | no Lean toolchain and no `lakefile`/`lean-toolchain` in the checkout; `lean`/`lake` not installed. Blocked on toolchain availability; no implementation claim made |
| W5 | Formalize/harden Paths A and D | **NOT_STARTED** | A: D1 shot contract fixed; D: D3-adjacent Pauli label unchanged |
| W6 | Paths B/C numerical assurance | **PARTIAL** | Path B dropped-mass reported + bounded (W3-02); Path C label audited (W3-03) |
| W7 | New simulator paths E/F/G | **NOT_STARTED** | research-only; router unchanged |
| W8 | QG models and scientific audit | **PARTIAL** | QG board reconciled (W3-21), F-08 ratio corrected; model parameterisation/competing-model work owed |
| W9 | SAT/#SAT/MaxSAT and certificates | **PARTIAL** | `certified`/`proof_level` (W3-09), proof deadline (W3-10), `hcs.sat.count.v1` (W4-07); MaxSAT/LRAT/CakeLPR pipeline owed |
| W10 | Noise/QPU/QEC experiments | **NOT_RUN** | no authorization/spend this session |
| W11 | Native CPU/Vulkan + GPU hardening | **PARTIAL** | CPU-only build + loader-free verified (W4-16); Vulkan parity/device-loss/ABI/sanitizers owed |
| W12 | Studio/API/CLI/MCP integration | **PARTIAL** | MCP `isError`/`-32602` (W4-02), MCP input bounds (W3-15), doctor solver line + Studio token (W4-06) |
| W13 | Web completion (hard gate) | **PARTIAL** | theme/contrast (W4-13), i18n parity (W4-14), WASM base URL + hash (W4-11), run-card error scope (W4-10), noise predicate (W3-12); full feature-completion matrix owed |
| W14 | Windows EXE completion (hard gate) | **NOT_STARTED** | build script exists; not exercised this session |
| W15 | Docs/localization/security/hardening | **PARTIAL** | SECURITY.md/classifiers fixed (W3-18), licence register (W3-20), llms.txt (W3-16) |
| W16 | Cross-surface regression + freeze | **NOT_STARTED** | |
| W17 | Independent release audit + authorization | **NOT_STARTED** | maintainer authorization required |
| W18 | Release + post-release verification | **NOT_STARTED** | maintainer authorization required |

---

## 2. V6 backlog carry-forward (V7 §19.0) — T6-01 … T6-13

| V6 ID | Item | Maps to V7 | Status |
|---|---|---|---|
| T6-01 | QG `ExecutionPlan` parity (Python/CLI/MCP/Studio) | W1, W12 | NOT_STARTED (generic ExecutionPlan is done; QG plan parity owed) |
| T6-02 | Studio + Web QG Lab screens | W12, W13 | NOT_STARTED |
| T6-03 | Native CPU-only CMake target | W11 | DONE (prior agent; verified W4-16) |
| T6-04 | Vulkan parity + device-loss/teardown | W11 | NOT_STARTED |
| T6-05 | Web conformance corpus (Python/WASM/WebGPU) | W3, W13 | PARTIAL (existing conformance corpus; WebGPU drift owed) |
| T6-06 | WebGPU fallback + device-loss/low-memory tests | W13 | PARTIAL (forge device-loss e2e exists; main-path owed) |
| T6-07 | Packaging: wheel/sdist/CPU/Vulkan EXE/SBOM/checksums | W16, W14 | PARTIAL (build constraints W3-17; artifacts owed) |
| T6-08 | SAT separator/OMNIWAVE budget + proof soundness | W9 | DONE-in-part (D3, W3-08 baseline, W4-07) |
| T6-09 | SYK forward/mirror follow-up | W8, W10 | NOT_RUN (needs key/authorization) |
| T6-10 | BMV scan/drift/uncertainty | W8 | PARTIAL (board reconciled; held-out analysis owed) |
| T6-11 | Mutation/fuzz/resource hardening | W3, W15 | PARTIAL (mutation 63/63; fuzz/resource owed) |
| T6-12 | Version/migration/changelog/release notes | W15, W18 | PARTIAL (version decision D-007; bump at W10-01 → V7 W16) |
| T6-13 | Independent candidate-SHA audit | W17 | NOT_STARTED |

---

## 3. This branch's V6 Wave-3 (honesty) — status

W3-01 D1 Path A shots **DONE** · W3-02 D10 Path B hygiene **DONE** · W3-03 D12 Path C label
audit **DONE** (not reproduced) · W3-04 Path B vs dense **DONE** · W3-05 D2 runner ledger
**DONE** · W3-06 D4 uncovered gates **DONE** · W3-07 D4 synthetic profile **DONE** · W3-08 SAT
baseline **DONE** · W3-09 D3 `certified`/`proof_level` **DONE** · W3-10 D3 proof deadline
**DONE** · W3-11 python-sat subprocess isolation **NOT_RUN** · W3-12 D5 web noise predicate
**DONE** · W3-13 Forge axe `wcag22aa` **DONE** · W3-14 Rust pin **DONE** (wasm rebuild NOT_RUN) ·
W3-15 D7 MCP bounds **DONE** · W3-16 llms.txt **DONE** · W3-17 build constraints **DONE** ·
W3-18 D8 version surfaces **DONE** · W3-19 D11 mutant count **DONE** · W3-20 licence register
**DONE** · W3-21 D9 QG board **DONE**. (Full detail: `WAVE3_REPORT.md`.)

## 4. This branch's V6 Wave-4 (contracts/hardening) — status

W4-01 threaded MCP + cancel **NOT_STARTED** · W4-02 MCP `isError`/`-32602` **DONE** · W4-03
shared service layer + `cq-hecs plan` + parity corpus **NOT_STARTED** · W4-04 ExecutionPlan
schema **PARTIAL** (OpenAPI + `/api/v1` owed) · W4-05 MCP negotiation/annotations **NOT_STARTED**
· W4-06 doctor + Studio token **DONE** · W4-07 `hcs.sat.count.v1` **DONE** · W4-08 separator
calibration **NOT_STARTED** · W4-09 WebGPU device-loss **NOT_STARTED** · W4-10 run-card error
scope **DONE** (Python parity owed) · W4-11 WASM base URL + hash **DONE** · W4-12 composer
keyboard/touch **NOT_STARTED** · W4-13 theme + contrast **DONE** · W4-14 XSS + i18n **PARTIAL**
(i18n parity done) · W4-15 mobile viewport projects **NOT_STARTED** · W4-16 CPU-only loader-free
**DONE** · W4-17 VkResult/fault-injection **NOT_STARTED** · W4-18 C ABI hardening **NOT_STARTED**
· W4-19 sanitizer lane **NOT_RUN** · W4-20 skip budget **DONE** · W4-21 QG/router mutants
**DONE** · W4-22 CI wiring **DONE** · W4-23 version decision **DONE**.

---

## 5. PLAN.md topics (mapped)

`PLAN.md` (1193 lines, German) is read at section level. Its §13 milestones M0–M12 and its
hypothesis classes map onto V7 waves as follows. Item-level detail within each milestone is
tracked as it is executed; nothing here is a new obligation beyond V7.

| PLAN.md item | Maps to V7 | Status |
|---|---|---|
| M0 Safe start + baseline freeze | W0 | PARTIAL (baseline reproduced) |
| M1 Claim/architecture/docs review | W1 | PARTIAL (`CLAIM_AUDIT.md` first cut; ARCHITECTURE split owed) |
| M2 Literature deep read + formal transfer audit | W2 | NOT_STARTED |
| M3 Test harness + evidence ledger | W3 | PARTIAL (skip budget, mutation, schemas, doc-consistency) |
| M4 SAT result contract + proof boundary | W9 | DONE-in-part (D3 `certified`/`proof_level`, W3-09/W3-10) |
| M5 SAT performance + research | W9 | PARTIAL (baseline captured; benchmarks owed) |
| M6 Math/quantum prototype | W5, W6, W7 | PARTIAL (B/C assurance started) |
| M7 Quantum core/native/noise hardening | W5, W6, W10, W11 | PARTIAL (CPU-only verified; Vulkan/noise owed) |
| M8 Backend/API/CLI/MCP + packaging | W11, W12, W16 | PARTIAL (MCP bounds/errors; packaging owed) |
| M9 Studio/Web UX/visual quality | W13 | PARTIAL (theme/contrast/i18n/run-card) |
| M10 Vercel preview/cloud/security | W13, W14, W15 | NOT_STARTED |
| M11 Release-candidate audit | W16, W17 | NOT_STARTED |
| M12 Stable release + post-release | W18 | NOT_STARTED |
| H-SAT-01…06 (watched, CDCL, adapter, parity, #SAT, proof) | W9 | DONE-in-part (watched + proof contracts; CDCL not started) |
| H-QUANT-01/02 (2D TN, Pauli selection) | W5, W6, W7 | NOT_STARTED (E/F/G research-only) |
| H-NOISE-01 (profile transfer) | W10 | NOT_RUN (needs held-out data) |
| H-UX-01 (explainability/provenance) | W13 | PARTIAL |

Obligation: the PLAN.md hypotheses must be carried into the V7 hypothesis register at W2 with a
precise claim, assumptions, transfer class and falsification criteria.

---

## 6. Open obligations (next work, in V7 order)

1. **W0/W1 finish:** a V7 `BASELINE.md` refresh and the remaining claim audit (DE/FR README,
   ARCHITECTURE split, `docs/**`, `PLAN.md`). `SOURCE_TREE_MAP.md`, `CLAIM_AUDIT.md` and
   `FEATURE_COVERAGE.*` are created (first cuts; `TODO_VERIFY` cells to close).
2. **W2:** carry the PLAN.md hypotheses into the V7 hypothesis register (claim, assumptions,
   transfer class, falsification) and produce the literature/claim matrices.
3. **W4 (Lean):** BLOCKED — no toolchain in this environment; requires installing Lean + Mathlib
   (network). Recorded, not faked.
4. **W1/W3:** unify the fixture/digest policy and add cross-surface conformance fixtures.
5. Then continue in V7 order; keep **W13 (Web)** and **W14 (EXE)** on the critical path.
