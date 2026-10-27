# Research ledger — next Stable after v2.2.1

Reviewed 2026-10-26. This ledger records what was considered, what was used,
and what was deliberately **not** adopted. A source appearing here is not a
claim that its results transfer to CQ-HECS.

## Methods actually used in this change

| Method | Source / basis | Use in CQ-HECS | Verification | Decision |
| :--- | :--- | :--- | :--- | :--- |
| Sequential conditional sampling from an MPS via right-norm environments | Ferris & Vidal, Phys. Rev. B 85, 165146 (2012); standard MPS sampling (Schollwöck, Ann. Phys. 326, 96 (2011)) | `MPSSimulator::sample_counts` builds right environments `R_q` and draws each site conditioned on the prefix; GHZ fast path only after an exact tensor check | 24-gate random differential vs dense; non-GHZ bond-2 support; 0.8/0.2 asymmetric counts; 300-qubit GHZ support | ADOPTED |
| Complex SVD two-site factorisation | Standard TEBD/DMRG tensor update | `factorise_theta` uses a one-sided Jacobi SVD of the contracted two-site tensor; truncation keeps the largest singular values | Dense differential on small circuits; adjacent CNOT order cases; non-adjacent routing; rank-growth tests | ADOPTED |
| Fixed-point probability evaluation for sampling | Project-internal convention (Q1.31 amplitudes) | Probabilities are evaluated in double precision from the stored Q1.31 values; this conversion is documented, not hidden | `test_statevector_contract`, `test_mps_contract` | ADOPTED (documented precision boundary) |

## Candidate algorithms reviewed, not adopted

| Candidate | Source | Why not adopted now | Revisit condition |
| :--- | :--- | :--- | :--- |
| Geometry-aware 2D tensor networks / boundary-MPS contraction | Rudolph & Tindall, *npj Quantum Information* (2026-09-24), https://www.nature.com/articles/s41534-026-01372-2 | Requires topology-aware ansatz selection, contraction-order optimisation and convergence control. Current 1D MPS and the four Python paths cover the supported stable scope; adding it without a reference-checked workload and error contract would be a speculative backend. | A reproducible 2D-heavy workload where every current path returns `UNRESOLVED`, plus a verified small-circuit reference and a convergence/error contract. |
| Code-compiled tensor networks with symmetry/relabelling | Deger et al., arXiv:2607.08396 (2026-07-09) | Efficiency depends on specific CSS-code symmetries and automorphisms, not general circuits. No sound symmetry detector exists in the repository yet. | A worked paper example reproduced independently, plus a proof-carrying structural detector and tests that relabelling preserves qubit/bit semantics. |
| Pauli propagation / sparse Pauli dynamics refinements | PRX Quantum (2026-08-11) https://journals.aps.org/prxquantum/abstract/10.1103/6vd7-l9bn ; PRX Quantum (2026-04-22) https://journals.aps.org/prxquantum/abstract/10.1103/fb28-wlv2 ; IBM docs https://qiskit.qotlabs.org/docs/api/pauli-prop/propagation | Path D already implements sparse-Pauli conjugation with a certified per-observable bound. The cited noise results are ensemble/average-case and do not justify arbitrary-circuit guarantees. | A concrete Path D workload that remains `UNRESOLVED` under the current bound, with a conservative pruning bound that accounts for every omitted term. |
| OpenAI Math theorem catalogue | https://github.com/openai/math | No theorem in the reviewed material provides a general efficient classical algorithm for arbitrary quantum circuits; several results are unformalised or assumption-specific. `research/v2_1/openai_math/*` already records the transfer audit. | A specific manuscript whose theorem assumptions match a CQ-HECS workload and whose conclusion is independently checkable. |

## External references used for test design (not as oracles in this run)

- Qiskit `BackendV2` and `qiskit.qasm3` for the legacy provider interface and
  QASM serialisation; the tests assert the provider's own contract, not Qiskit
  sampling streams.
- MQT Bench circuit families (GHZ, QFT, random) as workload-shape guidance.
- Cycle 2 uses Qiskit Aer (`Statevector`, MPS method) and Stim as **differential
  oracles** for small circuits: statevector fidelity, 5σ/TVD sampling bands and
  untruncated Aer MPS where the gate set permits it. These are test-only
  references; no claim of agreement beyond the exercised circuits is made.

## Engineering decisions recorded

1. **QASM address limit 0–255.** `J_QuantumOpcode` stores target/control indices
   in `uint8_t` (16-byte ABI invariant). Rather than change the ABI or silently
   wrap indices, the parser rejects `q[i]` for `i > 255`. Direct C++
   `MPSSimulator` still supports 300 qubits. Extending the opcode layout is a
   future, separately tested ABI change.
2. **Planner-only VulkanEngine.** The class stores site/bond metadata, not
   amplitudes. It now throws on gates and sampling instead of appearing to
   simulate. Real Vulkan compute remains unverified and unadvertised.
3. **Truncation semantics.** The SVD keeps the largest singular values; the
   discarded squared weight is a per-update diagnostic. Retained local tensors
   are rescaled to avoid fixed-point rank collapse. No propagated global error
   bound is claimed.
4. **GHZ fast path.** Selected only by exact structural comparison with the
   canonical GHZ MPS. Any other state, including a locally phase-flipped GHZ,
   uses the generic conditional sampler.

## Go/no-go summary

- Go: SVD MPS update, generic MPS sampling, dense statevector sampling,
  fail-closed planner facade, seeded GHZ diagnostic.
- Defer: 2D tensor networks, code-compiled tensor networks, propagated
  truncation-error bounds, >255-qubit QASM addressing, physical-GPU dispatch.
- No direct transfer from the OpenAI Math catalogue was found.
