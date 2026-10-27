# Test matrix — next Stable after v2.2.1

Platform: Windows 11, Python 3.14.6, MSVC 19.44, CMake Release, Vulkan SDK
1.4.357.0.

## Cycle 2 — post-merge hardening (base `812da80`)

Base: `812da806d9b4528f1c4f8ccd3cbb7b37b6f009ce` (`main`).
Branch: `agent/cq-hecs-v2.2.2-stable-hardening`.
Candidate results below were produced on this branch with the changes in
`FINDINGS.md`. Final exact-SHA CI results are recorded in the pull request /
release evidence, not assumed here.

### Local gates after the fixes (2026-10-27)

| Gate | Command | Result |
| :--- | :--- | :--- |
| Version surfaces | `python scripts/check_version.py` | PASS — all `2.2.2` |
| Python compile | `python -m compileall -q cqhecs tests scripts` | PASS (exit 0) |
| Python suite | `$env:PYTHONPATH="."; python -m pytest tests/ -q` | **366 passed in 83.85s** (0 failed, 0 skipped) |
| Native build | `cmake --build build --config Release --parallel` | PASS (exit 0) |
| Native suite | `ctest --test-dir build -C Release --output-on-failure` | **18/18 passed** in 17.13s |
| Branch coverage | `python -m coverage run --branch --source=cqhecs -m pytest tests/ -q` then `python -m coverage report --fail-under=70` | **82%**, exit 0 (CI threshold 70%) |
| Silent-truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS |
| Shader compilation | `python scripts/verify_vulkan_shaders.py` | PASS — 12/12 shaders, 0 warnings/errors |
| Mutation harness | `python scripts/run_mutation_tests.py` | 11/11 mutants killed, clean baseline |
| Workflow YAML | `python -c "import yaml; yaml.safe_load(...)"` for ci/nightly/release | PASS |
| Action pins | `git ls-remote --tags` for each pinned action | PASS — SHAs match `v7.0.1`, `v7.1.0`, `v7.0.2`, `v3.0.3` (peeled commit), `v1.7.0` |
| `git diff --check` | `git diff --check` | PASS for changed non-mission files; `GEMINI.md` retains pre-existing operator trailing spaces (not edited) |

`verify_vulkan_shaders.py` proves shader source compiles. It is **not** a
physical-GPU compute test and no GPU acceleration is claimed.

### New and strengthened suites in cycle 2

| Suite | Tests | What it actually exercises |
| :--- | ---: | :--- |
| `tests/test_path_c_operand_order.py` | 8 | Reversed (`q1 > q2`) CX/CP/SWAP and non-adjacent gates vs `Statevector`; backend CRX/CRY/CRZ in both operand orders at fidelity 1.0 |
| `tests/test_path_c_resources.py` | 12 | Budget validation, pre-allocation preflight, paging, fail-closed sampling refusal, missing/corrupt page `MPSResourceError`, shot/size ceilings |
| `tests/test_parser_strictness.py` | 18 | Qiskit measurement remap rejection, terminal measurement normalisation, integral-only index coercion, scalar operand rejection, wider parser contract |
| `tests/test_circuit_size_limits.py` | 3 | Per-backend width ceilings refuse before allocation (A/D 4096, B 22, C 4096) and shot ceilings |
| `tests/test_property_parser.py` | 5 | Deterministic Hypothesis properties for the strict parser |
| `tests/test_fuzz_sat.py` | 14 | 30 s subprocess timeout; adversarial DIMACS (oversized header, bad literal, truncated clause) never reported as UNSAT |
| `tests/test_adversarial_aer_and_stim.py` | 6 | Statevector fidelity, 5σ/TVD sampling envelopes, untruncated Aer MPS, Aer statevector for `crx`/`cry` |
| `tests/test_svd_precision.py` | 5 | Ill-conditioned/degenerate spectra, residual diagnostics, no-truncation roundoff |
| `tests/cpp/test_sat_parser.cpp` (CTest `test_sat_parser`) | 1 suite | Strict DIMACS grammar, hash coverage, literal/header bounds, timeout classified as error |
| `tests/python/test_qiskit_backend_contract.py` | — | QFT via `synth_qft_full(4)` (no deprecation call) |

### Updated existing suites

| Suite | Change |
| :--- | :--- |
| `tests/test_parser_strictness.py`, `tests/python/test_qiskit_backend_contract.py` | Measurement mapping and QFT updates |
| `tests/test_fuzz_sat.py` | Timeout and malformed-input expectations |
| `tests/test_adversarial_aer_and_stim.py` | Real differential assertions replace overlapping-key comparison |
| `tests/test_path_c_operand_order.py` | Adds backend-level CRX/CRY/CRZ order regression for CQ-01b |

### Boundaries and statistical policy

- Deterministic analytic invariants (norm, support, parity) are asserted exactly
  where the implementation is exact.
- Sampling tests use fixed seeds and derived statistical bands:
  `sigma = sqrt(N p (1-p))`, acceptance at 5σ, or per-outcome tolerance stated
  in the test. No test requires an unrelated RNG to reproduce the same stream.
- Resource boundaries use exact configured limits (`MAX_QUBITS`, `MAX_SHOTS`,
  `MAX_MPS_QUBITS`, `MAX_SAMPLING_ELEMENTS`) and check both sides where the API
  permits it.
- Unverified/unsupported paths (`RX/RY/U3/SWAP` on the MPS facade, >255-qubit
  QASM operands, physical GPU dispatch) are tested for refusal, not skipped.

### Not run here

| Gate | Status | Reason |
| :--- | :--- | :--- |
| Linux/macOS native build | NOT RUN locally | Windows host; delegated to GitHub Actions |
| ASan/UBSan | NOT RUN locally | MSVC Release build; delegated to CI where configured |
| Cloud Build | NOT VERIFIED | Requires project/trigger access; see release report |
| Physical GPU dispatch | NOT VERIFIED | No physical Vulkan compute device test performed |
| Windows/Linux CI on this branch | SEE PR #8 | Exact-SHA check results are recorded on pull request #8; they are not duplicated here |

## Cycle 1 — merged hardening (base `9fe014b`)

This cycle produced PR #7, merged as `812da80`. Its historical gate results are
kept for traceability; they are not evidence for cycle 2.

| Gate | Result |
| :--- | :--- |
| Version surfaces | PASS — all `2.2.2` |
| Python suite | **311 passed** |
| Native suite | **17/17 passed** |
| Branch coverage | **81%** |
| Mutation harness | 11/11 mutants killed |
| Shader compilation | 12/12 shaders |

New native contract suites in cycle 1: `test_statevector_contract`,
`test_mps_contract`, `test_qpu_facade_contract`. Strengthened:
`test_ghz300`, `test_bitexact_and_stress`, legacy Qiskit provider tests.
