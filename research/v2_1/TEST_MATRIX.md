# CQ-HECS v2.1 Test Matrix & Verification Coverage

Recorded on 2026-10-19 for the v2.1 engineering cycle. Every entry is labeled with its evidence class: **observed locally**, **observed in GitHub Actions**, **derived from source**, **literature claim**, **hypothesis**, or **not yet verified**.

---

## 1. Test Tiers & Execution Summary

| Tier | Tool / Runner | Command | Test Count | Pass / Fail / Skip | Duration | Evidence Label |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Python Unit & Contract** | `pytest` 8.x | `python -m pytest` | 209 tests (65 subtests) | 209 passed, 0 failed, 0 skipped, 2 warnings | ~22s | **observed locally** |
| **Native CTest** | `ctest` (MSVC) | `ctest --test-dir build -C Release --output-on-failure` | 13 tests | 13 passed, 0 failed, 0 skipped | 7.60s | **observed locally** |
| **Embedded Native Self-Test** | `cq_hecs.exe` | `.\build\bin\Release\cq_hecs.exe test` | 7 tests | 7 passed, 0 failed, 0 errors | < 1s | **observed locally** |
| **Shader Compilation** | `glslangValidator` | `python scripts/verify_vulkan_shaders.py` | 12 compute shaders | 12 passed, 0 warnings, 0 errors | < 2s | **observed locally** |
| **Mutation Testing** | `run_mutation_tests.py` | `python scripts/run_mutation_tests.py` | 7 mutants + baseline | 7/7 killed (100%), baseline OK, exit 0 | < 5s | **observed locally** |
| **Version Consistency** | `check_version.py` | `python scripts/check_version.py` | 8 surfaces checked | All consistent (2.0.0) | < 1s | **observed locally** |
| **Truncation Audit** | `verify_no_silent_truncation.py` | `python scripts/verify_no_silent_truncation.py` | AST regex audit | PASS, 0 patterns found | < 1s | **observed locally** |
| **CLI Smoke Tests** | `cqhecs.cli` | `python -m cqhecs.cli doctor` / `backend list` | Core diagnostic commands | All commands exit 0 | < 2s | **observed locally** |

---

## 2. Test Suites Detailed Breakdown

### A. Python Test Suite (209 Tests)

Located in `tests/`:

1. `test_clifford_tableau.py`: Symplectic tableau updates, Clifford gates (H, S, CX, CZ, SWAP), Pauli frame tracking, stabilizer measurement.
2. `test_stabilizer_rank.py`: Stabilizer rank decompositions of T, Tdg, RZ gates, norm verification, branch recombination, statevector evaluation up to 22 qubits.
3. `test_mps_simulator.py`: MPS tensor representations, site-to-site SVD, unitary preservation, bond dimension truncation/paging.
4. `test_sparse_pauli_dynamics.py`: Backward Heisenberg propagation, CZ sign correction, Pauli truncation mass bound, expectation value certification.
5. `test_correctness_contracts.py`: Fail-closed routing, seed determinism, bitstring endianness (Qiskit convention), Weissman support-aware finite-shot TV bound.
6. `test_qiskit_and_transpiler.py`: Qiskit BackendV2 contract, circuit conversion, classical bit mapping.
7. `test_fuzz_qasm.py`: OpenQASM fuzzing, malformed floats, comments, missing semicolons, unknown gate rejection.
8. `test_fuzz_sat.py`: SAT/DIMACS parsing boundaries, contradiction handling, empty CNF clauses.

### B. Native C++ CTest Suite (13 Tests)

Located in `build/` (built from `tests/` C++ sources):

1. `test_reversibility`: Matrix reversibility, symplectic inner product preservation.
2. `test_ghz300`: Native 300-qubit GHZ state representation and parity.
3. `test_constraint_solver`: Cuckoo loop pruning and ARX inversion logic.
4. `cq_hecs_cpp_hardening`: Memory bounds and integer overflow checks.
5. `cq_hecs_full_verification`: Monolithic C++ engine verification.
6. `test_bitexact_and_stress`: Deterministic float vs exact integer representations.
7. `test_exact_algebra`: GF(2) symplectic linear algebra operations.
8. `test_stabilizer`: Clifford operations in native C++.
9. `test_hybrid_mps`: Native MPS bond dimension operations.
10. `test_stress_limits`: Large-scale state allocation boundaries.
11. `test_exact_ring`: Z8 phase and cyclotomic ring operations.
12. `test_stabilizer_extreme`: Extreme scale stabilizer tracking.
13. `test_300q_stress`: 300-qubit lattice stress allocation.

### C. Compute Shader Validation (12 Shaders)

All 12 shaders compiled to SPIR-V 1.3 via `glslangValidator.EXE` (Vulkan SDK 1.4.357.0):
- `bond_svd.comp` (4,992 B)
- `cordic.comp` (9,112 B)
- `state_reset.comp` (1,628 B)
- `tensor_contract.comp` (4,092 B)
- `cordic_gate.comp` (14,612 B)
- `cq_hecs_core.comp` (7,600 B)
- `cuckoo_prune.comp` (6,424 B)
- `explosion_shield.comp` (5,916 B)
- `mcwf_noise.comp` (4,976 B)
- `mps_contract.comp` (7,532 B)
- `ring_multiply.comp` (5,756 B)
- `tensor_contract_2q.comp` (7,724 B)

---

## 3. Platform & Hardware Test Matrix

| Platform / Environment | Runner Type | Test Coverage | Status | Evidence Label |
| :--- | :--- | :--- | :--- | :--- |
| **Windows 11 (AMD Ryzen 7 7735HS)** | Local Host | Full Python suite (209), CTest (13), self-test (7), mutation (7), shaders (12), CLI | **VERIFIED** | **observed locally** |
| **Ubuntu 24.04 (GitHub Actions)** | CI Runner | Python suite, CTest, shader compilation, wheel build, clean venv smoke | **VERIFIED** in CI run `39262998612` | **observed in GitHub Actions** |
| **Windows Server 2022 (GitHub Actions)** | CI Runner | Python suite, CTest, MSVC build, wheel build, clean venv smoke | **VERIFIED** in CI run `39262998612` | **observed in GitHub Actions** |
| **Software Vulkan (Lavapipe)** | Linux CI Runner | Enumeration and SPIR-V pipeline loading | **VERIFIED** in CI | **observed in GitHub Actions** |
| **Physical GPU Compute** | AMD Radeon iGPU / Discrete GPU | Shader dispatch under runtime instrumentation and output check against CPU | **NOT VERIFIED** | **not yet verified** |

---

## 4. Planned Test Additions for v2.1.0

To achieve release readiness for v2.1.0, the following new test suites will be introduced:

1. **MPS Sequential Sampler Verification:**
   - 200, 256, and 300-qubit GHZ state sampling (asserting counts support is strictly $\{'0'\dots'0', '1'\dots'1'\}$).
   - 1D cluster state sampling (verifying stabilizer parity correlations $X_{i-1} Z_i X_{i+1} = +1$).
   - Statistical distribution test vs exact `Statevector` / `Aer` on small sizes ($n=4\dots16$) asserting total variation within Weissman confidence bound.
   - Resource refusal test: verify state remains uncorrupted if bond dimension exceeds memory limit.
   - Evidence Label: **hypothesis**.

2. **Path A Full-Shot Stabilizer Sampling:**
   - 200, 256, 300-qubit Clifford circuits with `shots=1000` and `shots=5000`.
   - Assert `sum(counts.values()) == shots` without clamping or resampling caps.
   - Differential comparison against `Stim` on identical seeded circuits.
   - Evidence Label: **hypothesis**.

3. **Selective Observables API Tests:**
   - Request bounded subset of observables on 200+ qubits (e.g. 5 specific $Z_i$ or parities).
   - Verify execution runtime and memory scale with requested observable count, not $O(n^2)$.
   - Evidence Label: **hypothesis**.

4. **Mutation Harness Meta-Tests:**
   - Test harness self-verification: supply a broken baseline (assert non-zero exit).
   - Supply a surviving mutant (assert non-zero exit).
   - Supply a killed mutant (assert zero exit).
   - Evidence Label: **hypothesis**.
