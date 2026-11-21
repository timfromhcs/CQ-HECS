# QGRAVITY — LIVE STATUS (durable resume state)

> Read this first after any interruption. Update it at every milestone boundary.
> Last update: 2026-11-21 (session 1).

## Current position

- Branch: `research/quantum-gravity-studio` (from `main` `fa1cc87`).
- Done this session: **M0–M5** (local vertical slice), **M8 local** (Studio API + MCP + CLI),
  Track A noise model, Track C bounded gauge toy, and a **real-QPU campaign** (smoke, BMV phase
  scan, SYK).
- In progress / next: M6 runner (functional), M9/M10/M11/M12; SYK hardware follow-up (F-10).
- Blocker: **B-1 RESOLVED**. Live QPU work done (21/25 Spark). **Key wiped** — a new key is
  needed for further runs; rotate the used key at the portal.

## Live QPU campaign (Stage 2 smoke) — COMPLETE

- Backend `rigetti:cepheus-1-108q` (live `QPU`), 1000 shots/circuit, Public/Standard.
- 4 preregistered circuits; quoted **4 credits**; **4 submitted, 4 Completed**. No refunds.
- Job ids: `9e8ae264…`, `fadc0f89…`, `e9641514…`, `24e61d7d…`.
- Result (in-support): basis 0.899, bell 0.954, ghz3 0.906, mirror 0.979. Bit order: little-endian.
- Raw evidence: `research/qg_2026/raw/qpu_smoke/` (+ `EVIDENCE_MANIFEST.json`).
- **Spark spent: 4 / 25.** Remaining: 21.

### Next scientific step (Stage 3 — BMV)

**Stage 3 status:** preregistered (`QPU_BMV.md`) and **complete** — full 5-point phase scan
(θ ∈ {0, π/8, π/4, 3π/8, π/2}) in {Y⊗Z, Z⊗Y} plus X⊗X at 3 points; 13 jobs, 1000 shots,
Public/Standard; **13 credits** (cumulative **17 / 25**). Result (F-08): ⟨Y⊗Z⟩ = 0.014/0.298/
0.616/0.734/0.854 and ⟨Z⊗Y⟩ = 0.012/0.386/0.666/0.820/0.874 across the scan; θ=0 null ~0;
measured value ≈ 0.85–1.0 × sinθ. Raw evidence: `raw/bmv_qpu/`, `raw/bmv_scan2/`.

**Stage 4 status:** SYK Trotter test. v1 **INVALID** (F-09). Corrected **v3** results: mirror
P(000)=0.947 [0.933,0.961], forward P(000)=0.118 [0.098,0.138] vs Trotter ideal 0.2326 —
mutually inconsistent under any single noise level → **INCONCLUSIVE** (F-10). The no-rewiring
retry (v4) failed on the contiguous-virtual-qubit constraint (F-11). No SYK hardware claim.

**Campaign spend:** **25 / 25 Spark** (2 failed/refunded); Full credits untouched. Drift repeat
and the ⟨X⊗X⟩(θ) trend recorded (F-11). Key wiped at session end (rotate at the portal).
- Remote: branch pushed; **PR #54** open (https://github.com/timfromhcs/CQ-HECS/pull/54); CI running.

## Next action (do this first on resume)

1. Run `python -m pytest tests/test_quantum_gravity_*.py -q` — must be green (currently 67).
2. Advance the highest milestone not `DONE` in `PLAN.md` §2. Options that need no credentials:
   - M6: strengthen the runner (`analyse`/`report` from raw evidence) + tests.
   - M8: Studio `/api/qg/v1/*` routes + MCP tools (local, no network).
   - M10: native CPU-only CMake split (`-DCQ_ENABLE_VULKAN=OFF`).
   - M9: Web/Studio QG Lab UI.
3. If `B-1` is resolved (Client Secret provided), run `doctor` then `discover` (read-only).

## Milestone board

| M | Status |
|---|---|
| M0 Baseline & safety | DONE |
| M1 Literature map | DONE (map drafted; DOI re-verify at M13) |
| M2 Hypotheses/prereg | DONE (registry + protocol + matrix + ledgers) |
| M3 BMV effective-phase | DONE (local; noise model QG-BMV-03 verified, device comparison NOT_RUN) |
| M4 SYK reference | DONE (exact; Trotter implemented, QG-SYK-02 partial) |
| M5 Contract integration | DONE (`cqhecs.quantum_gravity`, `cqhecs.qg.experiment.v1`, CLI, docs) |
| M6 OQ adapter/runner | IN_PROGRESS — BLOCKED for quote/submit (B-1) |
| M7 QPU campaign | BLOCKED (B-1, credits) |
| M8 Studio API + MCP | IN_PROGRESS (local routes + 3 MCP tools done; paid OQ proxy pending B-1) |
| M9 Web/Studio UI | NOT_RUN |
| M10 CPU/Vulkan split | NOT_RUN (scoped: headers `cq_hecs/vulkan/*` + tensor_network/constraint_solver couple Vulkan) |
| M11 WebGPU path | NOT_RUN |
| M12 Packaging | NOT_RUN |
| M13 Hardening/audit | IN_PROGRESS (full suite green; static gates clean; secret scan pending) |
| M14 Handoff | IN_PROGRESS (FINAL_REPORT draft + PR #54) |
| Track C gauge | SUPPORTED_WITHIN_MODEL (bounded `qg.gauge.z2.v1` toy) |

## Guardrails confirmed this session

- Historical `research/v3` `r-io-7` evidence untouched.
- No secret written into the repository tree; local credential file lives outside the repo.
- Loop heartbeat armed (temp, non-repo) to resume from this file every 2 minutes.
