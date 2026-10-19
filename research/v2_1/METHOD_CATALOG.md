# CQ-HECS v2.1 Classical Quantum Simulation Method Catalog

Purpose: Authoritative, comprehensive ledger of all 20 classical simulation methods investigated for CQ-HECS v2.1, in compliance with `GEMINI.md` §5 and §11.

Status Legend:
- **IMPLEMENTED**: Active production backend in CQ-HECS.
- **PROTOTYPE**: Implemented in research or testing seams.
- **DEFERRED**: Conceptually viable, scheduled for a future release cycle.
- **REJECTED**: Evaluated and excluded due to unfavorable complexity, license, or lack of verified niche.

Evidence Levels:
- `CPU_EXACT`: Exact algebraic/arithmetic execution on CPU, oracle-tested against Qiskit/Stim.
- `CPU_CERTIFIED`: Approximate execution with a mathematically proven error certificate.
- `NOT_VERIFIED`: Unverified on claimed hardware (e.g. physical GPU compute).

---

## 1. Production Methods (Implemented in v2.1)

### 1.1 Stabilizer Tableau (Gottesman–Knill) — Path A
- **Production Status:** **IMPLEMENTED** (`CPU_EXACT`)
- **Primary References:**
  - Gottesman (1998) *The Heisenberg Representation of Quantum Computers*, arXiv:quant-ph/9807006.
  - Aaronson & Gottesman (2004) *Improved Simulation of Stabilizer Circuits*, Phys. Rev. A 70, 052328.
- **Supported Circuit Class:** Pure Clifford circuits (H, S, Sdg, X, Y, Z, CX, CZ, SWAP, Clifford-angle rotations at multiples of $\pi/2$). Refuses non-Clifford gates.
- **Supported Outputs:** `counts` (exact multi-qubit sampling), deterministic measurement outcomes.
- **Error Metric & Semantics:** `error_bound = 0.0` (exact GF(2) symplectic arithmetic; no floating-point truncation). `sampling_error_bound` via support-aware Weissman bound.
- **Complexity & Budget:** $O(n^2)$ space for $(2n+1) \times (2n+1)$ binary tableau. Gate updates $O(n)$ bitwise; measurement $O(n^2)$ bitwise. In v2.1, supports $\ge 1,000$ shots for $n = 300+$ qubits.
- **Code Module & Entry Point:** `cqhecs/backends/path_a_stabilizer.py` -> `PathAStabilizerBackend`. CLI: `--backend path_a`.
- **Independent Reference:** Qiskit `Statevector` (small sizes), `Stim` (wide stabilizer circuits).
- **Known Failure Cases:** Fails immediately with `UnsupportedPathAOperation` if any non-Clifford gate ($T, T^\dagger, \text{non-}\pi/2\text{ rotations}$) or mid-circuit measurement is introduced.
- **Decision:** **IMPLEMENTED**. Hardened in v2.1: bug with wide-circuit attribute fixed, row sums vectorized, 100-shot cap removed.

### 1.2 Stabilizer Rank Decomposition — Path B
- **Production Status:** **IMPLEMENTED** (`CPU_EXACT` up to statevector ceiling)
- **Primary References:**
  - Bravyi, Smith, Smolin (2016) *Trading classical and quantum computational resources*, Phys. Rev. X 6, 021043.
  - Bravyi, Browne, Calpin, Campbell, Gosset, Howard (2019) *Simulation of quantum circuits by low-rank stabilizer decompositions*, Quantum 3, 181.
- **Supported Circuit Class:** Clifford $+ T$ circuits with low $T$-count ($T \le 12$) on $n \le 22$ qubits.
- **Supported Outputs:** `counts` (exact statevector sampling), state amplitudes.
- **Error Metric & Semantics:** `error_bound = 0.0` (exact algebraic decomposition; no dropped branches). Evaluated in IEEE-754 double precision (`numerical_mode = "float64-stabilizer-rank"`).
- **Complexity & Budget:** Memory $O(2^n)$ per branch ($64\text{ MB}$ at $n=22$); runtime $O(2^{\alpha T} \cdot 2^n)$ with $\alpha \approx 0.47$.
- **Code Module & Entry Point:** `cqhecs/backends/path_b_stabilizer_rank.py` -> `PathBStabilizerRankBackend`. CLI: `--backend path_b`.
- **Independent Reference:** Qiskit `Statevector.from_instruction`.
- **Known Failure Cases:** Refuses execution if $n > 22$ or projected rank branches exceed `max_rank_branches`.
- **Decision:** **IMPLEMENTED**. Retain explicit 22-qubit cap; do not claim universal 200-qubit simulation for dense Path B.

### 1.3 Untruncated Matrix Product State (MPS) — Path C
- **Production Status:** **IMPLEMENTED** (`CPU_EXACT` up to memory limit)
- **Primary References:**
  - Vidal (2003) *Efficient classical simulation of slightly entangled quantum computations*, Phys. Rev. Lett. 91, 147902.
  - Schollwöck (2011) *The density-matrix renormalization group in the age of matrix product states*, Annals of Physics 326, 96.
  - Ferris & Vidal (2012) *Perfect sampling from matrix product states*.
- **Supported Circuit Class:** 1D low-entanglement circuits up to $300+$ qubits (GHZ, 1D cluster states, shallow nearest-neighbor brickwork chains).
- **Supported Outputs:** `counts` via MPS-native sequential sampling in v2.1; full statevector (capped at $n \le 20$).
- **Error Metric & Semantics:** `error_bound = 0.0` (untruncated bond dimension; grows to exact numerical rank). Discarded mass below roundoff floor ($10^{-13}$) reported as `discarded_spectral_mass_diagnostic`. `numerical_error_bound = None`.
- **Complexity & Budget:** Memory $O(n \chi^2)$; sampling time $O(n \chi^3 \cdot \text{shots})$. Paging to disk storage if RAM budget ($120\text{ MB}$) is exceeded.
- **Code Module & Entry Point:** `cqhecs/backends/path_c_mps_exact.py` -> `PathCMPSExactBackend`. CLI: `--backend path_c`.
- **Independent Reference:** Qiskit `Statevector` ($n \le 16$), Qiskit Aer MPS.
- **Known Failure Cases:** If bond dimension grows exponentially (volume-law entanglement), halts with `unresolved=True` before exceeding memory limit.
- **Decision:** **IMPLEMENTED**. Upgraded in v2.1 with batched MPS sequential sampler, unlocking 200–300 qubit full-register sampling without dense statevectors.

### 1.4 Sparse-Pauli Dynamics (Heisenberg Propagation) — Path D
- **Production Status:** **IMPLEMENTED** (`CPU_CERTIFIED`)
- **Primary References:**
  - Classical Heisenberg-picture dynamics (Gottesman 1998, Rall 2020).
  - Huang, Kueng, Preskill (2020) *Predicting many properties of a quantum system from very few measurements*, Nature Physics 16, 1050.
- **Supported Circuit Class:** Arbitrary gate sets (Clifford + non-Clifford rotations, CX, CZ, SWAP) where target observables are requested.
- **Supported Outputs:** Certified `expectation_values` ($\langle Z_q \rangle$, $\langle Z_q Z_r \rangle$, or explicit user observables).
- **Error Metric & Semantics:** Certified upper bound on expectation values: $|\langle O \rangle_{\text{exact}} - \langle O \rangle_{\text{approx}}| \le \sum_{P \in D} |c_P|$. Does NOT certify joint bitstring distributions.
- **Complexity & Budget:** Memory $O(K \cdot n)$ where $K$ is max Pauli terms; runtime $O(K \cdot |C|)$ per observable.
- **Code Module & Entry Point:** `cqhecs/backends/path_d_sparse_pauli.py` -> `PathDSparsePauliBackend`. CLI: `--backend path_d`.
- **Independent Reference:** Qiskit `Statevector` expectation values.
- **Known Failure Cases:** Highly entangled circuits with non-Clifford gates expand Pauli operator support exponentially; if bound exceeds tolerance, halts with `unresolved=True`.
- **Decision:** **IMPLEMENTED**. Hardened in v2.1: added selective `observables` API to avoid $O(n^2)$ overhead on 200+ qubits.

---

## 2. Investigated Method Families (Detailed Audit)

### 2.1 Dense Statevector
- **Status:** **IMPLEMENTED AS REFERENCE ORACLE** (Test-only / small circuits).
- **Scope:** Universal $n \le 20$ circuits. $O(2^n)$ memory.
- **Decision:** Preserved as ground-truth verification oracle; excluded as a scalable 200-qubit method.

### 2.2 Density Matrix / Superoperator
- **Status:** **REJECTED FOR V2.1 CORE**.
- **Scope:** Mixed states and quantum noise channels.
- **Complexity:** $O(4^n)$ complex amplitudes ($16 \times 4^n$ bytes). At $n=15$, requires $16\text{ GB}$.
- **Rationale:** Exceeds single-node memory budgets for $n \ge 16$. Noisy simulation is out of scope for v2.1 pure-state mission.

### 2.3 Quasiprobability Stabilizer Extent / Monte Carlo
- **Status:** **REJECTED FOR V2.1 CORE**.
- **Scope:** Clifford $+ T$ circuits.
- **Complexity:** Sampling overhead scales as $\mathcal{E}(T)^2 \approx 2^{0.44 T} / \epsilon^2$.
- **Rationale:** Severe sign problem and sampling variance for deep circuits; does not beat Path C on structured circuits or Path D on observables.

### 2.4 Tree Tensor Networks (TTN) & PEPS
- **Status:** **DEFERRED**.
- **Scope:** 2D grid and tree topologies.
- **Complexity:** PEPS contraction is \#P-hard in general; approximate contraction requires boundary MPS.
- **Rationale:** High algorithmic complexity; requires comprehensive C++ tensor contraction library. Deferred to post-v2.1.

### 2.5 Generic Tensor-Network Contraction Ordering (Treewidth)
- **Status:** **DEFERRED** (Hypothesis H4).
- **Primary Reference:** Markov & Shi (2005) *Simulating quantum computation by contracting tensor networks*.
- **Scope:** Arbitrary circuit graphs with low treewidth.
- **Rationale:** Evaluated for 2D circuits. Current 1D MPS handles targeted 200+ qubit classes effectively. Adding an external contraction library adds binary dependency risks.

### 2.6 Decision Diagrams (QMDD / QuIDD / TDD)
- **Status:** **REJECTED FOR V2.1 CORE**.
- **Primary References:** Burgholzer et al. (2023) *Tensor Networks or Decision Diagrams?*; Zhang et al. (2024).
- **Scope:** Circuits with highly regular/repetitive amplitude vectors.
- **Rationale:** Highly sensitive to variable ordering; exponential node explosion on random or entangled states. Substantial code maintenance overhead without clear advantage over Path A/C on target benchmarks.

### 2.7 Feynman Path Sums / Path-Integrals
- **Status:** **DEFERRED**.
- **Scope:** Transition amplitudes $\langle x | U | y \rangle$.
- **Complexity:** Sum over $2^{G}$ paths, where $G$ is two-qubit gate count.
- **Rationale:** Catastrophic phase cancellation makes sampling individual bitstrings slower than statevector methods for $G > 30$.

### 2.8 Schrödinger–Feynman Hybrid Partitioning
- **Status:** **DEFERRED**.
- **Scope:** Wide circuits partitioned into two smaller registers connected by cut gates.
- **Complexity:** Memory $O(2^{n/2})$; time $O(4^k \cdot 2^{n/2})$ where $k$ is number of cut gates.
- **Rationale:** Requires separate cut accounting, estimator combination, and result schema modification.

### 2.9 Circuit Cutting / Wire Cutting
- **Status:** **DEFERRED**.
- **Scope:** Fragmenting circuits across spatial boundaries.
- **Complexity:** Sampling overhead $O(4^K)$ where $K$ is number of wire cuts.
- **Rationale:** Changes output contract to a reconstructed estimator with statistical variance.

### 2.10 Classical Shadows & Randomized Measurement Estimators
- **Status:** **PROTOTYPE / RESEARCH CONTEXT**.
- **Primary Reference:** Huang, Kueng, Preskill (2020).
- **Rationale:** Useful for predicting multiple observables from randomized Clifford measurements. Differs from Path D's deterministic Pauli truncation; bounds cannot be directly substituted into Path D without proof.

### 2.11 Free-Fermion / Matchgate / Gaussian Simulation
- **Status:** **DEFERRED** (Hypothesis H9).
- **Primary Reference:** Valiant (2002) *Quantum computers that can be simulated classically in polynomial time*; Terhal & DiVincenzo (2002).
- **Scope:** Matchgate circuits / non-interacting fermions on 1D chains.
- **Complexity:** $O(n^3)$ polynomial time via Pfaffian evaluation.
- **Rationale:** Highly restricted gate set (nearest-neighbor Givens rotations); cannot simulate universal quantum algorithms. Deferred as a specialized future plugin.

### 2.12 Symmetry / Sector Reduction
- **Status:** **DEFERRED**.
- **Scope:** Circuits conserving Hamming weight or $U(1)$ particle number.
- **Rationale:** Must only be applied when machine-checked invariant proofs exist. Unsound assumptions risk silent corruption.

### 2.13 Graph-State & Treewidth Simulation
- **Status:** **RESEARCH CONTEXT**.
- **Rationale:** Connected to Path A and tensor contraction. Investigated under H4.

### 2.14 Exact Circuit Preprocessing & Gate Fusion
- **Status:** **IMPLEMENTED** in Circuit Parsing / Analyzer (Hypothesis H8).
- **Scope:** Universal circuits. Cancels adjacent inverse gates, fuses single-qubit rotations, and prunes unmeasured dangling gates via backward lightcone analysis.
- **Benefit:** Reduces gate counts by $10\dots25\%$ prior to backend execution while preserving exact output.

### 2.15 Noisy Trajectory (MCWF) Simulation
- **Status:** **REJECTED FOR V2.1 CORE**.
- **Rationale:** The v2.1 mission objective is exact/certified pure-state simulation and scaling to 200+ qubits. Stochastic Monte Carlo wave function trajectories alter the result contract.

### 2.16 Distributed CPU / Multi-Node MPI
- **Status:** **DEFERRED**.
- **Rationale:** Single-machine multi-threaded and NVMe-paged architecture must be completely solid before introducing distributed MPI communication overhead.

### 2.17 Analog / Quantum-Inspired Classical Optimization
- **Status:** **REJECTED FOR V2.1 CORE**.
- **Rationale:** Heuristic energy optimizers (simulated annealing, QAOA emulators) do not simulate unitary quantum gate circuits or output true measurement distributions.

### 2.18 Automated Algorithm Selection / Output-Aware Router
- **Status:** **IMPLEMENTED** (Hypothesis H3).
- **Scope:** Automatic routing based on gate set, $T$-count, entanglement profile, and requested output type (`counts` vs `observables`).

---

## 3. Summary Capability Matrix for v2.1.0

| Backend | Method | 200+ Qubit Support | Output Types | Numerical Semantics |
| :--- | :--- | :--- | :--- | :--- |
| **Path A** | Stabilizer Tableau | **Yes** (Clifford circuits) | Exact `counts` ($\ge 1000$ shots) | Exact GF(2) symplectic arithmetic |
| **Path B** | Stabilizer Rank | No (capped at $n \le 22$) | `counts`, statevector | Exact algebra, float64 evaluation |
| **Path C** | Untruncated MPS | **Yes** (1D low-entanglement) | Correlated `counts` ($\ge 1000$ shots) | No truncation; float64 roundoff floor |
| **Path D** | Sparse-Pauli Dynamics | **Yes** (bounded observables) | Certified `expectation_values` | Rigorous truncation error bound $\epsilon \le \sum |c_i|$ |
