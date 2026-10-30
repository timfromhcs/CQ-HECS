# Open Quantum real-QPU suite (`r-io-7`) — preregistration

**Status:** RUN, 25/25 jobs (2026-10-30, `rigetti:cepheus-1-108q`, Public /
Standard, 1000 shots, 25 credits). H-V3-8 **`SUPPORTED`**: median ΔTV
−0.071905, 95 % CI [−0.135899, −0.006703]. Evidence:
`research/v3/evidence/openquantum/rigetti_cepheus-1-108q/`. The text below is
the protocol as preregistered before submission; it was not edited after the
counts were known.

## 1. Why our own runs

The v3 Stable gate V3-D (`V3_STABLE_PLAN.md` §4) needs a real input/output
record with **complete circuits** at a width the exact noisy path handles.
`r-io-5` publishes counts but not its circuits or layout, so its pooled
H-V3-1 test is `INCONCLUSIVE` and cannot carry the gate. Jobs we author
ourselves remove that gap: every circuit is fixed and hashed before
submission, and the counts are matched back to the hash.

## 2. Fixed before any run

| Item | Value |
| :--- | :--- |
| Generator | `cqhecs/openquantum_suite.py`, `build_suite(seed=20261030)` |
| Circuits | 25 OpenQASM 2.0 files in `research/v3/openquantum_suite/`, SHA-256 in `manifest.json` (test: `tests/test_openquantum_suite.py`) |
| Gate set | `h x s sdg t tdg sx rx ry rz cx` only; controlled phase and SWAP are lowered to `rz`/`cx` |
| Width | 2–5 qubits (exact density matrix, ≤ 10-qubit ceiling) |
| Shots | 1000 per job, 25 000 in total |
| Backend | **one** QPU for all 25 jobs, chosen after quoting (see §4) |
| Plan / priority | Public / Standard unless the person who pays chooses otherwise |
| Calibration | `--calibration` on every job; the file is hashed and recorded, not used by `M-FIT` |
| Ideal reference | CQ-HECS dense/noisy density matrix, cross-checked with Qiskit `Statevector` to ≤ 1e-12 in the tests |

## 3. Jobs and split

`FIT` jobs are used to fit the model. `EVAL` jobs are held out and only used
for the hypothesis test.

| Job | Name | Split | Family | Qubits | CX | Purpose |
| :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| OQ-01 | `readout_zero_5` | FIT | probe | 5 | 0 | P(1\|0) per qubit (X·X on every qubit) |
| OQ-02 | `readout_one_5` | FIT | probe | 5 | 0 | P(0\|1) per qubit |
| OQ-03 | `bitorder_q0_5` | FIT | probe | 5 | 0 | bit order: ideal `00001` (qubit 0 rightmost) |
| OQ-04 | `ghz5_pad2` | FIT | ghz_padded | 5 | 20 | CX error fit (5 CX per link) |
| OQ-05 | `ghz5_pad4` | FIT | ghz_padded | 5 | 36 | CX error fit (9 CX per link) |
| OQ-06 | `bell` | EVAL | ghz | 2 | 1 | `00`/`11` |
| OQ-07 | `ghz3` | EVAL | ghz | 3 | 2 | `000`/`111` |
| OQ-08 | `ghz4` | EVAL | ghz | 4 | 3 | `0000`/`1111` |
| OQ-09 | `ghz5` | EVAL | ghz | 5 | 4 | `00000`/`11111` |
| OQ-10 | `qpe3_t` | EVAL | qpe | 4 | 15 | phase 1/8 → `1001` |
| OQ-11 | `qpe3_s` | EVAL | qpe | 4 | 15 | phase 1/4 → `1010` |
| OQ-12 | `qft4_roundtrip` | EVAL | qft_mirror | 4 | 24 | QFT · QFT⁻¹ on \|1010⟩ → `1010` |
| OQ-13 | `mirror4_d10` | EVAL | mirror | 4 | 14 | U·U⁻¹ → `0000` |
| OQ-14 | `mirror4_d20` | EVAL | mirror | 4 | 16 | U·U⁻¹ → `0000` |
| OQ-15 | `mirror4_d40` | EVAL | mirror | 4 | 32 | U·U⁻¹ → `0000` |
| OQ-16 | `clifford_t3_d12` | EVAL | clifford_t | 3 | 3 | random Clifford+T |
| OQ-17 | `clifford_t4_d16` | EVAL | clifford_t | 4 | 10 | random Clifford+T |
| OQ-18 | `clifford_t5_d20` | EVAL | clifford_t | 5 | 10 | random Clifford+T |
| OQ-19 | `clifford_t5_d30` | EVAL | clifford_t | 5 | 9 | random Clifford+T |
| OQ-20 | `brickwork4_l3` | EVAL | brickwork | 4 | 5 | random rotations + CX bricks |
| OQ-21 | `brickwork5_l4` | EVAL | brickwork | 5 | 8 | random rotations + CX bricks |
| OQ-22 | `grover2_mark11` | EVAL | algorithm | 2 | 2 | `11` |
| OQ-23 | `bv4_1011` | EVAL | algorithm | 5 | 3 | `01011` |
| OQ-24 | `dj3_balanced` | EVAL | algorithm | 4 | 3 | `0111` |
| OQ-25 | `ghz5_repeat` | EVAL | ghz | 5 | 4 | same circuit as OQ-09, submitted last (drift) |

## 4. Procedure

On a machine that can reach Open Quantum, with the key stored by the Open
Quantum skill (`oq.py setup`; never in this repository):

```bash
python scripts/run_openquantum_suite.py generate
python scripts/run_openquantum_suite.py --oq path/to/oq.py quote -b <backend>
python scripts/run_openquantum_suite.py --oq path/to/oq.py submit -b <backend> --budget <approved total> --yes
python scripts/run_openquantum_suite.py --oq path/to/oq.py collect -b <backend>
python scripts/run_openquantum_suite.py evaluate -b <backend>
```

1. `quote` prices all 25 jobs and charges nothing. The total is shown to the
   person who pays; `submit` refuses without `--yes` or above `--budget`.
2. Backend choice: online, accepting jobs, ≥ 5 qubits, cheapest total quote.
   The choice is recorded in `suite_state.json` before submission.
3. Results land in `research/v3/evidence/openquantum/<backend>/OQ-xx/`
   (`result.json`, `job.json`, `circuit.qasm`, `calibration.json`).
4. Results may be committed: they are the submitter's own data. On the Public
   plan any publication must cite Open Quantum.

## 5. Model and hypothesis

**M-FIT** (fitted on FIT only): mean P(1|0) from OQ-01, mean P(0|1) from
OQ-02, one two-qubit depolarizing parameter `p` on every `cx`, chosen on a
fixed coarse-then-fine grid in `[0, 0.3]` to minimise the mean TV over OQ-04
and OQ-05. One-qubit gate error and relaxation are not modelled. Mean (not
per-qubit) readout is used because the provider's physical layout may differ
between jobs.

**H-V3-8:** on the 20 EVAL jobs, `ΔTV = TV(real, M-FIT) − TV(real, ideal)`
has a median below 0 and a 95 % bootstrap interval (5000 resamples of
circuits, seed 20261030) that excludes 0. Verdicts: `SUPPORTED`,
`REJECTED`, `INCONCLUSIVE`. With fewer than 20 EVAL results the verdict is
labelled `incomplete`.

**Stop rules:** if OQ-03 does not return `00001` as its mode, the evaluation
stops (`IntegrityError`); strings are never reversed silently. A QASM file
whose digest differs from the manifest is an `IntegrityError`.

## 6. What a result would and would not show

- `SUPPORTED` means a 3-parameter model beats the ideal distribution on held-out
  circuits of this suite, on one backend, at one time. It is not a general
  "close to real hardware" claim.
- `REJECTED` or `INCONCLUSIVE` are reported as such and block the claim, not
  the measurement.
- A complete run can close the open part of gate V3-D. v3 Stable still needs
  V3-C (W5, Sycamore gates), which this suite does not touch.
