# Transfer Candidates from Classical Simulation Literature

**Date:** 2026-10-19  

---

## 1. Identified Transfer Candidates

### Candidate 1: MPS Sequential Conditional Sampling (Implemented in v2.1)
- **Source Literature:** Vidal (2003) *Efficient classical simulation of slightly entangled quantum computations*; Ferris & Vidal (2012); Qiskit Aer MPS.
- **Workload Class:** 1D low-entanglement circuits up to 300+ qubits (GHZ, cluster states, brickwork circuits with bounded bond dimension).
- **Output:** Correlated full-register counts without dense statevectors ($O(n \\chi^3)$ time, $O(n \\chi^2)$ memory).
- **Status:** **IMPLEMENTED & VERIFIED** in CQ-HECS v2.1 (Hypothesis H1).

### Candidate 2: Vectorized Full-Shot Stabilizer Sampling (Implemented in v2.1)
- **Source Literature:** Aaronson & Gottesman (2004) *Improved simulation of stabilizer circuits*; Stim (Gidney 2021).
- **Workload Class:** Stabilizer / Clifford circuits up to 300+ qubits with arbitrary shot counts (1,000–10,000+).
- **Output:** Exact joint counts with $\sum \text{counts} = \text{shots}$.
- **Status:** **IMPLEMENTED & VERIFIED** in CQ-HECS v2.1 (Hypothesis H2).

### Candidate 3: Selective Observables Heisenberg Propagation (Implemented in v2.1)
- **Source Literature:** Classical Pauli path propagation, Huang et al. (2020).
- **Workload Class:** Bounded subset of target Pauli observables on wide circuits.
- **Output:** Rigorous expectation values with individual error certificates $\epsilon \le \sum |c_i|$.
- **Status:** **IMPLEMENTED & VERIFIED** in CQ-HECS v2.1 (Hypothesis H7).

### Candidate 4: Treewidth and Graph Contraction Optimizers (Researched / Deferred)
- **Source Literature:** Markov & Shi (2005) *Simulating quantum computation by contracting tensor networks*.
- **Evaluation:** For general 2D geometries where 1D MPS bond dimension scales poorly. Evaluated under Hypothesis H4; deferred for future major tensor refactor.
