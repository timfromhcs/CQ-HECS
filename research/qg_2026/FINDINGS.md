# FINDINGS.md

First-class record of positive, negative and inconclusive results. Session 1 established
the local foundation; the findings below are **engineering/model** findings, not physical
results about gravity.

## F-01 — No Quantum Gravity work existed prior to this campaign
Greenfield confirmation (BASELINE.md). All QG artifacts are new on this branch.

## F-02 — Open Quantum SDK key is a Client ID + Secret pair (not a single token)
The supplied `s_…` value authenticates as neither a JWT nor a complete key; docs and the
401 response agree. → `BLOCKED` (B-1). Consequence: the entire live-simulator/QPU branch of
the campaign is gated; local work is unaffected.

## F-03 — The BMV effective model has closed-form entanglement measures
`U_ZZ(θ)` on `|+>|+>` yields concurrence and negativity `|sin θ|` and `|sin θ|/2`
respectively (verified against the dense matrix in `tests/test_quantum_gravity_bmv.py`).
This supplies an independent oracle for the local slice **without** any QPU.

## F-04 — Majorana algebra + JW mapping reproduce the SYK spectrum
The seeded q=4 SYK Hamiltonian built from the Jordan–Wigner Majorana map is Hermitian,
respects the anticommutator algebra, and matches the dense independent spectrum to
float64 tolerance (`tests/test_quantum_gravity_syk.py`). No claim about spacetime.

## Negative / not-yet results
- No noisy witness scan yet (QG-BMV-03) → `NOT_RUN`.
- No Trotter/randomised evolution yet (QG-SYK-02) → `NOT_RUN`.
- No QPU evidence (QG-SYK-03) → `BLOCKED` (B-1).
None of these may be reported as supported.
