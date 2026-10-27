# Findings — next Stable after v2.2.1

Two audit cycles are recorded here.

- **Cycle 1** (base `9fe014b5509096ebe203ebae26cc146cb13b0a69`) produced PR #7,
  merged to `main` as `812da806d9b4528f1c4f8ccd3cbb7b37b6f009ce`.
- **Cycle 2** (base `812da80`, branch `agent/cq-hecs-v2.2.2-stable-hardening`)
  re-audited the merged tree against the mission's CQ-01…CQ-14 checklist. Its
  outcomes follow.

Status meanings: `CONFIRMED` (defect reproduced), `ALREADY FIXED` (no current
defect), `NOT REPRODUCED`, `BLOCKED` (external).

## Cycle 2 — CQ checklist (base `812da80`)

| ID | Severity | Surface | Status | Root cause | Fix | Regression test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CQ-01 | P1 | `ExactMPSTensorChain.apply_two_qubit_gate` (Path C) | CONFIRMED → fixed | The `q1 > q2` branch swapped the gate's **output** axes but left its **input** axes in chain order (`basm,lsmp->labp`), so a reversed two-qubit gate was applied with transposed inputs. | Replaced with the operand-ordered contraction `abcd,ldcp->lbap` and documented the tensor-index derivation. | `tests/test_path_c_operand_order.py` (8 tests: reversed CX/CP/SWAP, non-adjacent gates, both orders vs `Statevector`) |
| CQ-01b | P1 | `PathCMPSExactBackend` two-qubit gates | CONFIRMED → fixed (new finding) | The backend passed raw Qiskit little-endian 4×4 matrices (and hand-written `crx`/`cry`/`crz` matrices on the wrong basis block) to a chain whose axes are operand-ordered. Correct operand order alone could not fix CRX/CRY. | Added canonical little-endian matrices for CX/CZ/SWAP/CP/CU1/CRZ/CRX/CRY and `_chain_two_qubit_matrix()` (transpose `(1,0,3,2)`) at the chain boundary. | Same suite; backend-level CRX/CRY/CRZ in both operand orders match `Statevector` at fidelity 1.0 |
| CQ-02 | P1 | Path C RAM/storage budgets and paging | CONFIRMED → fixed | Budgets were converted to bytes without validation; two-site updates allocated before checking; sampling rehydrated every paged site regardless of RAM; missing/corrupt pages could leave `None` sites. | Validated finite/positive/bounded budgets; pre-allocation two-site and single-site preflight with a documented SVD workspace multiplier; fail-closed sampling refusal; `MPSResourceError` for missing/corrupt pages; `MAX_MPS_QUBITS=4096`, `MAX_SHOTS=10_000_000`. | `tests/test_path_c_resources.py` (12 tests) |
| CQ-03 | P1 | `parse_circuit` / Qiskit measurement mapping | CONFIRMED → fixed | The flat instruction IR carries qubit operands only, but Qiskit `measure(q[i]) -> c[j]` with `i != j` was silently relabelled as `c[i]`; terminal measurements also depended on source order. | Direct `parse_circuit()` accepts only identity terminal `measure q[i] -> c[i]`; `CQHecsBackend` keeps the full `(qubit, clbit)` layout via `_normalize_measurements()`/`_pad_counts()`. Terminal measurements are sorted ascending and exact duplicates removed. | `tests/test_parser_strictness.py` (18 tests), `tests/python/test_qiskit_backend_contract.py` |
| CQ-04 | P1 | Instruction-list qubit indices | CONFIRMED → fixed | `int(q)` coerced floats, strings and booleans (e.g. `1.7 → 1`, `True → 1`), silently simulating a different circuit; scalar operand lists were iterated or failed obscurely. | Accept only `numbers.Integral` (excluding `bool`); reject floats, strings, complex, NaN/inf and negatives; reject indices `>= 1<<20`; require iterable operand/parameter lists. | `tests/test_parser_strictness.py` |
| CQ-05 | P2 | Path C/Aer differential test | CONFIRMED under-proof → fixed | The earlier test compared only overlapping count keys and could pass without checking the state. | Real statevector fidelity for deterministic circuits; 5σ/TVD sampling envelope; explicit untruncated Aer MPS run for supported gates; Aer statevector for gates Aer MPS rejects (`crx`/`cry`). | `tests/test_adversarial_aer_and_stim.py` (6 tests) |
| CQ-06 | P2 | Native SAT subprocess fuzz helper | CONFIRMED → fixed | The helper could wait forever on a hostile DIMACS input, and the native parser accepted malformed/oversized headers, coerced literals and reported timeouts as UNSAT. | 30 s subprocess timeout in the test; strict DIMACS parsing with byte/var/clause/literal ceilings; timeout is an explicit error and exit 1, invalid input exits 2; hash covers all assigned variables; literals above the declared header count rejected. | `tests/test_fuzz_sat.py` (14 tests), `tests/cpp/test_sat_parser.cpp`, CTest `test_sat_parser` |
| CQ-07 | P2 | Path B "Bit-Exact" claim | CONFIRMED → fixed | Root `ARCHITECTURE.md` advertised `ε = 0.0 (Bit-Exact)` for Path B, which evaluates float64 amplitudes and branches. | Documented that `error_bound = 0.0` means "no deliberate approximation", not symbolic exactness or universal bitwise identity; cited `numerical_mode = "float64-exact-decomposition"`. | Documentation audit (no code change) |
| CQ-08 | P1/P2 | Path C numerical-rank cutoff wording | CONFIRMED → fixed | `ARCHITECTURE.md` claimed the discarded mass was reported as `numerical_error_bound`; the code deliberately reports it as `discarded_spectral_mass_diagnostic` and keeps `numerical_error_bound = None`. | Corrected the architecture text and preserved the distinction between deliberate approximation, measured diagnostics and derived bounds. | `tests/test_svd_precision.py` (5 tests), `tests/test_path_c_resources.py` |
| CQ-09 | P1 | Vulkan/native status claims | VERIFIED — no defect | Existing labels were already accurate. | No change: `PLANNER_ONLY`, `CPU_REFERENCE`, `LEGACY_DIAGNOSTIC`, `EXPERIMENTAL`, `PHYSICAL_GPU_UNVERIFIED` remain in README/ARCHITECTURE/V2 matrix. | Documentation audit; shader check is compile-only |
| CQ-10 | P1/P2 | Large-register validation | CONFIRMED → fixed | A syntactically legal huge QASM register could reach per-qubit allocations before any ceiling. | Per-backend ceilings: A/D `4096`, B `22` (dense statevector), C `4096`; all `MAX_SHOTS = 10_000_000`; refusals occur before tableau/statevector/observable allocation. | `tests/test_circuit_size_limits.py` (3 tests), `tests/test_path_c_resources.py` |
| CQ-11 | P2 | Version/docs consistency | CONFIRMED → fixed | Guides conflated Path C's 20-qubit dense-conversion cap with its 500-qubit MPS-native sampling ceiling; architecture text contradicted the result metadata. | Corrected `ARCHITECTURE.md`, `docs/ARCHITECTURE.md`, `docs/USAGE_GUIDE.md`; `python scripts/check_version.py` passes for `2.2.2`. | `python scripts/check_version.py` |
| CQ-12 | P2 | CI action runtime and pinning | CONFIRMED → fixed | Workflows used Node 20 actions (`checkout@v4`, `setup-python@v5`, `upload-artifact@v4`), movable tags and workflow-wide write permission. | Node 24 releases pinned by full SHA: `checkout@v7.0.1`, `setup-python@v7.1.0`, `upload-artifact@v7.0.2`, `action-gh-release@v3.0.3`, `install-vulkan-sdk-action@v1.7.0`. `contents: write` limited to the release job. SHAs verified with `git ls-remote` (annotated tag peeled). | YAML parse + upstream ref verification |
| CQ-13 | P2 | Qiskit QFT deprecation | CONFIRMED → fixed | The test used the deprecated `QFT(4).decompose()` blueprint. | Replaced with `synth_qft_full(4)` while keeping the same execution contract. | `tests/python/test_qiskit_backend_contract.py` (no QFT deprecation warning) |
| CQ-14 | P2 | Property/fuzz coverage | CONFIRMED → fixed | No property-based tests; Hypothesis undeclared. | Added deterministic Hypothesis parser properties; declared `hypothesis>=6.0.0` in dev extras and pinned `6.170.12` in `constraints/ci-py311.txt`; all CI install lanes include it. | `tests/test_property_parser.py` (5 tests) |

## Cycle 1 — merged findings (base `9fe014b`)

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
| `cqhecs` four-path Python router/backends | SUPPORTED |
| `cq_hecs::core::StateVectorSimulator` | SUPPORTED reference, ≤ 28 qubits, Q1.31 storage with double-precision sampling |
| `cq_hecs::core::MPSSimulator` | EXPERIMENTAL CPU reference: SVD updates and seeded sampling; truncation diagnostic is not a certified error bound |
| `cq_hecs::core::VulkanQpuEngine` | CPU reference facade; no GPU dispatch is claimed; QASM operands limited to qubits 0–255 |
| `cqhecs::vulkan::VulkanEngine` | PLANNER_ONLY memory allocator |
| `VRTS300Engine` | LEGACY_DIAGNOSTIC compact GHZ-correlation representation; sampling only for validated fully correlated states |
| Legacy native QASM executor | LEGACY_DIAGNOSTIC phase ledger, no statevector output |
| Physical Vulkan compute | UNVERIFIED; not advertised |

## Known limitations carried into the release

- Path C's `1e-13` relative singular-value floor is a double-precision rank
  convention. Discarded mass is reported as
  `discarded_spectral_mass_diagnostic`; `numerical_error_bound` stays `None`
  because no propagation bound is derived.
- Path C MPS-native sampling is capped at 500 qubits and is subject to the RAM
  budget and `shots × qubits` batch ceiling. Dense statevector conversion is a
  separate operation capped at 20 qubits.
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
