# CQ-HECS v2.1 Literature & Reference Map

Primary mathematical literature, formalizations, and technical reports audited, cited, and mapped to code in the v2.1 research cycle.

---

## 1. Shipped Classical Quantum Simulation Literature

| Citation | Core Theorem / Result | Mapped Code Module | Proof & Verification Status |
| :--- | :--- | :--- | :--- |
| **Gottesman (1998)**, arXiv:quant-ph/9807006 | Stabilizer formalism; Clifford group operations representable by symplectic transformations over GF(2). | `cqhecs/backends/path_a_stabilizer.py` | Long-established theorem; oracle-verified against `Stim` and Qiskit `Statevector` |
| **Aaronson & Gottesman (2004)**, Phys. Rev. A 70, 052328 | $O(n^2)$ stabilizer tableau update algorithm and deterministic/random measurement projection rules. | `cqhecs/backends/path_a_stabilizer.py` | Algorithm verified; vectorized row-sum mod 4 proven algebraically |
| **Vidal (2003)**, Phys. Rev. Lett. 91, 147902 | Classical simulation of quantum circuits with low Schmidt rank via Matrix Product States. | `cqhecs/backends/path_c_mps_exact.py` | Foundational MPS formulation; oracle-tested against Qiskit Aer MPS |
| **Ferris & Vidal (2012)**, Phys. Rev. B 85, 165146 | Exact sequential conditional sampling from Matrix Product States via right-norm environment contraction. | `cqhecs/backends/path_c_mps_exact.py` (`sample()`) | Algebraically proven and verified in v2.1; 0 spurious bitstrings on 300Q GHZ |
| **Bravyi, Smith, Smolin (2016)**, Phys. Rev. X 6, 021043 | Exact decomposition of non-Clifford gates into linear combinations of Clifford states with rank scaling as $2^{\alpha T}$. | `cqhecs/backends/path_b_stabilizer_rank.py` | Unitary identities verified against dense matrices for all supported gates |
| **Huang, Kueng, Preskill (2020)**, Nature Physics 16, 1050 | Observable-first quantum property estimation; Heisenberg-picture observable propagation. | `cqhecs/backends/path_d_sparse_pauli.py` | Conceptual basis for Path D observable targeting; error bounds derived independently |
| **Weissman et al. (2003)**, HP Labs HPL-2003-97R1; **Mardia et al. (2019)**, arXiv:1809.06522 | Support-aware $L_1$ / Total Variation deviation of empirical distributions: $TV \le \sqrt{\ln((2^K-2)/\delta)/(2n)}$. | `cqhecs/result.py` (`hoeffding_total_variation_bound`) | Formally derived and empirically validated across $K=2\dots64$; clamped at 1.0 |

---

## 2. OpenAI Math Corpus Citations (Audited in Phase 2)

| Manuscript / Family | Primary Result | Classification | Disposition in CQ-HECS |
| :--- | :--- | :--- | :--- |
| **Family 284** (*Nearly Quartic Separation...*) | Sharp quartic relation $R(f) = \widetilde{\Theta}(Q(f)^4)$ for total Boolean functions in the query model. | `quantum-complexity` | Complexity context; refutes arbitrary polynomial quantum speedups for total functions; non-transferable to circuit simulation |
| **Family 283** (*Unitary Synthesis from Boolean Oracle*) | Poly-size quantum circuit synthesis for arbitrary unitaries from a Boolean truth table oracle. | `quantum-information` | Synthesis theory; does not provide classical circuit simulation |
| **Family 279** (*Exact Quantum Factoring...*) | Constructive polynomial-time uniform quantum circuit factoring integers with probability 1. | `quantum-information` (Lean formalized) | Target workload for quantum computers; benchmark target for classical intractability |
| **Family 275** (*QMA-Hardness of Coulomb Energy*) | Ground-state energy of continuum Coulomb Hamiltonians is QMA-complete. | `quantum-complexity` | Proves classical ground-state simulation of continuum Coulomb systems is worst-case intractable |
| **Families 267–274** (*Heisenberg & Haldane spin chains*) | Rigorous spectral gap bounds in integer-spin chains and BEC depletion bounds. | `quantum-many-body` | Theoretical justification for why 1D MPS efficiently represents gapped spin chain states |
| **Family 130** (*Fourier Transforms Below n log n*) | Sub-$n\log n$ arithmetic circuits for structured DFTs. | `tensor-graph-fourier-algorithms` | Context for tensor/Fourier contraction |
| **Family 139** (*Log-Concave Sampling*) | Subpolynomial query complexity for log-concave continuous distributions. | `probability-sampling-statistics` | Non-transferable: quantum measurement parity distributions are non-log-concave |

---

## 3. Consulted & Deferred Literature

| Reference | Scope & Content | Reason Deferred / Excluded |
| :--- | :--- | :--- |
| **Markov & Shi (2005)**, arXiv:quant-ph/0511069 | Tensor network contraction via graph treewidth variable elimination. | High implementation overhead; 1D MPS is optimal for 1D circuits; deferred (H4) |
| **Burgholzer et al. (2023)**, arXiv:2302.06616 | Guidelines comparing Tensor Networks vs Decision Diagrams. | Confirms decision diagrams degrade on entangled states; rejected (H6b) |
| **Zhang et al. (2024)**, arXiv:2401.11362 | Fast Tensor Decision Diagrams (TDD). | Niche limited to repeated structures; high maintenance burden |
| **Valiant (2002)**; **Terhal & DiVincenzo (2002)** | Classical polynomial-time simulation of matchgate circuits. | Highly restricted gate set (non-interacting fermions); deferred (H9) |
