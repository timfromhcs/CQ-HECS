# Testing techniques applied in v3 (2026-10-30)

The goal of this slice was not to add another simulator path, but to apply
current quantum-software testing research to CQ-HECS and turn the result into a
user-runnable check. Sources were read on 2026-10-30; the classification says
what was actually transferred.

| Source | Technique | Classification | What CQ-HECS now does |
|---|---|---|---|
| Pontolillo, Mousavi, Grzesiuk, *QuCheck: A Property-based Testing Framework for Quantum Programs in Qiskit*, arXiv:2503.22641 (2025) | property-based testing with deterministic input generators, preconditions, statistical assertions and multiple-testing correction | DIRECT_TRANSFER (method) | `tests/test_property_circuits.py` generates native-gate circuits with Hypothesis; `cqhecs.selftest` applies a Bonferroni-corrected Hoeffding bound to finite-shot checks |
| Klimis et al., *Shaking Up Quantum Simulators with Fuzzing and Rigour*, OOPSLA 2025, DOI 10.1145/3763100 | differential benchmarking, mutation testing, invariant checks, unitary consistency modulo global phase | DIRECT_TRANSFER (oracle design) | inverse identity, MPS/dense parity, permutation equivariance, `p(θ)` vs `rz(θ)` global-phase relation |
| *From Ideal to Noisy: Adapting Property-Based Testing for Real Quantum Computers* (2025) | properties that remain meaningful under noise, rather than only ideal-state assertions | ADAPTABLE | Kraus trace/Hermiticity/positivity/unitality and readout column-stochasticity checks in `selftest`; noisy permutation fuzz (not committed as a test, result recorded below) |
| QuteFuzz, POPL 2025 | structured random circuit generation for compiler/simulator fuzzing | ADAPTABLE | Hypothesis circuit strategy plus the standalone fuzz runs listed below |
| Long et al., *Testing Quantum Programs with Multiple Subroutines*, arXiv:2208.09206 (2022) | metamorphic relations instead of a full statevector oracle | DIRECT_TRANSFER | inverse composition, qubit relabelling and global-phase metamorphic relations |
| FuzzQ / QuCheck mutation analysis | mutation score as a test-suite quality metric | ALREADY PRESENT | the repository's `scripts/run_mutation_tests.py` now covers 33 source mutants |

## What was applied

### 1. `cq-hecs selftest`

A deterministic, installation-level suite (`cqhecs/selftest.py`) with eight
checks:

1. probability normalization and non-negativity;
2. `C†C = I` on random circuits, on both the dense reference and the exact MPS
   chain;
3. qubit-permutation equivariance of the MPS engine, including the documented
   chain-order endianness;
4. `p(θ)` and `rz(θ)` agree on probabilities (global phase only);
5. exact MPS contraction equals the dense reference up to a global phase;
6. finite-shot MPS sampling is within a Hoeffding total-variation bound, with
   the failure budget divided across checks (Bonferroni);
7. Kraus channels preserve trace, Hermiticity and positivity; depolarizing is
   unital; the readout matrix is column-stochastic;
8. the dense expectation engine agrees with the statevector oracle.

The suite is deliberately *not* a proof of correctness: a wrong but consistent
gate matrix would pass every check. Qiskit/Aer differential tests remain the
independent oracle.

### 2. Property-based circuit tests

`tests/test_property_circuits.py` uses Hypothesis to generate circuits over the
native gate set (2–4 qubits, continuous angles) and asserts normalization,
inverse identity and MPS/dense parity. Failed examples shrink to a small gate
list.

### 3. Exploratory fuzzing before writing the tests

The following ad-hoc runs were used to look for defects before codifying the
properties. They are not committed as permanent tests because they are slow or
need Qiskit-specific gate constructors; the committed tests cover the same
relations on smaller inputs.

| run | cases | result |
|---|---|---|
| dense vs exact MPS statevector | 300 random circuits, 2–6 qubits, 3–15 gates | 0 mismatches (after accounting for the documented chain-order endianness) |
| dense vs Qiskit `Statevector` for composite-gate lowering | 200 random circuits with `u/u2/u3/sx/sxdg/rzz/ccx/cswap/...` | 0 mismatches |
| dense expectation vs `sparse_pauli`/`auto` | 300 random circuits and random Pauli labels | 0 mismatches on gates Path D supports; expected typed refusals for `cp/crx/cry/crz`, which Path D does not implement |
| noisy density matrix under qubit permutation | 100 random circuits, random 1q/2q depolarizing + asymmetric readout | 0 mismatches |
| MPS finite-shot marginals vs exact distribution | 30 circuits x 200k shots, ordered and permuted measurement order | within the Hoeffding bound in all cases |

These are **negative results**: no new defect was found in this slice. They do
not establish absence of defects.

## Reproduce

```bash
cq-hecs selftest --cases 8
cq-hecs --format json selftest --cases 8
python -m pytest tests/test_property_circuits.py tests/test_selftest.py -q
python scripts/run_mutation_tests.py
```

## Limits

* Property-based testing explores the input distribution encoded in the
  strategy, not all circuits.
* The Hoeffding bound is distribution-independent but conservative; a passing
  sampling check is evidence, not a guarantee for every future seed.
* The selftest does not exercise the native C++ engine or Vulkan dispatch; those
  have their own CTest/gate evidence.
* Mutation score is scoped to the listed source mutants.
