# Wave A / agent A2 - native hardening evidence

Tasks: W4-17 (VkResult checks + fault injection), W4-18 (C ABI hardening), W4-19 (sanitizer lane),
T6-04 (CPU-vs-Vulkan differential, device-loss/teardown), CPU-only CI lane verification.
Environment: Windows 11, MSVC 19.51 (VS 18 BuildTools), Vulkan SDK 1.4.357, hardware GPU
"AMD Radeon(TM) Graphics" (the only Vulkan device present). No g++/working clang, no software ICD, no Linux.
Build dirs used (all A2-private): `build-a2-vk` (Vulkan ON), `build-a2-cpu` (`-DCQ_ENABLE_VULKAN=OFF`),
`build-a2-asan` (`-DCQ_ENABLE_SANITIZERS=ON`). Generator: `Visual Studio 18 2026` (the shell `CXX`/`clang++`
shim is broken, so `env -u CXX` was used).

## Findings (root causes found and fixed; each has a regression test)

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| F-A2-01 | high / CORRECTNESS | Core C ABI `cq_execute_qasm` on a >16-qubit simulator accepted T/Tdg/RZ and returned a 16-bit bitstring for a 20-qubit circuit with rc 0 (the hybrid engine keeps only a 16-qubit shadow statevector). Silent wrong answer. Now refused (`-4`, `CQ_CORE_ERR_UNSUPPORTED`), validated before any gate runs. | Reproduced against the pre-change DLL: `OLD wide T: rc= 0 b'{"0000000000000000": 4}'`. |
| F-A2-02 | high / CORRECTNESS | Facade `cq_solve_sat` ignored `SATSolverResultCPP::timed_out`/`input_valid`: a timeout surfaced as satisfiable=0 / return 10 (UNSAT-shaped). Now returns 3 (no verdict), `satisfiable=-1`; the result struct is defined on every path. | Code-confirmed (solver sets `timed_out`, `satisfiable=false`, facade returned 10). NOT reproduced dynamically (10 s budget; no fast hard instance used). |
| F-A2-03 | high / ROBUSTNESS | `cq_create_simulator(0, ..)` threw a C++ exception across the C boundary (host process killed). Every entry point is now exception-fenced; absurd sizes return NULL + last error. | Pre-change DLL: `OSError: [WinError -529697949] 0xe06d7363`. |
| F-A2-04 | medium | `cq_apply_*` took unchecked qubit indices (OOB writes); `cq_apply_rz` cast negative/huge/NaN doubles to uint32 (UB). Now range/duplicate/finite checked, angle reduced mod 2*pi; refusals change no state. | `test_c_abi_core`, `test_native_c_abi_hardening.py`. |
| F-A2-05 | medium | `cq_omniwave_bcp_eval` copied the result with a void `copy_from_buffer`: a failed map left `out_status` uninitialised while returning 0. Copies now return bool, readback failure is rc -6 and the output is never half-written. | fault test (MapMemory at readback) in `test_vulkan_bcp_differential device`. |
| F-A2-06 | medium | BCP clause database was not validated: a code whose variable index >= 32*words, non-monotone/non-zero-based offsets, or NULL codes became an out-of-bounds device read in the shader. Validated on the host (rc 1/2/4) before any device work; size limits match the Vulkan guaranteed dispatch limits (65535 per axis, 32-bit cell index). | `test_vulkan_bcp_validation` (no GPU needed), pytest twin. |
| F-A2-07 | medium | `VulkanBuffer::allocate`: `track_allocation` throws at the 3 GB ceiling (would cross the C ABI), `find_memory_type` threw, `vkBindBufferMemory`/map were unchecked, and failure paths left `m_size`/manager set so the destructor double-released the VRAM accounting. Now non-throwing, fully checked, single release. | fault test asserts accounting is exactly unchanged after CreateBuffer/AllocateMemory/BindBufferMemory failures and the 3 GB+1 request. |
| F-A2-08 | medium | `VulkanContext`: after a failed `vkQueueWaitIdle` the command buffer/descriptor set were freed while possibly still executing. Found BY the fault-injection test (red: "site 14 iteration 12", recovery failed). Fixed: drain the queue before freeing. `VK_ERROR_DEVICE_LOST` is now latched (`is_device_lost()`), later dispatches fail fast, and the C ABI returns a distinct rc -5 and re-creates the context on the next call. | red -> green in `test_vulkan_fault_device`. |
| F-A2-09 | medium | Legacy `VulkanEngine::run_cq_hecs_core_phase` used 9 unchecked Vulkan results, memcpy'd through possibly-null mapped pointers and overwrote `state_data` from an unread buffer. Rewritten fail-closed (state_data written only after a completed dispatch). | code review + existing suites still pass; NOT fault-injected (legacy engine is not routed through `vkfault`). |

Other behaviour changes (documented in the headers): ABI 1.1 on both libraries (`cq_core_abi_version`/
`cq_core_check_abi`, `cq_abi_version`/`cq_check_abi`), `cq_create_context` returns NULL on absurd sizes,
input-size caps (16 MiB QASM core, 64 MiB facade), gate-after-measure and RX/RY refused instead of skipped,
`cq_core_last_error()` for the void entry points. The `cq_core_build_capabilities()` JSON is intentionally
unchanged (an existing test pins it; an extra key broke `test_native_cpu_only` and was reverted).

## Design

* `include/cq_hecs/vulkan/vk_fault.hpp` - fault-injection seam. Each fallible call in `VulkanContext`/`VulkanBuffer`
  goes through `vkfault::call(Site, fn)`; tests arm a site to fail the next call(s) with a chosen `VkResult`
  WITHOUT running the real call. Cost in production: one relaxed atomic load per call. It is a C++-only seam, not
  exported through the C ABI; the two fault tests compile `src/cq_hecs_api.cpp` into the test executable so they share
  the table (a separate DLL would own a separate table).
* `VulkanContext` four near-identical dispatch routines collapsed into one `run_compute()` (-300 lines), with a
  single submit/wait/cleanup path.

## Commands and results

```
cmake -S . -B build-a2-vk  -G "Visual Studio 18 2026" -A x64                      # Vulkan ON
cmake -S . -B build-a2-cpu -G "Visual Studio 18 2026" -A x64 -DCQ_ENABLE_VULKAN=OFF
cmake -S . -B build-a2-asan -G "Visual Studio 18 2026" -A x64 -DCQ_ENABLE_SANITIZERS=ON
```

| Run | Result |
|---|---|
| `ctest build-a2-vk -C Release` (all 26 tests; includes 5 new) | 26/26 passed (the earlier "test_bitexact_and_stress Not Run" was a parallel-MSBuild `generate.stamp` race, gone on a serial build) |
| `ctest build-a2-cpu -C Release` (Vulkan OFF) | 15/15 passed, includes `test_c_abi_core` |
| `test_vulkan_bcp_differential device` on AMD Radeon | 1,052,908 cells, 0 mismatches, SAT/CONFLICT/UNIT/OPEN = 339682/314589/132628/266009; 54 shapes incl. 64/65 clause group boundaries, 65535 fronts, empty clauses, duplicate/tautological literals, garbage on unassigned bits; every shape also re-run for determinism |
| same, failure paths | device lost at submit and at wait -> rc -5, output untouched, fresh context passes; dispatch OOM -> rc -4, upload OOM -> rc -3, readback map failure -> rc -6; 20 shutdown/re-init cycles (+ double shutdown) bit-identical |
| `test_vulkan_fault_injection device` | 6 dispatch sites x 100 injected OOMs (descriptor pool holds 64 sets, so any leak would exhaust it) then a correct dispatch; DEVICE_LOST latch, fail-fast, teardown + re-init; buffer-failure accounting; 3 GB ceiling returns false without throwing |
| `test_vulkan_fault_injection init` / `test_vulkan_bcp_validation` | pass; need no GPU |
| ASan (MSVC `/fsanitize=address`, Release, real GPU) `test_c_abi_core test_vulkan_fault_* test_vulkan_bcp_* test_qasm_contract cq_hecs_cpp_hardening test_constraint_solver test_exact_algebra` | 9/9 passed; instrumentation verified (`clang_rt.asan` import present in the exes/DLL, absent in the plain build) |
| `pytest tests/test_native_c_abi_hardening.py tests/test_c_api.py tests/test_omniwave_gpu_shutdown.py` (`CQ_HECS_BUILD_DIR=build-a2-vk/bin/Release`, `CQ_HECS_REQUIRE_NATIVE=1`) | 20 passed |
| `pytest tests/test_omniwave.py tests/test_omniwave_gpu_shutdown.py` | 490 passed (GPU BCP wrapper unaffected) |
| `pytest tests/test_native_cpu_only.py` (own CPU-only configure/build/CTest/loader scan) | 4 passed (after reverting the capability-JSON change) |

CMake: `CQ_ENABLE_SANITIZERS` now also supports MSVC (ASan only, Release config); GCC/Clang keep `address,undefined`.

## CI (`.github/workflows/ci.yml`, native lanes only)

* `linux-native-cpu-only` already existed and matches the contract (Vulkan dev packages removed, `-DCQ_ENABLE_VULKAN=OFF`,
  build+CTest, `tests/test_native_cpu_only.py` loader scan); YAML re-parsed, unchanged. It now also runs `test_c_abi_core`.
* `linux-native` step "Verify Vulkan compute dispatch": now runs `test_vulkan_compute_contract`,
  `test_vulkan_fault_device` and `test_vulkan_bcp_differential` with `CQ_REQUIRE_VULKAN=1` (lavapipe) so a missing
  device fails instead of skipping.
* `sanitizers` lane (ASan+UBSan, GCC 12): regex extended with `test_c_abi_core`, `test_vulkan_fault_init`,
  `test_vulkan_fault_device`, `test_vulkan_bcp_validation`, `test_vulkan_bcp_differential`, `CQ_REQUIRE_VULKAN=1`.
  YAML parsed with PyYAML; NOT executed (no GitHub runner here).

## NOT_RUN / limits (stated honestly)

* GCC/Clang ASan+UBSan (the actual CI lane) and any UBSan run: NOT_RUN locally (no g++, clang shim broken). Only MSVC ASan ran.
* Software-ICD (lavapipe/llvmpipe) conformance and Linux builds: NOT_RUN (`CQ_HECS_VULKAN_DEVICE=llvmpipe` -> "no device", test exits 77).
  All Vulkan results above are from ONE AMD hardware device; a different driver could behave differently.
* Facade `cq_solve_sat` timeout path (F-A2-02) was fixed from code reading, not reproduced dynamically.
* Legacy `VulkanEngine` (src/vulkan_engine.cpp) is checked but not routed through `vkfault`, so its failure paths are not injectable.
* The differential establishes bit-exact agreement with the CPU reference; it makes NO performance claim (see
  `scripts/omniwave_benchmark.py` for end-to-end timing).
* Non-owned: `research/v7/TASKS.md` still lists W4-17/18/19 as NOT STARTED - the integrator should update
  (suggested: W4-17 DONE for VulkanContext/VulkanBuffer; W4-18 DONE; W4-19 PARTIAL: lane existed, extended, only MSVC ASan verified;
  T6-04 DONE on hardware, software-ICD NOT_RUN).
* Untracked build dirs `build-a2-*` are A2-private and ignored by nobody - delete or do not `git add` them.
