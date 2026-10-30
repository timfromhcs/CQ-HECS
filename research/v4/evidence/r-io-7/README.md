# Corrected M-FIT-2 evidence

This folder holds the corrected fit used by the Studio and by
`research/v4/FINDINGS.md`.

| File | Format | Producer |
| :--- | :--- | :--- |
| `mfit2.json` | Studio model snapshot (`schema_version` 1.0) | `cqhecs.noise_fit` v4 branch / `write_fit` |
| `mfit2_evaluation.json` | per-job EVAL comparison | same |
| `profile.json` | validated `BackendProfile` schema 2.0 | same |

The CLI `cq-hecs noise-fit` on the v3.1.0 tree writes the
`cqhecs.fitted_noise_profile/2.0` format to
`research/v3/evidence/openquantum/rigetti_cepheus-1-108q/m_fit_2_profile.json`.
The two documents describe the same fitted numbers: `p10[0] = 0.03`,
`x_bitflip[0] = 0.536`, `cx_depolarizing = 0.005`.

Key result:

- FIT TV 0.2286 → 0.1209
- EVAL ΔTV vs ideal −0.0719 → −0.1054 (16/20)
- paired vs `M-FIT` −0.0265, 95 % CI [−0.0413, +0.0207] → H-V3-9 still not
  supported

Everything is post-hoc. The `OQ-02` 0.531 marginal is an `X`-gate anomaly, not
readout error; see `research/v4/FINDINGS.md` §1.
