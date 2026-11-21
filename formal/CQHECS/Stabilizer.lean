import Mathlib

/-!
# Stabilizer tableau: symplectic invariant (L-STAB-01, binary part)

Specification-level model of the `(x | z)` bit part of the Aaronson-Gottesman tableau used by
Path A (`cqhecs/backends/path_a_stabilizer.py`, class `StabilizerTableauSimulator`). A row's
`(x, z)` bits are a vector in `F_2^(2n)`; the symplectic form
`omega(p, q) = sum_i (x_i z'_i + z_i x'_i)` is the commutation invariant of Pauli rows
(`omega = 0` iff the Paulis commute; the single-qubit link is `Pauli.pauli_comm`).

Proved: each tableau gate update of Path A (`apply_h`, `apply_s`, `apply_cx`, `apply_cz`,
`apply_swap`; `apply_sdg` is `S` applied three times) preserves `omega`, hence a whole gate
sequence does, hence the initial `D_i = X_i`, `S_j = Z_j` relations persist.

NOT proved: the sign (`r`) column update for `CX` (the single-qubit sign rules are in
`Pauli.lean`; the `CX` sign rule is covered only by the Python dense/Stim oracle tests), the
measurement/`row_sum` update, and any refinement from this model to the NumPy code (V7 section 7.4).
-/

set_option linter.unusedSimpArgs false

namespace CQHECS

open Finset Function

/-- A Pauli row's bits: `(x_i, z_i)` for each qubit `i`. -/
abbrev PauliVec (n : ℕ) := Fin n → ZMod 2 × ZMod 2

/-- Single-qubit symplectic form. -/
def loc (p q : ZMod 2 × ZMod 2) : ZMod 2 := p.1 * q.2 + p.2 * q.1

/-- The symplectic form on `n`-qubit rows. -/
def omega {n : ℕ} (p q : PauliVec n) : ZMod 2 := ∑ i, loc (p i) (q i)

/-! ### Local rules -/

/-- Hadamard local rule: swap `x` and `z`. -/
def hLoc (a : ZMod 2 × ZMod 2) : ZMod 2 × ZMod 2 := (a.2, a.1)
/-- Phase-gate local rule: `z += x`. -/
def sLoc (a : ZMod 2 × ZMod 2) : ZMod 2 × ZMod 2 := (a.1, a.2 + a.1)

theorem loc_hLoc (a b : ZMod 2 × ZMod 2) : loc (hLoc a) (hLoc b) = loc a b := by
  revert a b; decide

theorem loc_sLoc (a b : ZMod 2 × ZMod 2) : loc (sLoc a) (sLoc b) = loc a b := by
  revert a b; decide

/-- CX local rule on the control/target pair: `x_t += x_c`, `z_c += z_t`. -/
def cxLoc (a b : ZMod 2 × ZMod 2) : (ZMod 2 × ZMod 2) × (ZMod 2 × ZMod 2) :=
  ((a.1, a.2 + b.2), (b.1 + a.1, b.2))

theorem loc_cxLoc (a b a' b' : ZMod 2 × ZMod 2) :
    loc (cxLoc a b).1 (cxLoc a' b').1 + loc (cxLoc a b).2 (cxLoc a' b').2
      = loc a a' + loc b b' := by
  revert a b a' b'; decide

/-! ### Gate updates on rows -/

/-- `H_q` (Path A `apply_h`, bit part). -/
def hGate {n : ℕ} (q : Fin n) (p : PauliVec n) : PauliVec n := update p q (hLoc (p q))
/-- `S_q` (Path A `apply_s`, bit part). -/
def sGate {n : ℕ} (q : Fin n) (p : PauliVec n) : PauliVec n := update p q (sLoc (p q))
/-- `CX(c,t)` (Path A `apply_cx`, bit part). -/
def cxGate {n : ℕ} (c t : Fin n) (p : PauliVec n) : PauliVec n :=
  update (update p c (cxLoc (p c) (p t)).1) t (cxLoc (p c) (p t)).2
/-- `SWAP(a,b)` (Path A `apply_swap`, bit part). -/
def swapGate {n : ℕ} (a b : Fin n) (p : PauliVec n) : PauliVec n := p ∘ Equiv.swap a b

/-- Single-site updates preserve the form when the local rule does. -/
theorem omega_update_one {n : ℕ} (f : ZMod 2 × ZMod 2 → ZMod 2 × ZMod 2)
    (hf : ∀ a b, loc (f a) (f b) = loc a b) (q : Fin n) (p p' : PauliVec n) :
    omega (update p q (f (p q))) (update p' q (f (p' q))) = omega p p' := by
  unfold omega
  refine Finset.sum_congr rfl (fun i _ => ?_)
  by_cases h : i = q
  · subst h; simp [hf]
  · simp [update_of_ne h]

theorem omega_hGate {n : ℕ} (q : Fin n) (p p' : PauliVec n) :
    omega (hGate q p) (hGate q p') = omega p p' :=
  omega_update_one hLoc loc_hLoc q p p'

theorem omega_sGate {n : ℕ} (q : Fin n) (p p' : PauliVec n) :
    omega (sGate q p) (sGate q p') = omega p p' :=
  omega_update_one sLoc loc_sLoc q p p'

theorem omega_swapGate {n : ℕ} (a b : Fin n) (p p' : PauliVec n) :
    omega (swapGate a b p) (swapGate a b p') = omega p p' := by
  unfold omega swapGate
  exact Equiv.sum_comp (Equiv.swap a b) (fun i => loc (p i) (p' i))

/-- Splitting a sum over `Fin n` around two distinct indices. -/
theorem sum_split_two {n : ℕ} (c t : Fin n) (hct : c ≠ t) (F : Fin n → ZMod 2) :
    ∑ i, F i = F c + F t + ∑ i ∈ ((univ.erase c).erase t), F i := by
  have h1 := Finset.add_sum_erase (univ : Finset (Fin n)) F (Finset.mem_univ c)
  have ht : t ∈ (univ : Finset (Fin n)).erase c := by simp [hct.symm]
  have h2 := Finset.add_sum_erase ((univ : Finset (Fin n)).erase c) F ht
  rw [← h1, ← h2]; ring

/-- **L-STAB-01 (CX).** `CX(c,t)` with `c ≠ t` preserves the symplectic form. -/
theorem omega_cxGate {n : ℕ} (c t : Fin n) (hct : c ≠ t) (p p' : PauliVec n) :
    omega (cxGate c t p) (cxGate c t p') = omega p p' := by
  unfold omega
  rw [sum_split_two c t hct (fun i => loc (cxGate c t p i) (cxGate c t p' i)),
      sum_split_two c t hct (fun i => loc (p i) (p' i))]
  have hc : ∀ i ∈ ((univ.erase c).erase t), loc (cxGate c t p i) (cxGate c t p' i)
      = loc (p i) (p' i) := by
    intro i hi
    have hit : i ≠ t := (Finset.mem_erase.mp hi).1
    have hic : i ≠ c := (Finset.mem_erase.mp (Finset.mem_erase.mp hi).2).1
    simp [cxGate, update_of_ne hit, update_of_ne hic]
  rw [Finset.sum_congr rfl hc]
  have key := loc_cxLoc (p c) (p t) (p' c) (p' t)
  have e1 : cxGate c t p c = (cxLoc (p c) (p t)).1 := by
    simp [cxGate, update_of_ne hct]
  have e2 : cxGate c t p t = (cxLoc (p c) (p t)).2 := by simp [cxGate]
  have e1' : cxGate c t p' c = (cxLoc (p' c) (p' t)).1 := by
    simp [cxGate, update_of_ne hct]
  have e2' : cxGate c t p' t = (cxLoc (p' c) (p' t)).2 := by simp [cxGate]
  rw [e1, e2, e1', e2']
  rw [key]

/-- `CZ(c,t) = H_t ; CX(c,t) ; H_t` (the decomposition Path A `apply_cz` uses). -/
def czGate {n : ℕ} (c t : Fin n) (p : PauliVec n) : PauliVec n :=
  hGate t (cxGate c t (hGate t p))

theorem omega_czGate {n : ℕ} (c t : Fin n) (hct : c ≠ t) (p p' : PauliVec n) :
    omega (czGate c t p) (czGate c t p') = omega p p' := by
  unfold czGate
  rw [omega_hGate, omega_cxGate c t hct, omega_hGate]

/-! ### Whole-circuit invariant -/

/-- Clifford gates supported by the Path A tableau (bit part). `sdg` is `S` thrice. -/
inductive Gate (n : ℕ) where
  | h (q : Fin n)
  | s (q : Fin n)
  | sdg (q : Fin n)
  | cx (c t : Fin n) (hct : c ≠ t)
  | cz (c t : Fin n) (hct : c ≠ t)
  | swap (a b : Fin n)

/-- Action of a gate on a row. -/
def Gate.act {n : ℕ} : Gate n → PauliVec n → PauliVec n
  | .h q => hGate q
  | .s q => sGate q
  | .sdg q => sGate q ∘ sGate q ∘ sGate q
  | .cx c t _ => cxGate c t
  | .cz c t _ => czGate c t
  | .swap a b => swapGate a b

theorem omega_act {n : ℕ} (g : Gate n) (p p' : PauliVec n) :
    omega (g.act p) (g.act p') = omega p p' := by
  cases g with
  | h q => exact omega_hGate q p p'
  | s q => exact omega_sGate q p p'
  | sdg q => simp [Gate.act, omega_sGate]
  | cx c t hct => exact omega_cxGate c t hct p p'
  | cz c t hct => exact omega_czGate c t hct p p'
  | swap a b => exact omega_swapGate a b p p'

/-- Apply a gate sequence (first gate first). -/
def run {n : ℕ} : List (Gate n) → PauliVec n → PauliVec n
  | [], p => p
  | g :: gs, p => run gs (g.act p)

/-- **L-STAB-01.** Any sequence of supported Clifford gate updates preserves the symplectic
form of every pair of tableau rows. -/
theorem omega_run {n : ℕ} (gs : List (Gate n)) (p p' : PauliVec n) :
    omega (run gs p) (run gs p') = omega p p' := by
  induction gs generalizing p p' with
  | nil => rfl
  | cons g gs ih => simp [run, ih, omega_act]

/-- Row `X_i` (destabilizer `i` of the initial tableau). -/
def xRow {n : ℕ} (i : Fin n) : PauliVec n := fun k => (if k = i then 1 else 0, 0)
/-- Row `Z_j` (stabilizer `j` of the initial tableau). -/
def zRow {n : ℕ} (j : Fin n) : PauliVec n := fun k => (0, if k = j then 1 else 0)

theorem omega_xRow_zRow {n : ℕ} (i j : Fin n) :
    omega (xRow i) (zRow j) = if i = j then 1 else 0 := by
  unfold omega
  by_cases h : i = j
  · subst h
    rw [if_pos rfl, Finset.sum_eq_single i]
    · simp [loc, xRow, zRow]
    · intro k _ hk
      simp [loc, xRow, zRow, hk]
    · intro hi; exact absurd (Finset.mem_univ i) hi
  · rw [if_neg h]
    refine Finset.sum_eq_zero (fun k _ => ?_)
    by_cases hk : k = i
    · subst hk; simp [loc, xRow, zRow, h]
    · simp [loc, xRow, zRow, hk]

theorem omega_zRow_zRow {n : ℕ} (i j : Fin n) : omega (zRow i) (zRow j) = 0 := by
  simp [omega, loc, zRow]

theorem omega_xRow_xRow {n : ℕ} (i j : Fin n) : omega (xRow i) (xRow j) = 0 := by
  simp [omega, loc, xRow]

/-- **L-STAB-01 (tableau invariant).** After any supported Clifford gate sequence the
destabilizer/stabilizer rows keep the initial symplectic relations: stabilizers commute,
destabilizers commute, and `D_i`, `S_j` anticommute exactly when `i = j`. -/
theorem tableau_invariant {n : ℕ} (gs : List (Gate n)) (i j : Fin n) :
    omega (run gs (xRow i)) (run gs (zRow j)) = (if i = j then 1 else 0)
    ∧ omega (run gs (zRow i)) (run gs (zRow j)) = 0
    ∧ omega (run gs (xRow i)) (run gs (xRow j)) = 0 := by
  refine ⟨?_, ?_, ?_⟩
  · rw [omega_run, omega_xRow_zRow]
  · rw [omega_run, omega_zRow_zRow]
  · rw [omega_run, omega_xRow_xRow]

end CQHECS
