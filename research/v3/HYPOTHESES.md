# CQ-HECS v3 Falsifiable Hypotheses (updated 2026-10-30)

Status vocabulary: `PROPOSED`, `RUNNING`, `SUPPORTED`, `INCONCLUSIVE`,
`REJECTED`, `BLOCKED`. A hypothesis is supported only by the run whose dataset
and model digests are recorded with it.

## H-V3-1 — A device-mean noisy model beats the ideal distribution on real counts

**Preregistered** before the first W4 run (V3_STABLE_PLAN.md §1, §4).

* **Population:** the 7 unique reconstructible circuits per backend (14 total;
  Bell, GHZ, QFT) on `ibm_fez` and `ibm_marrakesh`; repeated executions of the
  same circuit are pooled, not counted as independent circuits.
* **Prediction:** the device-mean noise model (median CX depolarizing, median
  symmetric readout) is closer to the measured counts than the noiseless
  distribution.
* **Statistic:** median paired difference
  `ΔTV = TV(real, noisy) − TV(real, ideal)`.
* **Acceptance:** `median ΔTV < 0` and the 95 % bootstrap interval (circuits
  resampled; shots resampled within each circuit) excludes 0.
* **Falsification:** the interval lies above 0, or the median is not negative.

**Result (2026-10-30, 14 unique circuits, 5000 resamples):**

| quantity | value |
|---|---|
| median ΔTV | **−0.015660** |
| 95 % CI | **[−0.032546, 0.000000]** |
| verdict | **INCONCLUSIVE** |
| circuits where noisy is better | 10/14 |
| Bell | n=2, median ΔTV −0.024086, CI [−0.031049, −0.017122] |
| GHZ | n=6, median ΔTV −0.038117, CI [−0.060869, −0.016476] |
| QFT | n=6, ΔTV exactly 0 (see H-V3-2) |

The pooled criterion is **not met** because the upper interval endpoint is
exactly 0. This is caused by six QFT circuits on which the model cannot move
the prediction at all, not by a noisy model that is worse than ideal. The
pre-specified verdict stays **INCONCLUSIVE**.

**Exploratory (not preregistered):** on the eight identifiable circuits
(Bell + GHZ), median ΔTV = **−0.031797**, 95 % CI
**[−0.054182, −0.017122]**, 8/8 better. This is reported as exploratory only;
it does not retroactively change H-V3-1.

**Threats to validity:** no physical layout, no published one-qubit gate
errors, 1024 shots per upstream execution, QFT input state assumed to be
`|0…0⟩`, and QFT decomposition not verified against the opaque upstream `QFT`
gate.

## H-V3-2 — Unital noise is invisible on a maximally mixed output

**Status: SUPPORTED by proof, not by statistics.**

If the ideal output of a circuit is `I/2^n` (for example QFT applied to
`|0…0⟩`), then every unital channel `Φ` satisfies `Φ(I/2^n) = I/2^n`. A
depolarizing channel and a symmetric readout assignment are unital (the latter
is doubly stochastic). Therefore any model built only from those elements
predicts exactly the ideal distribution, and `ΔTV = 0` regardless of noise
strength. This explains the six QFT ties in H-V3-1 and is a boundary on what
the dataset can test, not evidence for or against the model.

**Consequence:** future real-data evaluations must either use a non-unital
channel, an asymmetric readout map, or a circuit family with a non-maximally-
mixed ideal output. This is preregistered as H-V3-5.

## H-V3-3 — Layout-aware prediction is better than device-mean prediction

**Status: BLOCKED (data unavailable).**

* **Claim:** using the actual physical layout and per-qubit/per-edge
  calibration would reduce `TV(real, noisy)` relative to the device-mean model.
* **Why blocked:** R-IO-5 does not publish the circuit-to-device layout. The
  IBM job records referenced by the dataset are not reachable without
  credentials. R-IO-6 publishes a layout but its circuits are ≥20 qubits.
* **Test if unblocked:** pin the layout, build the per-edge profile, and run the
  same statistic on the same circuits. No tuning on the evaluation counts.

## H-V3-4 — Trajectory sampling reproduces 20-qubit patch XEB

**Status: PROPOSED (not run).**

* **Claim:** stochastic statevector trajectories with the calibrated noise
  model reproduce the measured patched-XEB fidelity of R-IO-6 within its
  bootstrap interval at depths 20–36.
* **Why it matters:** it extends the bridge past the exact density-matrix
  ceiling without claiming an exact noisy state.
* **Test:** fixed seeds, 20–21 qubit patches, XEB estimator from the dataset's
  own `analysis/compute_patch_xeb.py`, preregistered tolerance before looking
  at the counts.
* **Risk:** trajectory sampling has its own Monte-Carlo error; it must be
  reported separately from the model error.

## H-V3-5 — Asymmetric readout is required to explain QFT counts

**Status: PROPOSED.**

* **Claim:** the QFT count asymmetry (e.g. `00` low, `11` high) is explained by
  asymmetric readout (`p(1|0) ≠ p(0|1)`), not by coherent gate error.
* **Test:** calibrate `prob_meas1_prep0` and `prob_meas0_prep1` for the run-time
  snapshot, rebuild the readout map, and compare on the same QFT circuits.
* **Falsification:** symmetric readout already explains the counts within the
  shot-noise interval, or the asymmetry is stable across reruns with different
  readout calibration.

## H-V3-6 — Calibration drift bounds the achievable prediction

**Status: PROPOSED.**

* **Claim:** using a calibration snapshot more than a few hours from the job
  increases `TV(real, noisy)` measurably; the nearest-in-time snapshot is a
  better predictor than a device-mean model from another date.
* **Data:** R-CAL-2 (30.1 M calibration rows) plus job timestamps.
* **Test:** pre-register a time window, fit nothing on the evaluation counts,
  and report the TV as a function of calibration age.

## H-V3-7 — P = NP

**Status: NOT A HYPOTHESIS OF THIS PROJECT / NO CLAIM.**

P versus NP is open. The barriers (relativization, natural proofs,
algebrization) rule out whole classes of proof techniques; they do not settle
the question. No CQ-HECS code, benchmark, ETH artifact, SAT solver, or quantum
simulation can prove `P = NP`, and no document in this repository may claim
progress on it without a formally checked proof of the exact statement. The
ETH/OpenAI/Anthropic artifacts are classical #SAT algorithms with asymptotic
claims; they are not a proof of `P = NP` and do not transfer to arbitrary
quantum amplitudes. See `research/v3/LITERATURE_MAP.md` §1 and
`research/v3/COMPLEXITY_BOUNDARY.md`.

## H-V3-8 — A fitted 3-parameter model beats the ideal distribution on our own QPU runs

**Status: PREREGISTERED, NOT RUN.** Protocol: `research/v3/OPENQUANTUM_RUN_PLAN.md`.

* **Claim:** on the 20 held-out EVAL jobs of the `r-io-7` suite, `M-FIT`
  (mean readout + one CX depolarizing parameter, fitted on the 5 FIT jobs only)
  has a smaller TV to the measured counts than the ideal distribution.
* **Test:** median paired `ΔTV < 0` with a 95 % bootstrap interval (circuits
  resampled, 5000 draws, seed 20261030) excluding 0.
* **Data:** none yet. The Open Quantum API was not reachable from the session
  that registered this hypothesis.

## Experiment index

| ID | Hypothesis | Dataset | Evidence |
|---|---|---|---|
| E-V3-04 | H-V3-1 (pooled + exploratory) | R-IO-5, digest `8069ad50…` | `research/v3/evidence/r_io_5_evaluation.json` |
| E-V3-05 | H-V3-2 (unital invariance) | analytic + QFT simulation | this file; `tests/test_reference.py::test_qft_is_invariant_under_unital_noise` |
| E-V3-06 | H-V3-8 (own QPU suite) | R-IO-7 — **not run** | `research/v3/OPENQUANTUM_RUN_PLAN.md`; results will go to `research/v3/evidence/openquantum/` |
