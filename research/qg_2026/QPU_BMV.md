# QPU_BMV.md — preregistered BMV effective-phase witness on a live QPU (Stage 3)

Campaign `qg-2026-01`. Frozen before any paid submission.

## Purpose
Run the Track-A BMV effective-phase model (`qg.bmv.zz.v1`) on a real QPU and compare the
measured two-qubit correlators against the exact model and the declared noise model. This
tests a **model** on hardware; it makes no claim that gravity is quantum.

## Frozen inputs
Circuit files: `research/qg_2026/qasm/bmv_qpu/` (manifest `MANIFEST.json`).

Circuit: `H,H, CX, Rz(theta) q1, CX` then measurement-basis rotations, then `measure`.

| circuit_id | basis | theta | expected correlator | SHA-256 |
|---|---|---|---|---|
| bmv-t0-YZ | Y⊗Z | 0 | 0.0 | `eb59bedd…c42fc10` |
| bmv-t0-ZY | Z⊗Y | 0 | 0.0 | `3b849747…df9f2acae` |
| bmv-t0-XX | X⊗X | 0 | 1.0 | `9e3406c2…3b4632dfa` |
| bmv-t1-YZ | Y⊗Z | π/4 | 0.7071067811865476 | `a09563b9…07ede802f` |
| bmv-t1-ZY | Z⊗Y | π/4 | 0.7071067811865476 | `434b6cbc…aa8714587` |
| bmv-t1-XX | X⊗X | π/4 | 1.0 | `7b86fdba…44a3e8cd3` |
| bmv-t2-YZ | Y⊗Z | π/2 | 1.0 | `8dac5f2e…20242904f767b7` |
| bmv-t2-ZY | Z⊗Y | π/2 | 1.0 | `644f07e0…f82b8ef0fcd397` |
| bmv-t2-XX | X⊗X | π/2 | 1.0 | `63c750a8…7d239214961463b` |

(Full 64-hex digests are in `MANIFEST.json`.) Each circuit was verified locally (Qiskit
`Statevector`) to reproduce `⟨Y⊗Z⟩=⟨Z⊗Y⟩=sinθ` and `⟨X⊗X⟩=1` before preregistration.

## Declared parameters
- Backend: **`rigetti:cepheus-1-108q`** (live `QPU`). Shots: **1000**/circuit.
- Plan/priority: **Public Plan / Standard Queue**; subcategory `phys:oth`.
- 9 circuits × 1 credit = **9 credits** (enforced by the runner).

## Frozen analysis (no tuning)
- Correlator `E = (N00 + N11 − N01 − N10) / shots` from the raw counts (bit order
  little-endian, established by the Stage-2 smoke).
- Primary statistic: measured `⟨Y⊗Z⟩`, `⟨Z⊗Y⟩`, `⟨X⊗X⟩` vs the model values `sinθ, sinθ, 1`.
- Report per-point deviation and a normal-approximation interval from the finite shots.
- Compare to the Stage-2 device noise (excited-state/readout error) qualitatively; a full
  noisy-model fit is a separate step and is not claimed here.
- Acceptance: `⟨X⊗X⟩ ≈ 1` within noise at all θ, and `⟨Y⊗Z⟩`, `⟨Z⊗Y⟩` increase with θ and
  are within a declared tolerance of `sinθ`. Unresolved/negative outcomes recorded as-is.

## Budget and stop rule
- Authorised ceiling: **25 Spark**. Stage-2 spent **4**. This stage: **9**. Cumulative **13**.
- Full credits: **0**. Stop if a quote is not Public/Standard or cumulative > 25.

## Extension — phase-scan refinement (added 2026-11-21)

To turn the 3-point result (F-08) into a proper phase scan, add θ ∈ {π/8, 3π/8} in both
bases (set `qasm/bmv_scan2/`, circuits `bmv-s1-YZ/ZY`, `bmv-s2-YZ/ZY`), each locally
verified to give `sinθ`. **4 circuits × 1 credit = 4 credits** (cumulative → 17 / 25).

## Non-claims
A QPU running `U_ZZ(θ)` emulates a model. No graviton, spacetime or "gravity is quantum"
claim; a positive correlator is premise-dependent (see literature L-A3, L-A4).
