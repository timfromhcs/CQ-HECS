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
| H-SAT-03 | An optional external solver adapter adds breadth while preserving the trust boundary | W9 | ADAPTABLE | PARTIAL | `sat_external.py`; D3 trust boundary; A4 child isolation; abort 0xC0000409 reproduced on 3.13 (A4) and 3.14 (D5), see update below |
| H-SAT-04 | Sparse parity preprocessing reduces some CNF families (without changing counts) | W9 | ADAPTABLE | NOT_STARTED | `sat_separator.py` recognises exact parity only |
| H-SAT-05 | #SAT needs its own contract and algorithm path | W9 | DIRECT_TRANSFER | SUPPORTED | `hcs.sat.count.v1` (W4-07) |
| H-SAT-06 | Proof-carrying UNSAT is more checkable than an internal solver label | W9 | DIRECT_TRANSFER | SUPPORTED_IN_SCOPE | `certified`/`proof_level` (W3-09); `drat.py` |
| H-QUANT-01 | A 2D tensor-network prototype extends the suitable circuit families | W7 | CONTEXT_ONLY | INCONCLUSIVE (RESEARCH_ONLY) | `evidence/waveB_B5.md`, `QUANTUM_SIMULATION_RESEARCH.md` section 3 |
| H-QUANT-02 | Better Pauli-term selection keeps certification intact | W5 | DIRECT_TRANSFER | PARTIAL | per-observable bound (F-003) |
| H-NOISE-01 | New calibration profiles generalise across independent QPU splits | W10 | VALIDATION_ONLY | NOT_RUN | needs held-out data + authorization |
| H-UX-01 | Explainability and data provenance improve user understanding | W13 | ADAPTABLE | PARTIAL | run-card `error_scope`, plan explain |
| V7-E | Geometry-aware 2D tensor networks are a promotable Path E | W7 | CONTEXT_ONLY | INCONCLUSIVE (RESEARCH_ONLY) | B5: E-1..E-3 pass with caveats, E-5 not implemented |
| V7-F | MPS quantum-trajectory / open-system simulation is a promotable Path F | W7 | CONTEXT_ONLY | NOT_SUPPORTED (RESEARCH_ONLY) | B5: F-1 and F-4 fail on held-out seeds |
| V7-G | Matrix-product evolution (MPE) is a promotable Path G | W7 | CONTEXT_ONLY | NOT_SUPPORTED (RESEARCH_ONLY) | B5: G-1 fail, 0% win |
| V7-LEAN-01 | Small stabilizer/Pauli invariants are formalizable in Lean/Mathlib | W4/W5 | VALIDATION_ONLY | SUPPORTED_IN_SCOPE (FORMALIZED_LEMMA, specification level) | `formal/`, `evidence/LEAN_BUILD.md`, `evidence/waveA_A5.md`, `evidence/waveD_D5.md` |
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

## Waves A-D status update (2026-11-22, task D5)

Statuses change only on the preregistered test. Negative and inconclusive outcomes are kept.

| ID | Before | After | Basis (wave evidence) |
|---|---|---|---|
| H4-SAT-01 | SUPPORTED_IN_SCOPE | SUPPORTED_IN_SCOPE (unchanged) | A4: separator preflight bound `2**(w+1)`; 31 calibration rows, 0 violations of observed <= predicted, max induced width 14. Upper bound, not a runtime estimate. |
| H4-PAULI-01 | SUPPORTED_IN_SCOPE | SUPPORTED_IN_SCOPE (unchanged) | A5: sign rules and the bound lemma formalized at specification level; Python oracle vs stim tableau (n<=7, 10 seeds). |
| H-SAT-03 | PARTIAL | PARTIAL (unchanged) | A4: child-process isolation, parent re-verification. The external CaDiCaL abort 0xC0000409 at interpreter exit reproduces on Python 3.13 (A4) and 3.14.6 (D5) after a passing run; it is an external-package defect, recorded, not suppressed. Does not touch correctness of verified results. |
| H-SAT-06 | SUPPORTED_IN_SCOPE | SUPPORTED_IN_SCOPE (unchanged) | A4 tamper matrix on the pigeonhole_6_5 DRAT vector (125/235 single deletions rejected; some lemmas are redundant). In-repo LRAT replay is NOT_SUPPORTED. |
| H-QUANT-01 / V7-E | NOT_STARTED | INCONCLUSIVE (RESEARCH_ONLY) | B5: E-1..E-3 pass, but the wins come mostly from generic greedy order, the baseline is weak (no cotengra/opt_einsum), sizes are 12-16 qubits, and E-5 is not implemented. Not promoted. |
| V7-F | NOT_STARTED | NOT_SUPPORTED for promotion (RESEARCH_ONLY) | B5: F-1 and F-4 fail on held-out seeds 100-109. Recorded negative result. |
| V7-G | NOT_STARTED | NOT_SUPPORTED for promotion (RESEARCH_ONLY) | B5: G-1 fails, 0% win. Recorded negative result. |
| H-NOISE-01 | NOT_RUN | NOT_RUN (unchanged) | B4 delivered governance (calibration v3, fit/eval separation tests) but no VALIDATION split exists in r-io-7 and no held-out evaluation was run; needs authorization and data. |
| H-UX-01 | PARTIAL | PARTIAL (unchanged) | B3/C1 surfaces exist (QG lab, run cards); no comprehension measurement, so not supported. |
| H4-ROUTE-01 | DEFERRED | DEFERRED (unchanged) | B2/C3 gave plan parity across surfaces; no held-out regret suite was run. |
| V7-LEAN-01 | NOT_RUN | SUPPORTED_IN_SCOPE | Lean 4.33.1 workspace builds; lemma list in `formal/README.md`. Scope: specification lemmas only (no refinement proof; no component is FORMALLY_VERIFIED). D5 adds L-RESULT-01 (see `evidence/waveD_D5.md` for its build status). |
| H-SAT-01 | SUPPORTED (opt-in) | SUPPORTED (opt-in) (unchanged) | Not re-measured in Waves A-D. |
| H-SAT-02, H-SAT-04, V7-QEC-01 | NOT_STARTED | NOT_STARTED (unchanged) | Not touched. |
