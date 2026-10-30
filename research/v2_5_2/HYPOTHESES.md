# CQ-HECS v2.5.2 Hypotheses and Feature Decision

## 1. Decision: no new major feature in this cycle

GEMINI.md §9.6 stops feature expansion while a P0 is open, and §3 makes an
unresolved P0 in incorrect outputs a hard stop for Stable. The audit found two
P0 wrong-result defects in exact paths (CQ-V252-01, CQ-V252-03) and a P1
metric conflation in the v2.5.0 feature itself (CQ-V252-02). This cycle
therefore ships corrections only (patch version 2.5.2). The Hardware-Aware
Quantum Bridge stays at its v2.5.0 scope.

## 2. Hypotheses tested in this cycle

| ID | Hypothesis | Pre-specified test | Result | Status |
|---|---|---|---|---|
| H-252-1 | Every path that reports `EXACT` agrees with Qiskit `Statevector` on random circuits over the full gate manifest. | Seeded fuzz (seeds 1–4, 750 circuits, 1–5 qubits, depth 1–12): exact probabilities within 1e-6, sampled counts within the reported Hoeffding TV bound (δ = 0.05). | Rejected on the baseline (Path B T sign, native SWAP); after the fixes, one excursion in 750 × up to 6 engines, consistent with δ = 0.05. | SUPPORTED after fix (`/tmp` fuzz scripts summarised in EXECUTION_LOG.md; deterministic subset committed as tests) |
| H-252-2 | `BackendProfile.gate_errors` → channel preserves the reported average gate infidelity. | `1 − average_gate_fidelity(Kraus(channel)) == r` to 1e-12 for every profile entry. | Baseline: `r/2` (1q), `3r/4` (2q). | SUPPORTED after fix |
| H-252-3 | The three circuit front-ends (instruction list, Qiskit, OpenQASM 2) are semantically equivalent where all three accept the circuit. | 200 random circuits, identical seeded counts on Path C. | 84 accepted by all three: identical; 116 refused by QASM (gate definitions). | SUPPORTED (with CQ-V252-06 deferred) |

## 3. Carried over (not started)

- Relaxation channels from T1/T2 and gate durations (would change noisy
  results again; needs its own preregistered Aer comparison).
- Transpilation to a profile's basis gates before noise attachment.
- A real-provider adapter: BLOCKED (no credentials, no authorization for paid
  hardware).
