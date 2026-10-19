# CQ-HECS v2 Implementation Matrix

This is the condensed, test-anchored view of what v2 actually implements. The
long-form method discussion lives in `research/v2/METHOD_CATALOG.md`; the
mathematical claims are itemised in `research/v2/FORMALIZATION_STATUS.md`.

## Methods matrix

| Method | Path / module | Status | Correctness class | Evidence (tests) |
| :--- | :--- | :--- | :--- | :--- |
| Stabilizer tableau (Gottesman–Knill) | A · `cqhecs/backends/path_a_stabilizer.py` | **implemented** | exact (GF(2) symplectic algebra, no approximation) | `TestBitstringOrdering`, native-python parity tests, native `test_stabilizer` |
| Stabilizer-rank decomposition (Clifford + T/RX/RY/RZ) | B · `cqhecs/backends/path_b_stabilizer_rank.py` | **implemented** | algebraically exact decomposition, float64 arithmetic, finite-shot sampling reported separately | `TestPathBContract` incl. orientation/aliasing regressions; 22-qubit GHZ+T vs `Statevector` |
| MPS (1D chain, untruncated bond dimension) | C · `cqhecs/backends/path_c_mps_exact.py` | **implemented** | exact up to floating-point; discards only values below a relative roundoff floor; no certified roundoff bound reported | `TestSvdPrecision`-family, MPS paging/concurrency tests, wide-sampling refusal tests |
| Sparse-Pauli dynamics (Heisenberg propagation) | D · `cqhecs/backends/path_d_sparse_pauli.py` | **implemented** | certified bound on requested observables (⟨Z_q⟩, ⟨Z_q Z_r⟩); joint counts opt-in and labelled | `TestTwoQubitConjugationRules`, `TestPathDPerformanceAndContract`, statevector differential tests, bound-dominance test |
| Dense statevector | inside B's statevector evaluation | **implemented** (as Path B's ≤ 22 qubit evaluation) | exact algebra, float64 | same as B |
| Finite-shot confidence bound | `cqhecs/result.py` | **implemented** | support-aware TV concentration (Weissman) | K-dependence tests, violation-rate study E1 |
| Mutation harness ( behavioural) | `scripts/run_mutation_tests.py` | **implemented** | harness fails closed on broken baselines & surviving mutants | harness self-tests; exit code enforced in CI |

## Deferral / rejection summary

| Method | Decision | Reason (see METHOD_CATALOG §3 for detail) |
| :--- | :--- | :--- |
| General tensor network + contraction optimiser | deferred | substantial new optimiser; 1D MPS covers current workloads |
| Decision diagrams (QMDD/QuIDD) | rejected for v2 | regular-structure niche; licence/maintenance; no demonstrated win over A/B/C |
| Schrödinger–Feynman / circuit partitioning | deferred | needs own cut/error accounting and result type |
| Circuit cutting (wire/gate) | deferred | estimator combination changes output semantics |
| Feynman path sum | rejected for v2 | path count can explode without a cheap certificate |
| Symmetry/subspace reduction | deferred | requires sound invariant detection |
| ZX-calculus / graph-state rewrites | deferred | no workload where it beats A/B/C |
| Exact ring arithmetic (`Z[1/√2, i]`) backend | deferred | algebra known; separate backend not justified yet; float64 declared explicitly |
| Noise trajectories / density matrix / MPO | rejected for v2 | changes result contract semantics, not just adds a method |
| Monte Carlo stabilizer / quasiprobability | deferred | sampling complexity analysis required; not a current need |
| GPU compute via Vulkan | deferred | loader enumerated; **no physical-GPU compute dispatch demonstrated**; no acceleration claim is made |
| Cache/gate-fusion/SIMD (performance work) | deferred | correctness-first; no optimization without differential baselines |

## Gate set and routing

| Backend | Gate set | Refusal behaviour |
| :--- | :--- | :--- |
| A | H, X, Y, Z, S, S^†, CX, CZ, SWAP, Clifford-angle RZ/P/U1 | raises typed support error on non-Clifford |
| B | T, T^†, RZ/P/U1, RX, RY over Clifford skeleton | raises on unsupported rotations or above the documented 22q ceiling |
| C | general 1q rotations incl. CX/CZ via two-site contraction; no silent gate drop | raises on unknown ops; reports no counts beyond sampling limit |
| D | 1q rotations expressed in Pauli propagation + CX/CZ/SWAP conjugation | raises `UnsupportedPathDOperation` on missing rules |

Routing is capability-first and fail-closed: forced backends never silently
reroute; automatic escalation happens only on typed capability/resource
exceptions. Evidence: `TestFailClosedRouting` and the router contract tests.

## What v2 explicitly does not include

- No physical-GPU compute claim (loader-only status; see METHOD_CATALOG §3).
- No mixed-state / noise-channel backend.
- No joint bitstring counts from Path D by default.
- No performance claims from a single circuit family.
