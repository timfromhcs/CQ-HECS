# CQ-HECS v2.5.2 Findings

All findings were reproduced on baseline `1be682a` before any change. Each has
a regression test with an oracle independent of the code under test.

| ID | Severity | Defect | Reproduction | Root cause | Fix | Regression | Status |
|---|---|---|---|---|---|---|---|
| **CQ-V252-01** | P0 | Path B returned wrong probabilities, labelled `EXACT`, for circuits combining `t`/`tdg` with other phases. | `h t s h` on Path B → `P(0)=0.854`; Path C, Qiskit and the closed form `(1+cos 3π/4)/2` give `0.146`. Also with the published v2.5.1 wheel. Found by a seeded differential fuzz (router, A–D, noisy DM vs Qiskit `Statevector`, 600 random circuits). | `T = c0 I + c1 Z` with `c1 = (w − 1)/2` gives `diag(w, 1)` (`w = e^{iπ/4}`), i.e. `T†` up to global phase; same for `tdg`. Symmetric circuits (`h t h`, `t t t`) are invariant under `T ↔ T†`, so the existing Aer/Stim differential tests passed. | `c1 = (1 − w)/2` (`c0 + c1 = 1`, `c0 − c1 = w`). | `TestPathBTGateSign` (closed forms + 25 random Clifford+T circuits vs Qiskit); mutant 21. | RESOLVED (local); cloud gates in TEST_MATRIX.md |
| **CQ-V252-02** | P1 | Noise model used the reported gate error as depolarizing parameter. | `create_fake_manila_profile().to_noise_model()`: `sx` error 0.00025 → channel infidelity 0.000125; `cx` 0.0071 → 0.005325 (`qiskit.quantum_info.average_gate_fidelity`). | `to_target()` exports the value as Qiskit `InstructionProperties.error` ("average error rate", i.e. `1 − F_avg`), but `to_noise_model()` passed it to `DepolarizingChannel(p)`, whose infidelity is `p (d−1)/d`. Metric conflation (GEMINI.md §6.4). | `depolarizing_parameter_from_infidelity`: `p = d r/(d−1)` (Nielsen 2002; matches Qiskit Aer `_device_depolarizing_error` without relaxation). `r > (d−1)/d` is refused (Aer clips silently). | `TestGateErrorIsInfidelity`; mutant 22. | RESOLVED (local) |
| **CQ-V252-03** | P0 (native builds) | `swap` was the identity on Path A's native engine and in the C API while the engine is in tableau mode. | `x q0; swap q0,q1` on Path A with `_cqhecs_core` built → `01` (should be `10`); seeded fuzz: router/Path A TV = 1. | `HybridEngine::apply_swap` called `tableau.apply_swap` and then `HybridEngine::apply_cx` three times, which again acts on the tableau. | Shadow statevector updated through `statevector.apply_cx` only; `q1 == q2` is a no-op. | `test_swap_in_tableau_mode` (C++; fails on the v2.5.1 build), `TestPathASwap` (Python; detects it when the native module is loaded). No source mutant: the harness patches Python only. | RESOLVED (local) |
| **CQ-V252-04** | P2 | `BackendProfile` accepted invalid data. | Accepted: `t1_us={99: 1.0}` on 3 qubits, `T2 = 50 > 2·T1 = 20`, `coupling_map=[(0.9, 1)]` (truncated by `int()`), `[(True, 0)]`, `t1 = inf`, `gate_errors={"sx": {(0,1,2): 0.1}}` and `{"cx": {(0,): 0.1}}` (both silently dropped or never firing in the noise model), `{"cx": {(0, 0): 0.1}}`; a string error raised `TypeError`. | Validation checked ranges only, with `int()` coercion and no key checks. | Typed index checks, range checks for every table, `T2 ≤ 2 T1`, finite durations, key width must be 1 or 2 and match the manifest arity. | `TestProfileValidation` (20 invalid cases); mutants 23, 24. | RESOLVED (local) |
| **CQ-V252-05** | P3 | Noisy DM refused `cu1`, `crx`, `cry`, `crz`, which the router executes. | `NoisyDensityMatrixBackend().simulate([("crz",[0,1],[0.3])])` → `FAILED`. | Gate table incomplete (fail-closed, not a wrong result). | Controlled-rotation matrices `diag(I, R)`. | `TestNoisyDMControlledRotations` vs Qiskit `DensityMatrix`, both operand orders. | RESOLVED (local) |
| **CQ-V252-06** | P3 (diagnostic) | A QASM `gate` definition (as emitted by `qiskit.qasm2.dumps` for non-qelib1 gates) is refused with category `missing_semicolon`, which hides the real reason. | 116 of 200 fuzzed circuits exported with `qasm2.dumps`. | Line-level `;` check runs before statement dispatch. | Not changed: the refusal is fail-closed and the category set is shared with the native parser (docs/QASM_CONTRACT.md); changing it needs a coordinated change of both parsers. | — | DEFERRED |
| **CQ-V252-07** | Docs | README said "zuletzt veröffentlicht: v2.5.0" after v2.5.1 was published; the v2.5.1 release audit was not on `main`. | README line 335; branch listing. | Docs written before the release. | README updated; audit commit cherry-picked. | Doc review | RESOLVED |

## Checked and not defective

- Path C, Path D (`expectation_values`, all methods), dense reference and the
  noisy DM agree with Qiskit on the same fuzzed circuits (0 mismatches over
  200 random expectation-value cases, 600 distribution cases after the fixes;
  one Path C/router TV excursion of 0.0225 vs a δ = 0.05 Hoeffding bound of
  0.0215 is the expected rate of a 95 % bound, not a defect: Path C and the
  router produced identical counts from identical probabilities).
- Instruction list, Qiskit `QuantumCircuit` and OpenQASM 2 input give
  identical counts on Path C for every circuit the QASM parser accepts.
- The C-ABI `cq_execute_qasm` switch has `default: break`, but its parser only
  emits gates the engine implements, so no unitary gate can reach it.
