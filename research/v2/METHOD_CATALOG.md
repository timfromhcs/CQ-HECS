# CQ-HECS v2 Method Catalog

Purpose: record, for each classical simulation method considered for v2, what
was actually done with it and why. Every "implemented" row names the module and
its tests; every "rejected" or "deferred" row names the concrete reason.

Status legend: **implemented** · **prototype** · **deferred** · **rejected**

Verification levels used throughout (see `README.md` §8):

| Level | Meaning |
| :--- | :--- |
| `CPU_EXACT` | Exact on the CPU, verified against Qiskit `Statevector`/`Aer` |
| `CPU_CERTIFIED` | Approximate with a derived error bound |
| `LOADER_VERIFIED` | Vulkan loader present; no compute dispatch demonstrated |
| `NOT_VERIFIED` | Not exercised on this hardware |

---

## 1. Currently implemented

### 1.1 Stabilizer tableau — Path A · `CPU_EXACT`

`cqhecs/backends/path_a_stabilizer.py`

Gottesman–Knill simulation over GF(2) symplectic arithmetic. Algebraically
exact: there is no floating-point approximation, so `error_bound == 0.0`.

* Gates: H, X, Y, Z, S, Sdg, CX, CZ, SWAP, and Clifford-angle RZ/P/U1.
* Rejects non-Clifford gates rather than dropping them.
* Optional native `HybridEngine`; its qubit-0-leftmost bitstrings are normalised,
  and it is used only when it can faithfully run the circuit (it has no `apply_cz`
  and its `apply_rz` takes two ints, not an angle).

Measured: 6-qubit Clifford chain 0.53 ms, 8-qubit GHZ 0.91 ms.

Tests: `tests/test_correctness_contracts.py::TestBitstringOrdering`,
`::TestNativePythonParity`, native `test_stabilizer`, `test_stabilizer_extreme`.

### 1.2 Stabilizer rank decomposition — Path B · `CPU_EXACT`

`cqhecs/backends/path_b_stabilizer_rank.py`

Each non-Clifford gate is expanded into a finite sum over Clifford branches with
no dropped terms, so the *algebra* is exact. Evaluated in IEEE-754 float64, and
the returned counts are a finite-shot sample — both are reported separately from
`error_bound`.

Two-qubit gates are vectorised (reshape + slice), which removed the per-amplitude
Python loop that had forced an arbitrary 16-qubit ceiling. The ceiling is now
22 qubits and is documented as an implementation limit.

* Supports T, Tdg, RZ/P/U1, RX, RY, using the correct Clifford generator per
  gate (X for RX, Y for RY, Z for RZ/T).

Measured: 4-qubit low-T circuit 1.22 ms; 22-qubit GHZ+T verified against
`Statevector`.

Tests: `::TestPathBContract`, incl. orientation and aliasing regressions.

### 1.3 Untruncated MPS — Path C · `CPU_EXACT` up to memory

`cqhecs/backends/path_c_mps_exact.py`

Bond dimension always grows to the full numerical rank of the two-site block;
there is no truncation budget. Rank selection discards only values below a
relative roundoff floor (1e-13 × σ_max), which is a floating-point statement, not
a mathematical approximation.

* Refused allocations leave the chain coherent (checked before mutating).
* Exact dense sampling is capped at 20 qubits; wider circuits report no counts
  rather than a placeholder.
* Each chain owns a private scratch directory, so concurrent runs cannot collide.

**Known limitation (stated, not hidden):** `numerical_error_bound` is `None`.
The discarded singular-value mass is reported as
`discarded_spectral_mass_diagnostic`, but it is *not* a certified bound — see
§2.1.

Measured: 6-qubit rotation circuit 4.63 ms.

### 1.4 Sparse-Pauli dynamics — Path D · `CPU_CERTIFIED`

`cqhecs/backends/path_d_sparse_pauli.py`

Heisenberg-picture operator evolution. Truncating to a term budget K and
discarding set D gives, by the triangle inequality and ‖P‖∞ = 1:

    |<O_exact> - <O_approx>| <= sum_{P in D} |c_P|

**What this certifies:** Pauli expectation values — single-qubit `<Z_q>` and
parity `<Z_q Z_r>`. Parity terms are included because single-qubit marginals
cannot distinguish entangled states (a Bell state has all-zero marginals).

**What it does not certify:** a sampled bitstring distribution. Joint counts are
therefore opt-in via `allow_uncertified_joint_counts=True` and are labelled
`counts_are_joint_distribution=False`; metadata records `error_bound_covers` and
`error_bound_excludes`.

Measured: 4-qubit high-T circuit routes to Path C at auto settings; Path D is
reached when C's memory ceiling is hit or the path is forced.

### 1.5 Finite-shot confidence · corrected in this cycle

`cqhecs/result.py`

The previous `sqrt(ln(2/delta)/(2n))` was labelled a total-variation bound. That
expression bounds a *single* categorical outcome; total variation sums over all K
outcomes, so the `2^K − 2` concentration prefactor cannot be dropped.

Measured violation rate, n=1000, δ=0.05, uniform distribution:

| K | naive bound | violations |
| ---: | ---: | ---: |
| 2 | 0.0429 | 0.6% |
| 16 | 0.0429 | 73.0% |
| 64 | 0.0429 | **100.0%** |

Replaced with the Weissman et al. (2003) result via Lemma 1 of Mardia et al.
(2019), using φ ≥ 2 so the bound is distribution-independent:

    TV <= sqrt( ln((2^K − 2)/δ) / (2n) )

It reduces exactly to the classic value at K=2, holds within δ for K = 2…64, is
computed in log space (a 1000-qubit register no longer overflows), and is clamped
to 1.0.

---

## 2. Open numerical issues

### 2.1 Path C has no certified roundoff bound · open

Deriving one requires tracking the product of retained singular values across
every two-site rewrite. Until that exists, `numerical_error_bound` stays `None`.
A per-rewrite diagnostic is not a substitute; reporting it as a bound would
overstate what is known.

### 2.2 Path B exactness is algebraic, not symbolic · documented

The rank decomposition drops no terms, but coefficients like
`(1 + e^{iπ/4})/2` are evaluated in float64. The *structure* is exact; the
arithmetic is not. Reported via `numerical_mode: float64-exact-decomposition`.

---

## 3. Considered and not adopted

| Method | Status | Reason |
| :--- | :--- | :--- |
| Dense statevector beyond ~22q | deferred | O(2^n) memory. Path B already refuses above its ceiling rather than silently degrading. |
| Dense statevector ≤22q | implemented (Path B) | — |
| General tensor networks / contraction ordering | deferred | Path C is a 1D MPS. A real contraction-ordering optimiser is a substantial project; the roadmap's own table notes good contraction is not cheap for every graph. |
| Decision diagrams (QMDD/QuIDD) | rejected for v2 | Strong advantage only for highly regular structure; licence, maintenance and a second exact simulator would be added without a clear win over Paths A/B/C. Revisit if a concrete circuit class appears. |
| Schrödinger–Feynman / circuit cutting | deferred | Genuinely useful for wide shallow circuits, but combining sub-circuit estimates needs its own error accounting, and the sampling/estimation semantics differ from the current single-state contract. Would need its own path with its own result type. |
| Circuit cutting | deferred | Same reason as above; overhead and combined estimator error must not be hidden. |
| Feynman path sum | rejected for v2 | Number of contributing paths can explode without a cheap certificate; no advantage we could demonstrate against Path C. |
| Symmetry / subspace reduction | deferred | Requires provably safe invariant detection. Unsound symmetry assumptions silently corrupt results, which is exactly the failure class this project is removing. |
| ZX calculus / graph-state rewrites | deferred | Useful for particular graph-like tasks; not a general replacement. No workload identified where it beats Paths A/B/C. |
| Noise trajectories / density matrix / MPO | rejected for v2 | The current contract is pure-state simulation. Adding mixed state changes the result schema's meaning, not just adds a method. Out of scope for this contract. |
| Qubit reuse / circuit cutting with reuse | deferred | Same as circuit cutting. |
| GPU compute via Vulkan | `LOADER_VERIFIED` only | The loader enumerates a device; **no compute dispatch has been demonstrated on a physical GPU in this cycle**. CPU is the only verified execution path. See `README.md` §8. |

---

## 4. What "v2 must not claim"

Recorded so future work does not reintroduce them:

* No method here bypasses BQP ≠ BPP. Path D in particular degrades transparently
  rather than simulating arbitrary circuits in polynomial time.
* No bound is reported for a metric it does not cover.
* No hardware claim without evidence on that hardware.
* No count is returned that was not actually sampled.

---

## 5. Provenance

* Environment: Windows 11, Python 3.14.6, NumPy 2.4.6, Qiskit 2.5.1,
  Aer 0.17.2, Stim 1.16.0, MSVC 19.44, Vulkan SDK 1.4.357.
* Local suite: 202 passed, 0 failed (native engine built).
* Mutation harness: baseline OK, 7/7 killed.
* Timings in this document are single-run wall clock on the local CPU and are
  not a performance claim.
* Primary source for the finite-shot bound: Weissman, Ordentlich, Seroussi,
  Verdú, Weinberger (2003), *Inequalities for the L1 deviation of the empirical
  distribution*; lemma form via Mardia, Jiao, Tánczos, Nowak, Weissman (2019),
  arXiv:1809.06522, Lemma 1.