# Changelog

All notable changes to CQ-HECS (Classical Quantum High-Efficiency Compute Simulator) are documented in this file.

The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Work towards v3 (`research/v3/V3_STABLE_PLAN.md`). Not released.

### Added

- `cqhecs.calibration_import`: imports real IBM calibration snapshots
  (`props_*.json` / `conf_*.json`, e.g. from `qiskit-ibm-runtime`) into
  non-synthetic `BackendProfile`s with provenance URI, capture timestamp and
  source SHA-256. Non-operational gates (IBM's `gate_error = 1`), missing or
  physically inconsistent T1/T2 (`T2 > 2 T1`) and operations without a noise
  channel are listed in `calibration_flags`, never clipped or dropped.
- `BackendProfile` schema 2.0 (`calibration_flags`, `source_sha256`); 1.0
  profiles still load.
- T1/T2 relaxation: `ThermalRelaxationChannel`, `TensorChannel`,
  `ComposedChannel`, `depolarizing_parameter_with_relaxation`,
  `average_gate_infidelity`; `BackendProfile.to_noise_model(relaxation=True)`
  and `FakeHardwareBackend(..., relaxation=True)` follow Qiskit Aer's device
  model (depolarizing, then relaxation). Channel-level parity with Aer
  ≤ 1e-12.
- `OutOfModelError`: the fake backend refuses circuits on flagged qubits or
  pairs instead of running them without calibrated noise.
- `cqhecs.noisy_expectation_values` / `FakeHardwareBackend.expectation_values`:
  Pauli expectation values of noisy circuits. Exact density matrix up to 10
  qubits; above that, Heisenberg Pauli propagation with the adjoint noise
  channels and readout, reporting the discarded Pauli 1-norm as a worst-case
  bound (valid under noise because CPTP adjoints are operator-norm
  contractive). Both engines agree with Qiskit Aer to ≤ 1e-12 plus Aer's own
  trace loss. Method from Aharonov et al. 2023, Schuster et al. 2025,
  Angrisani et al. 2025; their average-case guarantees are not claimed.
- `NoisyDensityMatrixBackend.density_matrix()`.

---

## [2.5.2] — 2026-10-30

Correction release. Findings, reproductions and the test matrix are in
`research/v2_5_2/`. Every fixed defect has a regression test that fails on the
v2.5.1 source (`1be682a`) and an independent oracle (closed forms, Qiskit
`Statevector`/`DensityMatrix`, `average_gate_fidelity`).

### Fixed

- **CQ-V252-01 (P0) — Path B swapped `t` and `tdg`.** The stabilizer-rank
  decomposition wrote `T = c0 I + c1 Z` with `c1 = (e^{i pi/4} - 1)/2`, which is
  `diag(e^{i pi/4}, 1)`: the adjoint up to a global phase. Probabilities only
  differ once another phase breaks the mirror symmetry, so `h t h` was right but
  `h t s h` gave `P(0) = 0.854` instead of `0.146`, reported as `EXACT`. Every
  release with Path B was affected for circuits combining `t`/`tdg` with other
  phases. `c1` is now `(1 - e^{+-i pi/4})/2`.
- **CQ-V252-02 (P1) — gate error used as depolarizing parameter.**
  `BackendProfile.to_noise_model()` passed the reported gate error straight to
  `DepolarizingChannel(p)`. The same number is exported to Qiskit as
  `InstructionProperties.error`, an average gate infidelity `r`, and the
  channel with parameter `p = r` has infidelity `r/2` (one qubit) or `3r/4`
  (two qubits). The model now uses `p = d r / (d - 1)`
  (`depolarizing_parameter_from_infidelity`, the conversion Qiskit Aer uses
  without relaxation) and refuses `r > (d - 1)/d` instead of clipping it.
  Noisy results on `fake_manila`/`linear_5q` change accordingly.
- **CQ-V252-03 (P0, native builds) — SWAP was the identity on the native
  tableau.** `HybridEngine::apply_swap` applied the swap to the tableau and
  then called `HybridEngine::apply_cx` three times, which applied it again.
  Path A with the native module (and `cq_apply_swap` in the C API) returned
  the un-swapped state for Clifford circuits. The pure-Python wheel used the
  correct Python tableau and was not affected.
- **CQ-V252-04 (P2) — `BackendProfile` validation.** Refuses float/bool qubit
  indices, T1/T2/readout entries for qubits the profile does not have,
  `T2 > 2 T1`, non-finite times, negative or out-of-range gate durations,
  repeated qubits in a gate key and gate-error keys that do not match the
  gate's arity or are wider than two qubits (the noise model dropped those).
- **CQ-V252-05 (P3) — noisy density-matrix gate set.** `cu1`, `crx`, `cry`
  and `crz` are executed (checked against Qiskit) instead of refused, so the
  backend now covers every gate in the manifest.

### Added

- `cqhecs.depolarizing_parameter_from_infidelity(r, num_qubits)`.
- Four source mutants (24/24 killed) and a C++ regression for native SWAP.

---

## [2.5.1] — 2026-10-30

Correction release for the v2.5.0 Hardware-Aware Quantum Bridge. Findings are
recorded in `research/v2_5_1/FINDINGS.md`.

### Fixed

- **CQ-V251-01 (P0) — mirrored bitstrings in `NoisyDensityMatrixBackend`.**
  The density matrix was flattened with qubit 0 as the most-significant bit, so
  every outcome was rendered mirrored relative to the router and to Qiskit
  (`x q[0]` gave `10` on `--profile`, `01` on the router), and per-qubit
  readout errors were applied to the mirrored bit. Qubit 0 is now the
  least-significant bit and is rendered rightmost.
- **CQ-V251-02 (P1) — measurement semantics.** Terminal measurements were
  ignored (all qubits were always reported) and a mid-circuit measurement in an
  instruction list was silently dropped. The backend now reports only the
  measured qubits, like the router, and refuses mid-circuit measurement.
- **CQ-V251-03 (P0) — false calibration provenance.** `fake_manila` was marked
  `is_synthetic=False` with provider `IBM_Quantum_Snapshot`, a capture
  timestamp and a provenance URI, but its numbers do not match IBM's
  `FakeManila` snapshot. It is now `is_synthetic=True` with no timestamp or
  URI, and `BackendProfile` refuses a non-synthetic profile without
  `capture_timestamp` and `provenance_uri`.
- **CQ-V251-04 (P1) — noise attached to the wrong gate.** Gates were lowered
  before noise lookup, so a channel calibrated on `sx` (as in `fake_manila`)
  never fired and `h` noise fired twice per `sx`. Channels now attach to each
  gate as written in the source circuit (new `parse_source_circuit()`), which
  is also Qiskit Aer's semantics.
- **CQ-V251-05 (P2) — input validation.** `shots`/`seed` follow the router
  contract (bool, float and non-positive shots, negative or non-int seeds are
  rejected before parsing); gates with a missing or extra angle (`rx` without
  a parameter) are refused instead of being evaluated as the identity; every
  operation is validated before the density matrix is allocated.
- **CLI:** an unknown `--profile` name and a topology violation are usage
  errors (exit `2`, JSON `error` field) instead of a traceback with exit `1`.

### Release pipeline

- `release.yml` also runs on pushes to `main`. When no tag
  `v<scripts/version.py>` exists, it waits for green `ci.yml` on the pushed
  commit and then creates the tag and the release on exactly that commit;
  when the tag exists the run does nothing. Tag pushes work as before.

### Tests

- `tests/test_noisy_density_matrix_contract.py` (18 tests): exact differential
  comparison on random asymmetric 3- and 4-qubit circuits against
  `qiskit.quantum_info.DensityMatrix` with channels built by `qiskit_aer.noise`
  and readout computed from its definition; partial measurement, refusal and
  argument-validation cases; a CLI test that router and `--profile` agree.
  Against the v2.5.0 code this file fails 60 checks.
- Mutation harness: 20 mutants (new: noisy-DM bit order, measured-qubit
  marginal, noise on source gate, profile provenance).

### Documentation

- `RELEASE_NOTES.md` for v2.5.0 still described v2.4.0 under a 2.5.0 header;
  it now describes this release. `research/v2_5/RELEASE_AUDIT.md` recorded a
  candidate SHA that does not exist (`f97249a888c3…`); an erratum gives the
  real one (`f97249a1c4ad…`).

---

## [2.5.0] — 2026-10-30

### Added — Hardware-Aware Quantum Bridge

- **ExecutionMode hierarchy**: Added explicit, irreducibly separated execution modes (`IDEAL_CLASSICAL`, `NOISY_CLASSICAL`, `REAL_HARDWARE`) ensuring simulation, noise emulation, and hardware execution results can never be silently conflated or substituted.
- **BackendProfile schema**: Added typed, versioned device profiles capturing coupling maps, calibrated 1Q/2Q gate error rates, readout assignment errors ($p_{01}$, $p_{10}$), relaxation time $T_1$, dephasing time $T_2$, and synthetic vs physical calibration provenance flags. Includes Qiskit `Target` export and default calibration profiles (`fake_manila`, `linear_5q`).
- **Mathematically verified NoiseModel**: Implemented single- and two-qubit Kraus noise channels (`DepolarizingChannel`, `AmplitudeDampingChannel`, `PhaseDampingChannel`, `TwoQubitDepolarizingChannel`, `ReadoutErrorChannel`) with strict mathematical completeness checks ($\sum K_k^\dagger K_k = I_d$), trace preservation, Hermiticity, and positive semidefiniteness.
- **NoisyDensityMatrixBackend**: Added exact float64 density matrix simulator for circuits up to 10 qubits with tensor-contraction channel application, multinomial count sampling, and Hoeffding total-variation error bounds. Validated against independent analytical formulas and Qiskit Aer differential tests.
- **FakeHardwareProvider & FakeHardwareBackend**: Deterministic offline emulation enforcing device connectivity topology (rejecting gates violating coupling map) and tracking calibration provenance metadata.
- **RealHardwareProvider & RealHardwareBackend**: Fail-closed provider boundary enforcing explicit user authorization (`authorized=True`) and valid API credentials; strictly rejects unauthenticated execution and never silently falls back to classical emulation.
- **CLI Commands**: Added `cq-hecs profile list`, `cq-hecs profile show <NAME>`, and `--profile <NAME>` / `--noisy` options to `cq-hecs run`.
- **Qiskit Provider Integration**: Extended `CQHecsProvider` with `fake_hardware` and `real_hardware` accessors and registered fake backends.

---

## [2.4.0] — 2026-10-29

### Added — Pauli expectation values

- New `cqhecs.expectation.expectation_values(circuit, observables)` and
  `cq-hecs expect CIRCUIT -o PAULI [...]` evaluate `<psi|P|psi>` for general
  Pauli strings (`X`, `Y`, `Z`) and weighted sums, replacing the Z-only,
  Path-D-only observable surface. Strings are dense Qiskit labels (`IZX`,
  rightmost = qubit 0) or sparse (`X0 Z2`, `X[0]Z[2]`).
- Engines: `stabilizer` (exact tableau read-out for Clifford circuits up to
  4096 qubits, no sampling), `dense` (exact float64 statevector up to 22
  qubits, ceiling 26) and `sparse_pauli` (Path D with the certified
  truncation bound, basis-rotating `X`/`Y` into `Z`). `auto` picks the first
  that applies. Values that cannot be certified are `None` and
  `unresolved`; nothing is guessed. Mid-circuit measurement and `reset` are
  refused.
- New `cqhecs.backends.dense_reference`: a small, self-contained dense
  simulator that shares no code with the production paths. It is also the
  independent oracle for the new tests.
- Nine more exact gate lowerings: `r`, `iswap`, `dcx`, `ecr`, `cu3`, `cu`,
  `csx` and the multi-controlled `c3x`/`c4x` (Qiskit `mcx` with 3 or 4
  controls). Each is verified as a unitary identity including global phase.
  The Qiskit `Target` advertises the one- and two-qubit ones.
- Contract metadata (`numerical_status`, `numerical_rank_truncation_applied`,
  `bond_dimension_truncation_applied`, `error_bound_covers`,
  `counts_are_joint_distribution`, ...) is forwarded into the Qiskit
  `ExperimentResult.header`.

### Fixed — result and numerical contracts (from the v2.4 audit)

- **CQ-NEXT-H0:** `SimulationResult.total_error_bound` no longer sums an
  observable-space bound (Path D) into a total-variation figure for sampled
  counts, nor reports a number for unresolved/failed results or for
  independent-marginal counts.
- **CQ-NEXT-H1:** Path C's relative singular-value floor can discard a
  nonzero Schmidt coefficient. Results now say so explicitly
  (`numerical_rank_truncation_applied`, `discarded_singular_value_sum`,
  `numerical_status`) and distinguish it from a bond-dimension budget
  truncation. `exact=True` is documented as "no deliberate approximation
  beyond the documented numerical-rank rule", not mathematical exactness.
- **H8:** the sampling-bound documentation now states that
  `hoeffding_proportion_bound` holds simultaneously over the whole support
  and that `K*ln 2` conservatively replaces `ln(2^K - 2)`; exact-formula tests
  pin both bounds.
- Path D infers its width from the highest used qubit of an instruction list,
  so observables on an idle top qubit were rejected; the expectation API pads
  the circuit to the declared width.

### Changed

- Version 2.4.0 on every surface; mutation gate now has 14 mutants (added
  stabilizer-expectation sign and dense Pauli-Y orientation).


## [2.3.0] — 2026-10-29

### Added — exact composite-gate lowering

- New `cqhecs.gate_lowering`: `parse_circuit()` rewrites composite gates into
  natively executed gates through exact unitary identities (global phase
  included). Newly executable: `u`, `u3`, `u2`, `sx`, `sxdg`, `cy`, `ch`, `cs`,
  `csdg`, `rzz`, `rxx`, `ryy`, `ccx`/`toffoli`, `ccz`, `cswap`/`fredkin`.
  Routing sees the lowered circuit, so Clifford composites (`sx`, `cy`,
  `rzz(pi/2)`) still reach Path A and the T-count of `ccx` is its real
  decomposition cost. Malformed operands (wrong arity, duplicate qubits) are
  refused before execution.
- The Qiskit `Target` advertises the one- and two-qubit composites; three-qubit
  gates are left to the transpiler and are lowered when submitted untranspiled.
- New builtin circuits: `toffoli_adder`, `qft4`, `ising6`.
- `tests/test_gate_lowering.py` checks every rule against Qiskit's reference
  matrices in both operand orders and end to end against `Statevector`; a new
  mutant (`Toffoli lowering phase error`) keeps the decomposition pinned.

### Changed

- `reset` is now the only manifest operation that no path executes.
- The native legacy QASM executor (LEGACY_DIAGNOSTIC) still rejects `u`/`u2`/`u3`;
  only the Python four-path stack lowers them.

### Fixed

- Nightly workflow failed at test collection since 2026-10-28 because it did
  not install `hypothesis`; the dependency is now installed as in `ci.yml`.
- `python_bridge/cli_runner.py` annotated `Optional` without importing it.
- Removed dead locals and unused imports across `cqhecs`, `python_bridge`,
  `scripts` and `tests`; CI lint now enforces the full pyflakes `F` rule set
  and covers `python_bridge`.

### Fixed — Vulkan compute dispatch is now verified and fails closed

- **Spec fix:** `VkPhysicalDeviceFeatures::shaderInt64` is queried and enabled
  before device creation. The embedded CORDIC shader declares the `Int64`
  capability; without the feature, the Khronos validation layer reported
  `VUID-VkShaderModuleCreateInfo-pCode-08740` for every pipeline.
- **Fail-closed dispatch:** command-buffer allocation, recording, submission and
  queue-wait results are checked in `dispatch_cordic`,
  `dispatch_state_reset` and `dispatch_tensor_contract`; partial descriptor and
  command-buffer state is released on error paths. A failed `initialize()` now
  tears down whatever was already created.
- **Evidence:** new `tests/cpp/test_vulkan_compute_contract.cpp` (CTest
  `test_vulkan_compute_contract`) dispatches state reset, a CORDIC π/2 phase
  with inverse and Pauli-X, and a Q30 matrix contraction on the GPU, then
  compares the readback in device memory. It exits `77` (CTest SKIP) when no
  Vulkan device exists; `CQ_REQUIRE_VULKAN=1` requires any device (Lavapipe
  included, used by Linux CI) and `CQ_REQUIRE_HARDWARE_GPU=1` rejects software
  ICDs.
- **Verified locally** on an AMD Radeon(TM) Graphics iGPU (Vulkan `1.4.315`,
  driver `26.6.1`, SDK `1.4.357.0`), validation-clean, with CTest **19/19** and
  Python **366 passed**. This is primitive dispatch evidence only; no
  end-to-end GPU simulator acceleration is claimed.

---

## [2.2.2] — 2026-10-26

### Fixed — native simulation paths no longer report success without evolving a state

- `cqhecs::vulkan::VulkanEngine` is now explicitly **planner-only**. Its gate
  methods previously validated an index and returned a success-shaped result
  without storing amplitudes; they now throw `std::logic_error`, and
  `sample_fast_shots()` throws instead of emitting uniform random bits. Bond
  changes are documented as metadata-only planning.
- `VRTS300Engine::measure_parity_shots(num_shots, seed)` validates that the
  compact representation really is a fully correlated GHZ-like state, then
  draws seeded independent shots from the stored amplitudes. It throws for
  arbitrary 300-qubit states instead of forcing an exact half-and-half split.
  The GHZ test now checks the structural invariant and a derived 5σ binomial
  band.
- `StateVectorSimulator` now performs seeded Born-rule sampling, collapsing
  `measure(target, rng)`, validates qubit indices on every gate, rejects widths
  above 28 before shifting, and implements `apply_y`.
- `MPSSimulator` now contracts and factorises two-site tensors with a complex
  SVD, supports both CNOT directions and non-adjacent CNOT routing through
  exact swaps, samples arbitrary states through right environments, and uses
  its GHZ fast path only after an exact tensor check. Truncation keeps the
  largest singular values, records discarded weight as a diagnostic, and
  rescales retained local tensors so the fixed-point rank does not collapse.
- `VulkanQpuEngine` is documented and implemented as a CPU reference facade:
  it no longer fabricates indirect-dispatch metadata, dispatches every supported
  opcode to real state evolution, throws on unsupported opcodes, treats
  `MEASURE` as terminal and rejects gates after a measurement. Its
  `sample_counts(shots, seed)` delegates to the backend sampler.
- `Qasm3Parser` rejects qubit indices above 255 instead of truncating them to
  the 8-bit `J_QuantumOpcode` fields. The legacy Qiskit provider now tests a
  256-qubit GHZ circuit and requires a 300-qubit circuit to fail closed.

### Fixed — Path C two-qubit operand order and gate matrices

- `ExactMPSTensorChain.apply_two_qubit_gate()` used `basm,lsmp->labp` for the
  `q1 > q2` branch, which swapped the gate's output axes but not its input
  axes. It now uses the operand-ordered contraction `abcd,ldcp->lbap`.
- `PathCMPSExactBackend` passed raw Qiskit little-endian matrices to a chain
  whose axes are operand-ordered, and its `crx`/`cry`/`crz` matrices sat on the
  wrong basis block. Every two-qubit gate now uses a canonical little-endian
  matrix and `_chain_two_qubit_matrix()` (transpose `(1,0,3,2)`) at the chain
  boundary.
- Added `tests/test_path_c_operand_order.py`: reversed and non-adjacent
  CX/CP/SWAP plus backend-level CRX/CRY/CRZ in both operand orders against
  Qiskit `Statevector`.

### Hardened — Path C resources, paging and circuit-size ceilings

- Budgets (`ram_budget_mb`, `max_storage_mb`), `num_qubits` and `shots` are
  validated before allocation. Two-site updates run a pre-allocation preflight
  covering contraction, SVD outputs and a documented SVD workspace multiplier.
- Paged sampling checks the rehydration working set before loading pages and
  refuses fail-closed when it would exceed the RAM budget. Missing, truncated or
  malformed swap pages raise `MPSResourceError` and surface as `UNRESOLVED`.
- Added `MAX_MPS_QUBITS = 4096`, `MAX_SHOTS = 10_000_000` and
  `MAX_SAMPLING_ELEMENTS`. Path A/D cap at 4096 qubits, Path B at its 22-qubit
  dense-statevector ceiling, and every path enforces the shot ceiling before
  execution.
- Added `tests/test_path_c_resources.py` (12 tests) and
  `tests/test_circuit_size_limits.py` (3 tests).

### Fixed — measurement mapping and qubit-index coercion

- Direct `parse_circuit()` now accepts only identity terminal measurements
  (`measure q[i] -> c[i]`); `CQHecsBackend` remains the supported surface for
  arbitrary `(qubit, clbit)` layouts and preserves repeated measurements.
- Terminal measurements are normalised once (ascending, duplicates removed) so
  the lowest measured qubit is rightmost in every backend. Mid-circuit
  measurements stay in place.
- Instruction-list qubit indices accept only `numbers.Integral`; `bool`, floats,
  strings, complex values, NaN/inf, negatives and indices `>= 1<<20` are
  rejected. Operand and parameter arguments must be iterables.
- Added `tests/test_parser_strictness.py` (18 tests).

### Fixed — native SAT parser, timeout and exit codes

- Strict DIMACS parsing with byte/variable/clause/literal ceilings; malformed
  headers, extra tokens, truncated clauses and literals above the declared
  count are rejected.
- A search timeout is an explicit error (exit 1), never UNSAT; invalid input
  uses the documented exit 2. The subprocess fuzz helper times out at 30 s.
- Added `tests/cpp/test_sat_parser.cpp` (CTest `test_sat_parser`) and expanded
  `tests/test_fuzz_sat.py` to 14 tests.

### Changed — CI actions and property tests

- Upgraded to Node 24 action releases pinned by full SHA:
  `actions/checkout@v7.0.1`, `actions/setup-python@v7.1.0`,
  `actions/upload-artifact@v7.0.2`, `softprops/action-gh-release@v3.0.3`,
  `jakoch/install-vulkan-sdk-action@v1.7.0`. Workflow-wide `contents: write`
  was reduced to `contents: read`; only the release job retains write access.
- Added deterministic Hypothesis parser properties
  (`tests/test_property_parser.py`) and declared `hypothesis>=6.0.0` in the dev
  extra; `constraints/ci-py311.txt` pins `6.170.12`.
- Replaced deprecated `QFT(4).decompose()` coverage with `synth_qft_full(4)`.
- Corrected the documentation that called Path B "Bit-Exact", conflated Path C's
  20-qubit dense conversion with its 500-qubit MPS sampling ceiling, and
  reported discarded spectral mass as `numerical_error_bound` instead of
  `discarded_spectral_mass_diagnostic`.

### Verification

- Local Python suite: **366 passed in 83.85s** (0 failed, 0 skipped) on Windows
  11 / Python 3.14.6.
- Native CTest: **18/18 passed** in 17.13s.
- Branch coverage: **82%** (CI threshold 70%).
- Mutation harness: **11/11 killed**, baseline clean.
- Shader compilation: **12/12** sources compile with 0 warnings/errors.
- Version consistency: all surfaces report `2.2.2`.
- Exact-SHA Linux/Windows CI and release-asset checks are recorded in the PR and
  published release; they are not inferred from these local runs.

### Tests

- Added `test_statevector_contract`, `test_mps_contract` and
  `test_qpu_facade_contract`; strengthened the 300-qubit GHZ diagnostic and the
  MPS saturation checks. The MPS suite includes an optimal rank-one truncation
  regression against closed-form singular values, so a factorisation that
  reconstructs the tensor with non-orthonormal factors cannot pass as an SVD.

### Fixed — mutation harness bytecode cache

- The mutation harness no longer reuses cached bytecode from a same-size
  mutant after restoring the source. Checks run with
  `PYTHONDONTWRITEBYTECODE=1`, and the target module's `__pycache__` entry is
  invalidated on both apply and restore. This removes a spurious baseline
  failure observed in the scheduled nightly run after `v2.2.1`. The guard is
  covered by a regression test that pins the source mtime to reproduce the
  original race.

## [2.2.1] — 2026-10-26

Patch release. It fixes correctness and refusal defects in the Python QASM
reader, the capability routing layer, Qiskit measurement handling, Path D
observables and Path C resource accounting. It adds no simulator and no GPU
acceleration.

### Fixed — one strict QASM contract for Python and native

- The Python reader is no longer a permissive Qiskit-based loader. It is a
  strict, line-oriented OpenQASM subset parser that fails closed on unknown
  gates, missing semicolons, undeclared registers, out-of-range indices and
  malformed operands, with the same `{line, category, message}` categories as
  the native parser.
- Multiple quantum/classical registers now receive global offsets in
  declaration order (`qreg a[2]; qreg b[3]` maps `b[0]` to qubit 2), so the
  width is the sum of register sizes rather than `max(register_size)`.
- Whole-register operands expand in arity-sized chunks, matching native
  semantics; a non-multiple width is `operand_count_mismatch`.
- Angle expressions use a bounded recursive-descent grammar
  (`_MAX_ANGLE_LENGTH`, `_MAX_ANGLE_DEPTH`) instead of Python `eval()`;
  `nan`, `inf`, division by zero, `**`, unbalanced parentheses and trailing
  tokens are `invalid_parameter`.
- The parser no longer treats a bare `OPENQASM` keyword as a gate or silently
  drops statements it does not understand.
- Classical-bit remapping is refused explicitly instead of dropping the target;
  terminal measurement suffixes are sorted by qubit, mid-circuit measurements
  are preserved at their source position.

### Fixed — capability routing and Qiskit measurement semantics

- Added `cqhecs/gate_manifest.py` as the single source of truth for gate arity,
  parameter counts, per-path support and Clifford status. The analyzer, router,
  Qiskit `Target` and every backend derive their capabilities from it.
- `cp`, `crz`, `rx`, `ry`, `u1` and `p` are classified per parameter angle
  instead of by the first angle or by name alone. `cp(π/2)` is no longer offered
  to Path A; it is routed to Path C and executed or refused before execution.
- Removed the false Path A `reset` capability. `reset`, mid-circuit measurement
  and classically controlled operations are refused before execution.
- `normalize_measurements` rejects mid-circuit measurement instead of moving it
  to the end, preserves repeated measurements into distinct classical bits, and
  keeps non-contiguous classical indices.
- The Qiskit `Target` now covers every implemented path gate (`cp`, `cu1`,
  `crx`, `cry`, `crz`, `cz`, `swap`, ...) on a conservative linear coupling map;
  unimplemented gates stay absent so `transpile(qc, backend=backend)` cannot
  emit them.
- `CQHecsBackend.run()` requires counts, so a counts request cannot silently
  fall through to Path D expectation values.

### Fixed — Path D observables and certification

- Observable strings are parsed as a strict grammar. Trailing characters after
  valid tokens, malformed indices and out-of-range qubits are rejected instead
  of being partially accepted.
- `bool` masks, negative masks and masks wider than the system are rejected.
- Duplicate Pauli factors are simplified algebraically (`Z[i] Z[i] = I`).
- Per-observable bounds are reported; aggregate bounds are not invented.
- Marginal samples remain explicitly labelled as **not** a joint distribution.

### Fixed — Path C resource accounting

- `ram_budget_mb` is enforced fail-closed before a state update; a refusal keeps
  the last valid state and reports an atomic diagnostic.
- Process RSS and peak RSS are reported separately from internal NumPy tensor
  bytes (`process_rss_mb`, `process_peak_rss_mb`,
  `rss_measurement_available`), and are `None`/`false` when the platform cannot
  measure them. Tensor bytes are never presented as RSS.
- `numerical_error_bound` remains `None`; numerical rank reduction at the
  `1e-13` relative threshold is documented separately from a deliberate bond
  cut-off, and `exact=True` means "no deliberate truncation", not symbolic
  exactness.

### Changed — documentation and gates

- `docs/QASM_CONTRACT.md` now describes both parsers, register offsets,
  measurement placement and the deliberately different native/Python gate
  ceilings.
- The mutation anchor for T-count classification follows the new shared
  `_t_resource` classifier.
- Added `tests/test_hardening_v221.py`: 55 focused regression tests, including
  Python/native differential categories and Qiskit transpilation of Path C gates.

### Verification

- Local Python suite: **309 passed** with `CQ_HECS_REQUIRE_NATIVE=1`.
- Native CTest: **14/14 passed**.
- Branch coverage: **81 %** (CI threshold 70 %).
- Mutation harness: **11/11 killed**, baseline clean.
- Cloud Build: **not verified** (no project/credential verification available).
- Physical GPU compute: **not verified**.

## [2.2.0] — 2026-10-23

This is a hardening release. It adds structured diagnostics and explicit engine
classification, and it replaces several false-green tests and fail-open code
paths with fail-closed contracts. It does not add a new simulator, GPU
acceleration, or a new exactness claim.

### Fixed — native QASM parsing and execution

- **The native QASM parser no longer repairs invalid input.** Missing
  semicolons, unknown gates, malformed or non-finite angle expressions,
  out-of-range register references and block comments are rejected with a
  structured `{line, category, message}` error. The previous parser accepted
  several of these and executed a partially interpreted circuit.
- **`cq_hecs qasm` now returns exit code 2 for invalid circuit input** and emits
  a JSON error document on stdout when `--json` is used. Diagnostics remain on
  stderr.
- **The native QASM result is labelled honestly.** The `engine_class` is
  `legacy_z8_phase_ledger`, `statevector_simulation` is `false`, and the banner
  uses the canonical `CQ_HECS_VERSION` instead of a stale hardcoded string.
- **The C-ABI parser shares the same fail-closed semantics.** `cq_execute_qasm`
  refuses invalid circuits and returns `-3` for parse errors.
- Added `test_qasm_contract` to CTest, covering strict parsing and bounded
  randomized robustness.

### Fixed — false telemetry and resource accounting

- `VulkanComputeScheduler.submit_workload()` no longer reports
  `completed=True` for metadata-only submissions. It reports
  `planner_only=True`; completion requires `record_completion(backend)`.
- Timing-jitter harvesting is documented as a deterministic diagnostic, not as
  proof of hardware entropy.
- `TieredMemoryGovernor.allocate()` fails closed with `MemoryError` when a page
  cannot fit, instead of silently exceeding the budget.
- `JSpaceDelta.reinflate_matrix()` validates matrix shapes and labels its
  residual as a diagnostic rather than a certified bound.

### Fixed — tests that could pass without performing their measurement

- QASM fuzz tests now assert the strict parser contract and fail (rather than
  skip) when CI sets `CQ_HECS_REQUIRE_NATIVE=1`.
- Stress, concurrency and SVD tests now separate internal accounting from RSS,
  use explicit availability skips, verify independent-instance behaviour, and
  require real truncation measurements.
- The source-level mutation harness applies exact patches to production files,
  runs independent subprocess checks, restores source byte-for-byte, and fails
  on survivors or a broken baseline. The maintained set is 11 mutants; this is
  a scoped regression gate, not a proof of correctness.

### Changed — CI and test support

- CI now has a pinned Python 3.11 dependency lane, a separate newest-dependency
  compatibility matrix, branch coverage with an enforced 70% threshold, an
  ASan/UBSan native job, minimum token permissions, and uploaded test evidence.
- Supported Python is now declared as 3.11–3.14. Python 3.9/3.10 are no longer
  claimed after reaching end of life.

### Research & verification

- See `research/v2_2/BASELINE.md` and `research/v2_2/TEST_MATRIX.md` for the
  recorded local gates and the remaining unverified surfaces (physical GPU and
  Cloud Build).

---

## [2.1.0] — 2026-10-19

This release delivers verified 200+ qubit simulation and scalable full-register
sampling across structured circuit families, adds selective observable evaluation
for Path D, hardens the mutation testing framework, and conducts a complete
corpus audit of OpenAI Math.

### Added — 200+ qubit sampling and selective evaluation

- **MPS-native sequential conditional sampling (Path C):**
  Batched sequential sampling using right-to-left environment contraction $R^{[k]}$
  and vectorized left conditional projections $L^{[k+1]}$. Allows drawing thousands
  of full-register shots from 200–300+ qubit low-entanglement MPS states without
  constructing a dense $2^n$ statevector (e.g. 300Q GHZ sampled in 0.27s with zero
  dense statevector allocation). Dense statevector conversion remains protected behind
  `MAX_STATEVECTOR_QUBITS = 20`.
- **Selective observables API (Path D):**
  Added `observables` parameter to `execute()` and CLI to evaluate explicit subsets
  of Pauli observables (e.g. across 200-qubit Bell pairs) without $O(n^2)$ observable
  pair explosion. Automatically limits evaluation to single-qubit Z for circuits with
  $n > 30$ unless pair parities are explicitly requested.
- **200+ qubit acceptance suite:**
  Added `tests/test_200q_sampling_acceptance.py` exercising 300Q GHZ on Path A,
  300Q GHZ on Path C, 200Q 1D cluster states on Path C, 200Q selective observables on
  Path D, and router verification.

### Fixed — performance and harness correctness

- **Path A wide circuit sampling:**
  Fixed a latent `self.MAX_RESAMPLE_SHOTS` AttributeError for non-all-equal wide circuits.
  Vectorized symplectic phase accumulation in `_row_sum` using an algebraic mod 4 formula,
  yielding a ~10x speedup and removing unnecessary shot resampling bottlenecks.
- **Mutation testing harness trustworthiness:**
  Removed all shortcut `return True` fallback branches in `scripts/run_mutation_tests.py`
  (mutants 1, 2, 5) and properly injected wide-counts fabrication in mutant 6. Added
  meta-tests in `tests/test_mutation_harness_meta.py` ensuring the harness fails closed
  with non-zero exit on broken baselines, surviving mutants, and harness errors.
- **Large support-size stability in TV bound:**
  Protected `hoeffding_total_variation_bound` against integer-to-float `OverflowError`
  for massive registers ($K > 60$ bits support size), correctly returning 1.0.

### Research & Verification

- **OpenAI Math corpus audit:**
  Parsed and audited all 372 manuscript families and 719 preprints from upstream
  `openai/math` snapshot (`1581d4cb`). Generated complete manifests and identified
  complexity barriers (query complexity separations $\neq$ classical circuit simulation).

---

## [2.0.0] — 2026-10-19

This release cycle was a correctness audit. Every item below is a defect that
was reproduced, fixed and covered by a regression test.

### Fixed — fabricated or silently wrong results

- **Path B returned a uniform distribution** when its rank decomposition failed
  to normalize, and returned `{'0'*n: shots}` for every circuit wider than 16
  qubits. Both were reported as `exact=True, error_bound=0.0`. It now raises.
- **Path D sampled each qubit independently** from its own `<Z_q>` marginal and
  returned the result as a joint measurement distribution. A Bell state came
  out uniform. Path D now reports certified `expectation_values` (single-qubit
  Z and parity `Z_q Z_r`); joint counts require an explicit opt-in and are
  labelled `counts_are_joint_distribution=False`.
- **Path C returned an all-zeros placeholder** for circuits wider than its
  sampling limit. It now reports no counts rather than inventing them.
- **Path A inflated 100 real samples** up to the requested shot count for wide
  circuits. It now reports the number of shots actually drawn.

### Fixed — silently ignored gates

- **Path C** silently skipped any gate outside its dispatch chain and discarded
  singular values below an absolute `1e-14` cutoff while still claiming
  `exact=True`. Rank selection is now a relative roundoff floor scaled to the
  largest singular value, and the discarded mass is measured and reported.
- **Path B** silently ignored unknown gates, which hid two real bugs: Clifford
  angle `RZ` and *all* `RX`/`RY` gates were never applied. `RX`/`RY` also used
  the wrong Clifford generator (a hardcoded `Z`).
- **Path D** treated any unrecognised gate as the identity. `CZ`, `SWAP`, `RX`
  and `RY` all took that path and returned wrong answers.
- **Path A** never called its own `apply_cz`, dropped Clifford-angle
  `RZ`/`P`/`U1`, and its GHZ shortcut checked only the X block while ignoring Z.

### Fixed — bound math and the newest hardening round

- **The finite-shot confidence bound was not a TV bound.** The dimension-free
  `sqrt(ln(2/δ)/(2n))` expression violated at 73% (K=16) and 100% (K=64) for
  the uniform distribution in a direct measurement. It is replaced by the
  Weissman et al. (2003) support-aware form
  `TV ≤ sqrt(ln((2^K − 2)/δ)/(2n))`, computed in log space and clamped to 1.0;
  at K = 2 it reproduces the classic value exactly.
- **Path D's CZ rule was algebraically wrong.** `CZ†(X_a X_b)CZ` picks up a
  relative minus sign that the naive single-Pauli composition missed; every
  CZ-containing circuit was silently corrupted. The rule is now verified
  against explicit `U† P U` matrices over all two-qubit Paulis
  (`TestTwoQubitConjugationRules`).
- **Path B's two-qubit gates are vectorised.** The per-amplitude Python loop
  that forced a 16-qubit ceiling is gone; the ceiling is now 22 qubits,
  documented as an implementation limit. A vectorisation aliasing bug was
  caught by differential testing and fixed.
- **Path D evaluates all observables in one backward pass** with per-observable
  truncation kept separate, and terminates early (reporting `unresolved` with
  no values) once the bound provably exceeds the tolerance; previously deep
  circuits could run for minutes before returning unresolved.

### Fixed — bitstring ordering

Paths A and C did not use the Qiskit convention (qubit 0 rightmost): `X` on
qubit 0 of a 3-qubit circuit returned `'100'` instead of `'001'`. The native
C++ engine renders qubit 0 *leftmost*, the opposite of every Python path; its
output is now normalised, and the native engine is used only when it can
faithfully run the circuit (it has no `apply_cz` and takes two ints for
`apply_rz`).

### Fixed — fail-open routing

- The analyzer defaulted any unrecognised circuit input to **Path A**. It now
  raises `UnsupportedCircuitInput`.
- A user-forced path could silently reroute. It now raises
  `UnsupportedCircuitError` naming the offending gate.
- The router caught bare `Exception` around Path B, so a programming error
  would be misread as "try the next path". It catches only `StabilizerRankError`.
- `shots`, `seed`, `error_tolerance` and thresholds are validated before run.

### Changed — result schema

`error_bound` no longer conflates three different things. Results now carry
`error_bound` (deliberate approximation), `numerical_error_bound` (measured
float roundoff, where derivable) and `sampling_error_bound` (finite-shot
concentration bound, support-size dependent — see below). These are composed
by `total_error_bound` **only** when they target the same output metric; a
result can no longer report zero total error while actually being a finite-shot
estimate.

### Added

- **`cq-hecs` CLI**: one supported entry point (`version`, `doctor`,
  `backend list`, `analyze`, `run`, `verify`, `benchmark smoke`), registered via
  `[project.scripts]`. `--format json` emits exactly one JSON document on
  stdout; diagnostics go to stderr; exit codes are stable.
- **`cqhecs/circuit_parsing.py`**: one parser shared by all four backends.
- **`cqhecs/circuit_library.py`**: named circuits shared by the CLI and tests.
- **`scripts/version.py` / `scripts/check_version.py`**: one canonical version
  and a validator that fails CI when any public surface disagrees.
- **73 new tests** (`tests/test_correctness_contracts.py`,
  `tests/test_cli_contract.py`) validating every fix above against
  `qiskit.quantum_info.Statevector` references.

### Changed — build and release

- Build artifacts now go to `${CMAKE_BINARY_DIR}/bin` instead of the source tree.
- The core is compiled once into an object library instead of ~14 times.
- `CQ_ENABLE_AVX2` is target-scoped, so it can no longer make every binary
  require AVX2 hardware.
- `release.yml` resolves assets from the tag, verifies the tag matches the
  canonical version, smoke tests the built wheel in a clean venv, and verifies
  every asset exists before publishing.

### Documentation

Removed unsupported claims: "100% Cross-Vendor", "HARDWARE_VERIFIED" on AMD
hardware, "100% Certified (62/62)", and the estimated-VRAM-vs-measured-VRAM
comparison. The hardware matrix now distinguishes `CI_VERIFIED`,
`LOADER_VERIFIED` and `NOT_VERIFIED`. `docs/BENCHMARKS.md` is marked
STALE/HISTORICAL because those tables predate these fixes.

---

## [v0.2.0] - 2026-09-01

### Added
- **Vulkan 1.3 Hardening & Automated SPIR-V Compilation**: Integrated automated compilation and verification of all 12 compute shaders (`.comp` -> `.spv`) via `glslangValidator --target-env vulkan1.3 -V` in CMake and GitHub Actions CI. Provides vendor-agnostic compute across AMD, Intel, NVIDIA, and Apple/MoltenVK.
- **Exact Giles-Selinger Ring Arithmetic $\mathbb{Z}[1/\sqrt{2}, i]$**: Bit-exact ring implementation for Clifford+T quantum circuits, eliminating floating-point rounding drift.
- **VulkanComputeScheduler**: Queue submission manager, memory barrier recording, optimal workgroup dispatch calculation, and tiered storage offload governor.
- **EntanglementAdaptiveRouter**: Dynamic selection between Stabilizer (CPU), Stabilizer Rank, Vulkan-MPS, and Path D (Certified Sparse-Pauli-Dynamics).
- **Vulkan-MPS Comparative Benchmark Suite**: Reproducible benchmarks against Qiskit Aer MPS and cuTensorNet references, demonstrating Area-Law memory efficiency and honest Volume-Law physical boundaries.

### Changed
- **Functional Architecture Refactoring**: Eliminated legacy heuristics in favor of deterministic, functional technical components (`VulkanComputeScheduler`, `EntanglementAdaptiveRouter`).
- **Cryptographic Testbench Correction**: Standardized round counts to real specifications (ChaCha20: 20 rounds, SHA-256: 64 steps, BLAKE2b: 12 rounds) and clarified module as an algebraic verification testbench with zero preimage claims.
- **Unified License**: Resolved all licensing contradictions by standardizing exclusively on the Apache License 2.0.

### Verified Remote CI Logs (Ubuntu Linux & Windows MSVC 100% Green)
- **CI Run 1 (Commit `88dc726`):** [GitHub Actions Run 33562814848](https://github.com/timfromhcs/CQ-HECS/actions/runs/33562814848) — Duration: 2m55s (Ubuntu) | 12/12 Vulkan Shaders | 89/89 Pytest | 13/13 CTest | 100% Mutation Killed.
- **CI Run 2 (Commit `9c98d9d`):** [GitHub Actions Run 33563158293](https://github.com/timfromhcs/CQ-HECS/actions/runs/33563158293) — Duration: 3m03s (Ubuntu) | 12/12 Vulkan Shaders | 89/89 Pytest | 13/13 CTest | 100% Mutation Killed.
- **CI Run 3 (Dual-OS Matrix, Commit `62d3149`):** [GitHub Actions Run 33564612795](https://github.com/timfromhcs/CQ-HECS/actions/runs/33564612795) — **Ubuntu 24.04 (2m04s) & Windows Server 2025 (5m06s)** | 12/12 Vulkan Shaders on both OSs | 89/89 Pytest | 13/13 CTest | 100% Mutation Killed.

---

## [v0.1.0] - 2026-09-01

### Added
- **Clean Slate Release & Four-Path Architecture**:
  - Path A: Stabilizer-Tableau (Aaronson-Gottesman polynomial simulation).
  - Path B: Stabilizer-Rank-Decomposition (Bravyi-Smith-Smolin scaling with T-count).
  - Path C: Exact MPS with NVMe Tiered Paging (zero silent $\chi=48$ truncation).
  - Path D: Certified Sparse-Pauli-Dynamics with proven error bounds $\Delta \le \sum |c_P|$.
- **Qiskit BackendV2 Interface**: Drop-in execution for Qiskit circuits with automatic routing.
- **Adversarial Stim & Qiskit Aer Benchmarks**: Differential verification on GHZ and Clifford+T circuits.
- **Deterministic Mutation Testing**: 100% mutation score across critical architectural paths.

---

## [v4.5.0] - 2026-09-01 (Pre-Clean-Slate Legacy Reference)

### Added
- Monolithic Zero-Dependency Executable (`cq_hecs.exe`) and C-ABI Shared Library (`cq_hecs.dll`).
- Embedded SPIR-V shaders in C++ headers.
- Multi-thread concurrency stress harness (16 threads).
- Tiered VRAM governor keeping active memory $< 120$ MB.
- 5 Interlocking J-Spaces for ARX carry-shadow separation, exact cyclotomic phase ring, and SAT solving.
