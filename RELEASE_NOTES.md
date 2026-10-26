# CQ-HECS Release Notes

**Version:** 2.2.2
**Release date:** 2026-10-26
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.2.2.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.2.2` is a **patch release** on top of `v2.2.1`. It removes false-success
behaviour from the native reference and legacy surfaces and makes their
measurement semantics explicit. It adds **no new simulator, no new exactness
claim and no GPU acceleration**.

The supported Python package keeps the same four-path interface. The changes in
this release concern the native C++ reference/legacy implementations and the
tests that describe them.

| Surface | Status in 2.2.2 |
| :--- | :--- |
| `cqhecs` four-path router/backends | supported (unchanged) |
| `cq_hecs::core::StateVectorSimulator` | supported dense reference, ≤ 28 qubits |
| `cq_hecs::core::MPSSimulator` | experimental CPU reference with SVD updates and seeded sampling |
| `cq_hecs::core::VulkanQpuEngine` | CPU reference facade; no Vulkan dispatch; QASM operands limited to qubits 0–255 |
| `cqhecs::vulkan::VulkanEngine` | planner-only memory allocator |
| `VRTS300Engine` | legacy diagnostic for a validated fully correlated GHZ-like state |
| Legacy native QASM executor | legacy phase ledger, not a statevector simulator |

## 2. Fixed

### False-success native engine contracts

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

### QASM addressing

- `J_QuantumOpcode` stores target and control qubits in 8-bit fields. The QASM
  parser now rejects `q[i]` for `i > 255` instead of silently wrapping the
  index. The legacy Qiskit provider tests a 256-qubit GHZ circuit and requires a
  300-qubit circuit to raise. Direct C++ `MPSSimulator` still supports 300
  qubits; only the bytecode bridge is limited.

## 3. Tests

- New native suites: `test_statevector_contract`, `test_mps_contract`,
  `test_qpu_facade_contract`. The MPS suite pins optimal rank-one truncation
  against closed-form singular values.
- Strengthened: `test_ghz300` (correlation invariant plus seeded 5σ binomial
  band), `test_bitexact_and_stress` (MPS memory and rank contract).
- Updated legacy Qiskit provider tests: GHZ-256 executes; GHZ-300 fails closed.
- Local verification: `311 passed` Python tests, `17/17` CTest tests,
  `11/11` mutation mutants killed, 12/12 shaders compile.

## 4. Limits and non-claims

- No physical-GPU dispatch was verified. Shader compilation is not a compute
  test, and `VulkanEngine` is planner-only.
- `VulkanQpuEngine` rejects `RX`, `RY`, `U3` and `SWAP` on its MPS path rather
  than silently ignoring them.
- `MPSSimulator` truncation diagnostics do not constitute a global error bound.
  Generic sampling costs `O(n · χ² · shots)`; the GHZ fast path is selected only
  by an exact structural check.
- `HybridEngine` continues to fail closed for non-Clifford gates above 16
  qubits.
- No Tensor Network 2D, code-compiled, or noise-channel backend is included.
  See `research/next_stable/RESEARCH_LEDGER.md` for the deferral reasons.

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

- `research/next_stable/BASELINE.md` — start SHA and baseline gates.
- `research/next_stable/FINDINGS.md` — defects, root causes and regression tests.
- `research/next_stable/TEST_MATRIX.md` — commands, counts and boundaries.
- `research/next_stable/RESEARCH_LEDGER.md` — adopted methods and deferrals.
- The published release body records the exact source SHA and required CI run.
