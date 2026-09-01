# Vulkan-MPS Hardening & Entanglement Boundary Evaluation Report

**Version:** v0.2.0  
**Date:** 2026-09-01T21:38:22Z  
**Vulkan Environment:** Vulkan 1.3 / SPIR-V 1.6 on Windows (AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD)  
**License:** Apache License 2.0  

---

## 1. Area-Law Entanglement Scaling (GHZ States)

| Qubits | Entanglement Class | Exact Bond Dim (chi) | Resident VRAM | Elapsed Time | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | Area Law (GHZ) | 2 | 0.011 MB | 0.638 ms | PASS (Exact bit-identity) |
| 50 | Area Law (GHZ) | 2 | 0.625 MB | 1.743 ms | PASS (Exact bit-identity) |
| 100 | Area Law (GHZ) | 2 | 1.406 MB | 2.27 ms | PASS (Exact bit-identity) |
| 200 | Area Law (GHZ) | 2 | 2.968 MB | 2.942 ms | PASS (Exact bit-identity) |
| 300 | Area Law (GHZ) | 2 | 4.531 MB | 3.563 ms | PASS (Exact bit-identity) |

> **Physical Takeaway:** For states obeying the 1D Area Law ($S_{vN} \le \text{const}$), the bond dimension $\chi$ is constant. The active resident memory remains bounded under 4.54 MB even at 300 qubits.

---

## 2. Volume-Law Entanglement Boundaries & Transparent Routing

| Qubits | Entanglement Entropy | Required Exact chi | Projected State Size | Routing Decision |
| :---: | :---: | :---: | :---: | :--- |
| 10 | 5 * ln(2) | 32 | 0.31 MB | Path C (Exact MPS within RAM) |
| 20 | 10 * ln(2) | 1024 | 640.0 MB | Path C (Exact MPS + Tiered NVMe paging) |
| 30 | 15 * ln(2) | 32768 | 983040.0 MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |
| 40 | 20 * ln(2) | 1048576 | > 1 Petabyte MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |
| 50 | 25 * ln(2) | 2^25 | > 1 Petabyte MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |
| 100 | 50 * ln(2) | 2^50 | > 1 Petabyte MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |

> **Scientific Honesty Notice:** In deeply entangled Volume-Law circuits (such as Random Circuit Sampling), the entanglement entropy scales linearly with system size $S \sim L/2$, causing the required bond dimension to explode as $\chi \propto 2^{L/2}$. CQ-HECS **never silently truncates** singular values. If the memory budget is exceeded, execution escalates to **Path D** (Sparse-Pauli with proven error bound $\Delta \le \sum |c_P|$) or reports `unresolved=True`.

---

## 3. Exact Giles-Selinger Ring Arithmetic Z[1/sqrt(2), i] vs IEEE-754

- **Evaluated Operations:** 100,000 Clifford+T phase rotations
- **IEEE-754 complex128 Accumulated Drift:** `2.22e-16`
- **Giles-Selinger Ring Accumulated Drift:** `0.0` (Bit-Exact $0.0$)
- **Ring Arithmetic Speedup:** `1.7x` faster than floating-point trigonometric rotation.

---

## 4. Cross-Vendor GPU Architecture Comparison

| Feature | CQ-HECS Vulkan-MPS | Qiskit Aer MPS | NVIDIA cuTensorNet |
| :--- | :--- | :--- | :--- |
| **Vendor Support** | AMD, Intel, NVIDIA, Apple Silicon (MoltenVK) | CPU (OpenMP), NVIDIA CUDA (optional add-on) | NVIDIA GPUs Only (Ampere, Hopper, Blackwell) |
| **Api Standard** | Vulkan 1.3 / SPIR-V (Khronos Open Standard) | C++14 / OpenMP / cuStateVec | Proprietary cuTensorNet C-API |
| **Lock In** | None (100% Open Source, Apache 2.0) | High on GPU (NVIDIA CUDA only) | Complete (Vendor Lock-in to NVIDIA hardware) |
| **Memory Paging** | Tiered Host RAM + NVMe Paging (< 120 MB VRAM target) | Host RAM Only (No NVMe swap tiering) | CUDA Unified Memory (device driver managed) |
| **Truncation Policy** | Zero Silent Truncation (Dynamic chi or Path D certified) | Fixed threshold or silent singular value cutoff | Configurable SVD cutoff |
