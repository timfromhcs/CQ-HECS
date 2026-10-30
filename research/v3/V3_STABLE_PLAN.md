# CQ-HECS v3.0.0 Stable Plan — Real-Reference Bridge

**Status:** IN PROGRESS (2026-10-30). Baseline: v2.5.2 (released, `a65c35b`).
W1 and W2 implemented and tested (see §6); W8 implemented and tested. W4 is
**PARTIAL**: R-IO-5 is reachable, vendored and evaluated (H-V3-1 pooled result
`INCONCLUSIVE`, identifiable subset exploratory `SUPPORTED`); R-IO-1/2/3 remain
blocked. W3 and W5 are not started. W6 is partial.
**Goal:** Measure how close CQ-HECS's noisy emulation gets to *real* quantum
hardware, using complete public input/output records (circuit + raw measured
outcomes + calibration at run time), and ship v3.0.0 Stable only when that
bridge is built, tested against independent oracles and evaluated on real
data with a preregistered metric.

"Closer to real" is a measured number on named datasets, never a general
claim. A noisy model that does *not* beat the ideal model on held-out real
data is reported as such and blocks the claim, not the measurement.

---

## 1. Real data sources (verified 2026-10-30 from this environment)

| ID | Source | Real content | Licence | Reachable here | Use |
|---|---|---|---|---|---|
| **R-CAL** | `qiskit-ibm-runtime` 0.51.0 wheel (PyPI): `fake_provider/backends/*/props_*.json` + `conf_*.json` | **69 real IBM calibration snapshots** (`last_update_date` 2020-02-29 … 2026-04-17): per-qubit T1/T2/readout (`prob_meas0_prep1`, `prob_meas1_prep0`)/frequency, per-gate `gate_error`/`gate_length`, coupling map, basis gates. 3676 qubits in total. | Apache-2.0 | **yes** (pypi.org) | Real-calibration profiles (W1), Aer parity (W2) |
| **R-IO-1** | Google Sycamore 2019, Dryad `doi:10.5061/dryad.k6t1rj8` | Random circuits + measured bitstrings (≈500 000 per circuit for n < 53), amplitudes, noise data; tarballs per (n, m), e.g. `n12_m14.tar.gz`; ≈2.36 GB total | to verify on the record (Dryad publishes under CC0) | **no** — `datadryad.org` denied by network policy | Real I/O reference, XEB (W4, W5) |
| **R-IO-2** | "Application-motivated, holistic benchmarking of a full quantum computing stack", Zenodo 3832121 / 3832120 | Per the record description: `'strategy'_'device'.csv` shot counts of compiled circuits **on real devices**, device-property JSON per run, and counts from a noisy simulator built from those properties | to verify | **no** — `zenodo.org` denied | Real I/O with matching calibration — the closest fit for the profile bridge (W4) |
| **R-IO-3** | "Phase transition in Random Circuit Sampling", Zenodo 11663206 | Sycamore RCS circuits and `measurements_*.txt` bitstrings | to verify | **no** — `zenodo.org` denied | Second RCS reference |
| R-IO-4 | IEEE DataPort (IBM Sherbrooke teleportation, 292 runs × 4096 shots; IBM/Rigetti histograms, 1183 runs) | Real counts, IBM job IDs | to verify; may need login | **no** — `ieee-dataport.org` denied | Optional |

### Hugging Face Hub (searched 2026-10-30 via the Hub API)

| ID | Dataset | Real content | Licence | Usable for |
|---|---|---|---|---|
| **R-IO-5** | [`sahilfarib/quantum-noise-transfer`](https://hf.co/datasets/sahilfarib/quantum-noise-transfer) (arXiv:2604.24397) | Real raw counts from `ibm_fez` (job `d7gh5li2khts739ogh20`, 2026-04-16) and `ibm_marrakesh`, 85 circuits each (40 random, 15 Bell, 15 GHZ, 15 QFT, 2–5 qubits), device calibration snapshots (`calibration_A/B.json`, 156 qubits) | MIT | **Yes.** Hub API and `resolve/main` downloads work; 5 files vendored and SHA-256-pinned (179 923 bytes). Usable for real Bell/GHZ/QFT I/O (W4). |
| **R-IO-6** | [`BlueQubitDev/rcs-nighthawk`](https://github.com/BlueQubitDev/rcs-nighthawk) (revision `b9dd86b`) | 233 QASM/QPY circuits (4–40 cycles), 61 logical qubits of `ibm_phoenix`, raw patched bitstrings, 10^6-shot 36-cycle sample, mirror survival, layout | Apache-2.0 | **Yes.** `raw.githubusercontent.com` reachable; 4 small files pinned. Usable for 20-qubit patch XEB (future H-V3-4); not evaluated by W4 (above 10-qubit DM ceiling). |

| R-CAL-2 | [`phanerozoic/qiskit-calibration-drift`](https://hf.co/datasets/phanerozoic/qiskit-calibration-drift) | 30.1 M rows of IBM Heron calibration values (`backend.properties()` every 30 min, `is_failure_ceiling` flag, calibration age) joined with weather/space-weather data; updated daily | CC-BY-4.0 | Calibration history and staleness for W1 (choose the snapshot valid at a job's run time); no counts |
| — | `LightRiderInc/random-quantum-circuits`, `…/random-circuits-8q-rigetti` | 500 circuits each (QASM + JSON); tagged `synthetic`, the hardware only provided a random seed | CC-BY-4.0 | Circuit families only; no measured outputs |
| — | `merileijona/quantum-circuits-8k/21k`, `racineai/VDR_*`, `Neura-parse/*`, `Qiskit/qiskit_humaneval*` | text / code / image corpora for LLMs | various | not relevant |

`huggingface.co` is also denied by this environment's network policy for
direct downloads (the Hub API connector can read text excerpts only).

Contents of R-IO-* are taken from search-result snippets of the record pages;
they must be confirmed by downloading and reading the README before any use.
The datasets are not committed to the repository unless their licence permits
redistribution; otherwise tests download them by DOI/URL and pin SHA-256.

**Blocker B-NET (revised 2026-10-30):** the original blocker assumed no
real-I/O dataset was reachable. That is false for R-IO-5 and R-IO-6. R-IO-5 is
admitted and evaluated; its missing circuits/layout are a *dataset limitation*
(device-mean model, 14 unique reconstructible circuits), not a network blocker.
Full v3 Stable still needs at least one record with **complete circuits and a
published layout** at a width the exact noisy path can handle, or a validated
trajectory path for R-IO-6. R-IO-1 (Dryad payload 401) and R-IO-2/3 (Zenodo
403) remain blocked; R-IO-5 cannot carry the "close to real hardware" claim on
its own.

### Measured facts about R-CAL (drive the import design)

- 58 of 3676 qubits report `T2 > 2·T1` (physically impossible; fit artefacts).
- 1061 gate entries have `gate_error > (d−1)/d` — IBM marks non-operational
  gates/edges with `gate_error = 1`. Qiskit Aer silently clips such values.
- 1 qubit lacks T1/T2.
- Gate names present: `cx, cz, ecr, id, measure, measure_2, p, reset, reset_2,
  rx, rz, rzz, sx, u, u1, u2, u3, x`.

v2.5.2's `BackendProfile` refuses `T2 > 2·T1` outright, so a faithful import
cannot go through the current schema unchanged.

---

## 2. Workstreams

### W1 — Real-calibration import (schema 2.0)

- `BackendProfile.from_ibm_properties(props, conf, source)`; `source` records
  package name/version, file path inside the wheel and SHA-256 of the file.
  `is_synthetic=False`, `capture_timestamp=last_update_date`, per-entry dates
  preserved.
- Out-of-model data is **flagged, never clipped or dropped**:
  `non_operational` gates/edges (`gate_error ≥ (d−1)/d`), qubits whose T1/T2
  are inconsistent or missing (`relaxation_unusable`). A circuit that touches
  a flagged element is refused with a typed error naming it.
- The strict `T2 ≤ 2·T1` rule stays for hand-written profiles; imported
  profiles keep the raw values plus a flag (schema 2.0 adds `calibration_flags`).
- Tests: all 69 snapshots import or are refused with a typed reason; round-trip
  JSON; independent re-parse of the raw JSON in the test (no shared helper).

### W2 — Noise model parity with an independent implementation

- Add `ThermalRelaxationChannel(T1, T2, t)` (Kraus/Choi from the standard
  amplitude + phase damping composition) and Aer's "relaxation + depolarizing
  remainder" composition: `p = d (F_relax − F)/(d F_relax − 1)`.
- Readout from `prob_meas1_prep0` / `prob_meas0_prep1` (not the symmetric
  `readout_error`).
- **Acceptance (preregistered):** for every R-CAL backend with ≤ 7 qubits and
  for 5-qubit sub-layouts of larger ones, on the circuit families in §3,
  `TV(CQ-HECS noisy DM, Aer density_matrix with NoiseModel.from_backend) ≤ 1e-9`
  when both use the same transpiled circuit. Aer is the oracle; CQ-HECS must
  not import Aer at runtime.
- **Amendment (E-V3-02, after the first run):** the criterion above failed on
  ibmq_manila (TV 1.33e-9). Root cause: Aer's simulator drops noise terms with
  probability < 1e-10 and loses trace (1.328e-9 per `cx(0,1)`), while every
  channel agrees with Aer's own `QuantumError` to ≤ 1.6e-15 as a
  superoperator. The criterion is replaced, as a new experiment, by
  (a) channel parity `max|SuperOp diff| ≤ 1e-12` for every calibrated gate and
  (b) circuit parity `TV ≤ 1e-12 + (1 − trace of Aer's state)`.
  The original 1e-9 criterion is recorded as **not met** for manila.

### W3 — Basis translation and layout before noise

- Optional `transpile_to_profile(circuit, profile, seed)` (Qiskit transpiler,
  fixed seed) so that noise attaches to the gates the device would run.
  The result records the input hash, transpiled hash and layout.
- Without W3 the v2 behaviour stays: uncalibrated gates are noiseless, and the
  result says so.

### W4 — Real I/O reference harness (`cqhecs.reference`)

- Dataset adapters for R-IO-1/3 (Sycamore format) and R-IO-2 (CSV/JSON).
- Metrics, each with a bootstrap 95 % CI over shots:
  - linear XEB fidelity of the real samples (Sycamore definition) for R-IO-1/3;
  - TV and Hellinger distance between real counts and (a) the ideal
    distribution, (b) the CQ-HECS noisy prediction from the run-time
    calibration, for R-IO-2.
- **Preregistered hypothesis H-V3-1:** on held-out circuits, the noisy
  prediction is closer to the real counts than the ideal distribution
  (median paired difference of TV < 0, 95 % CI excluding 0).
  Rejection is a valid outcome and is reported; it blocks only the claim.
- No tuning of noise parameters on the evaluation set. Any fitted parameter
  is fitted on a disjoint split, recorded before evaluation.

### W5 — Gate set for real datasets

- Sycamore circuits need `fsim(θ, φ)`, `√X`, `√Y`, `√W` (and `phased_x`).
  Add them to the manifest with exact lowering or native kernels on the paths
  that can run them; differential tests against independent matrices.

### W6 — Result contract v3 (the breaking part)

- `SimulationResult.reference` block (dataset ID, DOI, file SHA-256, metric,
  CI); `BackendProfile` schema 2.0; `execution_mode` unchanged (real data is
  `REAL_HARDWARE` *source data*, the emulation stays `NOISY_CLASSICAL`).
- CLI: `cq-hecs profile import-ibm <backend>`, `cq-hecs reference run <dataset>`.
- Migration guide for schema 1.0 profiles (read-compatible; write 2.0).
- This schema change is what makes the release a major version.

### W8 — Noisy expectation values at scale (from the 2023–2025 literature)

Source: `research/v3/LITERATURE_MAP.md` §2 (Aharonov et al. 2023, Schuster et
al. 2025, Angrisani et al. 2025, Begušić et al. 2024; PDFs read).

- `cqhecs.noisy_expectation.noisy_expectation_values`: Pauli expectation
  values under a `NoiseModel` with two engines — exact density matrix
  (≤ 10 qubits) and Heisenberg Pauli propagation with the adjoint of every
  channel (unital and non-unital) and readout as an affine map on measured
  factors. `FakeHardwareBackend.expectation_values` adds the topology and
  calibration-flag checks.
- **Certified bound:** the discarded Pauli 1-norm. It remains a worst-case
  bound under noise because CPTP adjoints are unital and positive, hence
  operator-norm contractive (Russo–Dye). The literature's average-case
  guarantees are not claimed.
- **Acceptance (preregistered before the runs in E-V3-03):** both engines
  equal Aer within 1e-12 + Aer's trace loss on (a) channels built with Aer's
  constructors and (b) Aer's `NoiseModel.from_backend` on real calibration;
  truncated propagation never exceeds its reported bound against the exact
  density matrix; four mutants killed.
- **Not claimed:** speed-ups, typical-case efficiency, closeness to real
  hardware.

### W7 — Carry-overs

- CQ-V252-06: OpenQASM `gate` definitions (both parsers, shared category).
- Relaxation during idle periods (needs scheduling; deferred unless W2 needs it).

---

## 3. Preregistered circuit families (W2, W4)

Bell/GHZ (2–5 q), Clifford+T random (3–5 q, depth 10–40), QFT-3/4, mirror
circuits (should return the input), random SU(4) brickwork (4–5 q), and the
dataset's own circuits for W4. Seeds fixed in `research/v3/BENCHMARK_PROTOCOL.md`
before any run.

## 4. v3.0.0 Stable gates (in addition to GEMINI.md §15)

| Gate | Requirement |
|---|---|
| V3-A | W1: all 69 R-CAL snapshots import or are refused with a typed reason; zero silent clipping/dropping; flagged elements refuse circuits |
| V3-B | W2: Aer parity ≤ 1e-9 TV on the preregistered families |
| V3-C | W5: new gates differential-tested; mutation harness extended |
| V3-D | W4: ≥ 1 real I/O dataset downloaded, licence checked, SHA-256 pinned; metrics and H-V3-1 outcome recorded for the exact release SHA. **PARTIAL** — R-IO-5 admitted; pooled H-V3-1 `INCONCLUSIVE`; layout-aware dataset or trajectory path still needed for the full gate |
| V3-E | W6: schema 2.0 documented, migration tested, CLI/JSON contract tests |
| V3-F | CI 7/7 on the release SHA, release assets re-hashed, RELEASE_AUDIT |

**Release rule:** all of V3-A…F pass → `v3.0.0` Stable. If only the missing
layout-aware/trajectory evaluation blocks full V3-D, the additive parts may
ship as `v2.6.0` — never as v3 Stable and never with a "close to real hardware"
claim.

## 4a. Complexity boundaries that bind every v3 claim

- P vs NP is open; relativization, natural proofs and algebrization rule out
  whole classes of proof techniques. A simulator cannot "bridge" them, and no
  CQ-HECS text may suggest otherwise.
- BQP ⊄ PH relative to an oracle (Raz–Tal), #P-hardness of exact random-circuit
  probabilities (Bouland et al.) and the Ω̃(n²) stabilizer-rank lower bound
  (Mehraban–Tahmasbi) keep every exact path exponential in the worst case.
- Polynomial-time results for *noisy* circuits are average-case (over inputs
  or random circuits) and need constant noise per gate; CQ-HECS uses their
  mechanism (W8) but reports only per-instance worst-case bounds.

## 5. Order of work

1. Merge/release v2.5.2 (PR #17) — correctness first.
2. W1 → W2 (no network needed beyond PyPI).
3. W5 → W3.
4. W4 once B-NET is lifted.
5. W6, docs, gates, release.

## 6. Progress log

| Item | Status | Evidence |
|---|---|---|
| v2.5.2 | RELEASED, assets re-hashed | `research/v2_5_2/RELEASE_AUDIT.md` |
| W1 import | DONE (local) | `cqhecs/calibration_import.py`; all 68 shipped snapshots import (qiskit-ibm-runtime 0.51.0): 1049 non-operational gate entries and 59 relaxation-excluded qubits flagged, 0 clipped; `tests/test_v3_calibration_bridge.py` |
| W2 relaxation + Aer parity | DONE (local), amended criterion | channel parity ≤ 1.6e-15 (manila); circuit parity ≤ 1e-12 + Aer trace loss on manila/quito/lagos; preregistered 1e-9 not met on manila (Aer trace loss) |
| W3 basis translation | NOT STARTED | — |
| W4 real I/O | **PARTIAL** (R-IO-5 evaluated; R-IO-1/2/3 blocked) | `cqhecs/reference.py`, `scripts/run_reference_evaluation.py`, `tests/test_reference.py`; 14 unique circuits, median ΔTV −0.015660, 95 % CI [−0.032546, 0.000000], pooled `INCONCLUSIVE`; Bell+GHZ exploratory `SUPPORTED`; `research/v3/evidence/r_io_5_evaluation.json` |
| W5 Sycamore gates | NOT STARTED | — |
| W6 contract/CLI | PARTIAL | schema 2.0 profile fields; `reference list/run` CLI and JSON contract added; migration guide still missing |
| W8 noisy expectation values | DONE (local) | both engines = Aer to ≤ 1e-12 + trace loss (channels from Aer constructors; Aer `from_backend` on manila/lagos); truncated bound never violated (25 circuits); 127-qubit ibm_brisbane calibration, ~4000 gates: < 1.2 s, bound ≈ 1e-4 (functional check, not a benchmark); mutants 28–31 killed |
| Datasets | R-IO-5 admitted; R-IO-6 registered; R-IO-1/2/3 blocked | `research/v3/DATASETS.md` |
| Research: P vs NP / complexity | DONE (boundary only) | `LITERATURE_MAP.md` §1, `COMPLEXITY_BOUNDARY.md`: no proof; the item is `BLOCKED — open problem` |
