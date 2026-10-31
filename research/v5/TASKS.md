# v5 task list (target release v3.5.0)

Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `PASS`, `FAIL`, `DEFERRED`, `NOT_APPLICABLE`.
Each task records its evidence in `EVIDENCE_LEDGER.md`.

| ID | Milestone | Task | Status |
| :--- | :--- | :--- | :--- |
| T-M0-01 | M0 | Baseline SHA, tags, dirty state, version (`BASELINE.md`) | PASS |
| T-M0-02 | M0 | Keep user files (`PLAN.md` committed, `.claude/launch.json` untouched) | PASS |
| T-M0-05 | M0 | `cloudbuild.yaml`: no visible trigger; kept, marked UNVERIFIED_LEGACY | PASS |
| T-M2-01 | M2 | Read the OpenAI ETH manuscript (abstract, Thm 1.1), Lean scope, comparator statement | PASS |
| T-M2-02 | M2 | Read the Anthropic README, MainResults.lean, Challenge.lean, comparator config | PASS |
| T-M2-03 | M2 | Re-run either Lean build / comparator / nanoda | BLOCKED (B-01) |
| T-M2-04 | M2 | Claim matrix + transfer classes (`COMPLEXITY_CLAIM_AUDIT.md`) | PASS |
| T-M2-05 | M2 | Full read of all ≈4800 lines of proof | DEFERRED |
| T-M1-01 | M1 | Update ETH text in Studio, web guide (EN/DE/FR), v4 doc | TODO |
| T-M1-03 | M1 | Mark GEMINI.md / GEMINI_HANDOFF.md as historical | TODO |
| T-M1-04 | M1 | Document Python A–D vs browser WASM/WebGPU vs SAT engines | TODO |
| T-M4-01 | M4 | SAT certification field on Python/CLI/MCP/Studio | TODO |
| T-M4-02 | M4 | Browser SAT: UNSAT shown as not independently certified | TODO |
| T-M5-01 | M5 | Exact #SAT `count_models` + brute-force oracle (H-SAT-05) | TODO |
| T-M5-02 | M5 | Optional CaDiCaL adapter + independent DRAT checker (H-SAT-03/06) | TODO |
| T-M5-03 | M5 | Proof-corruption tests (mutated/truncated/wrong-formula proofs) | TODO |
| T-M5-04 | M5 | CDCL prototype (H-SAT-02) | DEFERRED |
| T-M5-05 | M5 | SAT Competition 2026 benchmark subset | DEFERRED (B-03) |
| T-M6-01 | M6 | GF(2) counting-preservation prototype (research-only) | TODO |
| T-M6-02 | M6 | 2D tensor-network prototype (H-QUANT-01) | DEFERRED |
| T-M9-01 | M9 | `docs/DESIGN_SYSTEM.md` | TODO |
| T-M9-02 | M9 | Web: engine/precision/provenance panel + JSON result export | TODO |
| T-M9-03 | M9 | Web: #SAT counter in SAT lab | TODO |
| T-M9-04 | M9 | Playwright E2E + axe in CI, screenshots at 6 viewports | TODO |
| T-M10-01 | M10 | PR CI on exact SHA, Vercel preview SHA match + smoke | TODO |
| T-M11-01 | M11 | v3.5.0 version/docs, packages, exe, hashes | TODO |
| T-M12-01 | M12 | Merge, release, post-release audit, FINAL_REPORT | TODO |
