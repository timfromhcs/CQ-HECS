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
