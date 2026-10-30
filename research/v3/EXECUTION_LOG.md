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
