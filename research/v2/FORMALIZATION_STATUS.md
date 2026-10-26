# CQ-HECS v2 Formalization Status

For every mathematical statement the code relies on: what its status is, where
its proof lives, and what exactly has been machine-checked in this repository.
This file exists so no formalized truth leaks into an unformalized claim or
vice versa.

## FS1. Empirical-distribution bound (finite-shot confidence)

- **Statement used:** for a categorical distribution with support size `K` on
  `n` i.i.d. samples, with probability ≥ `1 − δ`,
  `TV(empirical, true) ≤ sqrt(ln((2^K − 2)/δ) / (2n))`.
- **Status: verified against the primary source, implemented, empirically
  confirmed.**
- **Proof chain:** Weissman–Ordentlich–Seroussi–Verdú–Weinberger (2003),
  HP Labs Tech Report HPL-2003-97R1, derives
  `Pr(|P̂ − P|₁ ≥ ε) ≤ (2^K − 2)·exp(−n·D_B-min)`, lower-bounded by
  `(2^K − 2)·exp(−n ε²/4·φ(π))`, whose elementary simplification gives the
  tail `Pr(|P̂ − P|₁ ≥ ε) ≤ (2^K − 2) exp(−nε²/2)` used here. Since
  `|P̂ − P|₁ = 2·TV`, substituting `ε = 2t` yields
  `Pr(TV ≥ t) ≤ (2^K − 2) exp(−2 n t²)`, and inverting the tail exactly
  reproduces the implemented `t = sqrt(ln((2^K − 2)/δ)/(2n))`.
- **Sanity anchors checked:** at `K = 2` the prefactor is `2² − 2 = 2`, which
  reproduces the classic Hoeffding value `sqrt(ln(2/δ)/(2n))` exactly — matching
  the implementation's claimed reduction. The constant in the exponent
  (`2 n t²` after `ε = 2t`) is the Bretagnolle–Huber–Carol form quoted in the
  Weissman proof (equation chain (16)–(19) of the tech report).
- **Repository checks:** the violation-rate experiment (naive bound violated at
  73%/100% for K = 16/64) rejects the old formula; tests validate the
  K-dependence shape rather than restating the formula.
- **What it is not:** it is a bound on the *total variation of the whole
  empirical distribution*, not on individual observable error. Observable-bound
  composition is handled separately (FS4).

## FS2. Path D truncation certificate (triangle inequality)

- **Statement:** discarding Pauli terms with total coefficient mass `∑_{P∈D}|c_P|`
  errs by at most that sum on any expectation the terms could contribute, since
  `|⟨P⟩| ≤ ‖P‖∞ = 1` for normalized states.
- **Status: elementary and complete as stated; verified empirically** — the
  certificate always dominated the true error against exact `Statevector`
  expectations on truncating budgets (`TestPathDPerformanceAndContract::
  test_certified_bound_dominates_actual_error`).
- **Scope restriction (deliberate):** the certificate covers *requested
  observables only*. It is not a joint-distribution bound and the code never
  presents it as one.

## FS3. Path B decomposition exactness versus arithmetic

- **Statement:** the stabilizer-rank expansion of T/RZ/RX/RY gates is an
  identity — no terms are dropped — so the computed state is exact *if the
  arithmetic were exact* and if the scaled-coefficient generator identities
  hold per gate.
- **Status: algebra exact (per-generator matrix identities verified in tests);
  arithmetic is IEEE-754 float64 and reported as such**
  (`numerical_mode: float64-exact-decomposition`). No `error_bound = 0`
  claim is tied to the decomposition: sampling error is computed with FS1 and
  reported separately.

## FS4. Error-field composition rule

- **Statement:** `total_error_bound` may add fields only when both target the
  same output metric and triangle-inequality composition applies.
- **Status: enforced in the result contract** — deliberate approximation,
  propagation/roundoff diagnostics and sampling confidence are separate fields;
  addition happens only where the metric and assumptions match (e.g. the Path D
  total over independently-truncated observables of the same kind).
- **Where it is deliberately *not* applied:** Path C reports
  `numerical_error_bound = None` plus a labelled diagnostic instead of summing a
  per-rewrite SVD diagnostic into a fake global bound (FS5).

## FS5. Path C roundoff/diagnostic honesty (open)

- **Statement:** whether the accumulated discarded singular-value mass bounds
  the returned amplitudes is **not established**.
- **Status: open conjecture (OC1 in `HYPOTHESES.md`).** The code reports the
  accumulated mass under a diagnostic name and sets
  `numerical_error_bound = None`. No doc claims a certified roundoff bound.
- **Resource accounting (v2.2.1):** `ram_budget_mb` is a fail-closed internal
  tensor-byte budget, enforced before a state update. `active_ram_mb`,
  `active_tensor_mb` and `total_storage_mb` count NumPy tensor bytes; they are
  not process RSS. `process_rss_mb` and `process_peak_rss_mb` are measured
  separately when `psutil`/`resource` is available, and
  `rss_measurement_available=false` otherwise. Numerical rank reduction at the
  `1e-13` relative threshold is not a deliberate bond-dimension cut-off.

## FS6. Path D two-qubit Clifford conjugation rules

- **Statement:** exact `CX`, `CZ`, `SWAP` backward-conjugation identities in the
  `X^x Z^z` basis, including the relative sign
  `CZ†(X_a X_b)CZ = −X_a X_b Z_a Z_b`.
- **Status: verified by exhaustive explicit-matrix differential test** over all
  256 (x, z) pairs × 3 gates at n = 3 (`TestTwoQubitConjugationRules`).
- **Honest scope:** machine-checked exhaustively at n=3 for the two-qubit case;
  general `n` follows because the rules act per-qubit-pair, but the *proof* of
  that locality claim is by construction in the implementation, not by a formal
  system.

## FS7. Distributed/processing proofs

- GitHub PR #1 and this cycle’s commits carry the behavioural evidence
  (differential tests, mutation harness, contract tests). No external Lean/Coq
  formalization was produced or consumed in this cycle; the OpenAI Math
  catalogue was treated as a literature source per the mission contract and is
  recorded in `LITERATURE_MAP.md`.
