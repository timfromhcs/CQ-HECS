# v6 task ledger

Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `PASS`, `FAIL`, `DEFERRED`, `NOT_APPLICABLE`.
Every task points to evidence in `EVIDENCE_LEDGER.md` or `TEST_MATRIX.md`.

| ID | Milestone | Task | Owner | Status |
| :--- | :--- | :--- | :--- | :--- |
| T6-M0-01 | M0 | Capture branch, SHA, tags, version, dirty state, remotes | lead | PASS |
| T6-M0-02 | M0 | Preserve user files (`PLAN-v3.6.0.md`, `.claude/launch.json`) | lead | PASS |
| T6-M0-03 | M0 | Verify `origin/main` and reconcile with v3.5.0 audit | lead | PASS |
| T6-M0-04 | M0 | Re-read v3.5.0 release metadata and prior independent audit | lead | PASS |
| T6-M0-05 | M0 | Create isolated branch from verified `origin/main` | lead | PASS |
| T6-M1-01 | M1 | Python compileall + version consistency | lead | PASS |
| T6-M1-02 | M1 | Full local pytest baseline | lead | PASS (counts recorded) |
| T6-M1-03 | M1 | Native CTest baseline | lead | PASS |
| T6-M1-04 | M1 | Web unit tests and production build baseline | lead | PASS |
| T6-M1-05 | M1 | Mutation baseline | lead | PASS (54/54; watched mutants TODO) |
| T6-M1-06 | M1 | Playwright/axe local baseline | lead | PASS (13/13) |
| T6-M2-01 | M2 | Live architecture and capability matrix | lead | PASS |
| T6-M2-02 | M2 | Pin OpenAI/Anthropic sources and record verification status | lead | PASS (v5 audit, not re-run) |
| T6-M2-03 | M2 | SAT/#SAT/proof comparison literature map | lead | PASS (scope map) |
| T6-M2-04 | M2 | Reproduce OMNIWAVE benchmark | lead | PASS (quick, raw JSON) |
| T6-M3-01 | M3 | Audit status/certification drift across Python/CLI/MCP/Studio/Web | lead | PASS |
| T6-M3-02 | M3 | Fix unsound partial-assignment predicate + regression | lead | PASS |
| T6-M3-03 | M3 | Original vs canonical DIMACS digest | lead | PASS |
| T6-M3-04 | M3 | Duplicate-literal normalization decision | lead | PASS |
| T6-M3-05 | M3 | Timeout budget composition for solve + certificate | lead | PASS |
| T6-M3-06 | M3 | Browser SAT input digest / contract parity | lead | PASS |
| T6-M4-01 | M4 | Two-watched-literal engine behind opt-in flag | lead | PASS |
| T6-M4-02 | M4 | Differential tests vs scan DPLL and brute force | lead | PASS |
| T6-M4-03 | M4 | Edge cases: units, empty, tautology, budget, determinism | lead | PASS |
| T6-M4-04 | M4 | Reproducible scan-vs-watched benchmark | lead | PASS |
| T6-M4-05 | M4 | CLI `--engine watched` wiring + contract test | lead | PASS |
| T6-M5-01 | M5 | DRAT checker audit and external proof vectors | lead | PASS |
| T6-M5-02 | M5 | Optional LRAT/CakeLPR verification path | lead | PASS (manual CakeLPR check; CI TODO) |
| T6-M5-03 | M5 | Lean statement/axiom build for ETH artifacts | lead | PASS (build + Comparator + nanoda) |
| T6-M6-01 | M6 | Decide reusable OMNIWAVE primitives vs research-only | lead | PASS (research-only) |
| T6-M7-01 | M7 | GF(2) extraction witness audit | lead | PASS (no production extraction) |
| T6-M7-02 | M7 | Separator/treewidth exact count prototype | lead | PASS (research-only) |
| T6-M8-01 | M8 | CDCL prototype (only after M4/M5) | lead | DEFERRED |
| T6-M9-01 | M9 | Revalidate paths A–D against references | lead | PASS (full suite) |
| T6-M9-02 | M9 | Vulkan/WebGPU end-to-end evidence, not shader-only | lead | PASS (primitive dispatch; no end-to-end claim) |
| T6-M9-03 | M9 | Fix native Vulkan teardown crash and add process-exit regression | lead | PASS |
| T6-M10-01 | M10 | Web/Studio status and provenance UX audit | lead | PASS |
| T6-M10-02 | M10 | Responsive screenshots at 360/390/768/1024/1440/1920 | lead | PASS |
| T6-M11-01 | M11 | Secret scan, dependency/licence audit, workflow permissions | lead | PASS |
| T6-M11-02 | M11 | Clean wheel/sdist install smoke | lead | PASS |
| T6-M12-01 | M12 | Local release-candidate gate L0–L10 | lead | TODO |
| T6-M13-01 | M13 | Push feature branch, PR, exact-SHA CI | lead | TODO |
| T6-M13-02 | M13 | Vercel Preview exact-SHA smoke | lead | TODO |
| T6-M14-01 | M14 | Merge, Production, release asset verification | lead | TODO |
| T6-M15-01 | M15 | Post-release audit and backlog | lead | TODO |
