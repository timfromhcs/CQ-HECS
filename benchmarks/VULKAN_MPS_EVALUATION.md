# CQ-HECS Comprehensive Multi-Class Benchmark & Evaluation Report

**Version:** v0.2.0  
**Date:** 2026-09-04T22:50:19Z  
**Vulkan Environment:** Vulkan 1.3 / SPIR-V 1.6 on Windows (AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD)  
**License:** Apache License 2.0  

---

## 1. Area-Law Entanglement Scaling (GHZ States)

| Qubits | Entanglement Class | Exact Bond Dim (chi) | Resident VRAM | Elapsed Time | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | Area Law (GHZ) | 2 | 0.011 MB | 0.586 ms | PASS (Exact bit-identity) |
| 50 | Area Law (GHZ) | 2 | 0.625 MB | 1.694 ms | PASS (Exact bit-identity) |
| 100 | Area Law (GHZ) | 2 | 1.406 MB | 2.277 ms | PASS (Exact bit-identity) |
| 200 | Area Law (GHZ) | 2 | 2.968 MB | 3.155 ms | PASS (Exact bit-identity) |
| 300 | Area Law (GHZ) | 2 | 4.531 MB | 3.72 ms | PASS (Exact bit-identity) |

> **Physical Takeaway:** For states obeying the 1D Area Law ($S_{vN} \le \text{const}$), bond dimension $\chi$ is strictly constant ($\chi = 2$). Active memory remains bounded under 4.54 MB even at 300 qubits.

---

## 2. 1D Cluster Graph States (Measurement-Based QC)

| Qubits | State Class | Bond Dim (chi) | Shots | Exact | Elapsed Time | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | 1D Cluster Graph State | 2 | 500 | True | 0.791 ms | PASS (Area-law certified) |
| 30 | 1D Cluster Graph State | 2 | 500 | True | 1.804 ms | PASS (Area-law certified) |
| 50 | 1D Cluster Graph State | 2 | 500 | True | 3.675 ms | PASS (Area-law certified) |
| 100 | 1D Cluster Graph State | 2 | 500 | True | 12.415 ms | PASS (Area-law certified) |
| 200 | 1D Cluster Graph State | 2 | 500 | True | 47.338 ms | PASS (Area-law certified) |

> **Physical Takeaway:** 1D cluster states possess nearest-neighbor stabilizer stabilizers, solvable in exact polynomial time via Path A and bounded bond dimension in Path C.

---

## 3. Nearest-Neighbor Brickwork Layers (MPS Contraction)

| Qubits | Circuit Depth | 2-Qubit Gates | Exact | Elapsed Time | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | 3 | 9 | True | 1.617 ms | PASS (Exact MPS) |
| 20 | 3 | 19 | True | 1.304 ms | PASS (Exact MPS) |
| 30 | 3 | 29 | True | 1.79 ms | PASS (Exact MPS) |
| 40 | 3 | 39 | True | 2.139 ms | PASS (Exact MPS) |

---

## 4. Volume-Law Entanglement Boundaries & Transparent Escalation

| Qubits | Entanglement Entropy | Required Exact chi | Projected State Size | Routing Decision |
| :---: | :---: | :---: | :---: | :--- |
| 10 | 5 * ln(2) | 32 | 0.31 MB | Path C (Exact MPS within RAM) |
| 20 | 10 * ln(2) | 1024 | 640.0 MB | Path C (Exact MPS + Tiered NVMe paging) |
| 30 | 15 * ln(2) | 32768 | 983040.0 MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |
| 40 | 20 * ln(2) | 1048576 | > 1 Petabyte MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |
| 50 | 25 * ln(2) | 2^25 | > 1 Petabyte MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |
| 100 | 50 * ln(2) | 2^50 | > 1 Petabyte MB | Path D (Sparse-Pauli Certified Error Bound or Unresolved) |

> **Scientific Honesty Notice:** In deeply entangled Volume-Law circuits, entropy scales as $S \sim L/2$, requiring $\chi \propto 2^{L/2}$. CQ-HECS **never silently truncates** singular values. If the memory budget is exceeded, execution escalates to Path D (Sparse-Pauli with proven error bounds) or reports `unresolved=True`.

---

## 5. Large-Scale Clifford Circuit Scaling (Path A, N=10..300)

| Qubits | Gate Count | Shots | Exact | State | Elapsed Time | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | 60 | 500 | True | EXACT | 0.808 ms | PASS (Bit-exact symplectic) |
| 50 | 300 | 500 | True | EXACT | 5.522 ms | PASS (Bit-exact symplectic) |
| 100 | 600 | 500 | True | EXACT | 15.543 ms | PASS (Bit-exact symplectic) |
| 200 | 1200 | 500 | True | EXACT | 52.295 ms | PASS (Bit-exact symplectic) |
| 300 | 1800 | 500 | True | EXACT | 108.325 ms | PASS (Bit-exact symplectic) |

---

## 6. Low-T Stabilizer Rank Decomposition (Path B, T=2..14)

| T-Count | Qubits | Rank Branches | Exact | Error Bound | Elapsed Time | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2 | 4 | 4 | True | 0.0 | 0.783 ms | PASS (Bit-exact rank decomposition) |
| 4 | 4 | 16 | True | 0.0 | 0.859 ms | PASS (Bit-exact rank decomposition) |
| 6 | 4 | 64 | True | 0.0 | 2.54 ms | PASS (Bit-exact rank decomposition) |
| 8 | 4 | 256 | True | 0.0 | 9.791 ms | PASS (Bit-exact rank decomposition) |
| 10 | 4 | 1024 | True | 0.0 | 44.22 ms | PASS (Bit-exact rank decomposition) |
| 12 | 4 | 4096 | True | 0.0 | 204.243 ms | PASS (Bit-exact rank decomposition) |
| 14 | 4 | 16384 | True | 0.0 | 909.973 ms | PASS (Bit-exact rank decomposition) |

---

## 7. Sparse-Pauli Certified Observable Dynamics (Path D)

| Term Budget | <Z_0> Expectation | Certified Error Bound | Unresolved | State | Elapsed Time |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 4 | 0.0 | 0.0 | False | CERTIFIED | 0.055 ms |
| 8 | 0.0 | 0.0 | False | CERTIFIED | 0.024 ms |
| 16 | 0.0 | 0.0 | False | CERTIFIED | 0.021 ms |
| 32 | 0.0 | 0.0 | False | CERTIFIED | 0.018 ms |
| 64 | 0.0 | 0.0 | False | CERTIFIED | 0.018 ms |

---

## 8. Exact Giles-Selinger Ring Arithmetic vs IEEE-754 Float64

- **Evaluated Operations:** 100,000 Clifford+T rotations
- **IEEE-754 complex128 Drift:** `2.22e-16`
- **Giles-Selinger Ring Drift:** `0.0` (Bit-Exact $0.0$)
- **Ring Arithmetic Speedup:** `1.39x` faster than floating-point trigonometric rotation.

---

## 9. Classical SAT & ARX Cryptanalysis Solver Benchmarks

### DIMACS CNF Benchmarks
| Benchmark | Variables | Clauses | Satisfiable | Decisions | Pruned Cycles | Elapsed Time | Verified |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| pigeonhole_6_5.cnf | 30 | 81 | False | 359 | 0 | 16.224 ms | True |
| uf50_hard.cnf | 50 | 218 | True | 19 | 0 | 5.91 ms | True |

### ARX Cryptanalysis Step-Inversion
| Primitive | Rounds | Forward Verified | Inverse Verified | Carry Shadow Exact | Elapsed Time |
| :--- | :---: | :---: | :---: | :---: | :---: |
| BLAKE2b G-Function | 100 | True | True | True | 0.541 ms |
| ChaCha20 Quarter-Round | 20 | True | True | True | 0.114 ms |
| SHA-256 Schedule Expansion | 64 | True | True | True | 0.432 ms |

---

## 10. Cross-Vendor GPU Architecture Matrix

| Feature | CQ-HECS Vulkan-MPS | Qiskit Aer MPS | NVIDIA cuTensorNet |
| :--- | :--- | :--- | :--- |
| **Vendor Support** | AMD, Intel, NVIDIA, Apple Silicon (MoltenVK) | CPU (OpenMP), NVIDIA CUDA (optional add-on) | NVIDIA GPUs Only (Ampere, Hopper, Blackwell) |
| **Api Standard** | Vulkan 1.3 / SPIR-V (Khronos Open Standard) | C++14 / OpenMP / cuStateVec | Proprietary cuTensorNet C-API |
| **Lock In** | None (100% Open Source, Apache 2.0) | High on GPU (NVIDIA CUDA only) | Complete (Vendor Lock-in to NVIDIA hardware) |
| **Memory Paging** | Tiered Host RAM + NVMe Paging (< 120 MB VRAM target) | Host RAM Only (No NVMe swap tiering) | CUDA Unified Memory (device driver managed) |
| **Truncation Policy** | Zero Silent Truncation (Dynamic chi or Path D certified) | Fixed threshold or silent singular value cutoff | Configurable SVD cutoff |
