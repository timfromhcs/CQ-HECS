# Noise governance and QEC/RL ideas (W10, agent B4)

Status: PROPOSED / research note. Nothing here is a product claim. No QPU job, provider call,
credit spend or credential was used. Offline reproduction of existing evidence only.

## 1. Calibration schema v3 (implemented, additive)

`cqhecs/calibration_v3.py`, schema id `cqhecs.calibration/3.0`. It wraps an unchanged
`BackendProfile` (1.0/2.0); no existing field changed meaning.

| Field | Rule |
|---|---|
| backend_identity | `provider:name`, derived from the profile |
| calibration_timestamp | profile `capture_timestamp`, must parse as ISO-8601 |
| layout | logical-to-physical tuple; injective, in range (empty = not declared) |
| gate_basis | profile `basis_gates` |
| units | t1/t2 us, gate_duration ns, errors as probabilities |
| provenance_label | `synthetic / measured / derived / post_hoc / unknown` |
| freshness_policy | `max_age_hours`; status `fresh / stale / unknown`, never defaulted to fresh; future stamps are stale |

Label rules: a synthetic profile cannot be `measured`; a non-synthetic one cannot be
`synthetic`; `measured` requires timestamp plus URI or SHA-256; an unlabelled non-synthetic
profile is `unknown`, not `measured`. The label describes provenance only; it is not evidence
of predictive skill.

Uncalibrated gates: `CalibrationV3.check_gates(instructions, policy)` with
`refuse` (typed `UncalibratedGateError`), `warn` (reported warning) or `ideal` (accepted, still
reported in `uncovered_gates`). Wraps `BackendProfile.uncovered_gates`. Not yet wired into Studio/CLI
(NOT DONE; owned files only).

Model checks: `check_channel` (Kraus completeness, Choi Hermiticity, Choi minimum eigenvalue) and
`check_noise_model` (all channels plus column-stochastic, non-negative readout matrices).

Not done: transpilation into the calibrated basis (gates are still matched as written),
topology legality of a layout against the coupling map, schema-v3 migration from v1/v2 JSON files
on disk, UI exposure.

## 2. FIT / VALIDATION / EVAL separation

r-io-7 has FIT (5 jobs) and EVAL (20 jobs); there is no VALIDATION split in the committed suite.
Any model needing hyperparameter choice would need a new preregistered suite with a VALIDATION
split (see H4-NOISE-01); that was not created.

Enforcement tests (`tests/test_noise_governance.py`):
1. a recording wrapper on `SuiteRun.counts` shows `fit_profile` touches FIT jobs only;
2. adding 12345 to a count in every EVAL result file leaves the fitted profile identical
   (only `dataset_sha256`, a digest of all job files, is excluded as provenance).

Caveat: `M-FIT-2` is `EXPLORATORY_POST_HOC` (designed after EVAL counts were known); these tests prove
code-level independence, not that the design choice was independent of EVAL.

## 3. QEC / RL ideas (isolated, unvalidated)

- Syndrome-aware noise models: extend per-qubit readout/X-anomaly to correlated readout (a
  confusion matrix over pairs) and test on a fresh device; null hypothesis: independent readout.
- Decoder evaluation harness: compare MWPM-style and learned decoders on simulated circuit-level noise
  from the checked Kraus models, with fixed seeds and a held-out noise-parameter range.
- RL for calibration scheduling (when to re-calibrate given drift): needs real drift time series
  (not available offline here); simulation-only toy would not support any device claim.
- Risks: simulated noise is the model's own assumption, so a decoder tuned to it proves nothing about
  hardware; learned policies must be evaluated on held-out noise families.
None of these is implemented, benchmarked or promoted.

## 4. Verification

See `research/v7/evidence/waveB_B4.md`.
