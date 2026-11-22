import Mathlib

/-!
# L-RESULT-01: result-contract state/flag consistency (specification)

Mirrors `cqhecs/result.py` (`SimulationState`, `SimulationResult.__post_init__`,
`SimulationResult.total_error_bound`). Pinned to the Python behaviour by
`tests/test_formal_result_contract.py`.

Scope: this is a pure specification model of the state-derivation table and of the guard that
withholds a certified error figure. It is a `FORMALIZED_LEMMA`, not a refinement proof of the
Python class; it says nothing about what a backend puts into `counts`/`probabilities` (that is
covered by the Python contract tests).
-/

namespace CQHECS
namespace ResultContract

/-- Mirror of `SimulationState`. -/
inductive SimState where
  | exact
  | certified
  | unresolved
  | failed
  deriving DecidableEq, Repr

/-- Mirror of the `state is None` branch of `SimulationResult.__post_init__`:
`failed` (metadata flag) wins over `unresolved`, then `exact ∧ error_bound = 0`, else certified. -/
def deriveState (failed unresolved exact errZero : Bool) : SimState :=
  if failed then .failed
  else if unresolved then .unresolved
  else if exact && errZero then .exact
  else .certified

/-- Mirror of the state guard in `SimulationResult.total_error_bound`: an unresolved or failed
result exposes no certified error figure (`None`); otherwise the component sum `b` is exposed. -/
def totalBound (s : SimState) (b : ℝ) : Option ℝ :=
  match s with
  | .unresolved => none
  | .failed => none
  | .exact => some b
  | .certified => some b

/-- **L-RESULT-01a.** Unless the failed flag is set, an `unresolved` input derives `UNRESOLVED`. -/
theorem unresolved_derives_unresolved (exact errZero : Bool) :
    deriveState false true exact errZero = SimState.unresolved := by
  simp [deriveState]

/-- **L-RESULT-01b.** A set `failed` flag always wins. -/
theorem failed_wins (unresolved exact errZero : Bool) :
    deriveState true unresolved exact errZero = SimState.failed := by
  simp [deriveState]

/-- **L-RESULT-01c.** An unresolved input never derives a state that carries a value:
neither `EXACT` nor `CERTIFIED`. -/
theorem unresolved_never_certified_or_exact (failed exact errZero : Bool) :
    deriveState failed true exact errZero ≠ SimState.certified
    ∧ deriveState failed true exact errZero ≠ SimState.exact := by
  cases failed <;> simp [deriveState]

/-- **L-RESULT-01d.** `EXACT` is derived only from a non-failed, non-unresolved, exact result
with zero deliberate error bound. -/
theorem exact_requires (failed unresolved exact errZero : Bool)
    (h : deriveState failed unresolved exact errZero = SimState.exact) :
    failed = false ∧ unresolved = false ∧ exact = true ∧ errZero = true := by
  cases failed <;> cases unresolved <;> cases exact <;> cases errZero <;> simp_all [deriveState]

/-- **L-RESULT-01e (headline).** An `UNRESOLVED` (or `FAILED`) result cannot expose a certified
error figure. -/
theorem unresolved_has_no_certified_value (b : ℝ) :
    totalBound SimState.unresolved b = none ∧ totalBound SimState.failed b = none := by
  simp [totalBound]

/-- **L-RESULT-01f.** End to end: if the flags say `unresolved` the derived state exposes no
certified figure, for every candidate value. -/
theorem unresolved_flags_expose_no_value (failed exact errZero : Bool) (b : ℝ) :
    totalBound (deriveState failed true exact errZero) b = none := by
  cases failed <;> simp [deriveState, totalBound]

/-- **L-RESULT-01g.** A figure is exposed only for `EXACT` or `CERTIFIED` states. -/
theorem value_only_for_exact_or_certified (s : SimState) (b v : ℝ)
    (h : totalBound s b = some v) :
    s = SimState.exact ∨ s = SimState.certified := by
  cases s <;> simp_all [totalBound]

end ResultContract
end CQHECS
