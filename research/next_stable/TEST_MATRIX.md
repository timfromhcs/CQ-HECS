# Test matrix — next Stable after v2.2.1

Platform: Windows 11, Python 3.14.6, MSVC 19.44, CMake Release.
Baseline: `9fe014b5509096ebe203ebae26cc146cb13b0a69`.
Candidate results were produced on the task branch with the changes described
in `FINDINGS.md`. Final exact-SHA CI results are recorded in the pull request /
release evidence, not assumed here.

## Local gates after the fixes

| Gate | Command | Result |
| :--- | :--- | :--- |
| Version surfaces | `python scripts/check_version.py` | PASS — all `2.2.2` |
| Python compile | `python -m compileall -q cqhecs tests scripts python_bridge` | PASS (exit 0) |
| Python suite | `python -m pytest tests/ -q` | **311 passed** |
| Native build | `cmake --build build --config Release` | PASS (exit 0) |
| Native suite | `ctest --test-dir build -C Release --output-on-failure` | **17/17 passed** |
| Branch coverage | `python -m coverage run --branch --source=cqhecs -m pytest tests/ -q` then `python -m coverage report --fail-under=70` | **81%**, exit 0 (CI threshold 70%) |
| Silent-truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS |
| Shader compilation | `python scripts/verify_vulkan_shaders.py` | PASS — 12/12 shaders |
| Mutation harness | `python scripts/run_mutation_tests.py` | 11/11 mutants killed, clean baseline |
| Package build | `python -m build` | wheel + sdist `2.2.2` built |
| Clean install smoke | fresh venv, install wheel, `cq-hecs --help/version/doctor`, JSON bell run | PASS — one JSON document, counts `00`/`11` sum to shots |
| Checksums | `python scripts/generate_sbom_and_checksums.py` + independent SHA256 recompute | PASS — wheel, sdist and SBOM hashes match |

`verify_vulkan_shaders.py` proves shader source compiles. It is **not** a
physical-GPU compute test and no GPU acceleration is claimed.

## New native contract suites

| Suite | What it actually exercises |
| :--- | :--- |
| `test_statevector_contract` | `\|0>`, `\|1>`, `\|+>`, 0.8/0.2 asymmetric state, Bell state; seeded sampling sums to shots; measurement collapse/renormalisation; width boundary 0/28/29 and hostile index errors |
| `test_mps_contract` | 1q gates vs dense reference; Bell; adjacent CNOT in both control/target orders; non-adjacent CNOT routing; rank growth and saturation; truncation diagnostic and rank retention under repeated truncation; complex-SVD optimal rank-one truncation against closed-form singular values; non-GHZ bond-2 sampling support (4 outcomes at 1/4); asymmetric 0.8/0.2 sampling; 24-gate random differential vs dense; error paths; 300-qubit GHZ sampling |
| `test_qpu_facade_contract` | Terminal `MEASURE` accepted without state mutation; every shot accounted for; Bell support; mid-circuit measurement rejected; unsupported opcode throws; 256-qubit GHZ sampling; `q[256]` rejected instead of truncating to 8 bits |
| `test_300q_stress` | Planner/memory-governor arithmetic and allocation budget; gate/sampling calls fail closed |
| `test_ghz300` | GHZ correlation invariant (`non_parity == 0`), seeded binomial split within 5σ, shot accounting |

## Updated existing suites

| Suite | Change |
| :--- | :--- |
| `test_bitexact_and_stress` | 300-qubit MPS memory contract retained; 64-qubit saturation still asserts bond growth; no exact-50/50 claim |
| `tests/test_qiskit_and_transpiler.py` | GHZ-256 (largest 8-bit-addressable register) executes and samples real counts; GHZ-300 is required to raise instead of silently wrapping indices |
| `tests/test_mps_300qbits.py` | Unchanged; it tests the Python memory/matrix helpers, not native state evolution |
| `tests/test_qasm_contract.py` | Unchanged; re-run and still pins the legacy parser's fail-closed contract |

## Boundaries and statistical policy

- Deterministic analytic invariants (norm, support, parity) are asserted exactly
  where the implementation is exact.
- Sampling tests use fixed seeds and derived statistical bands:
  `sigma = sqrt(N p (1-p))`, acceptance at 5σ, or per-outcome tolerance stated
  in the test. No test requires an unrelated RNG to reproduce the same stream.
- Resource boundaries use exact configured limits (`max_bond_dim`,
  `MAX_SUPPORTED_QUBITS`) and check both sides where the API permits it.
- Unverified/unsupported paths (`RX/RY/U3/SWAP` on the MPS facade, >255-qubit
  QASM operands, physical GPU dispatch) are tested for refusal, not skipped.

## Not run here

| Gate | Status | Reason |
| :--- | :--- | :--- |
| Linux/macOS native build | NOT RUN locally | Windows host; delegated to GitHub Actions |
| ASan/UBSan | NOT RUN locally | MSVC Release build; delegated to CI where configured |
| Cloud Build | NOT VERIFIED | Requires project/trigger access; see release report |
| Physical GPU dispatch | NOT VERIFIED | No physical Vulkan compute device test performed |
