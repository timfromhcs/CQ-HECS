# CQ-HECS Release Notes

**Version:** 2.2.1
**Release date:** 2026-10-26
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.2.1.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.2.1` is a **patch release** on top of `v2.2.0`. It fixes correctness and
refusal defects in the Python QASM reader, capability routing, Qiskit
measurement handling, Path D observable parsing and Path C resource accounting.
It adds **no new simulator, no new exactness claim and no GPU acceleration**.

The four CPU paths keep their scope:

| Path | Method | Correctness class | Supported width & output |
| :--- | :--- | :--- | :--- |
| A | Stabilizer tableau (Gottesman–Knill) | Exact GF(2) symplectic arithmetic | 300+ qubits for Clifford circuits; full-register counts |
| B | Stabilizer-rank decomposition | Algebraically exact decomposition, float64 arithmetic | Up to 22 qubits (implementation limit); scales with T-count |
| C | MPS without deliberate truncation | No bond cut-off; float64 noise floor; no certified roundoff bound | 500-qubit routing/sampling ceiling; RAM budget enforced |
| D | Sparse-Pauli dynamics | Certified bound on requested **expectation values** | 200+ qubits; selective observables; no certified joint distribution |

---

## 2. Fixed in 2.2.1

### One strict QASM contract for Python and native

* The Python reader is no longer a permissive Qiskit-based loader. It is a
  strict, line-oriented OpenQASM subset parser with the same structured
  `{line, category, message}` errors as `src/qasm_parser.cpp`.
* Unknown gates, missing semicolons, undeclared registers, duplicate registers,
  out-of-range indices, bad arity and non-finite angles are rejected before any
  execution. No statement is silently skipped.
* Multiple registers receive global qubit offsets in declaration order:
  `qreg a[2]; qreg b[3];` maps `b[0]` to qubit 2 and the circuit width is 5.
* Whole-register operands expand in arity-sized chunks, matching native
  semantics; a flattened width that is not a multiple of the arity is
  `operand_count_mismatch`.
* Angles are evaluated by a bounded recursive-descent grammar, never by
  Python `eval()`. `nan`, `inf`, division by zero, `**`, unbalanced
  parentheses and trailing tokens are rejected.
* Classical-bit remapping is refused explicitly instead of dropping the target.
  Terminal measurements are sorted by qubit; mid-circuit measurements stay at
  their source position and are refused before execution.

### Capability-first routing

* Added `cqhecs/gate_manifest.py` as the single source of truth for gate arity,
  parameters, per-path support and Clifford status. The analyzer, router,
  Qiskit `Target` and every backend derive their capabilities from it.
* Parameterised gates are classified per angle, not by name or first parameter.
  `cp(π/2)` is no longer treated as a Path A Clifford gate; it is routed to
  Path C or refused before execution. The same applies to `crz`, `crx`, `cry`,
  `cu1`, `rz`, `p` and `u1`.
* Removed the false Path A `reset` capability. `reset`, mid-circuit
  measurement and classically controlled gates are refused before execution.
* `CQHecsBackend.run()` requires counts, so a counts request cannot silently
  degrade to Path D expectation values.

### Qiskit measurement semantics

* `normalize_measurements` no longer moves a mid-circuit measurement to the end.
  Such circuits are rejected before simulation.
* Repeated measurements of one qubit into distinct classical bits are
  preserved; non-contiguous classical indices are kept.
* `measure_all()` and terminal measurements are tested differentially where
  Aer is available.
* The Qiskit `Target` now lists every implemented path gate (`cp`, `cu1`,
  `crx`, `cry`, `crz`, `cz`, `swap`, ...) on a conservative linear coupling
  map. Gates without any path remain absent, so `transpile(qc, backend=backend)`
  cannot emit them.

### Path D observables and certification

* Observable strings are parsed as a strict grammar; trailing characters after
  valid tokens are rejected instead of being ignored.
* `bool` masks, negative masks and masks wider than the system are rejected.
* Duplicate Pauli factors simplify algebraically (`Z[i] Z[i] = I`).
* Per-observable bounds are reported; aggregate bounds are not invented.
* Marginal samples remain explicitly labelled as **not** a joint distribution.

### Path C resources and numerics

* `ram_budget_mb` is enforced fail-closed before a state update; a refusal
  preserves the last valid state and reports an atomic diagnostic.
* Process RSS and peak RSS are reported separately from internal NumPy tensor
  bytes (`process_rss_mb`, `process_peak_rss_mb`,
  `rss_measurement_available`). Tensor bytes are never presented as RSS.
* `numerical_error_bound` remains `None`. Numerical rank reduction at the
  `1e-13` relative threshold is documented separately from a deliberate bond
  cut-off; `exact=True` means "no deliberate truncation", not symbolic
  exactness.

### Tooling and gates

* Added `tests/test_hardening_v221.py` with focused regressions for every
  contract above, including Python/native differential categories and Qiskit
  transpilation of Path C gates.
* The T-count mutation anchor follows the shared `_t_resource` classifier.
* The release workflow now refuses to publish unless `ci.yml` succeeded for the
  exact tagged commit, and it appends the final SHA256 values to the release
  body.

---

## 3. Compatibility notes

* Python API additions are backwards compatible: `cqhecs.gate_manifest` is new,
  `UnsupportedCircuitInput` remains available as an alias of
  `UnsupportedCircuitInputError`, and existing result fields are unchanged.
* Behaviour that was previously wrong is now refused: `cp`/`crz`-style gates
  are no longer offered to Path A; `reset`, mid-circuit measurement and
  classical conditions raise `UnsupportedCircuitError` instead of producing a
  plausible but wrong result.
* `cq-hecs run` accepts the same strict QASM subset as the native `qasm`
  command. Callers that relied on unknown QASM statements being skipped must
  fix their input.
* The native executor still implements only its documented legacy gate table.
  `p`, `u1`, `cu1`, `crx`, `cry` and `crz` are Python/Path-C only; the
  divergence is an acceptance ceiling, documented in `docs/QASM_CONTRACT.md`
  §6, not a semantic difference.
* Supported Python remains 3.11–3.14.

---

## 4. Verification

Local evidence for the release candidate (Windows, MSVC 19.44, CPython 3.14.6,
Qiskit 2.5.1, Aer 0.17.2, Stim 1.16.0):

| Gate | Command | Result |
| :--- | :--- | :--- |
| Python suite + native | `CQ_HECS_REQUIRE_NATIVE=1 python -m pytest tests/ -q` | **309 passed** |
| Native CTest | `ctest --test-dir build -C Release --output-on-failure` | **14/14 passed** |
| Branch coverage | `coverage run --branch --source=cqhecs -m pytest tests/`; `coverage report --fail-under=70` | **81 %** (gate 70 %) |
| Mutation harness | `python scripts/run_mutation_tests.py` | **11/11 killed**, baseline clean |
| Fatal-error lint | `flake8 ... --select=E9,F63,F7,F82` | pass |
| Version consistency | `python scripts/check_version.py` | pass |
| Silent-truncation audit | `python scripts/verify_no_silent_truncation.py` | pass |
| Shader verification | `python scripts/verify_vulkan_shaders.py` | 12/12 SPIR-V shaders |
| Wheel/sdist build | `python -m build`, `twine check dist/*.whl dist/*.tar.gz` | pass |
| Clean-install smoke | fresh venv, `cq-hecs version/doctor/run name:bell` | pass |

GitHub Actions runs the required suite on the exact tagged commit; the release
job waits for that run and links it in the published body. A green run on an
earlier commit is not accepted.

---

## 5. Artifacts and supply chain

* `cqhecs-2.2.1-py3-none-any.whl` — pure-Python package (no native extension).
* `cqhecs-2.2.1.tar.gz` — source distribution.
* `cqhecs-sbom.spdx.json` — SPDX SBOM generated from the final artifacts.
* `sha256sums.txt` — SHA256 for every published asset; appended verbatim to the
  release body by the release workflow.

The Python wheel does **not** contain the native `libcq_hecs` / `cq_hecs.exe`
artifacts. Native builds are platform-specific and are not claimed as part of
the wheel. No signed provenance or attestation is claimed unless a workflow run
actually produced and verified one.

---

## 6. Cloud Build

**Status: NOT VERIFIED.** `cloudbuild.yaml` was reviewed, but no Google Cloud
project or credentials were available in the audit environment, so no real
Cloud Build run was started. This is not a passing result. Local tests and
GitHub Actions do not substitute for it.

---

## 7. Known limitations

1. **No physical GPU compute has been verified.** The Vulkan loader enumerates a
   device and shaders compile, but no compute dispatch on a physical GPU was
   demonstrated. All verified execution is CPU. Loader availability is not
   `PHYSICAL_GPU_COMPUTE_VERIFIED`.
2. **Path C reports no certified roundoff bound.** `numerical_error_bound` is
   `None`; discarded singular-value mass is a diagnostic, not a state-error
   bound.
3. **`exact=True` is not symbolic exactness.** Numerical rank reduction at
   `1e-13` and float64 rounding remain.
4. **500 MPS qubits are a routing ceiling, not an exactness guarantee.**
   Entanglement, bond dimension and available memory decide what is feasible.
5. **Path B exactness is algebraic, not symbolic.** Coefficients are evaluated
   in float64.
6. **Path D cannot produce a certified joint distribution.** The bound applies
   to the requested observables; joint counts are opt-in and labelled
   uncertified.
7. **No dynamic circuits.** Mid-circuit measurement, `reset` and classical
   conditions are refused; they are not simulated.
8. **The native QASM path is a legacy engine.** It is not a general statevector
   simulator and does not replace the four Python paths.
9. **The catalog/metadata audit is not a full re-read of all 719 OpenAI Math
   manuscripts.** No such claim is made here.

---

## 8. Upgrading

* Unknown QASM statements now fail instead of being skipped. Validate input
  before upgrading pipelines that fed partially valid QASM.
* Circuits containing `cp`/`crz`/`cu1`/`crx`/`cry` compile to Path C; code that
  forced Path A for these must stop forcing it.
* Circuits with mid-circuit measurement, `reset` or classical conditions now
  raise instead of returning a result. Split or rewrite them.
* Classical-bit remapping (`measure q[i] -> c[j]`) is refused; relabel the
  classical register or remap the counts afterwards.
* `CQHecsBackend.run()` now refuses a Path D fallback for counts requests; use
  an explicit Path D expectation-value request instead.
* Python 3.11 or newer is required.
