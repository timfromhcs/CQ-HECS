# CQ-HECS v3 Execution Log

All times 2026-10-30 (UTC).

## E-V3-00 Data search

Searched for complete public real-QPU input/output records. Candidates and
their reachability from this environment are in V3_STABLE_PLAN.md §1. Every
host that serves real circuit + raw-count datasets (zenodo.org,
datadryad.org, ieee-dataport.org, figshare, OSF, data.caltech.edu, gitee) is
denied by the session's network policy (proxy `connect_rejected`); the
web-fetch agent got DNS failures for the same hosts. PyPI and
raw.githubusercontent.com are reachable. The `qiskit-ibm-runtime` 0.51.0
wheel ships 69 `props_*.json` files (68 backends + `props_cambridge_alt`),
which are real IBM calibration exports. No repository on a reachable host
was found that commits real raw counts.

## E-V3-01 Real calibration import (W1)

- Scan of all snapshots: 3676 qubits; 58 with T2 > 2·T1; 1061 gate entries
  with gate_error above the depolarizing maximum (IBM's 1.0 sentinel);
  1 qubit without T1/T2.
- Importer flags these instead of clipping them. Result: 68/68 import and
  build noise models with and without relaxation. `armonk` (1 qubit) reports
  `coupling_map: null`, handled as no edges (first attempt raised TypeError).
- Fixtures: manila, oslo, algiers (Apache-2.0, NOTICE + SHA256SUMS).

## E-V3-02 Aer parity (W2)

- First run against `NoiseModel.from_backend(FakeXxxV2())` +
  `AerSimulator(method="density_matrix")`: quito 4.1e-15, lagos 2.4e-15,
  manila **1.33e-9** (preregistered bound 1e-9 → not met).
- Disabling Aer fusion and `zero_threshold` changed nothing. Per-channel
  comparison (SuperOp of Aer's `QuantumError` vs ours): ≤ 1.6e-15 for every
  gate. Prefix scan: each `cx(0,1)` reduces the trace of Aer's state by
  exactly 1.328e-9; our state stays trace-1. Aer's `cx(0,1)` error has 15 of
  144 terms with probability < 1e-10 summing to 1.3280e-9, i.e. Aer's
  simulator drops them. Not a CQ-HECS defect.
- Amended criterion (V3_STABLE_PLAN.md W2): channel parity ≤ 1e-12, circuit
  parity ≤ 1e-12 + Aer's trace loss. Passes on manila, quito, lagos.
- Readout: Aer's BackendV2 path uses the symmetric `readout_error`; the raw
  data has asymmetric `prob_meas*`. Importer default is asymmetric;
  `readout="symmetric"` reproduces Aer.
- Order matters: Aer applies depolarizing then relaxation. A mutant with the
  reverse order survived its first check because the chosen parameters gave
  p = 0 (relaxation alone exceeded the error); the check now uses p > 0.

## E-V3-03 Literature and W8 (noisy expectation values)

- Web search (P vs NP barriers, Williams 2025, Raz–Tal, RCS hardness,
  stabilizer-rank bounds, Pauli propagation under noise, sparse Pauli
  dynamics, BP tensor networks, Quantum Echoes) and PDF reading of
  arXiv:2211.03999, 2407.12768, 2501.13101, 2308.05077 and Aaronson's survey
  (pages listed in LITERATURE_MAP.md). arXiv is blocked locally; the hosted
  PDF reader worked.
- Acceptance for W8 written into V3_STABLE_PLAN.md before the oracle runs.
- First oracle run (Aer full pipeline, manila/lagos, X/Y/Z observables,
  readout, T1/T2): both engines within 1e-15 after Aer's trace loss; truncated
  propagation inside its bound.
- Three own mistakes caught before testing: lowered instead of source gates
  passed to the density matrix (would repeat CQ-V251-04), dead code, and the
  phase of the XZ factor in the readout map (−i, not +i).
- One test-construction error: Qiskit's `a.tensor(b)` puts `b` on the first
  qarg; the asymmetric two-qubit oracle channel had its factors reversed
  (failures only in trials containing that gate; channel check confirmed).
- 127-qubit functional check on the real ibm_brisbane snapshot (excluding
  flagged qubits): 2/4/6 kicked layers (1335/2669/4003 gates), thresholds
  1e-3 and 1e-4: 0.6–1.2 s, bounds 1.7e-3…1.1e-4. Light cones are small in
  this circuit; this is not a performance result.
- Mutants 28–31 (readout phase, skipped channels, swapped two-qubit operands,
  bound suppression) killed: 31/31.

## E-V3-04 Real I/O, dataset expansion and H-V3-1 (2026-10-30)

- Re-tested the network boundary from this environment. `huggingface.co` and
  `raw.githubusercontent.com` are reachable; `datadryad.org` serves metadata
  (`/api/v2/...` 200) but file payloads return 401 (bearer token required) and
  `stash/downloads/file_stream` returns 403; `zenodo.org` returns 403
  (Cloudflare) for API and record pages. B-NET is therefore **partial**, not
  total.
- Admitted R-IO-5 (Quantum Noise Transfer, MIT): 5 raw JSON files vendored
  under `tests/data/quantum_noise_transfer/` with SHA-256 pins; combined
  digest `8069ad5025d34ee18e8e8005b9e3381175328e76c19d2f7608ed54a5bd2012a3`.
  Verified 170 real executions (85 per backend), 2-5 qubits, 1024 shots each.
- Registered R-IO-6 (BlueQubit `rcs-nighthawk`, Apache-2.0, revision
  `b9dd86b`): 233 QASM/QPY circuits, 61 logical qubits, raw bitstrings and
  mirror survival counts. Four small files pinned; not evaluated because the
  smallest patched circuit is 20 qubits, above the exact density-matrix ceiling.
- Corrected the dataset reading: the upstream README says 8192 shots but every
  `raw_counts` block sums to 1024. The harness uses the raw counts.
- Implemented `cqhecs/reference.py`: registry + SHA-256 verification, Bell/GHZ/
  QFT reconstruction, device-mean calibration, unital-noise model, TV metric,
  two-level bootstrap, typed failures. Added `cq-hecs reference list|run` and
  `scripts/run_reference_evaluation.py`.
- Preregistered H-V3-1 (pooled unique circuits, median paired ?TV, 95 % CI).
  Result on 14 unique circuits: median ?TV = -0.015660, CI
  [-0.032546, 0.000000], **INCONCLUSIVE**. Bell (n=2) and GHZ (n=6) are
  negative with CIs excluding 0; QFT (n=6) is exactly 0 because QFT on
  `|0...0>` is maximally mixed and the model is unital (H-V3-2).
- Exploratory (not preregistered): Bell+GHZ n=8, median ?TV = -0.031797,
  CI [-0.054182, -0.017122], 8/8 better.
- Added 28 tests (`tests/test_reference.py`, `tests/test_cli_reference.py`):
  registry, integrity/corruption, reconstruction, model, metrics, evaluation
  contract, CLI JSON. Full suite and gates recorded in TEST_MATRIX.md.
- Added `research/v3/DATASETS.md`, `HYPOTHESES.md` and
  `COMPLEXITY_BOUNDARY.md`. The P versus NP item remains `BLOCKED � open
  problem`; no proof is claimed.
- Local baseline note: the checked-out tree initially failed 12 tests because
  `build/bin/Release/cq_hecs.dll` was still the 2.5.0 build (CLI reported
  2.5.0, Path A SWAP trials failed). `cmake --build build --config Release`
  rebuilt the 2.5.2 native library; the 12 failures disappeared. This is a
  stale-artifact issue, not a source regression.
- Gates after the change: flake8 E9/F clean; version consistency 2.5.2;
  silent-truncation audit PASS; pytest 540 passed / 4 skipped; coverage 88 %;
  mutation 33/33; CTest 19/19.

## E-V3-05 Metamorphic / property-based testing (2026-10-30)

- Web research: QuCheck (arXiv:2503.22641), FuzzQ (OOPSLA 2025,
  DOI 10.1145/3763100), noise-aware property-based testing (2025), QuteFuzz
  (POPL 2025) and metamorphic testing for quantum programs (arXiv:2208.09206).
  The transfer map is `TESTING_TECHNIQUES.md`.
- Exploratory fuzzing before codifying properties:
  - dense vs exact MPS statevector: 300 circuits (2-6 qubits), 0 mismatches
    after accounting for the documented chain-order endianness;
  - composite-gate lowering vs Qiskit `Statevector`: 200 circuits, 0 mismatches;
  - dense expectation vs `sparse_pauli`/`auto`: 300 circuits, 0 mismatches on
    Path-D gates; typed refusals for `cp/crx/cry/crz` are expected capabilities;
  - noisy density matrix under qubit permutation: 100 circuits with random 1q/2q
    depolarizing and asymmetric readout, 0 mismatches;
  - MPS finite-shot marginals: 30 circuits x 200k shots, ordered and permuted
    measurement order, all within the Hoeffding bound.
- Implemented `cqhecs/selftest.py` (12 metamorphic checks, deterministic seed,
  Bonferroni-corrected Hoeffding bound) and `cq-hecs selftest`. The noise checks
  cover permutation equivariance of the noisy density matrix, zero-noise
  identity, and `ComposedChannel(A,B) = B o A`.
- Added `tests/test_selftest.py` (8 tests) and
  `tests/test_property_circuits.py` (4 Hypothesis tests, shrinking enabled).
- No new defect was found. This is a negative result, not a correctness proof.
- Mutation harness extended with mutant 34 (selftest inverse relation skipped)
  and mutant 35 (ComposedChannel order reversed): 35/35 killed.

## E-V3-06 Own real-QPU suite via Open Quantum (2026-10-30)

- Goal: a real input/output record with complete circuits for V3-D, without
  depending on third-party datasets.
- Built `cqhecs/openquantum_suite.py` (25 circuits, seed 20261030, 5 FIT /
  20 EVAL), `scripts/run_openquantum_suite.py` (quote → submit → collect →
  evaluate via the Open Quantum skill's `oq.py`) and
  `tests/test_openquantum_suite.py` (15 tests).
- Every ideal distribution equals Qiskit `Statevector` to ≤ 1e-12. A first
  draft of the QPE circuits did not give a deterministic outcome; the inverse
  QFT ordering was fixed before the manifest was written.
- Synthetic round trip (counts sampled from a known model, test-only):
  `M-FIT` recovers `p = 0.04`, `p01 = 0.02`, `p10 = 0.05` within 0.01; changing
  an EVAL result does not change the fit; tampered QASM, wrong width, reversed
  bit order and a missing FIT job are refused.
- **Blocked:** `oq.py doctor` from the cloud session: all three Open Quantum
  hosts fail with a proxy `403` on `CONNECT`. No job was quoted or submitted
  and no credit was spent. H-V3-8 stays `PREREGISTERED, NOT RUN`.

## E-V3-06b r-io-7 results (2026-10-30)

- 25/25 jobs completed on `rigetti:cepheus-1-108q` (submitted from a machine
  with Open Quantum access, not from the cloud session). Reproduced offline
  here: `cq-hecs reference run --dataset r-io-7` gives the committed model
  exactly and the aggregate up to the last floating-point digit. H-V3-8
  `SUPPORTED`. No Open Quantum credential is present in the repository
  (`git grep` for the key prefixes: no hit).

## E-V3-07 Per-qubit noise fit, M-FIT-2 (2026-10-30, post-hoc)

- Implemented `cqhecs/noise_fit.py` and `cq-hecs noise-fit` (EMULATOR_BUILD_PLAN
  W1/W3/W4/W5) and `tests/test_noise_fit.py` (10 tests).
- W3: per-qubit readout through the density-matrix path equals the analytic
  product on GHZ-5 to 1e-12.
- Exploratory score on the 20 EVAL jobs: worse than the frozen M-FIT (median
  ΔTV +0.055345, CI [−0.006595, +0.091789]). Root cause from the raw counts:
  the qubit-0 readout defect (OQ-02: 404/1000 `11110`) is absent in the GHZ
  jobs (15–24/1000), i.e. a different physical layout. H-V3-9 rejected.
