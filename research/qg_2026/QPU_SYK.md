# QPU_SYK.md — preregistered small-N SYK Trotter test on a live QPU (Stage 4)

Campaign `qg-2026-01`. Frozen before any paid submission.

## Purpose
Run a small finite-N SYK model (`qg.syk.q4.v1`) time-evolution circuit on a real QPU and check
the return probability to the initial computational state, plus a forward+inverse mirror
control. This is a **finite-N model** experiment; it is not a spacetime or wormhole claim.

## Model and circuit (frozen)
- `N = 6` Majorana modes (`qg.syk.q4.v1`), 3 qubits, q = 4, seed **20260101**, scale **0.4**
  (Jordan-Wigner encoding; Hamiltonian terms and their digest in `MODEL_MANIFEST.json`).
- Time evolution `t = 1.0` via a first-order Lie-Trotter product formula (`reps = 1`).
- Gates limited to the backend-supported set (h, rz, rx, cx, s/sdg, t/tdg); 3-qubit logical
  circuit (verified valid for `rigetti:cepheus-1-108q`).

## Frozen inputs (`research/qg_2026/qasm/syk_qpu/`, manifest `MANIFEST.json`)
| circuit_id | description | ideal P(000) |
|---|---|---|
| syk-forward | evolve then measure in the computational basis | 0.428017 |
| syk-mirror | forward evolution followed by its inverse | 1.000000 |

## Declared parameters
- Backend: **`rigetti:cepheus-1-108q`** (live `QPU`). Shots: **1000**/circuit.
- Plan/priority: **Public Plan / Standard Queue**; subcategory `phys:oth`.
- 2 circuits × 1 credit = **2 credits** (cumulative → **19 / 25**).

## Frozen analysis
- `P(000) = counts["000"] / shots` (bit order little-endian, established in Stage 2).
- Reported: measured P(000) for both circuits, a finite-shot 95% interval, and the deviation of
  the forward circuit from the ideal 0.428017 (which itself carries Trotter error, reported
  separately from hardware noise in `processed/`).
- Acceptance: the mirror returns to `000` with high probability; the forward result is compared
  to ideal within a declared tolerance derived from the device error. Negative/unresolved
  outcomes recorded as-is.

## Budget and stop rule
- Authorised ceiling: **25 Spark**. Spent so far **17**. This stage: **2**. Cumulative **19**.
- Full credits: **0**. Stop if a quote is not Public/Standard or cumulative > 25.

## Non-claims
A finite-N digital SYK circuit is a model experiment. No black-hole, wormhole, graviton or
"spacetime" claim; sparsification/finite-size and Trotter limits apply.
