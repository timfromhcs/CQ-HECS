# Falsifiable hypothesis catalogue

Initial status of every entry: **PROPOSED** unless explicitly changed later. P0 correctness is not displaced by feature scoring. Benchmarks follow `BENCHMARK_PROTOCOL.md`; “15%” below is an end-to-end median improvement on a held-out named family with equal result semantics, not a universal SOTA threshold.

| ID | Priority | Assumptions and falsifiable prediction | Cost / minimal independent test | Acceptance / rejection and main risk | Decision |
|---|---|---|---|---|---|
| H0 | P0 | Non-joint counts or observable/numerical bounds can be serialized as a TV `total_error_bound`. | Low. Construct result-state matrix and trace every Path D constructor; independently inspect metric semantics. | Accept defect if any invalid combination returns a TV number; fix by metric-aware non-composition/schema truthfulness. Reject only with exhaustive code path plus negative tests. Risk: backward-compatible field name hides changed meaning. | **SUPPORTED by source inspection; executable confirmation pending.** |
| H1 | P0/P1 | Path C floor discards nonzero singular values while `EXACT/error_bound=0` implies no approximation. | Medium. Singular spectra near/below/above floor; NumPy/Qiskit statevector differential and repeated truncations. | Accept only with explicit numerical-zero semantics or truthful approximate/numerical status and scoped bounds. Reject if no nonzero value can be dropped. Risk: diagnostic mistaken for global bound. | INVESTIGATING |
| H2 | P1 | Explainable calibrated cost heuristic beats fixed routing on held-out circuit families. | High. Label time/RSS/terms per path; split by family; deterministic capability/resource fallback. | >=15% total or geometric-mean improvement with explicit weights or fewer memory failures, unchanged contracts; otherwise reject/defer. Risk: leakage and wrong cost estimates. | DEFER until P0/P1 contracts |
| H3 | P1 research | Graph-aware contraction/slicing solves a named low-treewidth/2D family below Path C peak memory. | High, isolated module. Dense small-system reference, axis/conjugation/order/slicing invariance and resource refusal. | Exact small-system parity and >=15% end-to-end or material memory win on held-out named family; otherwise experimental/reject. Risk: GHZ-only false generalization. | DEFER |
| H4 | P1 research | Adaptive MPS ordering reduces peak bonds enough to repay permutation/routing overhead. | High. Natural vs graph/min-cut orders, asymmetric circuits and measurement round trips. | >=15% end-to-end held-out improvement including overhead and identical bit order; otherwise reject. Risk: permutation changes public semantics. | DEFER |
| H5 | P1 | Reusable/vectorized Clifford sampling improves repeated high-shot workloads. | Medium. CQ-HECS vs Stim/Aer, separate setup and shots at 1/100/10000+, exact compatible outputs. | >=15% end-to-end named-family gain without optional-dependency fallback; otherwise document no duplication. Risk: incompatible semantics/setup exclusion. | DEFER |
| H6 | P1/P2 | Phase/branch merging and memoization lower end-to-end cost for low-T circuits. | Medium. T-count/qubit/depth sweeps, dense reference, peak terms/RSS and timing. | >=15% end-to-end gain and equal exact values; term-count reduction alone rejects performance claim. Risk: invalid cancellation/error reuse. | DEFER |
| H7 | P1 | Observable-aware sparse Pauli batching improves selected-observable workloads. | Medium. Matrix conjugation, phase/cancellation, repeated observables, per-observable bounds. | >=15% gain with every observable certified and unresolved fail-closed; no joint-distribution promotion. Risk: combined-bound misinterpretation. | DEFER behind H0 |
| H8 | P0/P1 | Confidence helpers may mix per-outcome error with TV or mishandle support/confidence. | Low/medium. Re-derive inequalities; K=1/2/small/large, shots/delta edges and known distributions. | Every bound names metric/support/iid/delta/clamping; invalid formula is corrected with independent tests. Monte Carlo cannot prove acceptance. Risk: vacuous bound hidden as strong certificate. | QUEUED after H0/H1 source triage |
| H9 | P2 experimental | One Vulkan kernel gives physical-device end-to-end gain after all overhead. | High. CPU equivalence, validation layers, device identification, cold/warm full-path benchmark. | Physical-device output parity, no validation errors, >=15% end-to-end gain; otherwise `EXPERIMENTAL/PHYSICAL_GPU_UNVERIFIED`. Risk: software ICD mistaken for GPU. | DEFER |
| H10 | P2 optional | Explicit provider adapter can validate a small circuit on real hardware. | High, mocks first; separately authorized bounded hardware run. | Provenance/job/transpiled hash/noise metrics complete; absent credentials means BLOCKED/NOT RUN. No fake hardware. Risk: cost/quota and simulator mislabeled as hardware. | NOT RUN / OPTIONAL |
| H11 | P1 | Canonical IR reduces parser/provider/native semantic divergence without accepting unsupported dynamics. | Medium/high. Paired formats, registers/global phase/bit offsets and structured refusal tests. | Identical semantics or refusal across every public entry point with compatibility/schema tests. Risk: accidental OpenQASM3/dynamic support claim. | DEFER behind P0 |
| H12 | P2 | A small formal/symbolic proof can protect one algebraic rewrite or bound-composition invariant. | Medium. One self-contained theorem plus executable matrix/property correspondence. | Claim only exact checked theorem; no memory/parser/kernel correctness inference. Risk: formal model differs from implementation. | DEFER |
| H13 | P2 experimental | Cutting reduces memory enough to repay fragments and estimator overhead on a named family. | High tiny prototype; exact reconstruction, complete fragments, budgets and combined confidence. | Material resource win with valid combined error/confidence; otherwise reject. Risk: exponential fragment/shot cost hidden. | DEFER |
| H14 | P2/future | Restricted noise trajectories/MPO can beat dense density matrices under exact noisy semantics. | High separate capability; CPTP/trace/positivity/noiseless differential and seeded ensembles. | Only a narrow correct tested subset; otherwise no stable integration. Risk: unitary parser silently accepts noise/reset. | RESEARCH_ONLY |
| H15 | P2 | Mechanically proven symmetry reduces effective dimension for selected circuits. | Medium. Preserved/broken random circuits, dense reference and measurement remap. | Automatic reduction only on mechanical preservation proof; otherwise opt-in/reject. Risk: false symmetry is a correctness bug. | DEFER |

## Ranking rule

When feature work begins, score relevance, independent evidence, benefit, implementability, reverse risk, independent-oracle quality, and portable CPU+AMD/Vulkan fit from 1–5. Record the scores before selecting at most one major prototype. No feature is selected yet.

## Decisions after the candidate cycle (2026-10-29)

| ID | Decision | Evidence / rationale |
| :--- | :--- | :--- |
| H0 | **SUPPORTED, fixed** | See `FINDINGS.md` CQ-NEXT-H0. |
| H1 | **SUPPORTED, fixed** | See `FINDINGS.md` CQ-NEXT-H1. |
| H7 | **PARTIAL - capability shipped, no performance claim** | General Pauli (X/Y/Z) strings and weighted sums now evaluate on a stabilizer engine (exact), a dense reference (exact) and Path D (certified, basis-rotated). The >=15% end-to-end acceptance criterion was **not** measured, so no speed claim is made. |
| H8 | **SUPPORTED as doc defect only** | Bound math re-derived and correct; wording fixed. |
| H11 | **PARTIAL** | Nine more gates lowered exactly; a canonical IR was not built. |
| H2, H3, H4, H5, H6 | DEFER | Need the benchmark protocol and held-out families; not attempted. |
| H9 | DEFER (EXPERIMENTAL / PHYSICAL_GPU_UNVERIFIED) | Primitive dispatch only. |
| H10 | NOT RUN / OPTIONAL | No hardware credentials or authorisation. |
| H12, H13, H15 | DEFER | |
| H14 | RESEARCH_ONLY | Noise needs a separate capability with CPTP tests; reset/noise stay refused. |

Ranking of the shipped feature (1-5): relevance 5, independent evidence 5 (Qiskit + closed forms), benefit 4, implementability 5, reverse risk 4, oracle quality 5, CPU+Vulkan fit 3 (CPU only).
