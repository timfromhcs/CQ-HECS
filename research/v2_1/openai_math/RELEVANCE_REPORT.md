# OpenAI Math Relevance & Impact Report for CQ-HECS

**Audit Date:** 2026-10-19  
**Corpus Scope:** 372 result families in 719 manuscripts (commit `1581d4cbdd69a0faf34b2089614fe2a814316a6a`).  

---

## 1. Executive Summary

Every manuscript in the OpenAI Math collection was screened against the computational model of classical quantum circuit simulation. The majority of the collection addresses pure mathematics (number theory, algebraic geometry, partial differential equations). Specific families in **Mathematical Physics** (Section 17), **Theoretical Computer Science** (Section 14), and **Probability & Statistical Mechanics** (Section 15) intersect quantum computing, complexity theory, and sampling algorithms.

Key finding: **None of the manuscripts provide an efficient universal classical algorithm for simulating arbitrary quantum circuits.** Rather, they establish rigorous complexity barriers (e.g. quartic query bounds, QMA hardness) or solve specific mathematical problems in quantum information, many-body physics, and continuous sampling.

---

## 2. In-Depth Audit of Priority Families

### Family 284: The Optimal Randomized–Quantum Query Exponent
- **Preprint:** `preprints/A-Nearly-Quartic-Separation-Between-Randomized-and-Quantum-Query-Complexity-October-5-2026/quartic-query-separation.pdf`
- **Result:** Establishes a sharp quartic relation $R(f) = \widetilde{\Theta}(Q(f)^4)$ between bounded-error randomized query complexity $R(f)$ and quantum query complexity $Q(f)$ for total Boolean functions $f$.
- **Model / Assumptions:** Black-box oracle query model. Queries count evaluations of an unknown input string $x \in \{0, 1\}^N$, not gate operations or wall-clock runtime.
- **Scientific Impact for CQ-HECS:**
  - Strongly refutes any naive claim that quantum polynomial speedups can be arbitrarily large for total Boolean function evaluation in query models ($Q \ge R^{1/4}$).
  - Clarifies that query complexity bounds do not translate to gate-level classical circuit simulation. Classical simulation of arbitrary quantum circuits remains exponential in entanglement/qubit count unless structure is exploited.

### Family 283: Polynomial-Time Unitary Synthesis from a Boolean Oracle
- **Preprint:** `preprints/Polynomial-Time-Unitary-Synthesis-from-a-Boolean-Oracle-October-5-2026/paper.pdf`
- **Result:** Given an oracle encoding an arbitrary unitary's truth table, constructs a quantum circuit of polynomial size synthesizing the unitary up to constant trace distance.
- **Model / Assumptions:** Relies on an uncomputed target-dependent classical Boolean oracle. The complexity of constructing the oracle itself is unrestricted.
- **Scientific Impact for CQ-HECS:**
  - Useful for understanding quantum unitary synthesis theory.
  - Does NOT imply that classical computers can simulate such unitaries; the oracle query model hides classical exponential work in the oracle definition.

### Family 279: Exact Quantum Factoring over a Fixed Finite Gate Set
- **Preprint:** `preprints/Exact-quantum-factoring-over-a-fixed-finite-gate-set-September-25-2026/main.pdf`
- **Lean Formalization:** `ComparatorChallenges/ExactQuantumFactoring.lean`, documented in `lean/docs/279.md`.
- **Result:** Constructive polynomial-time uniform quantum circuit family outputting the prime factorization of any integer $N$ with success probability exactly 1 using a fixed finite universal gate set.
- **Scientific Impact for CQ-HECS:**
  - Beautiful example of exact quantum circuit synthesis without bounded-error failure probability.
  - Demonstrates the target workload class for quantum computers. Simulating these circuits classically requires exponential resources on Path B or C once entanglement grows, honestly illustrating why universal quantum advantage exists.

### Family 275: QMA-Hardness of Continuum Coulomb Energy
- **Preprint:** `preprints/QMA-hardness-of-continuum-Coulomb-energy-September-25-2026/main.pdf`
- **Result:** Proves that computing the ground-state energy of electrons in a classical nuclear potential is QMA-complete.
- **Scientific Impact for CQ-HECS:**
  - Confirms that general many-body fermionic/Coulomb quantum states cannot be simulated efficiently in polynomial time by classical or even BQP algorithms unless QMA = BQP.

### Family 130: Fourier Transforms Below n log n
- **Preprint:** `preprints/Fourier-transforms-below-n-log-n-October-5-2026/main.pdf`
- **Result:** Sub-$n\log n$ arithmetic circuits for structured discrete Fourier transforms.
- **Model / Assumptions:** Specific algebraic arithmetic circuit model with precomputed twiddle factors.
- **Scientific Impact for CQ-HECS:**
  - Relevant for exact arithmetic preprocessing and tensor contractions involving permutation/FFT structures.

### Family 139: Subpolynomial-Query Log-Concave Sampling
- **Preprint:** `preprints/Subpolynomial-queries-for-log-concave-sampling-October-5-2026/main.pdf`
- **Result:** Subpolynomial query complexity for continuous log-concave probability distributions.
- **Scientific Impact for CQ-HECS:**
  - Relevant for continuous classical sampling algorithms, but inapplicable to quantum measurement bitstrings which exhibit non-log-concave multimodal distributions (such as GHZ parity mixtures).
