import CQHECS

/-!
# Axiom audit for the CQ-HECS specification lemmas (V7 W4)

Prints the axioms each named lemma depends on. The expectation (mirroring the external
`anthropics/formal-math` ETH artifact) is only the standard three:
`propext`, `Classical.choice`, `Quot.sound`.

A green `lake build` plus this audit is `FORMALIZED_LEMMA` for the named lemma only; it is
**not** a refinement proof of the shipped Python/C++ implementation (V7 §7.4).
-/

#print axioms CQHECS.truncation_bound

#print axioms CQHECS.expectation_truncation_bound

#print axioms CQHECS.pauli_mul

#print axioms CQHECS.pauli_comm

#print axioms CQHECS.sgd_mul_sg

#print axioms CQHECS.hh_mul_hh

#print axioms CQHECS.h_conj

#print axioms CQHECS.s_conj

#print axioms CQHECS.x_conj

#print axioms CQHECS.z_conj

#print axioms CQHECS.y_conj

#print axioms CQHECS.omega_hGate

#print axioms CQHECS.omega_sGate

#print axioms CQHECS.omega_swapGate

#print axioms CQHECS.omega_cxGate

#print axioms CQHECS.omega_czGate

#print axioms CQHECS.omega_run

#print axioms CQHECS.omega_xRow_zRow

#print axioms CQHECS.tableau_invariant
