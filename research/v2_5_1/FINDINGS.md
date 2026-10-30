# CQ-HECS v2.5.1 Findings

All findings were reproduced on baseline `a94ffb8` before any change. Each has
a regression test that fails on the baseline and passes on the fix.

| ID | Severity | Defect | Reproduction | Fix | Regression | Status |
|---|---|---|---|---|---|---|
| **CQ-V251-01** | P0 | `NoisyDensityMatrixBackend` flattened ρ with qubit 0 as the most-significant bit, so every bitstring was mirrored; readout errors were applied to the mirrored bit. | `x q[0]; measure q -> c;` → router `{"01"}`, `--profile fake_manila --no-noisy` `{"10"}`. Also reproduced with the **published v2.5.0 wheel** in a clean venv. | Reverse qubit axes before flattening; readout Kronecker order then matches qubit 0 = LSB. | `TestBitOrderAndMeasurement`, `TestDifferentialAgainstIndependentOracle`, `TestCliProfileAgreesWithRouter`; mutant 17. | RESOLVED (local); cloud gates pending |
| **CQ-V251-02** | P1 | Measurements ignored: all qubits always reported; a mid-circuit `measure` in an instruction list was silently dropped. | `QuantumCircuit(2,1); x(1); measure(0,0)` → `{"01": 1024}` (router: `{"0": 1024}`); `[measure q0, x q0]` → `EXACT {"1"}`. | Report terminal-measured qubits only (router convention); refuse mid-circuit measurement (`barrier`/`id` do not count as state-changing, as in `CircuitAnalyzer`). | `test_partial_measurement_*`, `test_mid_circuit_measurement_is_refused`; mutant 18. | RESOLVED (local) |
| **CQ-V251-03** | P0 | `fake_manila` labelled `is_synthetic=False`, provider `IBM_Quantum_Snapshot`, timestamp `2026-10-29T12:00:00Z`, URI `…/qiskit-ibm-runtime/fake_manila`; its values do not match IBM's data (e.g. T1 q0 165.2 vs 131.53 µs; CX(0,1) error 0.0071 vs 0.00883 in `props_manila.json` of qiskit-ibm-runtime 0.40.1, `last_update_date` 2024-05-27). | Read the profile; compared with `props_manila.json`. | Mark synthetic, drop timestamp/URI; `BackendProfile` refuses `is_synthetic=False` without `capture_timestamp` and `provenance_uri`. The existing test that asserted `is_synthetic is False` encoded the false claim and was corrected. | `test_backend_profile_valid`, `TestProfileProvenance`; mutant 20. | RESOLVED (local) |
| **CQ-V251-04** | P1 | Gates were lowered before noise lookup: `sx` → `h s h`, so a channel on `sx` never fired and `h` noise fired twice per `sx`; same for `u`, `u3`, etc. | Random differential test against Aer channels deviated by up to 0.057 in probability. | New `parse_source_circuit()`; each source instruction is lowered on its own and its noise applied after its block (Aer semantics). | Differential test; mutant 19. | RESOLVED (local) |
| **CQ-V251-05** | P2 | Input validation: `shots=True/2.5` accepted (truncated), `shots=-1` leaked NumPy `ValueError("n < 0")`, `seed=None` gave nondeterministic counts; `rx` without angle evaluated as identity; `u` with wrong arity → identity; unknown ops with ≥3 qubits skipped silently; `max_qubits` unchecked. | `simulate([("rx",[0],[])])` → `EXACT {"0": 1.0}`. | Router-equivalent `shots`/`seed` checks before parsing; per-gate parameter arity; full validation before allocation; `max_qubits` positive int. | `TestArgumentValidation`. | RESOLVED (local) |
| **CQ-V251-06** | P2 (docs) | `RELEASE_NOTES.md` (and the published `RELEASE_NOTES_v2.5.0.md` asset) describe v2.4.0 under a 2.5.0 header; `research/v2_5/RELEASE_AUDIT.md` cites candidate SHA `f97249a888c3a504ef51590fcbf61f3640b39678`, which does not exist (real: `f97249a1c4ad5c5abfc70985fb6b6833072c0365`). README pointed to `research/v2_2/` and said "published: v2.3.0". | `git rev-parse f97249a`; GitHub PR #14 head SHA. | New RELEASE_NOTES for 2.5.1; erratum appended to the v2.5 audit (historical text kept); README updated. Published v2.5.0 asset cannot be changed without rewriting a release — left as is and documented. | Doc review | RESOLVED (repo); published asset unchanged by design |
| **CQ-V251-07** | P3 | CLI: unknown `--profile` → traceback and exit 1; topology violation → exit 1 with traceback in log. | `cq-hecs run x.qasm --profile nope`. | `KeyError` → usage error; `HardwareBridgeError` handled as usage error (exit 2, JSON `error`). | `test_unknown_profile_is_a_usage_error`. | RESOLVED (local) |

## Not changed (documented limitations)

- `FakeHardwareBackend` does not transpile to the profile's basis gates;
  uncalibrated gates are noiseless. Documented in README, USAGE_GUIDE and the
  release notes rather than implemented (would be a new feature).
- `error_bound = 0.0` on `NOISY_CLASSICAL` results means "no deliberate
  approximation of the model", not a bound on model-vs-hardware error.
- Two-qubit noise is keyed by ordered pair; a channel on `(0, 1)` does not fire
  for `cx(1, 0)`. This matches the profile's directed `gate_errors`.
