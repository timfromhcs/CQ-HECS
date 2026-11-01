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
| M3 | Result schema / contracts | PARTIAL: `plan_check` metadata added additively; no field changed meaning |
| M4 | Explainable ExecutionPlan (Python/CLI/MCP/Studio API) | SUPPORTED_IN_SCOPE (Python+CLI+MCP+Studio API); Studio *UI panel* NOT STARTED |
| M5 | Path D general Pauli observables | DEFERRED (not started; needs phase-convention spec + dense oracle first) |
| M6 | Path C graph-aware ordering | DEFERRED |
| M7 | Noise calibration schema v3 | DEFERRED |
| M8 | Browser/Python/native conformance corpus | NOT STARTED |
| M9 | Native/GPU correctness+performance | NOT STARTED (Vulkan toolchain unverified) |
| M10 | Exact separator #SAT backend | IN_PROGRESS |
| M11 | CNF-to-XOR with witness | DEFERRED |
| M12 | Optional CDCL | DEFERRED |
| M13 | OMNIWAVE v4 experiments | DEFERRED |
| M14 | Formal verification | DEFERRED |
| M15 | UX/docs/provenance | NOT STARTED |
| M16 | Hardening/security | NOT STARTED |
| M17 | Local release-candidate gates | NOT STARTED |
| M18 | Remote CI/preview loop | NOT STARTED |
| M19 | Release decision | NOT STARTED -- publishing requires explicit user authorization |
