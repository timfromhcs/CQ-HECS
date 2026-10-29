# Literature and transfer map

## Live OpenAI Math snapshot

Pinned upstream: `openai/math@7ef5c0cc5ca4b0e072b7a050fca09ab24bc6fa3a` (2026-10-26). README, history, CONTENTS and `lean/formalization.yaml` were retrieved at that revision. Upstream reports 721 manuscripts / 373 families / ~42% top-line formalization. Prior local snapshot was 719 / 372 at `1581d4cbdd69a0faf34b2089614fe2a814316a6a`. The API recursive tree was truncated and is not used as a complete independent count.

All manuscript-derived claims remain research inputs, not implementation evidence. Classification uses `DIRECT_TRANSFER`, `ADAPTABLE`, `VALIDATION_ONLY`, `NEGATIVE_RESULT`, `NOT_RELEVANT`, or `UNVERIFIED_RESEARCH`; `RESEARCH_ONLY` below means no stable-code transfer.

| Candidate | Pinned upstream scope | Formalization catalogue/status | CQ-HECS decision and required check |
|---|---|---|---|
| 130 — Exact Fourier transforms below n log n | Exact complex arithmetic, unrestricted coefficients, supplied root of unity; scalar preparation/indexing model. | CONTENTS links `lean/docs/130.md`; exact theorem-to-paper scope still requires source inspection. | **ADAPTABLE / DEFER.** No automatic float64 tensor/FFT speedup. Transfer only after identical operation model, stability and end-to-end baseline comparison. |
| 273 — Entropy photon-number inequality | Finite-energy bosonic inputs/modes and beamsplitter mixing. | CONTENTS links Lean catalogue entry. | **NOT_RELEVANT (current qubit core) / RESEARCH_ONLY.** No bosonic/CV state representation; no forced qubit mapping. |
| 275 — QMA-hardness of continuum Coulomb energy | Continuum spinful-fermionic Coulomb infimum with stated reduction/promise conditions. | CONTENTS links Lean catalogue entry. | **VALIDATION_ONLY.** Complexity boundary; no runtime or ground-state algorithm claim. |
| 279 — Exact quantum factoring over fixed finite gate set | Polynomial uniform quantum circuit family, probability-one factoring on a quantum computer. | CONTENTS links `lean/docs/279.md`; prior local audit says headline circuit statement is formalized. | **VALIDATION_ONLY.** Potential reproducible quantum-circuit benchmark, never a classical simulation/factoring shortcut. |
| 283 — Polynomial-time unitary synthesis from Boolean oracle | Target-dependent unrestricted Boolean oracle; efficient classical oracle construction not asserted. | No Lean link in the pinned CONTENTS entry. | **NEGATIVE_RESULT for free-simulator claims.** Oracle truth-table/construction cost must remain in any complexity ledger. |
| 284 — Optimal quartic randomized/quantum query separation | Total Boolean functions, bit-query model, bounded error, unrestricted computation between queries. | No Lean link in pinned CONTENTS entry. | **VALIDATION_ONLY.** Query complexity is not gate-level classical runtime or sampling complexity. |
| October 26 ETH manuscript | Fixed-width CNF exact counting claim; public history says independent expert review is pending/requested. | New accompanying Lean formalization reported upstream; scope not yet independently audited. | **UNVERIFIED_RESEARCH.** No CQ-HECS complexity or solver claim until the exact formal statement and implementation reduction are independently checked. |

## Emulator and numerical references

- Stim 1.16.0 and Qiskit Aer 0.17.2 are installed locally for compatible differential references. Their outputs/options must be pinned per experiment; no runtime superiority is inferred from installation.
- Qiskit 2.5.1 Statevector/Operator and independent NumPy matrices are preferred small-system references. A reference must not call the CQ-HECS helper under test.
- Rudolph & Tindall, 2D tensor networks (DOI `10.1038/s41534-026-01372-2`) and NVIDIA cuTensorNet remain candidates for a later isolated H3 prototype, not evidence for a stable backend or Vulkan speedup.
- Weissman et al. (2003), Theorem 2.1, as cited in `result.py`, is the current TV-bound reference. H8 requires checking support, metric, confidence and clamping rather than treating tests as proof.

## Decision rule

P0/H0, H1 and H8 correctness work takes priority. At most one major architectural prototype may follow only after those contracts are resolved. No OpenAI Math manuscript is currently accepted as a new stable algorithm.

## SOTA emulator landscape (2026-10-29)

Live repository metadata (GitHub API, retrieved this session): Stim (`quantumlib/Stim`) latest release v1.16.0 (2026-05-22), pushed 2026-10-29; qsim v0.22.0 (2025-06-24); Qiskit Aer 0.18.2 (2026-10-26); MQT DDSIM v2.7.0 (2026-10-12); Qulacs v0.6.14 (2026-07-29). OpenAI Math head re-checked: `7ef5c0cc5ca4b0e072b7a050fca09ab24bc6fa3a` (2026-10-26), unchanged since the pinned snapshot.

**Limitation:** the web-search tool was unavailable in this session (model error on every call), so no paper or documentation page was read. The capability comparison below is from the projects' public descriptions as previously known, not freshly verified.

| Capability | Typical in SOTA tools | CQ-HECS 2.4.0 | Decision |
| :--- | :--- | :--- | :--- |
| Pauli expectation values | Aer (`save_expectation_value`), Stim (frame/observables), qsim, Qulacs | **added** (exact stabilizer/dense, certified Path D) | shipped |
| Wider standard gate coverage | Aer, qsim, Qulacs | 26 composite gates lowered exactly | shipped |
| Noise models / density matrix | Aer, Qulacs, Stim (Pauli noise) | none | RESEARCH_ONLY (H14) |
| Mid-circuit measurement / reset / classical control | Aer, Stim | refused | next candidate: Path A first (tableau collapse) |
| Batched Pauli-frame sampling | Stim | none | H5, needs benchmark |
| Gate fusion / SIMD / GPU statevector | qsim, Aer, Qulacs | CPU numpy only; Vulkan primitives | H9, DEFER |
| Decision-diagram simulation | DDSIM | none | not planned |
| Tensor-network contraction planning / slicing | cuTensorNet, quimb | none | H3, DEFER |
