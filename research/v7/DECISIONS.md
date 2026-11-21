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

## D-005 Path B is a low-T dense branch-sum method, not a stabilizer-rank advantage (2026-11-21)
Finding F-005 (W3-04) measured Path B against a plain dense Qiskit `Statevector` on a
fixed seeded corpus: Path B is slower on every case (2x at T=0 up to ~181x at T=8). It
contracts onto a dense statevector and carries none of the sparse-extent advantage that
would justify a stabilizer-rank method.

Decision: (1) describe Path B honestly as a branch decomposition over a dense statevector
(fix the remaining prose claims as they are encountered); (2) do **not** re-order the
router in Wave 3 — a router change is an H4-ROUTE-01 hypothesis with its own held-out
regret/refusal gate and belongs to Wave 6. No product behaviour changes here.

## D-006 Wave 3 defect dispositions (2026-11-21)
D3 second half (W3-10 deadline covers proof checking) is DEFERRED (B-005) rather than
half-fixed: a correct fix threads the remaining grand deadline from `unified` into each
engine, and a partial fix (bounding one engine's proof budget) would still let search +
proof exceed the caller's total. The verdict-honesty half of D3 (rejected proof is never
"checked") is fixed. D12 (Path C exact label) is NOT REPRODUCED as a defect (F-004).

