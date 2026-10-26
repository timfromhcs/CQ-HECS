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
| Shared gate manifest + capability-first routing | `cqhecs/gate_manifest.py`, `cqhecs/router.py` | **implemented (v2.2.1)** | one table supplies arity/parameters/support to analyzer, router, Qiskit `Target` and backends | `test_hardening_v221.py`, `TestFailClosedRouting`, mutation mutant 11 |
| Strict Python QASM reader | `cqhecs/circuit_parsing.py` | **implemented (v2.2.1)** | fail-closed line grammar, global register offsets, bounded angle grammar (no `eval`), source-order measurements | `TestPythonNativeQASMDifferential`, `TestStrictQASMParser` |

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

The authoritative table is `cqhecs/gate_manifest.py`; the entries below are a
summary. Arity, parameter count and per-path support are read from that table by
the analyzer, the router, the Qiskit `Target` and every backend, so the lists
cannot drift independently.

| Backend | Gate set | Refusal behaviour |
| :--- | :--- | :--- |
| A | H, X, Y, Z, S, S^†, ID, CX, CNOT, CZ, SWAP, RZ/P/U1 **only at exact multiples of π/2** | typed support error on non-Clifford angles (checked per angle, not just the first parameter) |
| B | Clifford skeleton + T, T^†, RZ/P/U1, RX, RY | raises on unsupported rotations or above the documented 22q ceiling |
| C | every implemented manifest gate: 1q rotations, CX/CNOT/CZ/SWAP and CP/CU1/CRX/CRY/CRZ; no silent gate drop | raises on unknown ops and on the 500-qubit routing/sampling ceiling |
| D | 1q rotations expressed in Pauli propagation, CX/CZ/SWAP conjugation, terminal measurement | raises `UnsupportedPathDOperation` on missing rules; joint counts opt-in and labelled uncertified |

`u`, `u2`, `u3`, `ccx`, `toffoli`, `ch`, `cs`, `csdg` and `reset` are known to
the manifest but supported by **no** path. They produce a precise capability
refusal instead of an "unknown gate" parse error or an identity fallback.
`cp`, `cu1`, `crx`, `cry` and `crz` are Path C only. `measure` is supported by
A and C. Mid-circuit measurement, reset and classical conditions are refused
before execution.

Routing is capability-first and fail-closed: forced backends never silently
reroute; automatic escalation happens only on typed capability/resource
exceptions. Evidence: `TestFailClosedRouting`, `tests/test_hardening_v221.py`
and the router contract tests.

## What v2 explicitly does not include

- No physical-GPU compute claim (loader-only status; see METHOD_CATALOG §3).
- No mixed-state / noise-channel backend.
- No joint bitstring counts from Path D by default.
- No performance claims from a single circuit family.
