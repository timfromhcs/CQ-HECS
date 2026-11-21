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
    |s.sum c| ≤ s.sum (fun i => |c i|) :=
  Finset.abs_sum_le_sum_abs c s

/-- **L-BOUND-01b (Path D form).** Let `e i = ⟨Pᵢ⟩` be the expectation of Pauli term `i` on a
normalised state, so `|e i| ≤ 1`. Then the error from keeping only the terms in `s` and dropping
the rest is bounded by the discarded coefficient mass:
`|∑_{i∈s} cᵢ eᵢ| ≤ ∑_{i∈s} |cᵢ|`.

Compared with L-BOUND-01 this makes the physical hypothesis `|⟨P⟩| ≤ 1` explicit instead of
absorbing it into the triangle inequality. The assumption is the only physics input; the
inequality itself is algebra. -/
theorem expectation_truncation_bound {ι : Type*} (s : Finset ι) (c e : ι → ℝ)
    (he : ∀ i ∈ s, |e i| ≤ 1) :
    |s.sum (fun i => c i * e i)| ≤ s.sum (fun i => |c i|) := by
  calc
    |s.sum (fun i => c i * e i)| ≤ s.sum (fun i => |c i * e i|) :=
        Finset.abs_sum_le_sum_abs _ _
    _ ≤ s.sum (fun i => |c i|) := by
      apply Finset.sum_le_sum
      intro i hi
      rw [abs_mul]
      exact mul_le_of_le_one_right (abs_nonneg (c i)) (he i hi)

end CQHECS
