# r-io-7 on IBM Quantum (`ibm_fez`)

**External run, not an execution by the `cqhecs` package.** The 25 circuits are
the SHA-256-pinned `r-io-7` circuits; only the backend and the fixed physical
mapping differ.

| Item | Value |
| :--- | :--- |
| Backend | `ibm_fez` (156 qubits, IBM Quantum open plan) |
| Runtime job | `dbidem5ep8hs73ankcvg` |
| Circuits | 25 (5 FIT + 20 EVAL) |
| Shots | 1000 per circuit |
| Fixed physical chain | `[98, 111, 110, 109, 118]` |
| QPU usage | 9 s (597 → 588 s remaining on the 600 s open-plan budget) |
| Bit-order probe | `OQ-03` mode `00001` (little-endian, as expected) |

A four-circuit pilot on `ibm_kingston` (job `dbiddvohoj4c73b5vkhg`, 3 s) was
run first to check the chain, transpilation and bit order. It is kept under
`pilot_pilot/ibm_kingston/`. The pilot already showed a healthy qubit 0:
`OQ-01 = 0.004`, `OQ-02 = 0.990`, `OQ-03 = 0.984`, `OQ-09 = 0.493`.

## Results

The frozen `M-FIT` model was fitted on the IBM FIT jobs and evaluated on the
IBM EVAL jobs:

| Quantity | Value |
| :--- | :--- |
| H-V3-8 | **`SUPPORTED`** |
| Median ΔTV (M-FIT − ideal) | **−0.036642** |
| 95 % bootstrap CI | **[−0.045217, −0.027301]** |
| EVAL jobs where M-FIT is closer | **20/20** |

The corrected `M-FIT-2` procedure was also fitted on IBM:

- no anomalous qubit was detected (`anomalies: []`), so the 0.531 `OQ-02`
  marginal seen on Rigetti is **backend-specific**, not a universal readout
  property;
- vs ideal: median ΔTV **−0.032766**, 95 % CI [−0.044632, −0.023821], 20/20
  better;
- vs `M-FIT`: median **+0.001688**, 95 % CI [+0.000327, +0.004045], 5/20
  better → `M-FIT-2` is **slightly worse** than the frozen mean on this
  backend. H-V3-9 remains **not supported**.

That is the useful part: the per-qubit fit is a better physical description on
Rigetti because of a real `X`-gate anomaly, but it is not a better predictor
than the device mean on a healthy backend. The anomaly did not transfer, and
the model did not beat the frozen model.

## Provenance

- `summary.json` — job ID, chain, transpiled digests, usage.
- `OQ-01 … OQ-25/` — original pinned `circuit.qasm`, measured `result.json`,
  `job.json` with the transpiled QASM.
- `calibration.json` — backend properties captured after the run.
- `h_v3_8_evaluation.json` — frozen `M-FIT`/H-V3-8 evaluation.
- `m_fit_2_profile.json`, `m_fit_2_exploratory.json` — corrected per-qubit
  procedure, post-hoc.

The API key lives in `apikey.json`, which is ignored by Git and is not copied
here. Rotate it at <https://quantum.cloud.ibm.com/> after the run if it was
shared.

External IBM run, 2026-10-30. No QPU execution is performed by the package.
