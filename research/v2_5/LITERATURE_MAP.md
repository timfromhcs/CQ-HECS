# CQ-HECS v2.5.0 Literature & Upstream Research Map

## 1. Upstream Primary Sources

### OpenAI Math
- Primary source: `https://github.com/openai/math`
- Checked revision: `7ef5c0cc5ca4b0e072b7a050fca09ab24bc6fa3a` (commit date: 2026-10-26T21:18:03Z).
- Status: 721 manuscripts across 373 families. No transferable algorithm directly applies to the hardware bridge or classical noisy channel simulator.
- Classification:
  - Manuscript 275 (QMA-hardness): `VALIDATION_ONLY`. Confirms complexity boundaries and forbids universal efficient classical simulation claims.
  - Manuscript 283 (Unitary synthesis): `NEGATIVE_RESULT`. Restricts claims regarding polynomial oracle simulation without counting truth-table complexity.

### Qiskit & Hardware Provider Specifications
- Qiskit BackendV2 & Target architecture (Qiskit 2.5.1 / IBM Quantum fake provider):
  - In `BackendV2`, calibration properties are stored in `backend.target` instructions (`InstructionProperties(error, duration)`).
  - Noise models in Aer (`NoiseModel.from_backend`) convert gate errors into depolarizing/thermal relaxation channels and readout errors into assignment matrices.
  - Readout error channel: assignment matrix $M_{ij} = P(\text{measured } i \mid \text{state } j)$.
  - Depolarizing channel: $\mathcal{E}(\rho) = (1 - p)\rho + \frac{p}{3}(X\rho X + Y\rho Y + Z\rho Z)$.
  - Amplitude damping: Kraus operators $K_0 = \text{diag}(1, \sqrt{1-\gamma})$, $K_1 = \begin{pmatrix} 0 & \sqrt{\gamma} \\ 0 & 0 \end{pmatrix}$.
  - Phase damping: Kraus operators $K_0 = \text{diag}(1, \sqrt{1-\lambda})$, $K_1 = \text{diag}(0, \sqrt{\lambda})$.

### Anthropic & Machine-Checked Verification Lessons
- Focus on small, high-value checkable claims:
  - Exact Kraus completeness $\sum_k K_k^\dagger K_k = I$.
  - Trace preservation $\text{Tr}(\mathcal{E}(\rho)) = 1$.
  - Complete positivity: eigenvalues of Choi state / output density matrix $\ge 0$.
  - Result schema serialization stability.

## 2. Decision
The Hardware-Aware Quantum Bridge is selected as the vertical slice for v2.5.0. No external network credentials or unverified physical hardware claims are admitted.
