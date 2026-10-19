# CQ-HECS v2.1 Baseline Record

Recorded on 2026-10-19 at the start of the v2.1 research and release mission cycle, in strict compliance with `GEMINI.md` §2. Every entry is labeled according to the required evidence categories: **observed locally**, **observed in GitHub Actions**, **derived from source**, **literature claim**, **hypothesis**, or **not yet verified**.

---

## 1. Git & Repository State

| Item | Value | Evidence Label |
| :--- | :--- | :--- |
| Upstream remote URL | `https://github.com/timfromhcs/CQ-HECS.git` | **observed locally** |
| Base `main` commit SHA | `ef7cbbda47c39cdad0f77050c1e6a8c0c2727cf1` (Merge PR #3) | **observed locally**, **observed in GitHub Actions** |
| Published release tag | `v2.0.0` (annotated tag `9ed0a3af0b4dd154ba01ebe0644a8afd46ecee95`) | **observed locally** |
| Commit tagged by `v2.0.0` | `19df10cdc80f26dc9bb81b4438192c084845f477` (Merge PR #2) | **observed locally**, **observed in GitHub Actions** |
| Post-v2.0.0 commit on `main` | `714d675fix(release): cover every published asset in sha256sums.txt` (PR #3) | **observed locally**, **observed in GitHub Actions** |
| Active mission branch | `agent/v2-1-200q-20261019` (branched from `origin/main` at `ef7cbbd`) | **observed locally** |
| Canonical software version at baseline | `2.0.0` | **observed locally**, **derived from source** |
| Target release version | `2.1.0` (SemVer minor feature release) | **hypothesis** |
| Open pull requests on upstream | 0 open PRs | **observed in GitHub Actions** / GitHub API |

---

## 2. Host Execution Environment

| Component | Detailed Specification | Evidence Label |
| :--- | :--- | :--- |
| Operating System | Windows 11 Pro 64-bit (build 10.0.26200, SP0) | **observed locally** |
| Host CPU | AMD Ryzen 7 7735HS with Radeon Graphics (8 physical cores, 16 logical processors) | **observed locally** |
| Total Physical RAM | 19.79 GB (~20 GB DDR5) | **observed locally** |
| Python Interpreter | Python 3.14.6 (tags/v3.14.6:c63aec6, MSC v.1944 64 bit AMD64) | **observed locally** |
| NumPy Version | 2.4.6 | **observed locally** |
| Qiskit Version | 2.5.1 | **observed locally** |
| Qiskit Aer Version | 0.17.2 | **observed locally** |
| Stim Version | 1.16.0 | **observed locally** |
| C++ Compiler | Microsoft Visual C++ Compiler 19.51.36231 (Visual Studio BuildTools 18) | **observed locally** |
| CMake Version | 4.4.0 (generator: Visual Studio 18 2026 / Visual Studio 17 2022) | **observed locally** |
| Vulkan SDK | LunarG Vulkan SDK 1.4.357.0 at `C:\VulkanSDK\1.4.357.0` | **observed locally** |
| Vulkan Instance Version | 1.4.357 (`vulkaninfo --summary`) | **observed locally** |
| Vulkan Loader | `vulkan-1.dll` present and runtime-loadable | **observed locally** |
| Enumerated Physical GPU 0 | AMD Radeon(TM) Graphics (Device Type: `PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU`, Vendor ID: `0x1002`, Device ID: `0x1681`, Driver: AMD proprietary 2.0.353 / 26.6.1) | **observed locally** |
| Physical GPU Compute Dispatch | **NOT VERIFIED** (Enumeration observed; compute shader dispatch under instrumented capture is unverified) | **not yet verified** |

---

## 3. Baseline Verification Commands & Results

All commands executed locally on commit `ef7cbbda47c39cdad0f77050c1e6a8c0c2727cf1` prior to functional changes:

| Test / Check | Exact Command | Exit Code | Observed Output / Result | Evidence Label |
| :--- | :--- | :--- | :--- | :--- |
| Version Script | `python scripts/version.py` | 0 | `2.0.0` | **observed locally** |
| Version Consistency | `python scripts/check_version.py` | 0 | `Version consistency OK: all surfaces report 2.0.0` | **observed locally** |
| Truncation Audit | `python scripts/verify_no_silent_truncation.py` | 0 | `[PASS] no silent-truncation or fabricated-result patterns found.` | **observed locally** |
| Python Test Suite | `python -m pytest` | 0 | `209 passed, 2 warnings, 65 subtests passed in 21.94s` | **observed locally** |
| Native CTest Suite | `ctest --test-dir build -C Release --output-on-failure` | 0 | `13/13 passed in 7.60 sec (100% tests passed)` | **observed locally** |
| Embedded Self-Test | `.\build\bin\Release\cq_hecs.exe test` | 0 | `ALL 7 TESTS PASSED (0 ERRORS)` | **observed locally** |
| Vulkan Compute Shaders | `python scripts/verify_vulkan_shaders.py` | 0 | `All 12 Vulkan 1.3 compute shaders compiled & verified with 0 warnings / 0 errors.` | **observed locally** |
| Mutation Testing Harness | `python scripts/run_mutation_tests.py` | 0 | `Baseline OK: all 7 checks hold. 7/7 killed (100.0%). Exit 0.` | **observed locally** |
| CLI Doctor Smoke Test | `python -m cqhecs.cli doctor` | 0 | All backends, dependencies (numpy, qiskit, aer, stim), native binding (`_cqhecs_core`), and vulkan loader available | **observed locally** |
| CLI Backend List | `python -m cqhecs.cli backend list` | 0 | Paths A, B, C, D enumerated with supported gates and operational contracts | **observed locally** |

---

## 4. Observed Warnings and Known Limitations in Baseline

1. **Qiskit Deprecation Warning in Test Suite:**
   - Location: `tests/python/test_qiskit_backend_contract.py:218`
   - Cause: `qiskit.circuit.library.basis_change.qft.QFT` is deprecated as of Qiskit 2.1 and slated for removal in 3.0.
   - Evidence Label: **observed locally**.

2. **Path C Dense Statevector & Sampling Ceiling:**
   - In `cqhecs/backends/path_c_mps_exact.py`, sampling is currently restricted to circuits with `<= 20` qubits because it converts the MPS to a dense statevector (`to_statevector()`) to draw counts. Above 20 qubits, no counts are returned.
   - Evidence Label: **derived from source**, **observed locally**.

3. **Path A Shot Resampling Cap:**
   - In `cqhecs/backends/path_a_tableau.py`, wide-circuit measurements have used a resampling cap (`MAX_RESAMPLE_SHOTS = 100`). Requesting 1,000 shots on wide circuits did not deliver 1,000 independent samples.
   - Evidence Label: **derived from source**.

4. **Path B Practical Dimension Limit:**
   - In `cqhecs/backends/path_b_stabilizer_rank.py`, vectorized dense statevector limit is 22 qubits (`MAX_STATEVECTOR_QUBITS = 22`).
   - Evidence Label: **derived from source**.

5. **Path D Expectation-Only and Unbounded Pair Observables:**
   - Path D only computes expectation values (single-qubit Z and pair parities). It does not produce joint counts. Requesting all pairs for 200+ qubits requires $O(n^2)$ observables (~20,000 pairs), which is computationally prohibitive unless bounded by an explicit observable request API.
   - Evidence Label: **derived from source**, **observed locally**.

6. **Physical GPU Compute Status:**
   - The integrated AMD GPU is enumerated via the Vulkan loader. However, shader compute execution on this physical hardware has not been instrumented or verified against independent CPU reference outputs.
   - Evidence Label: **not yet verified**.
