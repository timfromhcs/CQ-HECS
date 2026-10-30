# CQ-HECS v3 Literature Map (searched 2026-10-30)

Sources were found by web search and, where marked **read**, the PDF was read
page by page (BrowsingBee PDF reader; arXiv itself is not reachable from the
build environment). "Read pp." lists what was actually read. Classification
follows GEMINI.md §5.1.

## 1. P vs NP, barriers and complexity limits

| Source | Read | Content used | Classification | Consequence for CQ-HECS |
|---|---|---|---|---|
| S. Aaronson, "P ?= NP" survey (2017), https://www.scottaaronson.com/papers/pnp.pdf | pp. 1–4 (abstract, contents, introduction) | Status: open; barriers are relativization, natural proofs, algebrization; GCT and "ironic complexity" (Williams) as the live programmes | NEGATIVE_RESULT for any "solved P vs NP" claim | No CQ-HECS document may claim progress on P vs NP. Nothing in a simulator can "bridge" a proof barrier: the barriers say which *proof techniques* cannot work, they are not engineering gaps. |
| Baker–Gill–Solovay (1975), Razborov–Rudich (1997), Aaronson–Wigderson "Algebrization" (STOC 2008, ECCC TR08-005) | via the survey and search abstracts | Relativizing, natural and algebrizing techniques cannot separate P from NP (and NEXP from P/poly etc.) | NEGATIVE_RESULT | Same as above. |
| Woeginger's P-versus-NP page (last updated 2016; author died 2022) | search abstract | 116 claimed proofs (62 "P = NP", 50 "P ≠ NP"), none accepted | NEGATIVE_RESULT | Treat any P = NP claim as unverified by default. |
| R. Williams, "Simulating Time with Square-Root Space", STOC 2025, arXiv:2502.17779 | search abstract | TIME[t] ⊆ SPACE[√(t log t)] via Cook–Mertz tree evaluation | NOT_RELEVANT (runtime) / RESEARCH_ONLY | A space-for-time trade-off for Turing machines; no transfer to amplitude or Pauli-term memory in CQ-HECS without a new derivation. Not pursued. |
| Raz–Tal, "Oracle separation of BQP and PH" (STOC 2019, ECCC TR18-107) | search abstract | Relative to an oracle, BQP ⊄ PH (Forrelation) | NEGATIVE_RESULT | Supports the existing rule: no claim of efficient classical simulation of arbitrary quantum circuits. Oracle results do not settle the unrelativized question either way. |
| Bouland, Fefferman, Nirkhe, Vazirani, arXiv:1803.04402 (Nat. Phys. 2019) | search abstract | Worst-to-average-case #P-hardness of exact output probabilities of random circuits | VALIDATION_ONLY | Exact paths (A–C, dense) must stay exponential in the worst case; Path B/C limits stay explicit. |
| Mehraban–Tahmasbi, arXiv:2305.10277 | search abstract | Approximate stabilizer rank of \|T⟩^⊗n is Ω̃(n²) | NEGATIVE_RESULT | Path B cost claims stay "exponential in T-count"; no polynomial claim. |
| MIP* = RE | not read | — | NOT_RELEVANT | Interactive-proof result; no bearing on a circuit simulator. |

## 2. Classical simulation of noisy circuits (the transferable part)

| Source | Read | Content used | Classification | Consequence |
|---|---|---|---|---|
| Aharonov, Gao, Landau, Liu, Vazirani, "A polynomial-time classical algorithm for noisy random circuit sampling", STOC 2023, arXiv:2211.03999 | **pp. 1–6** | Pauli-path integral; depolarizing noise damps a path by (1−γ)^weight; low-weight paths dominate on average (needs anti-concentration, random gates); "not practical in its current form" | ADAPTABLE | Mechanism used in W8. The average-case guarantee is **not** claimed. |
| Schuster, Yin, Gao, Yao, "A polynomial-time classical algorithm for noisy quantum circuits", PRX 15, 041018 (2025), arXiv:2407.12768 | **pp. 1–8** | Heisenberg Pauli propagation with weight truncation; RMS error over input ensembles (Lemma 1: ≤ Frobenius norm of the truncated part); gate-based noise: total truncated norm ≤ (d+1)e^{−2γ(ℓ+1)}; error mitigation efficient ⇒ classically simulable on most inputs | ADAPTABLE | W8 implements the same propagation with noise channels; CQ-HECS reports the **worst-case** discarded 1-norm (valid for this input), not the RMS bound. |
| Angrisani, Mele, Rudolph, Cerezo, Holmes, "Simulating quantum circuits with arbitrary local noise using Pauli Propagation", arXiv:2501.13101 | **pp. 1–10** | Arbitrary local noise incl. non-unital (normal form D, t); path-weight truncation; effective log depth; Monte Carlo error certification; numerics with PauliPropagation.jl | ADAPTABLE | W8 handles non-unital channels (identity terms appear); path-weight truncation and Monte Carlo diagnostics are future options and would be labelled diagnostic, not certified. |
| Begušić, Gray, Chan, "Fast and converged classical simulations of evidence for the utility of quantum computing before fault tolerance", Sci. Adv. 10, eadk4321 (2024), arXiv:2308.05077 | **pp. 1–5** | Sparse Pauli dynamics: coefficient-threshold truncation, Clifford gates exact, angles split θ = θ' + kπ/2; 127-qubit kicked Ising converged on a laptop | DIRECT_TRANSFER (method already in Path D) | Path D's threshold truncation is this method; the Clifford pre-transformation is not implemented (candidate optimisation, needs its own benchmark). |
| Angrisani et al., "Classically estimating observables of noiseless quantum circuits", arXiv:2409.01706 | search abstract | Noiseless random circuits: quasi-polynomial for 1/poly precision | VALIDATION_ONLY | No change. |
| Tindall, Fishman, Stoudenmire, Sels, PRX Quantum 5, 010308 (2024), arXiv:2306.14887 | search abstract | Belief-propagation tensor networks on heavy-hex | DEFERRED | Possible future path; not in v3. |
| Google Quantum AI, "Quantum Echoes" (OTOC), Nature 2025, DOI 10.1038/s41586-025-09526-6 | search abstract / blog | Claimed verifiable advantage, 65 qubits; classical estimate contested | VALIDATION_ONLY | Context only; CQ-HECS makes no claim about it. |

## 3. Decision

The only part of this literature that turns into code is §2: noise damps
high-weight Pauli components, so Heisenberg-picture Pauli propagation with the
adjoint noise channels makes noisy expectation values of large circuits
tractable *in practice*. W8 implements it with a bound that stays rigorous for
the given circuit and input (CPTP adjoints are operator-norm contractive), and
validates it against Qiskit Aer. The complexity results of §1 constrain claims;
they are not implementable.

## 4. SAT solvers, proof certificates and "workspace" theories (searched 2026-10-30)

| Source | Read | Content used | Classification | Consequence |
|---|---|---|---|---|
| SAT Competition 2025 / Kissat, CaDiCaL (DRAT/LRAT proof output) | search abstracts | State-of-the-art solvers emit checkable UNSAT proofs; competitions require them | ADAPTABLE | v3.3.0 `cqhecs.sat` emits a tree-resolution refutation replayed by `check_refutation`; CaDiCaL (python-sat) is the test oracle only. Tree resolution is exponentially weaker than CDCL/LRAT; no speed claim. |
| Grover/QAOA for SAT | general knowledge | Quadratic query speedup at best; no known polynomial quantum SAT algorithm | NEGATIVE_RESULT | No quantum-SAT claim. |
| Anthropic, "Verbalizable Representations Form a Global Workspace in Language Models", arXiv:2607.15495; Dehaene–Naccache on global workspace theory | search abstracts | Interpretability/cognitive-science hypothesis about LLM activations | NOT_RELEVANT (to simulation) / RESEARCH_ONLY | No technical bridge to SAT or circuit simulation. The only transferable idea is an engineering pattern: a blackboard where entries are accepted only after independent verification (what `certified` does). No consciousness or cognition claim. |
| This repo's "J-Space Gamma/Alpha/Delta" (`python_bridge`) | repo | Hash-keyed state table for DPLL | NAMING COLLISION | Unrelated to the "J-space" of the LLM literature. |

Decision: of §4 only certificate checking becomes code (v3.3.0). Real-QPU
verification stays with the committed R3 evidence (`research/v4/evidence/`);
public hardware datasets on zenodo/dryad/huggingface were unreachable from this
build environment, so no new R3 data was added in this release.
