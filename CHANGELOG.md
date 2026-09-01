# Changelog

All notable changes to CQ-HECS (Classical Quantum High-Efficiency Compute Simulator) are documented in this file.

The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
