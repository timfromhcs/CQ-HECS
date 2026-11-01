# Decisions

## D-001 Scope of v4.0.0 (2026-11-01)
AGENTS.md section 16: "a small v4 with two genuinely correct improvements is
better than a large v4 full of unverified engines". Promoted candidates:

1. **Explainable ExecutionPlan** (section 3.2). Pure analysis over the shared
   gate manifest; zero backend allocation; routing semantics unchanged.
2. **Separator / elimination #SAT backend** (section 3.9A). Prototype existed in
   `research/v6/prototypes/separator_count.py` with an exhaustive oracle test.

Everything else in AGENTS.md section 3.3-3.10 is DEFERRED and is *not*
described as shipped anywhere. Rationale: each of the others needs its own
oracle, held-out benchmark and (for Path C ordering, noise v3, CDCL) a
preregistered acceptance gate that cannot be satisfied cheaply or honestly in
one pass.

## D-002 Plan is a report, router stays authoritative
`ExecutionPlan.selected_path` reuses `CircuitAnalyzer.recommended_path`; it does
not introduce a second routing policy. Cost estimates may only produce a typed
`RESOURCE_BUDGET` refusal for the *selected* path, never a silent path switch.
A learned/adaptive policy stays out of v4 (AGENTS.md 3.2: opt-in, seeded,
held-out).

## D-003 Plan-vs-actual is observation only
`metadata["plan_check"]` records planned vs actual path and elapsed time. It
never feeds back into later routing (reproducibility).

## D-004 Line endings
The work tree is CRLF (`core.autocrlf=true`), the repository stores LF. New and
edited files keep CRLF in the work tree so diffs stay minimal.
