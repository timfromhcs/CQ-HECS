# CQ-HECS Release Notes

**Version:** 2.2.0
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v<version>.md`. The content describes the current code,
> not a historical target. No release tag is created by the hardening work
> itself; publication requires explicit authorization.

---

## 1. What this release is

`v2.2.0` is a **hardening release**. It adds structured diagnostics and an
explicit engine classification, and it replaces fail-open code paths and
false-green tests with fail-closed contracts. It adds **no new simulator, no
GPU acceleration, and no new exactness claim**.

The four CPU simulation paths are unchanged in scope:

| Path | Method | Correctness class | Supported width & output |
| :--- | :--- | :--- | :--- |
| A | Stabilizer tableau (Gottesman-Knill) | Exact (GF(2) symplectic arithmetic) | 300+ qubits; full-register counts (Clifford) |
| B | Stabilizer-rank decomposition | Exact algebra, float64 arithmetic | Up to 22 qubits (implementation limit); scales with T-count |
| C | MPS, unbounded bond dimension | Exact algebra; no deliberate cutoff; float64 noise floor | 300+ qubits (low entanglement); sequential conditional sampling without a dense statevector |
| D | Sparse-Pauli dynamics | Certified bound on **expectation values** | 200+ qubits; selective observables API |

---

## 2. Fixed in 2.2.0

### Native QASM parsing and execution

* The native parser no longer repairs invalid input. Missing semicolons,
  unknown gates, malformed or non-finite angle expressions, out-of-range
  register references and block comments are rejected with a structured
  `{line, category, message}` error. Previously several of these were accepted
  and a partially interpreted circuit was executed.
* `cq_hecs qasm` returns exit code **2** for invalid circuit input and emits a
  JSON error document on stdout in `--json` mode. Diagnostics remain on stderr.
* `cq_execute_qasm` in the C ABI returns **`-3`** on parse errors and zeroes the
  result structure. `cq_get_version()` reports the canonical version.
* The native engine is labelled `engine_class = legacy_z8_phase_ledger` with
  `statevector_simulation = false`. The version banner derives from
  `CQ_HECS_VERSION`; the stale hardcoded `v4.5.0` output is gone.
* `--qubits` is enforced as a hard cap.
* `test_qasm_contract` covers strict parsing and bounded randomized
  robustness; the C-ABI test suite covers invalid-circuit rejection.

### Scheduler and resource accounting

* `VulkanComputeScheduler.submit_workload()` no longer reports
  `completed=True` for metadata-only submissions. It reports
  `planner_only=True`; completion requires `record_completion(submission,
  backend)`. Negative dispatch counts are rejected.
* Timing-jitter harvesting is documented as a deterministic diagnostic, not as
  proof of hardware entropy.
* `TieredMemoryGovernor.allocate()` raises `MemoryError` when a page cannot fit,
  instead of silently exceeding the budget.
* `JSpaceDelta.reinflate_matrix()` validates matrix shapes and labels its
  residual as a diagnostic rather than a certified bound.

### Tests that could pass without evidence

* QASM fuzz tests assert the strict parser contract and fail, rather than skip,
  when `CQ_HECS_REQUIRE_NATIVE=1` is set.
* Stress, concurrency and SVD tests separate internal accounting from RSS, use
  explicit availability skips, verify independent-instance behaviour, and
  require real truncation measurements.
* The source-level mutation harness applies exact patches to production files,
  runs independent subprocess checks, restores source byte-for-byte, and exits
  non-zero on a broken baseline or a surviving mutant. The maintained set is
  **11 mutants**; this is a scoped regression gate, not a proof of correctness.

### CI and packaging

* CI is split into static/package smoke, pinned Linux native, pinned Windows
  native, Python 3.12–3.14 compatibility, and an ASan/UBSan native job.
* Branch coverage is enforced at a **70 %** floor against a measured local
  baseline of 76 %.
* Workflow permissions are least-privilege; test evidence and package artifacts
  are uploaded.
* Supported Python is declared as **3.11–3.14**. Python 3.9/3.10 are no longer
  claimed after reaching end of life.
* `pyproject.toml` uses SPDX license metadata and the canonical version
  surfaces agree across Python, CMake, C ABI, citation and changelog.

---

## 3. Verification

Local evidence for this tree (Windows, MSVC 19.51, CPython 3.14.6):

* Python: **254 passed** with `CQ_HECS_REQUIRE_NATIVE=1`.
* Python 3.11 pinned lane: **251 passed, 3 explicit skips** (native-only tests,
  which CI's native jobs require instead of skipping).
* Native CTest: **14/14 passed**.
* Mutation harness: baseline clean, **11/11 killed**, exit code 0.
* Branch coverage: **76 %** local; CI gate is 70 %.
* Version consistency, silent-truncation audit and SPIR-V verification: pass
  (12/12 shaders).

GitHub Actions for the pushed hardening commit runs the Linux/Windows native
jobs, the ASan/UBSan job, the Python 3.12–3.14 matrix and the package smoke
job. The run link is recorded in `research/v2_2/TEST_MATRIX.md` after the push.
A green run on an earlier SHA is not evidence for a later commit.

---

## 4. Known limitations

These are deliberate and documented, not defects to be discovered later.

1. **No physical GPU execution has been verified.** The Vulkan loader
   enumerates a device and shaders compile, but no compute dispatch on a
   physical GPU was demonstrated. All verified execution is CPU. See
   `README.md` §9.
2. **Cloud Build was not observed.** `gcloud` is not installed in the audit
   environment. Status: **BLOCKED**, not passed.
3. **Path C reports no certified roundoff bound.** The discarded singular-value
   mass is exposed as `discarded_spectral_mass_diagnostic`, but per-rewrite
   masses do not compose into a state-norm bound without propagation analysis
   that is not implemented.
4. **Path B exactness is algebraic, not symbolic.** The decomposition drops no
   terms, but coefficients are evaluated in float64.
5. **Path D cannot produce a certified joint distribution.** Its bound applies
   to the requested observables. Joint counts are opt-in and labelled as
   uncertified.
6. **The native QASM path is a legacy engine.** It is not a general statevector
   simulator and is not a replacement for the four Python paths.

---

## 5. Upgrading

* `cq_hecs qasm` now exits **2** on invalid circuit input instead of executing a
  partially parsed circuit. Callers that treated non-zero as a generic failure
  should distinguish parse/usage errors from unresolved simulations.
* The native version banner no longer prints `v4.5.0`; it reports `2.2.0` from
  the canonical CMake version.
* Scheduler users must call `record_completion()`; `submit_workload()` no longer
  claims execution.
* `TieredMemoryGovernor.allocate()` raises `MemoryError` instead of overcommitting.
* Python 3.9/3.10 are unsupported; use Python 3.11 or newer.
* The legacy `python_bridge/` and `python/` packages remain available for
  reference but are not the supported entry point. Use `cq-hecs`.
