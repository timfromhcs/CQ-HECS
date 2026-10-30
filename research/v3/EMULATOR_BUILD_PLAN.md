# Emulator build plan derived from `r-io-7`

**Status:** W1, W3, W4, W5 implemented (2026-10-30); W2 met; W6 open. See §7
for what the implementation found: the per-qubit readout of §1.1 does **not**
transfer to the other jobs, so §1.1's conclusion 3 and §2's "computed, then
discarded" are superseded. The text of §1–§6 is kept as written before the
code change.

**Run status at time of writing:** 25/25 jobs completed, H-V3-8 `SUPPORTED`
(median ΔTV −0.071905, 95 % CI [−0.135899, −0.006703], 14/20 EVAL circuits
closer to measurement than ideal). The plan below is derived from the measured
numbers, not from the hypothesis outcome — a `SUPPORTED` verdict on a model
this coarse is exactly why the per-qubit work matters.

**Input data:** 25 jobs, 1000 shots each, one backend
(`rigetti:cepheus-1-108q`, Open Quantum, Public/Standard),
`research/v3/evidence/openquantum/rigetti_cepheus-1-108q/`.

---

## 1. What the measurement says

These are the numbers the emulator now has to answer to. All are measured
counts, not model output.

### 1.1 Readout error is large, asymmetric, and concentrated on one qubit

`OQ-01` (`readout_zero_5`, ideal `00000`) and `OQ-02` (`readout_one_5`, ideal
`11111`), 1000 shots each, qubit 0 rightmost:

| qubit | P(1\|0) | P(0\|1) |
| ---: | ---: | ---: |
| 0 | 0.070 | **0.531** |
| 1 | 0.039 | 0.060 |
| 2 | 0.003 | 0.059 |
| 3 | 0.042 | 0.093 |
| 4 | 0.011 | 0.077 |
| **mean** | **0.033** | **0.164** |

Three facts follow directly:

1. The two directions differ by a factor of five on the device mean, and by
   7.6× on qubit 0.
2. Qubit 0 alone accounts for most of the mean: 0.531 against 0.059–0.093 on
   the rest, a spread of 9×.
3. A device-mean readout model — what `M-FIT` in
   `cqhecs/openquantum_suite.py` fits — cannot represent this. It assigns
   0.164 to every qubit in the `1` state, which is right on average and wrong
   everywhere individually.

### 1.2 The CX term is not the dominant error at this depth

`OQ-04` (GHZ-5, 20 CX) and `OQ-05` (GHZ-5, 36 CX) are the same state with
almost twice the two-qubit depth:

| job | CX | share in `00000`+`11111` |
| :--- | ---: | ---: |
| OQ-04 `ghz5_pad2` | 20 | 0.729 |
| OQ-05 `ghz5_pad4` | 36 | 0.719 |

An 80 % increase in CX count costs 0.010 in ideal-outcome share. Width costs
much more than depth:

| job | qubits | CX | share |
| :--- | ---: | ---: | ---: |
| OQ-06 `bell` | 2 | 1 | 0.927 |
| OQ-07 `ghz3` | 3 | 2 | 0.891 |
| OQ-08 `ghz4` | 4 | 3 | 0.783 |
| OQ-09 `ghz5` | 5 | 4 | 0.730 |

That is the signature of readout, not of gate error: every extra qubit adds
one more chance to misread, while gate count barely moves. A single scalar
`p` on every `cx` will therefore absorb readout error into the "gate" term and
report a CX error that the device does not have.

### 1.3 Bit order is confirmed, and the probe works

`OQ-03` (`bitorder_q0_5`) returned `00001` as its mode (0.459), i.e. qubit 0
is rightmost, as preregistered. The 44.3 % in `00000` is the qubit-0 readout
defect from §1.1, not a bit-order problem. The probe earns its place: it
separates the two explanations without manual bit reversal.

### 1.4 No calibration snapshot was delivered

Every job was requested with calibration, but the provider returned
`calibration_data_url = null` for all of them. The run is therefore
**uncalibrated in the provenance sense**: the counts stand on their own, and
nothing may be inferred about T1/T2 or gate timing from this dataset.

### 1.5 What this dataset cannot say

- One backend, one day, one queue state. No drift claim; `OQ-25` is the only
  repeat and cannot separate drift from shot noise on its own.
- No per-qubit calibration values, so no T1/T2 model can be validated here.
- 1000 shots cap the resolvable probability at ~0.001 per outcome; small
  differences between jobs are inside shot noise.

---

## 2. What the emulator already has

Read against `cqhecs/hardware_bridge.py`, the gap is narrower than it looks:

| Capability | State |
| :--- | :--- |
| Per-qubit **asymmetric** readout | **exists**: `BackendProfile.readout_errors: {qubit: (p01, p10)}`, `ReadoutErrorChannel`, column-stochastic validation |
| Per-qubit values in the `r-io-7` model | **computed, then discarded**: `fit_model()` derives `p01_q`/`p10_q` per qubit and stores them in `FittedModel`, but `noise_model()` calls `set_readout_error(qubit, self.p01, self.p10)` for every qubit — the device mean |
| Kraus channels, T1/T2 | exists, validated |
| Exact density matrix ≤ 10 qubits | exists |
| IBM calibration import | exists (schema 2.0) |
| Fit a profile **from measured counts** | **missing** |
| A pinned real dataset to regress a profile against | **missing** (R-IO-5 has no circuits) |
| Provider adapter behind `RealHardwareBackend` | missing, fail-closed by design |

The engine can *represent* what §1.1 measured, and the fit already *computes*
it. The one line that would apply it is deliberately not taken: `M-FIT` is
preregistered and frozen. Changing it now would be a post-hoc model change,
not a test. Any per-qubit model is therefore `M-FIT-2`, evaluated after the
fact on the same 25 jobs, labelled exploratory, and confirmable only on data
that did not exist when it was written.

---

## 3. Work packages

Ordered by dependency. Each package states its acceptance test, because a
package without one is not planned, only wished for.

### W1 — Fit a profile from measured counts (`cq-hecs noise-fit`)

**Why:** §1.1 and §1.2 show that the mean-parameter model is structurally
wrong. The fit has to be per qubit and per direction.

**Change:** new CLI `cq-hecs noise-fit --dataset <id> --out profile.json`
that consumes a counts dataset plus the circuit definitions, fits

- `p01[q]`, `p10[q]` per qubit from dedicated probes,
- one depolarizing parameter per CX edge from GHZ ladders,

and emits a versioned `BackendProfile` with a `provenance` block naming the
dataset SHA, the job IDs, the fit objective, and the shots.

**Acceptance:**

- On the `r-io-7` data the fitted `p01`/`p10` reproduce the §1.1 table to
  within the binomial standard error of 1000 shots.
- The fitted profile scores a lower median ΔTV on the EVAL split than the
  three-parameter mean model, on the same held-out jobs, with the same
  bootstrap (5000 resamples, seed 20261030).
- Fitting twice on the same input gives byte-identical profiles.

Because `M-FIT` is frozen (§2), the first comparison is **post-hoc and
exploratory**: the model is written after seeing these 25 jobs. It is a
mechanism check, not a confirmation. Confirmation needs a fresh suite on a
backend that was not used to write the model; until then the README must say
so in the same sentence as the number.

### W2 — Pin `r-io-7` as a reproducible dataset

**Why:** §1.5 limits what can be claimed, but the counts themselves are
checkable forever if they are pinned. Right now the evidence lives only in a
working tree.

**Change:** commit the 25 result folders (counts + circuit hashes + job IDs,
no credentials) under `research/v3/evidence/openquantum/<backend>/`, register
the dataset in `research/v3/DATASETS.md` with SHA-256 pins, and add
`cq-hecs reference run --dataset r-io-7`.

**Acceptance:** `cq-hecs reference run --dataset r-io-7` reproduces the
published `h_v3_8_evaluation.json` numbers from a clean checkout, offline.

### W3 — Prove per-qubit asymmetric readout in the noisy path

**Why:** the schema supports it; no test pins it to a measured magnitude.

**Change:** regression test that builds a profile with the §1.1 values,
evolves a GHZ-5 circuit through the density-matrix backend, and asserts the
simulated `00000`/`11111` split matches the analytic prediction for those
matrices. Include the 0.531 case explicitly.

**Acceptance:** the test fails if any qubit's readout is collapsed to the
device mean — i.e. it distinguishes the mean model from the per-qubit model.

### W4 — Separate gate error from readout error in the fit

**Why:** §1.2 makes it very likely that a scalar CX parameter absorbs readout
error. Reporting that number as "gate error" would be a false claim with a
decimal point.

**Change:** fit the CX term **after** correcting the counts for the fitted
readout matrices, not before; report the corrected and uncorrected numbers
side by side, with the correction stated as an assumption.

**Acceptance:** the report emits both numbers; on `r-io-7` the corrected CX
error is lower than the uncorrected one and the difference is documented, not
hidden.

### W5 — Record absent calibration instead of silence

**Why:** §1.4. A profile with no calibration and a profile with good
calibration currently look the same downstream.

**Change:** `BackendProfile.provenance.calibration` gains an explicit
`absent` state; the reference report prints it.

**Acceptance:** a dataset without calibration snapshots evaluates successfully
and marks `calibration: absent` in every artifact; a test asserts the field is
never silently defaulted.

### W6 — Open Quantum adapter (blocked by design)

**Why:** the run needed a hand-written `oq.py` because no adapter exists. That
is fine for one run, not for a reproducible workflow.

**Change:** `cqhecs/hardware_bridge.py` gains an adapter that submits through
the Open Quantum SDK, behind the existing `REAL_HARDWARE` boundary: explicit
credentials, explicit budget, explicit approval, no fallback.

**Acceptance:** dry-run tests only; no test may spend credits. A real
submission stays a manual, separately approved action.

---

## 4. Order and effort

| Order | Package | Depends on | Size |
| ---: | :--- | :--- | :--- |
| 1 | W3 | — | S |
| 2 | W1 | W3 | M |
| 3 | W2 | — | S |
| 4 | W4 | W1, W2 | M |
| 5 | W5 | W2 | S |
| 6 | W6 | W1 | L |

W3 first because it is the cheapest way to find out whether the engine's
readout path is even correct at the magnitudes §1.1 measured. If it is not,
W1 fits a profile that the simulator then applies wrongly.

---

## 5. Non-goals

- **No "we match real hardware" claim.** One backend, one day, 25 circuits
  with 1000 shots does not support it.
- **No tuning on the EVAL split.** W1's second acceptance criterion is the
  only place the EVAL jobs are touched, and only as a hold-out score.
- **No silent bit reversal.** §1.3 is handled by a probe, not by guessing.
- **No calibration values invented for `r-io-7`.** §1.4 stands.
- **No topological transpilation work here.** The circuits used gates that
  every target accepted; routing is a separate problem with its own evidence
  needs.

---

## 6. How the plan is judged

The plan succeeds if, at the end, a reader can answer all four questions from
the repository alone:

1. Which measured numbers produced this profile? (§1, W2)
2. Which code applies them, and which test would notice if it stopped? (W3)
3. Which numbers are correction assumptions rather than measurement? (W4)
4. What is explicitly not claimed? (§5)

---

## 7. Outcome of W1–W5 (2026-10-30)

| Package | State | Evidence |
| :--- | :--- | :--- |
| W1 `cq-hecs noise-fit` | **done**; profile is byte-identical on refit, readout reproduces §1.1 exactly with binomial SE | `cqhecs/noise_fit.py`, `tests/test_noise_fit.py`, `evidence/openquantum/rigetti_cepheus-1-108q/m_fit_2_profile.json` |
| W1 acceptance "lower median ΔTV than M-FIT" | **not met**: +0.055345, 95 % CI [−0.006595, +0.091789], 7/20 better | `m_fit_2_exploratory.json` |
| W2 pinned dataset | **met**: `cq-hecs reference run --dataset r-io-7` reproduces `h_v3_8_evaluation.json` offline | `DATASETS.md` |
| W3 per-qubit readout in the noisy path | **done**: GHZ-5 with the §1.1 matrices equals the analytic product to 1e-12; the mean model differs by TV > 0.05 | `tests/test_noise_fit.py::PerQubitReadoutTests` |
| W4 corrected vs uncorrected CX | **done, both reported**: 0.00125 corrected (fit TV 0.297) vs 0.018 uncorrected (fit TV 0.135) | `m_fit_2_profile.json` |
| W5 explicit calibration state | **done**: `calibration: absent` in the profile and `calibration_status` in the H-V3-8 output | tests above |
| W6 Open Quantum adapter | open | — |

**Why W1 fails its acceptance.** In `OQ-02` (X on every qubit) 404 of 1000
shots read `11110`: logical qubit 0 misreads `1` as `0`. In the GHZ jobs the
same single-zero pattern on qubit 0 occurs 15–24 times per 1000. The probes
and the entangling circuits ran on different physical qubits, so the probe's
qubit 0 says nothing about the GHZ's qubit 0. The corrected CX fit is lower
than the uncorrected one only because the transferred readout is wrong for
those jobs; its fit TV (0.297) is worse than the uncorrected fit (0.135).
Reporting 0.00125 as the "true" CX error would be the false claim §W4 warned
about, in the other direction.

**What follows.** A per-qubit model needs either the physical layout of every
job or a readout probe inside each job. Neither is available for `r-io-7`.
The next suite should (a) request and pin the provider's layout, or (b) add
mid-suite readout probes compiled with the same layout as the circuits they
calibrate, and (c) run on a second backend so a model is confirmed on data it
was not written from.
