# CQ-HECS Release Notes

**Version:** 2.2.2
**Release date:** 2026-10-27
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.2.2.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.2.2` is a **patch release** on top of `v2.2.1`. It removes false-success
behaviour from the native reference and legacy surfaces, fixes two Path C
two-qubit operand-order defects, hardens Path C resource accounting and the
strict input parsers, and updates CI to current pinned actions. It adds **no new
simulator, no new exactness claim and no GPU acceleration**.

The supported Python package keeps the same four-path interface. Existing
`2.2.x` result metadata remains compatible; the new refusal paths raise typed
errors or return `UNRESOLVED` instead of fabricating output.

| Surface | Status in 2.2.2 |
| :--- | :--- |
| `cqhecs` four-path router/backends | supported |
| `cq_hecs::core::StateVectorSimulator` | supported dense reference, ≤ 28 qubits |
| `cq_hecs::core::MPSSimulator` | experimental CPU reference with SVD updates and seeded sampling |
| `cq_hecs::core::VulkanQpuEngine` | CPU reference facade; no Vulkan dispatch; QASM operands limited to qubits 0–255 |
| `cqhecs::vulkan::VulkanEngine` | planner-only memory allocator |
| `VRTS300Engine` | legacy diagnostic for a validated fully correlated GHZ-like state |
| Legacy native QASM executor | legacy phase ledger, not a statevector simulator |

## 2. Fixed

### Native false-success engine contracts

- `cqhecs::vulkan::VulkanEngine` previously accepted gate calls and returned
  without storing amplitudes, and `sample_fast_shots()` returned uniform random
  bits. It is now explicitly **planner-only**: gate and sampling methods throw,
  invalid qubit indices throw, and `truncate_bond()` is documented as a metadata
  adjustment. Use `cq_hecs::core::MPSSimulator`,
  `cq_hecs::core::StateVectorSimulator` or the Python four-path router for
  actual state evolution.
- `VRTS300Engine::measure_parity_shots(num_shots, seed)` now validates that all
  300 sites carry the same amplitude pair and entanglement flag, then draws
  seeded independent shots from the stored distribution. It throws for
  arbitrary states instead of forcing an exact 50/50 split. The GHZ test is now
  a correlation diagnostic with a derived binomial acceptance band.

### Statevector and MPS reference paths

- `StateVectorSimulator` implements seeded Born-rule `sample_counts(shots,
  seed)`, collapsing `measure(target, rng)`, width validation before any shift
  (`MAX_SUPPORTED_QUBITS = 28`), per-gate index validation and `apply_y`.
  Probabilities are evaluated in double precision from the stored Q1.31
  amplitudes; that conversion is documented instead of hidden.
- `MPSSimulator` performs correct two-site CNOT updates with a complex SVD,
  supports both control/target orders, routes non-adjacent CNOTs through exact
  adjacent SWAPs and restores the ordering, samples arbitrary states through
  right environments, and selects its GHZ fast path only after an exact tensor
  check. Truncation keeps the largest singular values, records discarded weight
  as a diagnostic, and rescales retained local tensors so the fixed-point rank
  does not collapse. The discarded weight is **not** a certified propagated
  error bound.
- `VulkanQpuEngine` no longer fabricates indirect-dispatch metadata. Every
  supported opcode is dispatched to real CPU state evolution; unsupported
  opcodes throw. `MEASURE` is terminal, and a gate after measurement is
  rejected as unsupported mid-circuit measurement. `sample_counts(shots, seed)`
  delegates to the active backend sampler.

### Path C two-qubit operand order (CQ-01 / CQ-01b)

- `ExactMPSTensorChain.apply_two_qubit_gate()` applied the `q1 > q2` branch with
  the gate's output axes swapped but its input axes left in chain order. The
  contraction is now `abcd,ldcp->lbap`, which preserves the gate operand order
  on both sides.
- `PathCMPSExactBackend` passed raw Qiskit little-endian matrices (and `crx`,
  `cry` and `crz` matrices on the wrong basis block) to a chain expecting
  operand-ordered axes. All two-qubit matrices are now canonical little-endian
  and are converted at the chain boundary by `_chain_two_qubit_matrix()`
  (transpose `(1,0,3,2)`).
- Regression coverage executes CX, CZ, SWAP, CP, CU1, CRX, CRY and CRZ in both
  operand orders, including non-adjacent gates, against Qiskit `Statevector`.
  The backend-level CRX/CRY/CRZ cases match at fidelity 1.0.

### Path C resources and paging (CQ-02 / CQ-10)

- `ram_budget_mb` and `max_storage_mb` are validated as finite, positive and
  bounded before conversion to bytes. `num_qubits` and `shots` are validated
  before any allocation.
- Two-site updates run a preflight that covers the contract/evolve matrices, the
  worst-case SVD outputs and a documented SVD workspace multiplier. The estimate
  is reported in `last_preflight`/result metadata; it is an estimate, not an
  allocator measurement.
- Sampling checks the bytes needed to rehydrate paged sites **before** loading
  them and refuses fail-closed when the RAM budget would be exceeded.
- Missing, truncated or malformed swap pages raise `MPSResourceError` and are
  surfaced as `UNRESOLVED`; they never become silent `None` sites or partial
  results.
- Added `MAX_MPS_QUBITS = 4096` and `MAX_SHOTS = 10_000_000`. Path A and Path D
  use the same 4096-qubit ceiling; Path B uses its 22-qubit dense-statevector
  ceiling. All paths enforce the shot ceiling before execution.

### Input and measurement contracts (CQ-03 / CQ-04)

- Direct `parse_circuit()` accepts only terminal identity measurements
  (`measure q[i] -> c[i]`). A Qiskit circuit that maps a qubit to a different
  classical bit is rejected with a message pointing to `CQHecsBackend`, which
  preserves arbitrary `(qubit, clbit)` layouts via
  `_normalize_measurements()`/`_pad_counts()`.
- Terminal measurements are normalised once (sorted ascending, exact duplicates
  removed) so the lowest measured qubit is rightmost in every backend. A
  mid-circuit measurement stays in place.
- Instruction-list indices accept only `numbers.Integral` and reject `bool`,
  floats, strings, complex values, NaN/inf, negatives and indices `>= 1<<20`.
  Scalar operand/parameter lists are rejected instead of being iterated.

### Native SAT parser and timeout (CQ-06)

- Strict DIMACS parsing: byte, variable, clause and clause-literal ceilings;
  malformed headers, extra tokens, truncated clauses and literals above the
  declared header count are rejected.
- A search timeout is now an explicit error and exit code 1; invalid input uses
  the documented exit code 2. A timeout is never reported as UNSAT.
- The subprocess fuzz helper has a 30 s timeout.

### CI and supply chain (CQ-12)

- Node 24 action releases pinned by full commit SHA: `actions/checkout@v7.0.1`,
  `actions/setup-python@v7.1.0`, `actions/upload-artifact@v7.0.2`,
  `softprops/action-gh-release@v3.0.3` and
  `jakoch/install-vulkan-sdk-action@v1.7.0`. Each SHA was verified against its
  upstream tag with `git ls-remote`; the annotated `v3.0.3` tag was peeled to
  the pinned commit.
- Workflow-wide `contents: write` was reduced to `contents: read`; only the
  release job receives `contents: write`.

### Documentation and test quality (CQ-05 / CQ-07 / CQ-08 / CQ-09 / CQ-11 / CQ-13 / CQ-14)

- Path B's `error_bound = 0.0` is now documented as "no deliberate
  approximation" with float64 evaluation, not symbolic exactness or bitwise
  identity.
- Path C's discarded mass is documented and reported as
  `discarded_spectral_mass_diagnostic`; `numerical_error_bound` remains `None`
  because no propagated bound is derived.
- The 20-qubit dense-statevector conversion cap is no longer conflated with the
  500-qubit MPS-native sampling ceiling.
- GPU/native labels remain `PLANNER_ONLY`, `CPU_REFERENCE`,
  `LEGACY_DIAGNOSTIC` and `PHYSICAL_GPU_UNVERIFIED`; no acceleration is claimed.
- QFT coverage uses `synth_qft_full(4)` instead of the deprecated `QFT`
  blueprint.
- Added deterministic Hypothesis parser properties (`tests/test_property_parser.py`),
  declared `hypothesis>=6.0.0` in the dev extra and pinned `6.170.12` in the
  CI constraints file.
- Differential tests now compare real statevector fidelity and sampling
  envelopes against Qiskit Aer/Stim instead of only overlapping count keys.

### QASM addressing

- `J_QuantumOpcode` stores target and control qubits in 8-bit fields. The QASM
  parser rejects `q[i]` for `i > 255` instead of silently wrapping the index.
  The legacy Qiskit provider tests a 256-qubit GHZ circuit and requires a
  300-qubit circuit to raise. Direct C++ `MPSSimulator` still supports 300
  qubits; only the bytecode bridge is limited.

## 3. Tests

- New native suite: `test_sat_parser` (strict DIMACS grammar, hash coverage,
  header/literal bounds, timeout classification); CTest now registers 18 suites.
- Cycle-1 native suites retained: `test_statevector_contract`,
  `test_mps_contract`, `test_qpu_facade_contract`.
- New Python suites: `test_path_c_operand_order.py` (8),
  `test_path_c_resources.py` (12), `test_parser_strictness.py` (18),
  `test_circuit_size_limits.py` (3), `test_property_parser.py` (5).
  Strengthened: `test_fuzz_sat.py` (14), `test_adversarial_aer_and_stim.py` (6),
  `test_svd_precision.py` (5), Qiskit backend contract.
- Local verification on Windows 11 / Python 3.14.6 / MSVC 19.44:
  - `python -m pytest tests/ -q` → **366 passed in 83.85s**, 0 failed, 0 skipped.
  - `ctest --test-dir build -C Release --output-on-failure` → **18/18 passed**.
  - Branch coverage → **82%** (CI threshold 70%).
  - Mutation harness → **11/11 killed**, clean baseline.
  - `verify_vulkan_shaders.py` → **12/12 shaders** compile, 0 warnings/errors.
  - `check_version.py` → all surfaces report `2.2.2`.
  - `compileall`, `verify_no_silent_truncation.py` → PASS.
- Exact-SHA Linux/Windows CI results and artifact hashes are recorded in the
  pull request and the published release, not inferred from these local runs.

## 4. Limits and non-claims

- No physical-GPU dispatch was verified. Shader compilation is not a compute
  test, and `VulkanEngine` is planner-only.
- `VulkanQpuEngine` rejects `RX`, `RY`, `U3` and `SWAP` on its MPS path rather
  than silently ignoring them.
- `MPSSimulator` truncation diagnostics do not constitute a global error bound.
  Generic sampling costs `O(n · χ² · shots)`; the GHZ fast path is selected only
  by an exact structural check.
- Path C's `1e-13` relative singular-value floor is a double-precision rank
  convention, not a proof that the discarded component is physically
  irrelevant. `numerical_error_bound` stays `None`.
- Path C MPS-native sampling is capped at 500 qubits and is subject to RAM and
  `shots × qubits` limits; dense statevector conversion is capped separately at
  20 qubits.
- `HybridEngine` continues to fail closed for non-Clifford gates above 16
  qubits.
- No Tensor Network 2D, code-compiled, or noise-channel backend is included.
  See `research/next_stable/RESEARCH_LEDGER.md` for the deferral reasons.
- The 4096-qubit and shot ceilings bound interpreter bookkeeping, not a promise
  that an accepted circuit fits in the caller's memory.

## 5. Installation and smoke test

```bash
python -m pip install cqhecs-2.2.2-py3-none-any.whl
cq-hecs version
cq-hecs doctor
cq-hecs --format json run name:bell --shots 128
```

The pure-Python wheel does not contain the native C++/Vulkan binaries. Build
those from source with CMake and a C++20 toolchain if you need the native
reference paths.

## 6. Evidence

- `research/next_stable/BASELINE.md` — base SHA and baseline gates.
- `research/next_stable/EXECUTION_LOG.md` — cycle-2 finding log and gate table.
- `research/next_stable/FINDINGS.md` — defects, root causes and regression tests.
- `research/next_stable/TEST_MATRIX.md` — commands, counts and boundaries.
- `research/next_stable/RESEARCH_LEDGER.md` — adopted methods and deferrals.
- The published release body records the exact source SHA and required CI run.
