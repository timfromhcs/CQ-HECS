# CQ-HECS Release Notes

**Current version:** see `scripts/version.py` (single source of truth).
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v<version>.md`. The content below describes the current
> state of the code, not a historical target.

---

## 1. What this release is

A correctness release. Its purpose is that every reported number can be
justified and every failure mode is explicit rather than silent.

Four classical simulation paths, all CPU-based:

| Path | Method | Correctness class |
| :--- | :--- | :--- |
| A | Stabilizer tableau | Exact (GF(2) symplectic arithmetic) |
| B | Stabilizer rank decomposition | Exact algebra, float64 arithmetic, finite-shot counts |
| C | MPS, unbounded bond dimension | No truncation; no certified roundoff bound (see §4) |
| D | Sparse-Pauli dynamics | Certified bound on **expectation values** |

---

## 2. Correctness work

### Fabricated results removed

* **Path B** substituted a uniform distribution when its rank decomposition
  failed to normalize, and returned `{'0'*n: shots}` for circuits wider than the
  statevector limit — both reported as `exact=True, error_bound=0.0`. Both now
  raise.
* **Path C** returned an all-zeros placeholder beyond its sampling limit. It now
  reports no counts.
* **Path A** inflated 100 real samples up to the requested shot count for wide
  circuits. It now reports the number of shots actually drawn.
* The legacy `python/cq_hecs` Qiskit provider returned a fabricated 50/50 counts
  dict when the native engine was absent, with `success=True`. It now raises.

### Correlation loss fixed

Path D sampled each qubit **independently** from its own `<Z_q>` marginal and
returned the result as a joint measurement distribution. A Bell state came out
uniform. Path D now reports certified `expectation_values` — single-qubit Z and
**parity `Z_q Z_r`**, which are what actually carry correlation structure. Joint
counts are opt-in and labelled `counts_are_joint_distribution=False`.

### Silently ignored gates fixed

* Path C skipped any gate outside its dispatch chain and discarded singular
  values below an absolute `1e-14` cutoff while still claiming exactness.
* Path B ignored unknown gates, hiding two real bugs: Clifford-angle `RZ` and
  *all* `RX`/`RY` gates were never applied. `RX`/`RY` also used a hardcoded `Z`
  as their Clifford generator.
* Path D treated unrecognised gates as the identity. `CZ`, `SWAP`, `RX` and `RY`
  all took that path and returned wrong answers.
* Path A never called its own `apply_cz`, and dropped Clifford-angle rotations.

### Bitstring ordering corrected

Paths A and C did not use the Qiskit convention (qubit 0 rightmost): `X` on
qubit 0 of a 3-qubit circuit returned `'100'` instead of `'001'`. The native
C++ engine renders qubit 0 *leftmost*, the opposite of every Python path; its
output is normalised, and the native engine is used only when it can faithfully
run the circuit.

The Qiskit BackendV2 integration also mis-mapped classical bits:
`measure_all()` maps qubit q to clbit q+n, so the outcome belongs in the *high*
columns. `X` on qubit 2 of 3 qubits returned `000100` where Aer returns
`100 000`.

### Fail-closed routing

The analyzer defaulted **any** unrecognised circuit input to Path A. A
user-forced path could silently reroute. The router caught bare `Exception`,
turning a programming error into "try the next path". All three now fail closed
with typed errors naming the offending gate.

---

## 3. Numerical guarantees

`SimulationResult` separates three error sources instead of conflating them:

| Field | Meaning |
| :--- | :--- |
| `error_bound` | Deliberate approximation. `0.0` means nothing was deliberately approximated. |
| `numerical_error_bound` | Measured float roundoff, where derivable. |
| `sampling_error_bound` | Finite-shot confidence bound. |

`total_error_bound` composes them **only** when they share a metric; it is
`None` for observable-only results, because a bound on expectation values does
not bound a bitstring distribution.

### The finite-shot bound was wrong and is now correct

The previous expression `sqrt(ln(2/δ)/(2n))` was documented as a total-variation
bound. It bounds a *single* categorical outcome; total variation sums over all K
outcomes, so the `2^K − 2` concentration prefactor cannot be dropped.

Measured violation rate at n=1000, δ=0.05: **73% at K=16 and 100% at K=64**,
while claiming to hold with probability 95%.

Replaced with the Weissman et al. (2003) result (via Mardia et al. 2019,
Lemma 1), distribution-independent using φ ≥ 2:

    TV <= sqrt( ln((2^K − 2)/δ) / (2n) )

It reduces exactly to the classic value at K=2, holds within δ for K = 2…64,
is computed in log space (no overflow at 1000 qubits), and is clamped to 1.0.

---

## 4. Known limitations

These are deliberate and documented, not defects to be discovered later.

1. **Path C reports no certified roundoff bound.** The discarded
   singular-value mass is exposed as `discarded_spectral_mass_diagnostic`, but
   per-rewrite masses do not compose into a state-norm bound without a
   propagation analysis that is not implemented. Reporting it as a bound would
   overstate what is known.
2. **Path B exactness is algebraic, not symbolic.** The decomposition drops no
   terms, but coefficients are evaluated in float64.
3. **Path C counts stop at 20 qubits.** Wider circuits are executed and
   reported, but produce no counts rather than a placeholder.
4. **No physical GPU execution has been verified.** The Vulkan loader
   enumerates a device; no compute dispatch on a physical GPU was demonstrated.
   All verified execution is CPU. See `README.md` §8.
5. **Path D cannot produce a joint distribution.** By design; see §2.

---

## 5. Engineering

* `cq-hecs` CLI (`version`, `doctor`, `backend list`, `analyze`, `run`,
  `verify`, `benchmark smoke`) with a strict JSON contract: `--format json`
  emits exactly one document on stdout, diagnostics go to stderr, exit codes
  are stable (0 ok, 1 unexpected, 2 usage, 3 unresolved, 4 environment).
* One version source (`scripts/version.py`) with a CI-enforced consistency
  checker. Previously SECURITY.md, the docs, the SBOM generator and the release
  workflow carried four different versions.
* CMake: artifacts under `${CMAKE_BINARY_DIR}`, core compiled once instead of
  ~14 times, AVX2 scoped to one target, Vulkan requirement stated explicitly.
* Native engine auto-discovery in the build output.

---

## 6. Verification

* Python: **202 passed, 0 failed** with the native engine built.
* Without the native build: **171 passed, 31 skipped**. The skipped tests
  genuinely did not verify the native component; they are reported as skipped,
  not counted as passing.
* Native ctest: **13/13** (MSVC 19.44, Vulkan SDK 1.4.357).
* Mutation harness: baseline gate passes, **7/7 killed**.
* CI: green on Ubuntu and Windows.

---

## 7. Upgrading

* `error_bound` no longer conflates approximation, roundoff and sampling. Code
  reading `total_error_bound` must handle `None`.
* Path D no longer returns `counts` by default. Use `allow_uncertified_joint_counts=True`
  and treat the result as a marginal sample, not a joint distribution.
* `HOEFFDING`-style guarantees from prior releases are withdrawn; the sampling
  bound is now support-size dependent.
* The `cq_hecs` legacy CLI is not the supported entry point. Use `cq-hecs`.