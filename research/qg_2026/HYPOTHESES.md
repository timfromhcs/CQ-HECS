# HYPOTHESES.md — registry (campaign `qg-2026-01`)

Frozen before any paid job. Each record: claim, model, system/params, observable,
null/competing models, primary statistic, expected direction/tolerance, acceptance /
rejection / inconclusive criteria, shots/seed/circuits, split, multiple-testing method,
budget/stop rule, confounds, and code/manifest digests. Status starts `PROPOSED`.

Statistics policy: bootstrap CIs with deterministic seed; resampling unit = independent
circuits (repeated shots on one circuit are **not** independent circuits); Holm across a
sweep; a CI crossing the null is `INCONCLUSIVE`, never "almost supported".

---

### QG-BMV-01 — Effective two-probe phase model produces the predicted entanglement
- Model: `qg.bmv.zz.v1` — `U_ZZ(θ)=exp(-iθ/2 · Z⊗Z)` on `|+>|+>` with local phases factored
  out; entangling invariant `φ00+φ11−φ01−φ10 = θ` (derived in `MODEL_MANIFEST` / code doc).
- System: 2 qubits, θ ∈ [0, 2π].
- Observable: concurrence, negativity, entanglement entropy; witness threshold τ.
- Oracle: closed-form concurrence `C=|sin θ|` (derived) + dense matrix reference.
- Primary statistic: max absolute deviation of simulated concurrence from oracle.
- Acceptance: `max|ΔC| ≤ 1e-9` over the sweep. Reject if any point exceeds. Inconclusive if
  the oracle itself is under-specified for a point.
- Null: `QG-BMV-02`. Seed: fixed; no shots (exact). Budget: 0 credits.
- Cannot establish: any physical coupling to gravity.

### QG-BMV-02 — Local-only / LOCC null controls remain separable
- Model: explicit local unitaries + shared classical randomness (θ=0 branch).
- Observable: negativity `𝒩` and partial-transpose spectrum.
- Acceptance: `𝒩 ≤ 1e-12` for all null controls from a product state.
- Reject if any null produces entanglement (would indicate a construction bug).

### QG-BMV-03 — Declared noise preserves/destroys the witness in predicted regions
- Model: dephasing, amplitude damping, single/two-qubit depolarizing, asymmetric readout
  on `QG-BMV-01` (`cqhecs.quantum_gravity.noise`, `qg.noise.uniform.v1`).
- Method: noisy density matrix (exact model) + rigorous Hoeffding interval for `Z⊗Z`.
- Acceptance: measured witness vs the noisy model prediction within the model's own
  numerical tolerance; classify regions where TV is non-discriminating explicitly.
- Status: `SUPPORTED_WITHIN_MODEL` for channel correctness and monotonicity (local tests);
  the preregistered **device** comparison (`QPU`/simulator) is `NOT_RUN` (B-1).
- Budget: local ONLY unless a QPU check is separately preregistered (gated by B-1).

### QG-SYK-01 — Small-N sparse SYK mapping preserves algebra and spectrum
- Model: `qg.syk.q4.v1` — N Majorana, q=4, seeded Gaussian couplings.
- Observable: `{γi,γj}=2δij`; Hermiticity; parity `P`; exact spectrum vs dense oracle.
- Acceptance: anticommutator residual ≤ 1e-10; `‖H−H†‖` ≤ 1e-10; spectrum match ≤ 1e-9;
  sparse-vs-full spectrum match within declared sparsification tolerance.

### QG-SYK-02 — Chosen time-evolution method estimates the observable within tolerance
- Observable: Loschmidt amplitude / OTOC at fixed t on small N.
- Oracle: exact matrix exponential (SciPy expm) + independent dense reference.
- Acceptance: Trotter error decays with step count and is reported separately from any
  shot/sampling error; no single conflated number.
- Status: PROPOSED (evolution implemented next slice).

### QG-SYK-03 — QPU returns the sign/time-dependent SYK signal consistent with the model
- Requires B-1 + a live QPU + frozen manifest. B-1 resolved; a live QPU was used.
- Status: **INCONCLUSIVE** — the corrected v3 forward and mirror results are mutually
  inconsistent under a standard noise model (F-09, F-10); no SYK hardware claim is made.

### QG-SYK-04 — Mirror-circuit performance predicts target-observable decay
- Paired circuit/mirror experiments; predeclared comparison; statistical uncertainty.

### QG-GAUGE-01 — Lattice Hamiltonian preserves encoded gauge constraints
- `[H, G_v]=0` on a bounded Z2 square-lattice toy (`qg.gauge.z2.v1`), with
  `G_v^2 = B_p^2 = I` and integer spectrum. Status: `SUPPORTED_WITHIN_MODEL` (toy);
  a QFT bridge, not a gravity claim.

### QG-GAUGE-02 — Noise-induced gauge leakage predicted by declared channels
- Exact small reference + noisy comparison. Status: PROPOSED (not implemented).

---

## Hypothesis x acceptance summary

| ID | Gate type | Needs credits? | Status |
|---|---|---|---|
| QG-BMV-01 | exact-arithmetic oracle | no | PROPOSED |
| QG-BMV-02 | exact separability | no | PROPOSED |
| QG-BMV-03 | noisy model + CI | no* | PROPOSED |
| QG-SYK-01 | exact linear algebra | no | PROPOSED |
| QG-SYK-02 | numerical convergence | no | PROPOSED |
| QG-SYK-03 | QPU held-out evaluation | yes | BLOCKED (B-1) |
| QG-SYK-04 | paired paired-experiment | yes | PROPOSED |
| QG-GAUGE-01 | exact commutator | no | SUPPORTED_WITHIN_MODEL |
| QG-GAUGE-02 | noisy comparison | no* | PROPOSED |

\* local simulation only unless a QPU replication is preregistered under a new version.
