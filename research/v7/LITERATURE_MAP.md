# Literature map (v4)

Scope: prior art for the three promoted features only. Search date 2026-11-01.
**What was read:** the bibliographic records and abstracts/excerpts returned by a
web search; the full papers were *not* read or reproduced in this session. Nothing
here is copied code; all implementations are original and tested against
independent oracles.

| Feature | Prior art (verified record) | Status | Relation to CQ-HECS |
|---|---|---|---|
| Variable-elimination #SAT | R. Dechter, "Bucket elimination: A unifying framework for reasoning", *Artificial Intelligence* (1999), doi 10.1016/S0004-3702(99)00059-4 | peer-reviewed | The elimination scheme (bucket per variable, join, sum out) is this framework applied to counting. Not a novelty claim. |
| Treewidth-based model counting | M. Samer, S. Szeider, "Algorithms for propositional model counting", LPAR 2007 (LNCS 4790, pp. 484-498) and *J. Discrete Algorithms* (2010), doi 10.1016/j.jda.2009.06.002 | peer-reviewed | Counts in time exponential in treewidth. Our induced-width preflight is a min-fill upper bound, not a treewidth computation. |
| Pauli propagation / Heisenberg truncation | M. S. Rudolph, T. Jones, Y. Teng, A. Angrisani, Z. Holmes, "Pauli Propagation: A Computational Framework for Simulating Quantum Systems", arXiv:2505.21606 (2025); LOWESA: arXiv:2308.09109; Fontana et al., arXiv:2306.05400 | preprints (peer-review status of each not checked) | Path D's coefficient-truncation scheme is in this family. The per-observable discarded-mass bound is the elementary triangle inequality, not a result from these papers. |

## Claims deliberately not made

* No novelty claim for any algorithm; v4 integrates known techniques with
  exactness oracles, refusal semantics and provenance.
* The #SAT benchmark compares CQ-HECS's own two backends. It is not a comparison
  with sharpSAT, d4, GPMC or any mature counter (none was run; **NOT RUN**).
* The Path D checks compare against Qiskit `Statevector`; no comparison with
  PauliPropagation.jl or other Pauli-propagation tools was run (**NOT RUN**).

## Falsification oracles used

Brute-force enumeration (n <= 11) and the existing DPLL counter for #SAT; Qiskit
`Statevector.expectation_value(Pauli)` and `cqhecs.backends.dense_reference` for
Path D; the shared gate manifest and the existing router for the plan.

## V7 additions (2026-11-21, W2)

Sources for the V7 wave targets. Full statement/method detail for the formal artifacts is in
`evidence/LEAN_ENV.md`. Search date 2026-11-21; the formal artifacts were downloaded and their
statement files read.

| Topic | Source (pinned) | Status | Relation / caution |
|---|---|---|---|
| ETH refutation + #k-SAT counting (formalized) | `anthropics/formal-math` @ `16a5ce41304fcdaea4e0be7c132e1c361dc26da5`; `eth/` | AI-authored research artifact, Apache-2.0 | `MainResults.lean` states `ETHIsFalse` and `MainTheorem` on Mathlib `Turing.FinTM2`; Comparator + nanoda check statements/kernel. External evidence, not a CQ-HECS proof. Paper-vs-formalized runtime nuance (PLAN.md §3.1) must be stated exactly. |
| Zeta zeros (formalized) | `anthropics/formal-math` `zeta23/`; L. Alpöge, R. Furman, arXiv:2608.13637 | AI/author artifact | Not integrated; context only. Never cite as a CQ-HECS result. |
| 3SUM / APSP (formalized) | `anthropics/formal-math` `3sum-apsp/`; J. Alman, V. Vassilevska Williams | AI/author artifact | Not integrated; context only. |
| OpenAI ETH preprint + Lean scope | `openai/math` (repo) | AI-authored preprint | The abstract bound and the Lean scope bound differ; do not cite interchangeably. |
| Lean-Quantum / Lean-QIT | github.com/Hayata-Yamasaki-Group/lean-quantum; github.com/QuAIR/Lean-QIT | to pin in W2 | Reusable state/channel/operator interfaces for the L-* backlog. |
| FloatLib | github.com/lean-dojo/FloatLib | to pin in W2 | Numerical theorems connecting execution to rounding/exactness. |
| 2D tensor networks | Rudolph & Tindall, doi:10.1038/s41534-026-01372-2 | to read in W7 | Path E candidate: hardware-topology-aware contraction. |
| Matrix Product Evolution | Kawabe et al., arXiv:2608.03472 | to read in W7 | Path G candidate. |
| QEC / RL calibration | Sivak et al., Nature (2026), doi:10.1038/s41586-026-10759-2 | to read in W10 | Research-only, hardware-gated. |
| SAT Competition 2026 rules | satcompetition.github.io/2026/rules.html | to read in W9 | Benchmark/competition discipline; no winner claim. |

Each entry must be re-opened and its exact revision/DOI confirmed before any claim depends on it.

