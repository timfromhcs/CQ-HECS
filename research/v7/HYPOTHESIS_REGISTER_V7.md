# HYPOTHESIS_REGISTER_V7.md — consolidated hypothesis register (V7 W2)

Created 2026-11-21 on branch `agent/v6-rc`. Consolidates the PLAN.md hypotheses (H-SAT-*,
H-QUANT-*, H-NOISE-*, H-UX-*), the V6 hypotheses (`HYPOTHESES.md`: H4-*), and the V7 research
directions (paths E/F/G, Lean, QEC/RL) into one register. Existing `HYPOTHESES.md` and
`FINDINGS.md` are preserved (V7 §17.2); the detailed preregistrations stay in their source files.

Transfer classification (V7 §6.1): `DIRECT_TRANSFER`, `ADAPTABLE`, `VALIDATION_ONLY`,
`CONTEXT_ONLY`, `DEFERRED`, `NOT_REPRODUCIBLE`.

Status: `SUPPORTED_IN_SCOPE`, `NOT_SUPPORTED`, `INCONCLUSIVE`, `NOT_STARTED`, `NOT_RUN`,
`DEFERRED`, `PARTIAL`, `REJECTED`. A status changes only on its preregistered test.

| ID | Claim (scope) | V7 wave | Transfer class | Status | Evidence / source |
|---|---|---|---|---|---|
| H4-ROUTE-01 | A cost-aware router picks a lower-cost supported path than fixed A→B→C→D | W6 | ADAPTABLE | DEFERRED | `HYPOTHESES.md`; needs a held-out regret suite |
| H4-SAT-01 | Variable elimination exactly and quickly counts bounded-width CNF | W9 | DIRECT_TRANSFER | SUPPORTED_IN_SCOPE | FINDINGS F-001; `evidence/sat_separator_bench.json` |
| H4-PAULI-01 | Native X/Y/Z propagation with a per-observable certified bound | W5 | DIRECT_TRANSFER | SUPPORTED_IN_SCOPE | FINDINGS F-003; `tests/test_path_d_pauli_observables.py` |
| H-SAT-01 | Two-watched literals reduce propagation work vs scan DPLL | W9 | DIRECT_TRANSFER | SUPPORTED (opt-in) | `sat.py` watched path + benchmark |
| H-SAT-02 | An own CDCL solver can beat the own DPLL on realistic instances | W9 | ADAPTABLE | NOT_STARTED | PLAN.md §5.3; research-only until proven |
| H-SAT-03 | An optional external solver adapter adds breadth while preserving the trust boundary | W9 | ADAPTABLE | PARTIAL | `sat_external.py`; D3 trust boundary |
| H-SAT-04 | Sparse parity preprocessing reduces some CNF families (without changing counts) | W9 | ADAPTABLE | NOT_STARTED | `sat_separator.py` recognises exact parity only |
| H-SAT-05 | #SAT needs its own contract and algorithm path | W9 | DIRECT_TRANSFER | SUPPORTED | `hcs.sat.count.v1` (W4-07) |
| H-SAT-06 | Proof-carrying UNSAT is more checkable than an internal solver label | W9 | DIRECT_TRANSFER | SUPPORTED_IN_SCOPE | `certified`/`proof_level` (W3-09); `drat.py` |
| H-QUANT-01 | A 2D tensor-network prototype extends the suitable circuit families | W7 | CONTEXT_ONLY | NOT_STARTED | PLAN.md §5.3; path E research-only |
| H-QUANT-02 | Better Pauli-term selection keeps certification intact | W5 | DIRECT_TRANSFER | PARTIAL | per-observable bound (F-003) |
| H-NOISE-01 | New calibration profiles generalise across independent QPU splits | W10 | VALIDATION_ONLY | NOT_RUN | needs held-out data + authorization |
| H-UX-01 | Explainability and data provenance improve user understanding | W13 | ADAPTABLE | PARTIAL | run-card `error_scope`, plan explain |
| V7-E | Geometry-aware 2D tensor networks are a promotable Path E | W7 | CONTEXT_ONLY | NOT_STARTED | V7 §9.1 |
| V7-F | MPS quantum-trajectory / open-system simulation is a promotable Path F | W7 | CONTEXT_ONLY | NOT_STARTED | V7 §9.2 |
| V7-G | Matrix-product evolution (MPE) is a promotable Path G | W7 | CONTEXT_ONLY | NOT_STARTED | V7 §9.3 |
| V7-LEAN-01 | Small stabilizer/Pauli invariants are formalizable in Lean/Mathlib | W4/W5 | VALIDATION_ONLY | NOT_RUN | no Lean toolchain here |
| V7-QEC-01 | Adaptive/RL calibration improves held-out control (research) | W10 | CONTEXT_ONLY | NOT_STARTED | V7 §12.3; hardware-gated |

## Rules carried into V7

- A hypothesis is supported only by its preregistered test, never by exploratory tuning.
- A confidence interval crossing the null is `INCONCLUSIVE`, not "almost supported".
- No asymptotic, ETH/SETH or P=NP inference from any benchmark curve.
- Research paths E/F/G and CDCL stay opt-in / `RESEARCH_ONLY` until their promotion gates pass;
  the default router is unchanged absent proof and benchmarks.

## Open W2 obligations

- Pin exact source revisions/DOIs for the V7 §6/§25 literature (Lean-Quantum, Lean-QIT, FloatLib,
  Rudolph & Tindall 2D TN, Kawabe MPE, Sivak QEC/RL, SAT Competition 2026) into
  `LITERATURE_MAP.md`, then replicate the small results feasible locally.
- Produce `QUANTUM_SIMULATION_RESEARCH.md`, `SAT_PROOF_REVIEW.md`, `NOISE_QEC_RESEARCH.md`.
