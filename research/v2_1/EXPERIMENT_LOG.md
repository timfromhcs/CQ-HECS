# CQ-HECS v2.1 Experiment Log

Chronological, reproducible record of experiments conducted during the v2.1 research and engineering mission.

---

## Experiment 1: Baseline Reproduction & System Verification
- **Date & Time:** 2026-10-19 14:12 UTC
- **Host:** Windows 11, AMD Ryzen 7 7735HS (8C/16T, ~20 GB RAM), Python 3.14.6, MSVC 19.51, Vulkan 1.4.357.
- **Commands:**
  - `python -m pytest`: 209 passed, 2 warnings (Qiskit deprecation in test helper), 65 subtests in 21.94s.
  - `ctest --test-dir build -C Release`: 13/13 passed in 7.60s.
  - `cq_hecs.exe test`: all 7 embedded self-tests passed.
  - `python scripts/verify_vulkan_shaders.py`: 12/12 shaders compiled to SPIR-V with 0 warnings / 0 errors.
  - `python scripts/run_mutation_tests.py`: baseline OK, 7/7 mutants killed.
- **Conclusion:** Baseline v2.0.0 is cleanly reproducible on the local host.

---

## Experiment 2: MPS Sequential Conditional Sampling Prototype
- **Date & Time:** 2026-10-19 14:19 UTC
- **Objective:** Verify whether right-norm environment contraction ($R^{[k]}$) and sequential left projection ($L^{[k+1]}$) can generate exact measurement bitstrings without dense statevectors.
- **Circuit 1:** 4-qubit GHZ state ($(|0000\rangle + |1111\rangle)/\sqrt{2}$).
  - Shots: 1,000.
  - Result: Exactly 500 $\times$ `0000` and 500 $\times$ `1111`. Exactly 0 invalid bitstrings. Norm squared = 1.0000.
- **Circuit 2:** 6-qubit random circuit (H, T, RX, RY, CX, CZ, RZ).
  - True distribution from Qiskit `Statevector`.
  - Shots: 50,000.
  - Result: $TV = 0.00384 \ll 0.0217$ (well within Weissman 95% confidence bound).
- **Conclusion:** Mathematical formulation of MPS sequential conditional sampling is exact and verified.

---

## Experiment 3: Batched 300-Qubit MPS Sampling Performance
- **Date & Time:** 2026-10-19 14:20 UTC
- **Objective:** Evaluate runtime and memory of batched sequential sampling on a 300-qubit MPS.
- **Setup:** 300-qubit GHZ circuit ($H_0 \prod_{i=0}^{298} CX_{i, i+1}$).
- **Sequential Unbatched Loop:**
  - $R$ environment computed in 0.002s.
  - 1,000 shots in pure Python loop: 4.924s.
- **Batched Vectorized Implementation:**
  - Vectorized $L$ tensor across all 1,000 shots simultaneously: shape `(1000, chi, chi)`.
  - Vectorized conditional probability and RNG decision per site.
  - Runtime: **0.274 seconds** for 1,000 shots over 300 qubits!
  - Result: 503 $\times$ $|0\dots0\rangle$ and 497 $\times$ $|1\dots1\rangle$.
  - Peak memory allocated during sampling: $< 1.0\text{ MB}$.
- **Conclusion:** Batched sequential MPS sampling achieves sub-second performance on 300 qubits with strict correlation preservation.

---

## Experiment 4: Path A Wide-Circuit Audit & Row-Sum Vectorization
- **Date & Time:** 2026-10-19 14:21 UTC
- **Objective:** Evaluate Path A shot capability on wide circuits ($n \ge 50$).
- **Defect Discovered:**
  - When $n > 30$ and the circuit is not all-equal (e.g. 50-qubit cluster state with CZ gates), executing `StabilizerTableauSimulator.sample(shots=100)` raised:
    `AttributeError: 'StabilizerTableauSimulator' object has no attribute 'MAX_RESAMPLE_SHOTS'`.
  - Cause: `MAX_RESAMPLE_SHOTS` was declared at module scope, but referenced as `self.MAX_RESAMPLE_SHOTS`.
- **Optimization:**
  - Vectorized `_row_sum` using algebraic identity $g(x_1, z_1, x_2, z_2) \equiv z_1 x_2 - x_1 z_2 + 2(x_1 z_1 (z_2 - x_2) + x_2 z_2 (x_1 - z_1)) \pmod 4$.
  - Benchmarked across 100 row sums on a 300-qubit tableau: runtime dropped from 15.65 ms to 2.34 ms (**6.7x speedup**).
- **Conclusion:** Bug resolved and 6.7x speedup achieved; allows removing the 100-shot cap.

---

## Experiment 5: Complete OpenAI Math Corpus Scan
- **Date & Time:** 2026-10-19 14:35 UTC
- **Repository:** `https://github.com/openai/math.git` (commit `1581d4cbdd69a0faf34b2089614fe2a814316a6a`).
- **Processing:**
  - Extracted all 372 result families from `overview.tex` using balanced-brace parsing.
  - Extracted all 719 manuscripts from `CONTENTS.md`.
  - Verified that all 719 PDF files exist on disk in the local cache.
  - Screened every manuscript against classical simulation categories.
  - Conducted in-depth reviews of Families 284, 283, 279, 275, 267–278, 130, 139.
- **Conclusion:** No paper provides an efficient classical simulator for arbitrary universal quantum circuits. Specific mathematical boundaries (quartic query exponent, QMA hardness) confirm the necessity of CQ-HECS's class-specific architecture.

---

## Experiment 6: Mutation Testing Harness Audit
- **Date & Time:** 2026-10-19 14:22 UTC
- **Inspection:** Inspected `scripts/run_mutation_tests.py`.
- **Finding:**
  - Mutants 1, 2, and 5 contained `return True  # baseline already wrong` shortcut branches.
  - Mutant 6 did not inject a mutation; it merely checked unmutated code.
- **Remediation Plan:**
  - Remove all `return True` fallback branches from mutant functions; raise errors on baseline failure.
  - Properly inject the wide-counts fabrication mutant in Mutant 6.
  - Create meta-tests in `tests/test_mutation_harness_meta.py`.
