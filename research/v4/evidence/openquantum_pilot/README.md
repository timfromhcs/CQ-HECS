# r-qpu-pilot-1 — five-job IonQ pilot (25 Spark credits)

**Status:** submitted 2026-10-30; collection pending.

This is **not** the preregistered `r-io-7` suite. The account held 25 Spark
credits; `ionq:forte-1` quoted 49 credits for a 1000-shot job and 5 credits for a
100-shot job. A full 25-job run was therefore impossible. Instead, five probe
jobs were submitted at 100 shots each, for exactly 25 credits (all of them):

| job | circuit | why |
| :--- | :--- | :--- |
| `OQ-01` | `readout_zero_5` | `P(1|0)` on qubit 0 |
| `OQ-02` | `readout_one_5` | the 0.531 marginal seen on Rigetti |
| `OQ-03` | `bitorder_q0_5` | the single-X probe that identified the anomaly |
| `OQ-04` | `ghz5_pad2` | a GHZ state with no `X` gate |
| `OQ-09` | `ghz5` | a second GHZ state with no `X` gate |

The circuits are byte-identical to the SHA-256-pinned preregistered copies in
`research/v3/openquantum_suite/`; only the shot count and the subset differ.

## Second batch — higher statistics on the identification triple

A second account key held another 25 Spark credits. They were spent on three
jobs that sharpen the same question:

| job | shots | credits | provider job |
| :--- | ---: | ---: | :--- |
| `OQ-01` | 200 | 10 | `5898bb8e-7c38-4f62-8f4c-403d9f8b9485` |
| `OQ-03` | 200 | 10 | `f5237406-458c-459a-b393-84cee2921fa7` |
| `OQ-02` | 100 | 5 | `da9549e3-d4f0-43b3-8394-28a4e1eec846` |

`OQ-01` is the readout control (`P(1|0)`), `OQ-02` is the all-`X` circuit, and
`OQ-03` is the single-`X` probe that identified the anomaly. At 200 shots the
binomial 95 % interval at `p = 0.5` is about ±0.07, so this batch can resolve
"about half" from "about seven percent" with more margin than the first batch.
It is stored under `ionq_forte-1-highstats/`; it is still not the preregistered
suite and still cannot confirm a full noise model.

Balance after the second batch: `spark=0`, `full=0`.

## Collection

The two batches were submitted under different organization credentials. Use
the matching key for each `oq.py results` call; mixing keys cannot retrieve the
other organization's jobs. The runner
`scripts/collect_openquantum_pilot.py` reads the job IDs from each folder and
downloads whatever the current credentials can see.

## What the pilot can and cannot say

With 100 shots the binomial 95 % interval at `p = 0.5` is about ±0.10. The pilot
can separate “about half” from “about seven percent” on qubit 0. It cannot fit a
noise model, cannot evaluate `H-V3-8`, and cannot confirm `M-FIT-2`.

## Verdict rule (fixed before collection)

- `ANOMALY_REPRODUCED`: `OQ-03` and `OQ-09` both have a 95 % lower bound above
  0.30 on qubit 0.
- `ANOMALY_NOT_REPRODUCED`: `OQ-03`'s upper bound is below 0.20 and `OQ-01`'s
  upper bound is below 0.20.
- otherwise `INCONCLUSIVE`.

A negative result is reported as measured and is not retried with other
settings.

## Job IDs

| job | provider job |
| :--- | :--- |
| `OQ-01` | `08cda1d3-44d6-4e73-b8ec-5a120a6ce2f7` |
| `OQ-02` | `56da9b09-39a2-48ce-a118-404918394449` |
| `OQ-03` | `7762e3c8-66c8-4921-a153-e6acf6ce9b8c` |
| `OQ-04` | `a724f1fd-46dd-49a6-ba44-73d8b092b529` |
| `OQ-09` | `c6ffca4f-3618-4e3a-baae-6329d28f4992` |

Balance after submission: `spark=0`, `full=0`. No credential is stored in this
folder. Rotate the SDK key after collection.
