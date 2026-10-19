# Non-Transferable Results & Complexity Boundaries

**Date:** 2026-10-19  
**Purpose:** Explicit documentation of negative results, model mismatches, and mathematical boundaries identified during the OpenAI Math corpus review, adhering to `GEMINI.md` §1 ("Non-goals and scientific honesty").

---

## 1. Why Family 284 Does NOT Provide a Classical Simulator
- **Paper:** *A Nearly Quartic Separation Between Randomized and Quantum Query Complexity* (Family 284)
- **Claim:** $R(f) = \widetilde{\Theta}(Q(f)^4)$ for total Boolean functions in the black-box query model.
- **Why Non-Transferable:**
  1. **Query Complexity $\neq$ Time Complexity:** An algorithm making $Q(f)$ queries may take exponential classical time between queries.
  2. **Total Boolean Functions Only:** Quantum circuits of interest (e.g. quantum phase estimation, Shor's algorithm, random circuit sampling) compute relational or sampling problems on partial/structured inputs, where exponential separations (e.g. Simon's problem, period finding) apply.
  3. **No Simulation Algorithm:** The paper proves a lower bound on randomized query complexity, not an efficient classical algorithm for evaluating quantum circuits.

---

## 2. Why Family 283 Does NOT Eliminate Quantum Supremacy
- **Paper:** *Polynomial-Time, Constant-Error Unitary Synthesis from a Boolean Oracle* (Family 283)
- **Claim:** Any unitary can be synthesized by a poly-size quantum circuit given an oracle for its Boolean truth table.
- **Why Non-Transferable:**
  1. The oracle itself requires exponential classical information or evaluation time for general unitaries.
  2. The paper constructs a quantum circuit, not a classical simulation of one.

---

## 3. Why Family 139 Cannot Sample Quantum Entangled States
- **Paper:** *Subpolynomial Queries for Log-Concave Sampling* (Family 139)
- **Claim:** Subpolynomial query complexity for sampling from log-concave continuous distributions.
- **Why Non-Transferable:**
  1. Quantum measurement distributions are discrete and generally non-log-concave (e.g. GHZ state has support on $|00\dots0\rangle$ and $|11\dots1\rangle$ with zero probability everywhere between them).
  2. Log-concave sampling techniques fail on multimodal discrete parity states.

---

## 4. Conclusion on Scientific Honesty
Classical quantum circuit simulation cannot evade exponential worst-case scaling on arbitrary universal circuits unless BPP = BQP. CQ-HECS targets **structured classical quantum simulation** (stabilizer states via Path A, low non-Clifford rank via Path B, low entanglement 1D/MPS states via Path C, and bounded-observable Pauli dynamics via Path D). No paper in the corpus alters this fundamental complexity boundary.
