# CQ-HECS v3 real-data registry (2026-10-30)

This file records what was actually reachable and usable from the build
environment, not what a search result claimed. Every admitted file is pinned by
SHA-256. A dataset that is registered but not vendored is marked as such; it is
never silently substituted by synthetic data.

## 1. Admitted records

### R-CAL — IBM calibration snapshots (already used by W1/W2)

| field | value |
|---|---|
| source | `qiskit-ibm-runtime` 0.51.0 wheel, `fake_provider/backends/*/props_*.json` + `conf_*.json` |
| content | 69 snapshots (68 backends plus `props_cambridge_alt`), 3676 qubits, per-qubit T1/T2/readout/frequency, per-gate error/duration, coupling map |
| licence | Apache-2.0 |
| reachability | PyPI (verified) |
| use | schema-2.0 profiles, Aer parity, noise models |

### R-IO-5 — Quantum Noise Transfer (real counts)

| field | value |
|---|---|
| source | <https://huggingface.co/datasets/sahilfarib/quantum-noise-transfer> |
| paper | arXiv:2604.24397 |
| content | 170 real executions on `ibm_fez` and `ibm_marrakesh` (85 each), 2–5 qubits, raw counts, run-time calibration snapshots |
| licence | MIT (dataset card) |
| reachability | **yes** on 2026-10-30 (Hub API and `resolve/main` downloads) |
| vendored | `tests/data/quantum_noise_transfer/` (5 files, 179 923 bytes) |
| pinned | `tests/data/quantum_noise_transfer/SHA256SUMS`; combined digest `8069ad50…12a3` |

Limitations that are part of the record:

* the upstream README says 8192 shots, but every `raw_counts` block sums to
  1024; the harness uses the raw counts and records the mismatch;
* circuits are not published, only family/width/depth/gate counts. Bell, GHZ
  and QFT are reconstructed from their standard definitions; the 40 random
  circuits are excluded;
* the physical layout is not published, so the evaluation uses a device-mean
  noise model (median CX error, median symmetric readout) rather than a
  per-circuit layout;
* QFT is applied to the zero state in the published family, so its ideal
  output is maximally mixed. Any unital channel leaves it invariant; this makes
  six of the fourteen unique circuits structurally uninformative for a
  unital-noise comparison (recorded, not hidden).

### R-IO-6 — BlueQubit `rcs-nighthawk` (real circuits and bitstrings)

| field | value |
|---|---|
| source | <https://github.com/BlueQubitDev/rcs-nighthawk> |
| revision | `b9dd86b016743465ebc97fb9f6677f4a251a3baa` (2026-09-23) |
| content | 233 QASM/QPY circuits (4–40 cycles), 61 logical qubits of `ibm_phoenix`, raw patched bitstrings, a 10^6-shot 36-cycle sample, mirror survival counts, layout |
| licence | Apache-2.0 |
| reachability | **yes** on 2026-10-30 (`raw.githubusercontent.com`) |
| pinned | `data/layout.json`, `data/circuits/manifest.json`, `data/counts/mirror_survival.json`, `data/results/patch_xeb.json` (digests in `cqhecs/reference.py`) |
| use here | registered; not evaluated by W4 because exact density matrices stop at 10 qubits and the smallest patched circuit is 20 qubits |

### R-IO-7 — own Open Quantum suite (preregistered, not run)

| field | value |
|---|---|
| source | jobs authored here and submitted through Open Quantum (IonQ, Rigetti, IQM, AQT) |
| circuits | 25 OpenQASM 2.0 files, SHA-256-pinned in `research/v3/openquantum_suite/manifest.json` |
| licence | results belong to the submitter; Public-plan results must cite Open Quantum |
| reachability | **no** from the cloud session on 2026-10-30: `id`/`scheduler`/`management.openquantum.com` → proxy `403` |
| use here | `cqhecs.openquantum_suite`, `scripts/run_openquantum_suite.py`, `cq-hecs reference run --dataset r-io-7`; protocol in `OPENQUANTUM_RUN_PLAN.md` |

## 2. Reachable metadata, blocked payloads

| record | status | why it is not used |
|---|---|---|
| R-IO-1 Sycamore 2019, Dryad `doi:10.5061/dryad.k6t1rj8` | metadata API 200; file downloads **401** (“must have current bearer token”); `stash/downloads/file_stream` 403 | complete circuits + counts exist (CC0, 37 files, 2.36 GB), but no unauthenticated payload access from this environment. `n12_m14.tar.gz` is 169.9 MB. |
| R-IO-2 Zenodo 3832121 / 3832120 | **403** (Cloudflare) for API and record pages | closest fit for the profile bridge (counts + calibration), but unreachable |
| R-IO-3 Zenodo 11663206 | **403** | second RCS reference, unreachable |
| R-IO-4 IEEE DataPort | not reachable | login wall |
| R-CAL-2 `phanerozoic/qiskit-calibration-drift` | reachable metadata | calibration history only, no counts |

## 3. Rejected candidates

| candidate | why rejected |
|---|---|
| `sahilfarib/quantum-noise-transfer` random circuits | gate *counts* only; no gate sequence, angles or layout, so they are not reconstructible |
| `LightRiderInc/random-quantum-circuits` | circuits only, tagged synthetic; no measured outputs |
| GitHub code-search hits with `ibm_fez` counts (e.g. `anulum/scpn-quantum-control`) | no peer-reviewed provenance, inconsistent schemas; not admitted without an independent record |

## 4. Reproduction

```bash
# verify the vendored files and run the preregistered evaluation
python scripts/run_reference_evaluation.py --bootstrap 5000

# JSON contract
cq-hecs --format json reference list
cq-hecs --format json reference run --bootstrap 5000
```

The harness refuses missing, wrong-size or wrong-hash files. It does not
download in tests and does not tune the noise model on the evaluation counts.
