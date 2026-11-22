# v4 hypotheses (preregistered before the deciding measurement)

Outcome vocabulary: SUPPORTED_IN_SCOPE, NOT_SUPPORTED, INCONCLUSIVE, DEFERRED.

## H4-ROUTE-01 -- cost-aware router beats fixed A->B->C->D
Status: **DEFERRED / not tested.** v4 ships the *explainable plan* only
(DECISIONS D-002); the router's selection is unchanged. No claim of better path
choice is made. A future test needs a held-out circuit-family suite with
measured regret.

## H4-SAT-01 -- variable elimination safely accelerates exact #SAT at bounded width

**Claim (scope).** For CNF formulas whose min-fill induced width is small,
`count_models(method="separator")` returns *exactly* the integer
`count_models(method="dpll")` returns, and is faster on declared low-width
families. On high-width formulas it refuses (`UNKNOWN`) or is bypassed, never
returning a wrong or partial count.

**Null / falsification.**
1. Correctness: any count mismatch against brute force (n <= 11) or the DPLL
   counter on the declared families falsifies the claim outright.
2. Soundness of refusal: any `COUNTED` result produced after a budget/deadline
   refusal falsifies it.
3. Speed (secondary, descriptive only): reported as median wall time; no
   asymptotic or general-speedup claim is made in either direction.

**Design.** Fixed seeds; families and parameters are fixed in
`scripts/sat_separator_benchmark.py` *before* it was run. The default method
stays `dpll`; `auto`'s width limit (`AUTO_SEPARATOR_MAX_WIDTH = 14`, i.e.
tables <= 2^15 entries) was chosen a priori and **not tuned on this benchmark**.
If it is changed after seeing these numbers, the benchmark becomes training data
and a new held-out set is required.

**Outcome.** See `FINDINGS.md` (filled after the run; raw data in
`evidence/sat_separator_bench.json`).

## H4-PAULI-01 -- native X/Y/Z Heisenberg observables with per-observable certified bounds

**Honest scope note.** `cqhecs.expectation` already evaluated X/Y/Z strings on
Path D in v3.7.0 by appending basis-change gates and running one Path D pass per
rotation pattern, reporting the *shared total* bound for every value. This
hypothesis is therefore about two narrow improvements, not about "adding"
general Paulis: (a) native propagation of `coeff * X^x Z^z` terms (Y = iXZ) in a
single pass, and (b) a separate bound per observable.

**Claim.** For every supported circuit, observable and truncation setting,
`|<O>_exact - <O>_PathD| <= error_bound(O)` where `error_bound(O)` counts only
`O`'s own discarded Pauli mass; and an observable that exceeds the tolerance does
not make other observables unresolved.

**Falsification.** Any case where the true error (Qiskit `Statevector` +
`Pauli.expectation_value`, an independent implementation) exceeds that
observable's bound; any untruncated disagreement above 1e-9; any phase error in
the exhaustive one-/two-qubit tables; the Y-phase mutation not being detected.

**Data.** `tests/test_path_d_pauli_observables.py` (203 tests; fixed seeds
`range(120)` untruncated, `1000+range(150)` truncated). No performance claim.

**Limits (not supported, typed refusal or absent):** products of Paulis on one
qubit (`X[0]Z[0]`), weighted sums as a single native observable (still handled
one level up by `expectation_values`), gates outside Path D's conjugation set
(`UnsupportedPathDOperation`), float64 roundoff in the bound, any statement about
counts or joint distributions.


---

# V7 hypotheses: status at the freeze (E3, 2026-11-22)

Append-only. The v4 entries above are unchanged. The V7 register is `HYPOTHESIS_REGISTER_V7.md` (with its "Waves
A-D status update" table, task D5); this section restates the outcomes that matter for the release and ties each to
its evidence. A status changes only on a preregistered test. No new hypothesis was tested in Wave E, and E3 ran no
benchmark, so no status below moved because of this task.

| ID | Hypothesis (short) | Status at the freeze | Basis | Not shown |
|---|---|---|---|---|
| H4-SAT-01 | Separator DP counts exactly and safely at bounded width | SUPPORTED_IN_SCOPE | A4 calibration: observed table at most `2**(w+1)` in 31 rows; budget gives `UNKNOWN`, never a partial count | no speedup claim over external counters; random high-width 3-SAT is slower |
| H4-PAULI-01 | Native X/Y/Z observables with per-observable bound | SUPPORTED_IN_SCOPE | v4 tests; A5 Lean bound lemma and spec-correspondence tests | float64 roundoff is not in the bound |
| H-SAT-03 | An optional external solver adapter adds breadth while preserving the trust boundary | PARTIAL | A4 isolation; D5 shows the python-sat exit abort persists | the abort is an external defect (B-V7-01) |
| H-SAT-06 | Proof-carrying UNSAT is more checkable than an internal solver label | SUPPORTED_IN_SCOPE | A4 tamper matrix on one DRAT vector (corrupted proofs rejected) | LRAT, external checkers NOT_RUN |
| H-QUANT-01 / V7-E | A 2D tensor-network path beats the baselines | INCONCLUSIVE, `RESEARCH_ONLY` | B5: E-1 to E-3 pass with caveats, E-5 not implemented, baseline weak, 12 to 16 qubits | not promoted; absent from the router |
| V7-F | MPS trajectories as a promotable Path F | NOT_SUPPORTED for promotion, `RESEARCH_ONLY` | B5: F-1 and F-4 fail on held-out seeds 100 to 109 | recorded negative result |
| V7-G | Matrix-product evolution as a promotable Path G | NOT_SUPPORTED for promotion, `RESEARCH_ONLY` | B5: G-1 fails, 0 percent win | recorded negative result |
| V7-LEAN-01 | Small stabilizer, Pauli and result-contract invariants are formalizable | SUPPORTED_IN_SCOPE (`FORMALIZED_LEMMA`, specification level) | `lake build` exit 0 at the freeze; axioms limited to `propext`, `Classical.choice`, `Quot.sound` | no refinement link; no component is `FORMALLY_VERIFIED_COMPONENT`; Comparator and nanoda NOT_RUN |
| H-NOISE-01 | Calibrated models improve held-out QPU prediction | NOT_RUN | B4 delivered governance only (FIT/EVAL separation, channel checks) | no VALIDATION split in `r-io-7`; needs authorised data |
| H-UX-01 | Provenance UI reduces interpretation errors | PARTIAL | surfaces exist (QG lab, run cards, plan panel) | no comprehension measurement |
| H4-ROUTE-01 | A cost-aware router beats fixed A to D | DEFERRED | plan parity across surfaces only | no held-out regret suite; Path B is slower than dense on every measured case (F-005), which is input to a future router study, not a result |
| H4-GPU-01 (AGENTS.md section 5; not in the V7 register) | Persistent GPU BCP beats CPU end to end | NOT_RUN | A2: CPU and Vulkan BCP agree on 1,052,908 cells (correctness only) | no end-to-end timing claim; one AMD iGPU |
| H-SAT-01, H-SAT-02, H-SAT-04, V7-QEC-01 | see the register | unchanged | not touched in Waves A to E | |

Wording rule for the final report: "supported in scope" means the preregistered test passed for the stated scope;
it is not a general claim. `INCONCLUSIVE` and `NOT_SUPPORTED` entries are published, not hidden.
