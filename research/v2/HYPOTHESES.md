# CQ-HECS v2 Hypotheses

Every hypothesis in this file is falsifiable: it names the circuit class, the
baseline it is measured against, the prediction, the adversarial cases and the
stop criterion. Statuses: **conjecture** → **experimentally supported** /
**experimentally refuted** → (where applicable) **formally verified under
assumptions**.

## H1. Support-aware sampling bound

- **Claim:** for a categorical measurement distribution over `K` equiprobable
  outcomes sampled with `n` shots, `TV(empirical, true) <=
  sqrt(ln((2^K − 2)/δ) / (2n))` holds with probability ≥ `1 − δ`.
- **Baseline it replaces:** the dimension-free `sqrt(ln(2/δ)/(2n))` formula that
  used to be labelled a TV bound for arbitrary joint distributions.
- **Prediction:** the naive bound violates for the uniform distribution over
  `K` outcomes at a rate that grows with `K`; the support-aware bound never
  does.
- **Adversarial cases:** uniform over `K = 2, 16, 64` with `n = 1000`,
  `δ = 0.05`; highly skewed distributions (bound must hold there too, though it
  is loose).
- **Result:** naive bound violated at 73% (K=16) and 100% (K=64); replacement
  bound held in all trials for K = 2…64, reduces exactly to the classic value
  at K=2, and is computed in log space. Status: **experimentally supported**;
  the underlying inequality is Weissman et al. (2003) via Lemma 1 of Mardia et
  al. (2019) — **formally verified in the literature**, with the
  distribution-independent substitution φ ≥ 2 documented in
  `research/v2/FORMALIZATION_STATUS.md`.

## H2. Path B two-qubit vectorisation preserves exactness

- **Claim:** vectorising Path B's two-qubit gate application (reshape + slice
  instead of a per-amplitude Python loop) leaves amplitudes bit-identical to
  the loop version for equal seeds.
- **Prediction:** identical outputs on every small-`n` differential case;
  the practical qubit ceiling rises from 16 to at least 22.
- **Adversarial cases:** reversed qubit operands (aliasing), CX with far-apart
  control/target, RX/RY/RZ parameter sweeps, GHZ+T at 22 qubits against
  `Statevector`.
- **Result:** bit-identical on all differential tests, including an aliasing
  regression caught and fixed during the change; 22-qubit GHZ+T verified
  against `Statevector`. Status: **experimentally supported**.

## H3. CZ conjugation needs a relative parity sign

- **Claim (mathematical):** in the `X^x Z^z` storage basis,
  `CZ† (X_a X_b) CZ = −X_a X_b Z_a Z_b`; a rule composed naively from the
  single-Pauli images `CZ† X_a CZ = X_a Z_b` must flip the coefficient when
  both qubits carry an X.
- **Prediction:** the explicit-matrix differential test over all two-qubit
  Paulis fails for the old rule (hypothetically measured) and passes for the
  fixed rule.
- **Result:** verified against explicit `U† P U` matrices for every CX/CZ/SWAP
  and all 256 (x,z) pairs at n=3; the old CZ rule silently corrupted every
  CZ-containing circuit. Status: **formally verified** (computed explicitly)
  and covered by
  `tests/test_correctness_contracts.py::TestTwoQubitConjugationRules`.

## H4. Batching observables into one backward walk preserves Path D bounds

- **Claim:** propagating all `<Z_q>` and `<Z_q Z_r>` observables in a single
  backward pass, truncating per observable, produces the same values and the
  same per-observable derived bounds as one walk per observable.
- **Prediction:** identical `expectation_values` and `total_bound` to places
  requested across random circuits.
- **Adversarial cases:** truncated walks (small `max_pauli_terms`), where the
  bound accumulation differs structurally (shared vs separate walks).
- **Result:** agreement to 12 decimal places on random 5-qubit circuits
  (`TestPathDPerformanceAndContract`), and the certificate dominates the true
  error against `Statevector` for deliberately truncating budgets. Status:
  **experimentally supported**.

## H5. Early hopeless-circuit termination for Path D

- **Claim:** once the combined truncation bound exceeds `len(observables)`
  (each |⟨Z…⟩| ≤ 1), no observable can be certified, so the walk can stop
  early and report `unresolved=True` with no values.
- **Prediction:** deep 20–30 qubit circuits that previously burned minutes
  return unresolved within seconds, with no misleading values attached.
- **Result:** unresolved deep circuits return promptly (< 60 s, typically < 5 s
  in the regression) with `expectation_values is None`. Status:
  **experimentally supported**.

## H6. Method-inventory conclusions (roadmap Phase C)

Each candidate method from the roadmap was evaluated against the criteria in
`research/v2/METHOD_CATALOG.md` §3. The working conclusions:

- **H6a:** a general tensor-network contraction ordering pays off only with a
  real optimiser — speculative for v2 → *deferred*.
- **H6b:** decision diagrams (QMDD/QuIDD) only win on highly regular amplitude
  structure; licence/maintenance risk without a demonstrated niche →
  *rejected for v2*.
- **H6c:** circuit cutting/Schrödinger–Feynman needs its own error accounting
  and result contract → *deferred* rather than bolted onto the current result
  schema.
- **H6d:** noise/mixed-state methods change the result contract's meaning, not
  just add a method → *rejected for v2*.
- **H6e:** unproven symmetry assumptions are exactly the silent-corruption
  failure class the project removed → *unless an invariant is machine-checked,
  deferred*.

## Open conjectures (not pursued in v2, listed so they are visible)

- **OC1:** a rigorous composite roundoff bound for Path C (product of retained
  singular-value ratios across the chain). Tracked as METHOD_CATALOG §2.1;
  until proven, Path C reports `numerical_error_bound = None` plus a labelled
  diagnostic.
- **OC2:** observable-first simulation (marginals only) on wider-than-dense
  circuits with certified bounds at production budget. Partially demonstrated
  by Path D; scaling beyond its budget is future work.
