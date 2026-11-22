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
D3 is fully fixed: the verdict-honesty half (a rejected proof is never "checked") and the
deadline half (W3-10 — the proof check is bounded by the remaining deadline in both
`sat_external` and OMNIWAVE; an exhausted deadline yields UNKNOWN). D12 (Path C exact
label) is NOT REPRODUCED as a defect (F-004). W3-11 (python-sat child-process isolation)
is NOT RUN because python-sat is not installed where this session ran.

## D-007 Version decision: v6.0.0 (2026-11-21, Wave 4)
Wave 4 exit decision (PLAN_V6 decision 1). **The next release is `6.0.0`, not `5.1.0`,
because a caller-visible breaking change shipped in Wave 3.** Migration file:
`MIGRATION_V6.md` (authored at Wave 10).

Breaking change (major reason):

- **Path A shot contract (D1, W3-01).** A wide (n > 30) non-all-equal circuit no longer
  returns a silently truncated count; it draws every requested shot or raises
  `PathAShotBudgetError`. A caller that relied on the old ~100-shot behaviour must pass
  `max_resample_shots` explicitly. This changes the meaning of a public result field
  (`counts` sum / `sampled_shots`), so it is a breaking change.

Additive changes (no break; listed for the migration doc):

- SAT: `UnifiedResult.certified`/`proof_level`, `SATResult.proof_status`,
  `solve_unified(require_certified=...)`, `hcs.sat.count.v1` schema id.
- Hardware: `BackendProfile.uncovered_gates`, `FakeHardwareBackend(uncovered_gate_policy)`,
  `SimulationResult.uncovered_gates`; synthetic profiles carry no capture timestamp.
- MCP: server-side input bounds (out-of-range input is refused).
- Web run card: explicit engine precision (`f64`/`f32`/`n/a`) and a WebGPU `cross_check_tv`.

`scripts/check_version.py` must keep passing on whatever `scripts/version.py` reports; the
bump itself happens at Wave 10 (W10-01), not here.

## D-008 AGENTS_V7.md is the governing execution contract (2026-11-21)
The maintainer added `AGENTS_V7.md` (untracked at the repo root) as the new work order for
the next major release. It is adopted here as the **governing execution contract**. `AGENTS_V7.md`
supersedes the *execution order* of `AGENTS_V6.md` and `PLAN.md`, but does not erase their
technical obligations. Where V7 conflicts with an older plan, the stricter condition wins;
the conflict is recorded here. `AGENTS_V7.md` is committed onto this branch so the contract
travels with the work (matching how `AGENTS_V6.md` was added).

Consequences for this branch's completed work — all of it is retained and mapped, none is
renamed or dropped (V7 §19.0):

- The Wave-3 honesty fixes (D1–D12) map to V7 **W1** (interface/claim freeze) and are
  additive except the Path A shot contract (D1), which is the recorded breaking change D-007
  relies on.
- The Wave-4 contracts and gates map to V7 **W0** (baseline), **W3** (test harness/evidence:
  skip budget, mutation suite, ExecutionPlan schema, QG doc consistency) and **W1**
  (`hcs.sat.count.v1` is additive).
- The CPU-only native build + loader-free verification (T6-03 / W4-16) maps to V7 **W11**.
- Web theme/contrast/i18n/WASM-URL/run-card work maps to V7 **W13** (a hard product gate:
  Web and the Windows EXE must not be deferred past the release).
- `research/v7/PLAN_COVERAGE.md` is the required mapping of every V6/V7/PLAN item to a V7
  wave/task/status/owner/gate; it is created alongside this decision.

§19.0 carry-forward: the V6 backlog T6-01..T6-13 is preserved and re-mapped in
`PLAN_COVERAGE.md`; no V6 task ID is silently dropped or renamed.

## D-009 Version decision: 7.0.0 (2026-11-22, freeze), supersedes D-007
The maintainer asked for "v7 stable". The release version is therefore `7.0.0`, superseding
D-007's `6.0.0`. Going from 5.0.0 to 7.0.0 skips 6, which was only an internal planning label
and was never tagged or published; there is no 6.x release. `MIGRATION_V7.md` states this and
migrates "from 5.0.0 to 7.0.0". The D-007 breaking-change rationale (Path A shot contract)
still holds and justifies a major bump. Nothing is published by this decision; the README
"last published release" stays `v5.0.0` until publication.
