# CQ-HECS v2.5.0 Benchmark Protocol

## Preregistered Workloads

1. **Ideal 4-Path Baseline Circuits**:
   - `bell`: 2-qubit Bell state (Path A / Stabilizer).
   - `ghz8`: 8-qubit GHZ state (Path A / Stabilizer).
   - `ising6`: 6-qubit Ising chain (Path D / Pauli expectation).
   - `toffoli_adder`: 4-qubit arithmetic circuit (Path B / Stabilizer Rank).
   - `qft4`: 4-qubit Quantum Fourier Transform (Path C / MPS).

2. **Hardware-Aware Bridge Workloads**:
   - `noisy_bell`: 2-qubit Bell state under depolarizing noise ($p=0.01$) and readout assignment error ($p_{0\to 1} = 0.02, p_{1\to 0} = 0.03$).
   - `amplitude_damping_single`: 1-qubit excited state under amplitude damping ($\gamma = 0.1$).
   - `phase_damping_superposition`: 1-qubit $|+\rangle$ state under phase damping ($\lambda = 0.05$).
   - `fake_manila_smoke`: 5-qubit linear circuit routed through `FakeHardwareProvider`.

## Metrics
- End-to-end wall clock time (median over 5 runs).
- Verification against analytical / Qiskit Aer density matrix reference.
- Maximum deviation from analytical Kraus channel state $< 10^{-10}$.
- Memory and allocation ceilings strictly preflighted.
