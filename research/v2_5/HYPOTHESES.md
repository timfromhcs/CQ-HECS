# CQ-HECS v2.5.0 Falsifiable Hypotheses & Preregistered Experiments

## 1. Candidate selection gate

| Candidate ID | Description | Relevance (1-5) | Evidence Quality (1-5) | Implementability (1-5) | Expected Benefit (1-5) | Independent Oracle Quality (1-5) | Portability (1-5) | Reverse-Risk (1-5) | Total Score | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| **H-BRIDGE** | **Hardware-Aware Quantum Bridge & Narrow Noise Model** | 5 | 5 | 5 | 5 | 5 | 5 | 5 | **35/35** | **ACCEPTED (Major Feature for v2.5.0)** |
| H-QMA | OpenAI Math QMA-hardness bound application | 3 | 4 | 2 | 2 | 3 | 4 | 3 | 21/35 | REJECTED (Validation only, no algorithm) |
| H-2DTN | 2D Tensor-Network contraction planning | 4 | 3 | 2 | 3 | 3 | 2 | 2 | 19/35 | DEFERRED (High complexity, needs cuTensorNet / heavy deps) |
| H-STIM-FRAME | Pauli-frame batched sampling integration | 4 | 4 | 3 | 3 | 4 | 4 | 4 | 26/35 | DEFERRED (Stabilizer already handles Clifford efficiently) |
| H-DYN-CIRC | Mid-circuit measurement and reset in Path A | 4 | 4 | 4 | 3 | 4 | 4 | 3 | 26/35 | DEFERRED (Tableau state collapse requires careful tracking; bridge first) |

## 2. Hypothesis H-BRIDGE (Hardware-Aware Quantum Bridge)

### Statement
A Hardware-Aware Quantum Bridge can be integrated into CQ-HECS with:
1. Three strictly isolated execution modes (`IDEAL_CLASSICAL`, `NOISY_CLASSICAL`, `REAL_HARDWARE`), where real hardware execution cannot silently degrade or fall back to simulation.
2. A typed, validated, and versioned `BackendProfile` schema capturing backend topology, basis gates, gate error rates, readout errors, T1/T2 constants, and calibration timestamps.
3. A mathematically rigorous narrow noise-model engine supporting 1-qubit depolarizing, amplitude damping, phase damping, and readout assignment error channels with machine-verified Kraus completeness ($\sum_k K_k^\dagger K_k = I$), trace preservation ($|\text{Tr}(\rho) - 1| \le 10^{-12}$), Hermiticity, and positive semidefiniteness.
4. An offline deterministic `FakeHardwareProvider` for regression testing and an authorized, fail-closed `RealHardwareProvider` boundary that requires explicit credential confirmation and returns typed errors instead of hanging or silent simulation.

### Falsification criteria
- If any execution mode falls back from `REAL_HARDWARE` to `IDEAL_CLASSICAL` or `NOISY_CLASSICAL` without explicit user request and visible result relabeling, the hypothesis is FALSIFIED.
- If any Kraus channel fails the completeness relation $\sum K_k^\dagger K_k = I$ within $10^{-10}$ tolerance, the hypothesis is FALSIFIED.
- If a noisy density matrix ever has negative eigenvalues (beyond $10^{-12}$ numerical tolerance) or trace deviating from $1.0$ by more than $10^{-12}$, the hypothesis is FALSIFIED.
- If the FakeProvider results are non-deterministic for a fixed seed, the hypothesis is FALSIFIED.
- If default CI requires real provider credentials or makes unmocked external network calls, the hypothesis is FALSIFIED.
- If existing 4-path classical simulation or Pauli expectation value contracts regress, the hypothesis is FALSIFIED.
