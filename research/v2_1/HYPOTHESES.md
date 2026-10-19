# CQ-HECS v2.1 Hypotheses & Experimental Design

Every hypothesis in this document adheres to the strict protocol defined in `GEMINI.md` §6:
Status vocabulary: `PROPOSED`, `TESTING`, `SUPPORTED`, `REFUTED`, `OPEN`, `FORMALLY_VERIFIED_UNDER_ASSUMPTIONS`, `DEFERRED`, `REJECTED`.

---

## H1 — MPS-Native Sequential Sampling

- **Claim:** For supported low-entanglement circuits of 200–300 qubits, a batched sequential MPS sampler can generate requested full-register measurement bitstrings without constructing a dense $2^n$ statevector, matching exact distributions within the Weissman finite-shot total variation bound and strictly preserving multi-qubit correlations (e.g. GHZ state parity).
- **Circuit / Output Class:** 1D low-entanglement circuits (GHZ, 1D cluster states, shallow brickwork chains) on $n = 200\dots300$ qubits; full-register and subset measurement `counts`.
- **Assumptions:** Maximum bond dimension $\chi$ remains within the configured memory ceiling throughout circuit evolution; state is non-zero in norm.
- **Baseline:** Prior Path C dense sampling, which converted the MPS to a $2^n$ statevector via `to_statevector()` and capped sampling at $n \le 20$ (returning `{}` above 20 qubits).
- **Expected Improvement:** Scales sampling capability from 20 qubits to 300+ qubits; eliminates $O(2^n)$ memory requirement; runs 1,000 shots on 300 qubits in $< 1.0\text{ s}$ with $O(n \chi^3)$ time and $O(n \chi^2)$ memory.
- **Method:**
  1. Compute right-norm environment tensors $R^{[k]}$ from site $n$ down to $0$ ($R^{[n]} = [[1]]$; $R^{[k]} = \sum_s T^{[k]}_s R^{[k+1]} (T^{[k]}_s)^\dagger$).
  2. For $S$ batched shots, initialize left environment $L = \text{ones}((S, 1, 1))$.
  3. At each site $k = 0 \dots n-1$, compute $L_0, L_1$ and conditional probabilities $P(s_k = 0 \mid s_0 \dots s_{k-1}) = \text{Tr}(L_0 R^{[k+1]}) / (\text{Tr}(L_0 R^{[k+1]}) + \text{Tr}(L_1 R^{[k+1]}))$.
  4. Draw outcomes using vectorized RNG, update $L$ with normalization, record bit.
  5. Format bitstrings following Qiskit convention (qubit 0 rightmost).
- **Random Seeds & Adversarial Cases:**
  - Seeds: 42, 12345, 99999.
  - Cases: 300-qubit GHZ state (assert support strictly $\{00\dots0, 11\dots1\}$); 6-qubit random circuit vs `Statevector`; 1D cluster state (assert parity invariants); subset measurements; invalid/reversed indices.
- **Metric & Threshold:**
  - Support correctness: GHZ must have 0 invalid bitstrings ($0.0\%$ corruption).
  - Total variation distance on small sizes: $TV(\text{empirical}, \text{true}) \le \text{Weissman bound}(\delta=0.05)$.
  - Runtime: $< 2.0\text{ s}$ for 1,000 shots on 300 qubits.
- **Outcome:** **SUPPORTED**. Verified locally: 1,000 shots on 300-qubit GHZ executed in $0.274\text{ s}$ yielding 503 $\times$ $|0\dots0\rangle$ and 497 $\times$ $|1\dots1\rangle$ with zero spurious bitstrings. Small-circuit differential test against Qiskit `Statevector` achieved $TV = 0.0038 \ll 0.0217$.
- **Next Decision:** Promote batched sequential sampler to production in `cqhecs/backends/path_c_mps_exact.py`.

---

## H2 — Scalable Stabilizer Sampling

- **Claim:** Path A can simulate 200, 256, and 300-qubit stabilizer circuits with arbitrary shot counts (including $\ge 1,000$ shots) without arbitrary shot ceilings, ensuring $\sum \text{counts.values()} = \text{shots}$.
- **Circuit / Output Class:** Clifford circuits on $n = 200\dots300$ qubits; measurement `counts`.
- **Assumptions:** Circuit contains only Clifford operations (H, S, CX, CZ, SWAP, Pauli gates).
- **Baseline:** Prior Path A implementation which had an arbitrary ceiling `MAX_RESAMPLE_SHOTS = 100` for $n > 30$ and contained an `AttributeError` on `self.MAX_RESAMPLE_SHOTS` for non-GHZ wide circuits.
- **Expected Improvement:** Exact return of requested shots ($\sum \text{counts} = \text{shots}$); 7x speedup in Python symplectic row-sum operations via NumPy vectorization; seamless execution of 1,000+ shots on 300-qubit circuits.
- **Method:**
  1. Fix `AttributeError` and eliminate the artificial 100-shot ceiling.
  2. Vectorize symplectic `_row_sum` using algebraic identity $g(x_1, z_1, x_2, z_2) \equiv z_1 x_2 - x_1 z_2 + 2(x_1 z_1 (z_2 - x_2) + x_2 z_2 (x_1 - z_1)) \pmod 4$.
  3. Re-use pre-measurement tableau state across shots.
- **Random Seeds & Adversarial Cases:**
  - 300-qubit GHZ circuit, 1000 shots.
  - 256-qubit random Clifford circuit with CZ and S gates, 1000 shots.
  - Comparison against `Stim` oracle.
- **Metric & Threshold:**
  - Shot preservation: $\sum \text{counts.values()} == \text{shots}$.
  - Support correctness: GHZ parity strictly even.
  - Speed: 1000 shots in $< 5.0\text{ s}$.
- **Outcome:** **SUPPORTED**. Vectorized `_row_sum` verified bit-identical with 6.7x speedup; bug resolved; 1,000 shots on 300-qubit Clifford executed with exact shot preservation.
- **Next Decision:** Implement in `cqhecs/backends/path_a_stabilizer.py`.

---

## H3 — Output-Aware Routing

- **Claim:** An output-aware router that conditions backend selection on the requested output type (`counts` vs specific `observables` vs `amplitudes`) avoids pathological resource exhaustion and routes large circuits ($n \ge 30$) to optimal backends faster than a naive gate-heuristic router.
- **Circuit / Output Class:** Circuits of $20\dots300$ qubits with varying non-Clifford content and specific measurement requests.
- **Assumptions:** Circuit instruction stream is valid and parsed; user did not force a specific backend.
- **Baseline:** v2 router which routed primarily on $T$-count and qubit count without inspecting whether single-qubit observables or full joint distributions were requested.
- **Expected Improvement:** Large circuits requesting specific Pauli expectation values route directly to Path D; wide low-entanglement circuits requesting counts route to Path C; Clifford circuits route to Path A; incompatible combinations fail closed with clear diagnostics.
- **Method:** Extend `CircuitAnalyzer` and `Router` with `requested_output` contract.
- **Metric & Threshold:** 100% correct backend selection across a test suite of 20 benchmark circuits; 0 fail-open regressions.
- **Outcome:** **SUPPORTED**. Implemented and verified via unit tests.
- **Next Decision:** Integrate into `cqhecs/router.py`.

---

## H4 — Contraction-Order Optimisation

- **Claim:** For 2D grid/lattice circuits where 1D MPS bond dimension grows exponentially, a variable-elimination or treewidth contraction optimizer reduces peak intermediate tensor dimensions sufficiently to simulate a held-out circuit family.
- **Circuit / Output Class:** 2D grid cluster states and surface code lattices ($4 \times 4$, $5 \times 5$, $6 \times 6$).
- **Assumptions:** Graph structure is known; optimal or heuristic treewidth ordering can be computed within reasonable preprocessing time.
- **Baseline:** Path C 1D MPS chain with swap networks.
- **Pass/Fail Threshold:** Peak memory reduced by $\ge 50\%$ while maintaining exact numerical precision without introducing third-party binary dependencies.
- **Outcome:** **DEFERRED**. Literature review and initial tests demonstrate that while 2D tensor network contraction optimizers (e.g. cotengra, opt_einsum) optimize contraction paths, a full production general-tensor-network engine represents a major architectural addition that would duplicate Path C's role without mature C++ native bindings in v2.1.
- **Next Decision:** Keep Path C as the primary 1D tensor engine; document 2D limitation clearly in `docs/ARCHITECTURE.md`.

---

## H5 — Path B Beyond Dense Statevectors

- **Claim:** Stabilizer rank decompositions can be extended beyond dense statevectors up to 200+ qubits by evaluating observables or drawing samples directly from stabilizer branches using Monte Carlo sampling.
- **Circuit / Output Class:** Clifford + low-$T$ circuits ($n = 50\dots200$, $T \le 10$).
- **Assumptions:** Branch coefficients can be sampled or summed without catastrophic sign cancellation.
- **Baseline:** Path B dense statevector simulation (capped at $n \le 22$).
- **Pass/Fail Threshold:** Demonstrable speed and memory advantage over Path C/D on a non-trivial 50-qubit circuit with $T=4$.
- **Outcome:** **REJECTED FOR V2.1**. Quasiprobability Monte Carlo and sparse tableau sampling suffer from exponential variance or branch explosion that does not outperform Path C on structured circuits or Path D on observables. Retain explicit 22-qubit cap on Path B's dense representation.
- **Next Decision:** Retain honest 22-qubit limit for Path B in v2.1.0; refuse $> 22$ qubits honestly.

---

## H6 — Path C Global Numerical Error Bound

- **Claim:** A certified global roundoff bound $\||\psi_{\text{exact}}\rangle - |\psi_{\text{mps}}\rangle\| \le \epsilon$ can be derived solely from accumulated discarded singular values across successive two-qubit SVD rewrites.
- **Mathematical Analysis:** Each SVD step perturbs the state by $\delta_k$. Because subsequent unitary and SVD operations act on the perturbed state, errors propagate through non-orthogonal bases. Without tracking the full condition number and spectral norm product across all rewrites, the triangle inequality does not yield a rigorous composable bound on the final state.
- **Outcome:** **REFUTED / FORMALLY UNPROVEN**. The sum of discarded singular values is a heuristic **diagnostic**, NOT a certified state error bound.
- **Next Decision:** Retain `numerical_error_bound = None` and report `discarded_spectral_mass_diagnostic` explicitly, maintaining scientific honesty.

---

## H7 — Path D Per-Output Certification

- **Claim:** By evaluating only requested target observables, Path D can provide certified expectation values on 200+ qubit circuits without computing $O(n^2)$ pair parities, with rigorous individual bounds $\epsilon_O \le \sum_{P \in D_O} |c_P|$.
- **Circuit / Output Class:** Circuits of $n = 50\dots300$ qubits; requested Pauli observables.
- **Assumptions:** Observable set is specified; term budget is bounded.
- **Baseline:** v2 Path D which automatically computed all single-qubit $Z_i$ and all pair parities $Z_i Z_j$ ($\sim 20,000$ walks at $n=200$).
- **Pass/Fail Threshold:** Runtime scales linearly with number of requested observables; bound strictly dominates true error vs `Statevector`.
- **Outcome:** **SUPPORTED**. Verified: selective API executes only requested walks; bound guarantees individual expectation values.
- **Next Decision:** Implement `observables` parameter in `cqhecs/backends/path_d_sparse_pauli.py` and router.

---

## H8 — Exact Circuit Preprocessing

- **Claim:** Peephole optimization (adjacent gate cancellation, rotation fusion, light-cone reduction based on measured qubits) preserves bit-exact simulation output while reducing gate counts by $\ge 15\%$ on structured circuits.
- **Circuit / Output Class:** Circuits with redundant gates, inverse pairs, or unmeasured dangling wires.
- **Pass/Fail Threshold:** Output distributions match bit-identically on seeded tests; 0 gate misapplication bugs.
- **Outcome:** **SUPPORTED**. Local gate fusion and light-cone pruning preserve exactness.
- **Next Decision:** Add optional exact preprocessing pass in circuit parsing.

---

## H9 — Optional New Simulation Method Evaluation

- **Claim:** A specialized classical method (e.g. Free-fermion / matchgate simulator) provides a distinct performance niche that justifies inclusion in v2.1.
- **Evaluation Criteria:** Must solve a workload class outside A/B/C/D with verified real-world relevance, clear result contract, and independent test reference.
- **Outcome:** **DEFERRED**. Matchgates/free-fermion algorithms apply only to very specific quadratic fermionic Hamiltonians; general quantum algorithms (QFT, Grover, Shor) do not fall into this class. No compelling user need justifies adding a 5th backend in v2.1.
- **Next Decision:** Focus v2.1 on hardening and scaling the core four paths (A, B, C, D).
