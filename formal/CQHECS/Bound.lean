import Mathlib

/-!
# CQ-HECS specification lemmas

Lemma backlog: `FORMAL_ASSURANCE_PLAN.md`. A proved specification is not a refinement proof of
the shipped implementation (V7 section 7.4).
-/

namespace CQHECS

open Finset

/-- **L-BOUND-01 (specification).** For a finite set of discarded Pauli terms `D` with real
coefficients `c`, the deviation introduced by dropping them is bounded by the discarded mass:
`|∑_{P∈D} c P| ≤ ∑_{P∈D} |c P|`.

This is the specification-level form of the Path D per-observable error bound
`|⟨O_exact⟩ − ⟨O_kept⟩| ≤ Σ_{P∈D} |c_P|`. It proves the real-arithmetic inequality only; it does
not prove that the implementation computes `c` or `D` correctly (that is tested by
`tests/test_path_d_pauli_observables.py`). -/
theorem truncation_bound {ι : Type*} (s : Finset ι) (c : ι → ℝ) :
    |∑ i in s, c i| ≤ ∑ i in s, |c i| :=
  Finset.abs_sum_le_sum_abs c s

end CQHECS
