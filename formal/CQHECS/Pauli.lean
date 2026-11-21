import Mathlib

/-!
# Single-qubit Pauli algebra and Clifford phase rules (L-PAULI-01, L-STAB-01 phase part)

Specification-level facts about 2x2 complex matrices. They state the *mathematical* rules the
Python Path A tableau updates (`cqhecs/backends/path_a_stabilizer.py`) and the Path D stored basis
(`cqhecs/backends/path_d_sparse_pauli.py`) are meant to implement. They are not a refinement proof
of either implementation (V7 section 7.4).

Conventions. `pauli a b = X^a Z^b` (the Path D *stored* basis, `XZ = -iY`). `herm a b` is the
Hermitian letter `i^(ab) X^a Z^b` (so `herm true true = Y`), the convention of the tableau rows.
-/

set_option linter.unusedSimpArgs false

namespace CQHECS

open Matrix

/-- Pauli X. -/
def PX : Matrix (Fin 2) (Fin 2) ℂ := !![0, 1; 1, 0]
/-- Pauli Z. -/
def PZ : Matrix (Fin 2) (Fin 2) ℂ := !![1, 0; 0, -1]

/-- Stored-basis Pauli `X^a Z^b`. -/
def pauli (a b : Bool) : Matrix (Fin 2) (Fin 2) ℂ :=
  (if a then PX else 1) * (if b then PZ else 1)

/-- Hermitian-letter Pauli `i^(ab) X^a Z^b`: `I, X, Z, Y`. -/
def herm (a b : Bool) : Matrix (Fin 2) (Fin 2) ℂ :=
  (if a && b then Complex.I else 1) • pauli a b

/-- The sign `(-1)^c`. -/
def sgn (c : Bool) : ℂ := if c then -1 else 1

/-- **L-PAULI-01 (multiplication rule).** `(X^a Z^b)(X^c Z^d) = (-1)^(bc) X^(a+c) Z^(b+d)`
(exponents mod 2). This is the phase rule behind Path D's stored-basis multiplication. -/
theorem pauli_mul (a b c d : Bool) :
    pauli a b * pauli c d = sgn (b && c) • pauli (xor a c) (xor b d) := by
  cases a <;> cases b <;> cases c <;> cases d <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [pauli, sgn, PX, PZ, Matrix.mul_apply, Fin.sum_univ_two])

/-- **L-PAULI-01 (commutation).** `P(a,b) P(c,d) = (-1)^(ad+bc) P(c,d) P(a,b)`: two stored-basis
Paulis commute iff the single-qubit symplectic form `ad + bc` vanishes mod 2. This is the
single-qubit link between the tableau's symplectic form and physical commutation. -/
theorem pauli_comm (a b c d : Bool) :
    pauli a b * pauli c d = sgn (xor (a && d) (b && c)) • (pauli c d * pauli a b) := by
  cases a <;> cases b <;> cases c <;> cases d <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [pauli, sgn, PX, PZ, Matrix.mul_apply, Fin.sum_univ_two])

/-- Pauli Y. -/
def PY : Matrix (Fin 2) (Fin 2) ℂ := !![0, -Complex.I; Complex.I, 0]
/-- Unnormalised Hadamard `√2 · H`. The Hadamard is `H = (1/√2) • hh`, so `H P H† = (1/2) • hh P hh`. -/
def hh : Matrix (Fin 2) (Fin 2) ℂ := !![1, 1; 1, -1]
/-- Phase gate `S = diag(1, i)`. -/
def sg : Matrix (Fin 2) (Fin 2) ℂ := !![1, 0; 0, Complex.I]
/-- `S† = diag(1, -i)`. -/
def sgd : Matrix (Fin 2) (Fin 2) ℂ := !![1, 0; 0, -Complex.I]

/-- `S† S = 1`: `sgd` really is the inverse of `sg`. -/
theorem sgd_mul_sg : sgd * sg = 1 := by
  ext i j; fin_cases i <;> fin_cases j <;>
    simp [sgd, sg, Matrix.mul_apply, Fin.sum_univ_two]

/-- `hh * hh = 2 • 1`, i.e. `H = hh/√2` is an involution. -/
theorem hh_mul_hh : hh * hh = (2 : ℂ) • (1 : Matrix (Fin 2) (Fin 2) ℂ) := by
  ext i j; fin_cases i <;> fin_cases j <;>
    simp [hh, Matrix.mul_apply, Fin.sum_univ_two]
  <;> norm_num

/-- **L-STAB-01 (H phase/permutation rule).** `H P(a,b) H† = (-1)^(ab) P(b,a)` for Hermitian
letters: `X <-> Z`, `Y -> -Y`. Tableau update: swap the `x`,`z` bits, `r ^= x & z`. -/
theorem h_conj (a b : Bool) :
    (1 / 2 : ℂ) • (hh * herm a b * hh) = sgn (a && b) • herm b a := by
  cases a <;> cases b <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [herm, pauli, sgn, PX, PZ, hh, Matrix.mul_apply, Fin.sum_univ_two] <;> ring)

/-- **L-STAB-01 (S phase rule).** `S P(a,b) S† = (-1)^(ab) P(a, a+b)`: `X -> Y`, `Y -> -X`,
`Z -> Z`. Tableau update: `z ^= x`, `r ^= x & z`. -/
theorem s_conj (a b : Bool) :
    sg * herm a b * sgd = sgn (a && b) • herm a (xor a b) := by
  cases a <;> cases b <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [herm, pauli, sgn, PX, PZ, sg, sgd, Matrix.mul_apply, Fin.sum_univ_two])

/-- **L-STAB-01 (X rule).** `X P(a,b) X = (-1)^b P(a,b)`. Tableau update: `r ^= z`. -/
theorem x_conj (a b : Bool) :
    PX * herm a b * PX = sgn b • herm a b := by
  cases a <;> cases b <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [herm, pauli, sgn, PX, PZ, Matrix.mul_apply, Fin.sum_univ_two])

/-- **L-STAB-01 (Z rule).** `Z P(a,b) Z = (-1)^a P(a,b)`. Tableau update: `r ^= x`. -/
theorem z_conj (a b : Bool) :
    PZ * herm a b * PZ = sgn a • herm a b := by
  cases a <;> cases b <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [herm, pauli, sgn, PX, PZ, Matrix.mul_apply, Fin.sum_univ_two])

/-- **L-STAB-01 (Y rule).** `Y P(a,b) Y = (-1)^(a+b) P(a,b)`. Tableau update: `r ^= x ^ z`. -/
theorem y_conj (a b : Bool) :
    PY * herm a b * PY = sgn (xor a b) • herm a b := by
  cases a <;> cases b <;>
    (ext i j; fin_cases i <;> fin_cases j <;>
      simp [herm, pauli, sgn, PX, PZ, PY, Matrix.mul_apply, Fin.sum_univ_two])

end CQHECS
