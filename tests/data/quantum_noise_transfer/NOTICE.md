# Quantum Noise Transfer — vendored reference data

Source: <https://huggingface.co/datasets/sahilfarib/quantum-noise-transfer>
Paper: *Few-Shot Cross-Device Transfer for Quantum Noise Modeling on Real Hardware*
(arXiv:2604.24397), Sahil Al Farib, Sheikh Redwanul Islam, Azizur Rahman Anik.
Licence: MIT, as declared on the dataset card.

Retrieved 2026-10-30 from the `main` revision of the dataset repository.

Vendored files (the five files needed to reproduce the v3 reference
evaluation; the upstream repository also contains figures and result files
that are not used here):

| file | content |
|---|---|
| `circuit_meta.json` | circuit ID, family, width, depth and gate counts (no gate angles or layout) |
| `calibration_A.json` | `ibm_fez` calibration snapshot retrieved 2026-04-17 |
| `calibration_B.json` | `ibm_marrakesh` calibration snapshot |
| `noisy_A.json` | raw measured counts from `ibm_fez` (1024 shots per circuit) |
| `noisy_B.json` | raw measured counts from `ibm_marrakesh` (1024 shots per circuit) |

`SHA256SUMS` pins every vendored file. The harness refuses a file whose digest
does not match.

## Known limitations of this dataset

* The upstream README states 8192 shots; every vendored `raw_counts` block sums
  to 1024. The harness uses the raw counts and records the mismatch.
* The published circuits are not included. Bell, GHZ and QFT circuits are
  reconstructible from their family definition and gate counts. The 40 random
  circuits are not reconstructible and are excluded from the evaluation.
* The physical layout (circuit qubit to device qubit) is not published, so the
  evaluation uses a device-mean noise model built from the run-time calibration.
  This is weaker than a per-circuit layout; it is recorded in the result.
