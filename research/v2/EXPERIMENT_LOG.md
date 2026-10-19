# CQ-HECS v2 Experiment Log

Chronological record of the experiments performed in the v2 cycle, with
method, input, observation and decision. Every entry corresponds to a commit in
`agent/v2-correctness` or to a documented decision.

## E1 — Finite-shot bound violation measurement

- **Question:** does `sqrt(ln(2/δ)/(2n))` hold as a TV bound for a joint
  distribution?
- **Method:** Sample arbitrary samples from the uniform distribution over
  `K ∈ {2, 16, 64}` outcomes; `n = 1000`, `δ = 0.05`; count the rate at which
  `TV(empirical, uniform)` exceeds the bound over repeated trials.
- **Observation:** violation rates 0.6% / 73.0% / 100.0% for K = 2 / 16 / 64 —
  the dimension-free claim is false by direct construction.
- **Decision:** replace with the Weissman-style support-aware bound
  (commit `a0eb...` branch commit `a0be9b4`); keep the K=2 collapse exact;
  compute in log space; clamp to 1.0. Covered by tests validating the theorem
  shape (K-dependence) rather than only the formula.

## E2 — Mutation-harness fail-closed verification

- **Question:** does the harness fail on a broken baseline and on surviving
  mutants?
- **Method:** run the harness's own checks against deliberately broken
  baselines and surviving-mutant injections added as tests
  (`tests/test_mutation_harness_contract`-style checks; see the harness diff in
  commit `a0be9b4` and its predecessor `349468f`).
- **Observation:** original version counted broken baselines as killed
  mutants. After the fix, baseline failure aborts with non-zero exit and any
  surviving mutant produces non-zero exit.
- **Decision:** mutation gate runs in CI; exit code is part of the gate.

## E3 — Path B aliasing regression discovery

- **Question:** are vectorised two-qubit gates index-correct under Qiskit's
  little-endian ordering?
- **Method:** differential testing of path B against `Statevector` on circuits
  with CX on every (control, target) orientation pair.
- **Observation:** one aliasing bug (an operand-keeping bug in the vectorised
  application) produced amplitude corruption for specific orientations.
- **Decision:** fix in commit `febf275`; regression test added; ceiling raised
  16 → 22 qubits and documented as an implementation limit, not a theorem.

## E4 — Path D explicit-matrix conjugation audit

- **Question:** are CX / CZ / SWAP backward conjugation rules exact?
- **Method:** for every two-qubit Pauli `X^x Z^z` at n=3, compare
  `U† P U` computed by dense matrices vs the simulator's rule output.
- **Observation:** the CZ rule missed the relative sign for `X_a X_b` terms
  (H3 in `HYPOTHESES.md`); every CZ-containing circuit was silently wrong.
- **Decision:** fix in commit `623f587` with
  `TestTwoQubitConjugationRules` (all 256 pairs × 3 gates) as the regression.

## E5 — Path D batched evaluation equivalence + bound dominance

- **Question:** batched backward walk ≡ per-observable walks? and does the
  certificate dominate it?
- **Method:** random Clifford+T circuits (4–5 qubits, seeds 11/21–23/31),
  comparing batched vs single values (12 dp) and batched values vs `Statevector`
  expectations against the accumulated bound on a deliberately truncating
  budget (`max_pauli_terms = 8`).
- **Observation:** identical values; bound always ≥ true error.
- **Decision:** adopt batching (E5 is part of commit `623f587`); certificate
  dominance test added.

## E6 — Early unresolved termination timing

- **Question:** can deep hopeless circuits return promptly?
- **Method:** random 20q×25d Clifford+T circuit, measure wall time until
  `unresolved=True` with no values.
- **Observation:** without the bail-out the walk ran for minutes; with it the
  regression completes well under 60 s (typically seconds).
- **Decision:** adopt early bail-out; test enforces both promptness and the
  absence of misleading values.

## E7 — Small-circuit timing spot checks (informative only)

Single-run wall clock, local CPU, default settings. Recorded in
`research/v2/METHOD_CATALOG.md`_simps; **not** a performance claim:

| Circuit | Path | wall |
| :--- | --- | ---: |
| 6q Clifford chain | A | ~0.5 ms |
| 8q GHZ | A | ~0.9 ms |
| 4q low-T | B | ~1.2 ms |
| 6q rotation chain | C | ~4.6 ms |

The `cq-hecs benchmark smoke` output (regenerated for the release) carries the
same disclaimer and a schema version.

## E8 — Method inventory decisions (Phase C)

Full decision table with reasons: `research/v2/METHOD_CATALOG.md` §3. Summary
of the negative results and deferrals, so they are not "invisible":

- General TN contraction, circuit cutting, Schrödinger–Feynman: deferred with
  reasons (own error accounting / optimiser scope / result-contract change).
- Decision diagrams, Feynman path sum, noise/mixed-state paths: rejected for
  v2 with reasons.
- GPU/Vulkan compute: loader verified only; compute dispatch on a physical GPU
  was not demonstrated, so no acceleration claim is made.
