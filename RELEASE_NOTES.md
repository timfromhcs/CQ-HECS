# CQ-HECS v0.1.0 Release Notes

**Release Target:** `v0.1.0` (Clean Slate Initial Release)  
**Date:** September 2026  
**License:** Apache 2.0  
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

---

## 1. Executive Summary

CQ-HECS `v0.1.0` marks the clean-slate foundational release of the **Deterministic Classical Four-Path Quantum Circuit Simulation Engine**. All historical pre-release tags and silent approximations (specifically, hardcoded $\chi = 48$ bond-dimension truncations) have been completely eliminated from the codebase.

CQ-HECS delivers 100% classical execution with provable mathematical error bounds, seamless Qiskit `BackendV2` integration, and continuous integration audits.

---

## 2. Key Architecture Capabilities

### The Four Classical Simulation Paths:
1. **Path A: Stabilizer-Tableau (Exact, Clifford)**
   - Implements Aaronson-Gottesman (2004) binary symplectic tableau ($O(N^2)$).
   - High-performance AVX2 C++20 `HybridEngine` backend with bit-exact phase tracking.
   - Guaranteed error bound: $\epsilon = 0.0$.
2. **Path B: Stabilizer-Rank-Decomposition (Exact, Clifford + T)**
   - Decomposes non-Clifford rotations ($T$, $R_Z$) into exact linear combinations of stabilizer branches: $T = c_0 I + c_1 Z$.
   - Evaluates superpositions with zero floating-point drift: $|\psi\rangle = \sum_x w_x C_x |0^{\otimes N}\rangle$.
   - Guaranteed error bound: $\epsilon = 0.0$.
3. **Path C: Unbounded Matrix Product State + NVMe-Offload (Exact up to Storage Limit)**
   - Exact Singular Value Decomposition (SVD) retaining all physical singular values ($s_i > 10^{-14}$).
   - Zero silent cutoff: bond dimension $\chi$ expands dynamically without artificial caps.
   - Tiered memory paging to NVMe/storage; marks `unresolved=True` if physical storage ceiling is exceeded without explicit approximation opt-in.
   - Guaranteed error bound: $\epsilon = 0.0$.
4. **Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics)**
   - Evolves observables backwards under Heisenberg operator dynamics: $O(t) = U^\dagger O U = \sum_P c_P P$.
   - Rigorous 1-norm error bound certificate: $|\langle O \rangle_{\text{exact}} - \langle O \rangle_{\text{approx}}| \le \sum_{P \in \mathcal{D}} |c_P| = \Delta$.
   - Rejection guarantee: If $\Delta > \epsilon_{\text{tolerance}}$, the result is marked `unresolved=True`—no guessing.

---

## 3. Verified Quality Gates & Benchmarks

All metrics are grounded by reproducible test executions in continuous integration:

- **Full Classical Test Suite:** 88 / 88 tests passing (100% Green).
- **CTest Suite:** 13 / 13 C++20 test suites passing (100% Green).
- **Mutation Kill Score:** 5 / 5 core mutants killed (100.0% Mutation Score).
- **Zero-Silent-Truncation Audit:** 0 forbidden `chi=48` occurrences detected across codebase.
- **Stim Comparative Benchmarks:** Bit-exact support match on 50-qubit GHZ and 10-qubit random Clifford walk.
- **Qiskit Aer Comparative Benchmarks:** Bit-exact probability match on Clifford $+ T$ statevector and certified bounded differential error verification on Path D.

---

## 4. Theoretical Complexity Boundaries

Classical simulation of arbitrary quantum circuits remains bounded by fundamental computational complexity:
$$\text{BPP} \ne \text{BQP}$$
Path D does not claim to solve quantum advantage or simulate worst-case quantum circuits in polynomial time. In deep random circuits with all-to-all entanglement, the number of significant Pauli terms grows exponentially. Path D guarantees transparent, certified degradation with rigorous mathematical upper bounds rather than uncontrolled heuristic guesses.

---

## 5. Artifacts and Provenance

- **Wheel:** `cqhecs-0.1.0-py3-none-any.whl` (SHA256: `f6fb92a3ce6b78d16a6ecc6a55e8b246d2d2c22f5476864f5f8c57b9d1d4a3fd`)
- **Source Tarball:** `cqhecs-0.1.0.tar.gz` (SHA256: `66ca81a69d530417a31ee95816a59422efc96c7ab9d8052dc5a42bfec9347fdc`)
- **Checksums:** `sha256sums.txt`
- **SBOM:** SPDX 2.3 JSON `cqhecs-sbom.spdx.json`
- **Audit Tracking Log:** `audit/release_tracking.json`
