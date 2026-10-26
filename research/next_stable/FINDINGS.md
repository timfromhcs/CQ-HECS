# Findings — next Stable after v2.2.1

All findings were checked against live source at `9fe014b` and re-verified
after the fixes. Status meanings: `CONFIRMED` (defect reproduced),
`ALREADY FIXED` (no current defect), `NOT REPRODUCED`, `BLOCKED` (external).

| ID | Severity | Surface | Status | Root cause | Fix | Regression test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| F1 | P0 | `cqhecs::vulkan::VulkanEngine` (`src/vulkan/vulkan_engine.cpp`) | CONFIRMED → fixed | Gate methods validated the index and returned, leaving a state that was never stored; `sample_fast_shots()` emitted uniform random bits. | Reclassified as `PLANNER_ONLY`: gate methods throw `std::logic_error`, sampling throws, index errors throw `std::out_of_range`. `truncate_bond()` is documented as metadata-only. | `tests/cpp/test_300q_stress.cpp` (planner/memory contract + fail-closed gates/sampling) |
| F2 | P0 | `VRTS300Engine` (`src/tensor_network.cpp`) | CONFIRMED → fixed | `measure_parity_shots()` forced `num_shots/2` zeros and derived non-parity count from flags. | Validates that all 300 sites carry the same amplitude pair and are entangled, then draws seeded independent shots from the two-outcome distribution; throws for non-correlated states. Header documents the compact-state restriction. | `tests/test_ghz300.cpp` (correlation invariant + seeded binomial 5σ band); `test_300q_stress` |
| F3 | P0 | `StateVectorSimulator` | CONFIRMED → fixed | `measure()` used a deterministic `p > 0.5` decision; `sample_counts()` assigned all shots to the most likely basis state; width check happened after the shift. | Seeded Born-rule `sample_counts(shots, seed)`, real `measure(target, rng)` with projection and renormalisation, `MAX_SUPPORTED_QUBITS = 28` guard before shifting, index validation on every gate, added `apply_y`. | `tests/cpp/test_statevector_contract.cpp` |
| F4 | P0/P1 | `cq_hecs::core::VulkanQpuEngine` | CONFIRMED → fixed | Built indirect-dispatch metadata that was never submitted; executed CPU code; MPS sampling was GHZ-only via `measure_ghz_parity()`; statevector seed was fixed internally. | Removed fabricated dispatch metadata and the unused struct path; all supported opcodes dispatch to real CPU state evolution; unsupported opcodes throw; `sample_counts(shots, seed)` delegates to the backend sampler. `MEASURE` is accepted as a terminal opcode and gates after measurement are rejected as unsupported mid-circuit measurement. | `tests/cpp/test_qpu_facade_contract.cpp`; Python Qiskit provider tests |
| F5 | P0 (new) | `Qasm3Parser` | CONFIRMED → fixed | `J_QuantumOpcode` stores qubit indices in `uint8_t`, but the parser cast arbitrary indices to `uint8_t`. A 300-qubit Qiskit circuit silently wrapped `q[256]→q[0]`; the old passing test only survived because MPS sampling returned a GHZ pattern without inspecting the state. | Reject indices above 255 with `std::out_of_range` before building an opcode. The QASM bridge now truthfully supports 0–255; the direct C++ `MPSSimulator` still supports 300 qubits. | `test_qpu_facade_contract::test_unaddressable_qubit_index_is_rejected`; `tests/test_qiskit_and_transpiler.py::test_qiskit_ghz300_is_rejected_not_truncated` |
| F6 | P1 | `MPSSimulator` CNOT/SWAP | CONFIRMED → fixed | Adjacent CNOT built a replacement tensor by index assignment instead of an SVD; non-adjacent CNOTs could silently do nothing; sampling used a GHZ heuristic. | Correct two-site contraction, gate application and complex SVD factorisation; exact SWAP factorisation; non-adjacent CNOT routed through adjacent SWAPs and restored; generic right-environment conditional sampler; GHZ fast path only after exact tensor-shape/amplitude validation; truncation diagnostics recorded; local spectral rescaling prevents fixed-point rank collapse. | `tests/cpp/test_mps_contract.cpp` (dense differential, adjacent/order cases, non-adjacent, rank growth, truncation, non-GHZ sampling, 300-qubit GHZ) |
| F7 | P1 | Legacy native QASM executor (`QASMParserCPP::execute_on_vulkan`) | ALREADY LABELLED | Method is a `legacy_z8_phase_ledger`, not a statevector simulator. | No semantic change; contract re-verified (parse errors prevent execution, no fabricated counts). | `tests/test_qasm_contract.cpp` |
| F8 | P1 | `cqhecs/scheduler.py` | ALREADY FIXED | Planner-only submission was fixed in v2.2.1. | None. | `tests/test_scheduler_contract.py` |
| F9 | P1 | Physical GPU / Vulkan compute | NOT VERIFIED | No physical device dispatch test was run in this environment. | No GPU claim added; VulkanEngine is planner-only. | `verify_vulkan_shaders.py` is shader compilation only, not a GPU test |
| F10 | P2 | Legacy 300-qubit GHZ test wording | CONFIRMED → fixed | The test called an exact 25 000/25 000 split a statistical measurement audit. | Renamed to parity diagnostic; asserts the structural invariant (`non_parity == 0`) and a derived 5σ binomial tolerance, with seeded sampling. | `tests/test_ghz300.cpp` |
| F11 | P2 | `tests/test_bitexact_and_stress.cpp` | CONFIRMED → fixed | "Truncation engine" test only proved bond memory saturation and never sampled or checked rank retention. | Still asserts the memory cap and growth, and the adjacent MPS contract now pins rank retention and valid sampling after repeated truncation. | `test_bitexact_and_stress`, `test_repeated_truncation_keeps_rank_and_sampling_valid` |

## Semantic classification after the fixes

| Surface | Status |
| :--- | :--- |
| `cqhecs` four-path Python router/backends | SUPPORTED (unchanged in this release) |
| `cq_hecs::core::StateVectorSimulator` | SUPPORTED reference, ≤ 28 qubits, Q1.31 storage with double-precision sampling |
| `cq_hecs::core::MPSSimulator` | EXPERIMENTAL CPU reference: SVD updates and seeded sampling; truncation diagnostic is not a certified error bound |
| `cq_hecs::core::VulkanQpuEngine` | CPU reference facade; no GPU dispatch is claimed; QASM operands limited to qubits 0–255 |
| `cqhecs::vulkan::VulkanEngine` | PLANNER_ONLY memory allocator |
| `VRTS300Engine` | LEGACY_DIAGNOSTIC compact GHZ-correlation representation; sampling only for validated fully correlated states |
| Legacy native QASM executor | LEGACY_DIAGNOSTIC phase ledger, no statevector output |
| Physical Vulkan compute | UNVERIFIED; not advertised |

## Known limitations carried into the release

- `MPSSimulator` truncation is a per-update diagnostic. No propagated global
  error bound is claimed; `cumulative_discarded_weight` is not a certificate.
- Generic MPS sampling costs `O(n · χ² · shots)` (plus environment build); the
  GHZ fast path is selected only by an exact tensor check.
- `VulkanQpuEngine` rejects `RX`, `RY`, `U3`, `SWAP` on the MPS path rather than
  silently ignoring them; the Python legacy provider therefore does not promise
  every gate in its Qiskit `Target`.
- `HybridEngine` still fails closed for non-Clifford gates above 16 qubits
  (unchanged, documented behaviour).
- No physical-GPU dispatch was verified; graphics-loader/shader validation is
  not a compute test.
