# Preregistration: `r-iqm-1`, the r-io-7 suite on IQM Garnet

**Registered:** 2026-10-30, committed and pushed **before** any job was submitted.
**Backend:** IQM Garnet (`iqm:garnet`, 20-qubit superconducting QPU) via Open Quantum,
Public plan. **Budget:** 25 Spark credits, the whole balance, approved by the owner.

## Why this run

`M-FIT` and the post-hoc `M-FIT-2` have been measured on Rigetti Cepheus (one day,
1000 shots) and on three IBM Heron backends (1k and 10k shots). They have never
been run on a third vendor. IQM Garnet is a different vendor and gate set, so it
is a fresh-backend test of whether the procedure transfers. That is the
confirmation step that FINDINGS §2 says `M-FIT-2` still needs.

## What is fixed (unchanged from `research/v3/OPENQUANTUM_RUN_PLAN.md`)

- The 25 circuits `OQ-01` … `OQ-25`, byte-identical to the committed
  `research/v3/openquantum_suite/manifest.json`. `generate` was re-run, and
  `git diff` on that directory was empty on 2026-10-30.
- The FIT/EVAL split, the `M-FIT` fitting procedure, the bootstrap
  (5000 resamples, seed 20261030, circuits resampled), and the bit-order stop
  condition (`OQ-03` must return `00001`).
- **H-V3-8:** `SUPPORTED` iff the 95 % CI of the median
  ΔTV = TV(real, M-FIT) − TV(real, ideal) over the EVAL jobs lies entirely
  below 0. `REJECTED` iff it lies entirely above 0. Otherwise `INCONCLUSIVE`.
- `M-FIT-2` vs `M-FIT` is reported with the same paired bootstrap. It is
  exploratory, so no hypothesis verdict is attached.

## The one deviation

**Shots: 500 per circuit instead of 1000.** Open Quantum prices Garnet at
1 credit per job for ≤ 500 shots and 2 credits for 1000. The full 25-circuit
suite at 1000 shots would cost 50 credits; the balance is 25. Running all 25
circuits at 500 shots keeps the preregistered design intact, at higher
finite-shot noise. The alternative was dropping circuits, which would break
the FIT/EVAL split.

Consequence, stated in advance: the shot-noise floor of TV for a 5-qubit
distribution roughly doubles (≈ 1/√N). This biases ΔTV toward 0, so the
deviation makes `SUPPORTED` harder, not easier.

## Stop rules

- Any QASM digest mismatch, a bit-order probe ≠ `00001`, or results from two
  backends in one folder: stop. Evaluate nothing and report it.
- No re-run with other settings after the counts are seen. A `REJECTED` or
  `INCONCLUSIVE` verdict is published as measured.
- Jobs that never complete are reported as missing. The verdict is then
  computed on the completed EVAL jobs and marked `complete: false`.

## Outputs

`research/v3/evidence/openquantum/iqm_garnet/` (counts, calibration snapshots,
`suite_state.json`), `h_v3_8_evaluation.json`, `m_fit_2_exploratory.json`, and a
row in `research/v4/FINDINGS.md`.
