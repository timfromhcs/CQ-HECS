# CQ-HECS v2.2 baseline and audits

## v2.2.1 hardening cycle (2026-10-26)

**Starting release:** `v2.2.0` (published 2026-10-23)
**Starting `main`:** `ce1c66e8ba79f5f3fe1ac68ced151365e2be3010`
**Working branch:** `agent/cq-hecs-v2.2.1-hardening`
**Target:** patch release `v2.2.1` (no `v2.3.0` research scope)

### Confirmed defects on the starting SHA

All findings below were reproduced with a failing regression test before the
fix. The tests live in `tests/test_hardening_v221.py`.

| ID | Finding | Reproduction | Fixed by |
| :--- | :--- | :--- | :--- |
| A1 | Python QASM reader was a permissive Qiskit loader: it skipped unknown gates and missing semicolons, treated a bare `OPENQASM` as a gate, and used `max(register_size)` for the width | `qreg a[2]; qreg b[3]; h b[0];` lost the offset; `nope q[0];` was accepted | strict line-oriented reader with shared categories, global offsets, arity-chunk expansion, bounded angle grammar |
| A2 | Router classified parameterised gates by name/first angle; `cp(π/2)` was offered to Path A; `reset` was advertised for Path A | `QuantumCircuit(2); qc.cp(pi/2, 0, 1)` routed to A | `cqhecs/gate_manifest.py` + capability-first routing; per-angle Clifford test |
| A3 | Qiskit `normalize_measurements` moved mid-circuit measurements to the end and collapsed repeated measurements with `setdefault` | measure → X → measure produced a terminal-measurement result | source-order preservation, mid-circuit refusal, full `(qubit, clbit)` layout |
| A4 | Path D parsed observables by extracting valid `Z[n]` tokens; `Z[0]junk` was accepted; duplicate factors were not simplified; bool/negative/wide masks were accepted | `Z[0]junk`, `Z[0]Z[0]`, `True` masks | strict grammar, mask validation, `Z[i]Z[i]=I`, per-observable bounds |
| A5 | Path C reported internal tensor bytes ambiguously and had no enforced RAM budget | large rewrite exceeded `ram_budget_mb` without a structured refusal | fail-closed budget, atomic refusal, separate RSS/peak-RSS metadata, honest `numerical_error_bound=None` |
| A6 | `if_else` raised a confusing `TypeError`; reset was not refused consistently | Qiskit control-flow circuit | typed `UnsupportedCircuitError` before execution |
| A7 | Analyzer limit 300 vs sampler limit 500; Qiskit `Target` omitted implemented Path C gates | `transpile` could not emit `cp`/`crz` | analyzer ceiling aligned to 500 (documented as routing ceiling); target expanded on a linear coupling map |

### Verification (local, release candidate)

| Gate | Result |
| :--- | :--- |
| Python suite (`CQ_HECS_REQUIRE_NATIVE=1`) | **309 passed** |
| CTest (MSVC Release) | **14/14 passed** |
| Branch coverage | **81 %** (gate 70 %) |
| Mutation harness | **11/11 killed**, baseline clean |
| Fatal lint / version / truncation / shaders | pass / pass / pass / 12 of 12 |
| Clean-install wheel smoke | pass |

### SemVer decision

`2.2.1` (patch). The change set corrects wrong behaviour and adds refusal
paths; it does not add a new simulator or a new capability class. The new
`gate_manifest` module and the `UnsupportedCircuitInput` alias are additive.

### Remaining unverified surfaces (unchanged)

- **Google Cloud Build:** no project/credentials available; `NOT_VERIFIED`.
- **Physical GPU compute:** loader/shader evidence only; no dispatch on a
  physical device.
- **CI on the exact release SHA:** recorded in the published release body,
  which is generated only after the required `ci.yml` run for that SHA passes.

---

## v2.2.0 baseline and audit

**Audit date:** 2026-10-23
**Repository:** `https://github.com/timfromhcs/CQ-HECS`
**Default branch at audit:** `main`
**Starting SHA:** `22fd300ff2984ad3aaf473d14a71ae1fe043e559` (`v2.1.0`)
**Working branch:** `agent/v2.2.0-stable-hardening`
**Latest published release observed:** `v2.1.0` (GitHub release, 2026-10-19)
**Published tags observed:** `v0.2.0`, `v2.0.0`, `v2.1.0`

The starting checkout had one pre-existing user modification: the rewritten
`GEMINI.md` mission document. It was preserved and committed, not reverted.

## Environment

| Surface | Value |
| :--- | :--- |
| OS | Windows (`win32`) |
| Python | CPython 3.14.6 (primary local), CPython 3.11.15 (pinned-lane rehearsal) |
| NumPy | 2.4.6 |
| Qiskit | 2.5.1 |
| Qiskit Aer | 0.17.2 |
| Stim | 1.16.0 |
| pytest | 9.1.1 |
| psutil | 7.2.2 |
| CMake | 4.4.0 |
| Compiler | MSVC 19.51 (Visual Studio 2026 Build Tools) |
| Vulkan SDK | 1.4.357.0 |
| Native artifacts | `build/bin/Release/cq_hecs.exe`, `cq_hecs.dll`, `cq_hecs_core.dll` |

## Baseline commands and initial status

| Gate | Command | Initial status | Notes |
| :--- | :--- | :--- | :--- |
| Canonical version | `python scripts/version.py` | PASS | printed `2.1.0` |
| Version surfaces | `python scripts/check_version.py` | PASS | all surfaces agreed before the release bump |
| Silent-truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS | pattern audit only; not a proof of correctness |
| Shader validation | `python scripts/verify_vulkan_shaders.py` | PASS | 12 compute shaders compiled to SPIR-V |
| Python syntax | `python -m compileall cqhecs tests` | PASS | |
| Native build | `cmake --build build --config Release` | PASS | MSVC/Release |
| CTest | `ctest --test-dir build -C Release` | PASS before hardening | 13 tests at baseline; `test_qasm_contract` was added later |
| Python tests | `pytest tests/` | PASS before hardening | the suite contained tests that could pass without performing their measurement; see below |
| Mutation gate | `python scripts/run_mutation_tests.py` | **FAIL** during hardening | the harness at the start of this mission was not trustworthy; after reconstruction it reported 6/11 killed and 5 survivors |

## Findings fixed in this cycle

### P0 — invalid QASM was silently repaired and executed

The native parser and the C-ABI parser accepted malformed input (missing
semicolons, unknown gates, invalid angle tokens, out-of-range references) and
executed a partially interpreted circuit. The parser now fails closed with
structured errors, and `cq_hecs qasm` returns exit code 2 for invalid circuit
input. The legacy executor refuses any circuit with parse errors. The result is
explicitly labelled `legacy_z8_phase_ledger` with
`statevector_simulation=false`.

### P1 — false completion and swallowed resource failures

`VulkanComputeScheduler.submit_workload()` reported `completed=True` for
metadata-only submissions. It now reports `planner_only=True` and requires
`record_completion(backend)` before completion is recorded.
`TieredMemoryGovernor.allocate()` accepted a page larger than the configured
budget; it now raises `MemoryError` after eviction cannot make room.

### P1 — tests could pass without evidence

- QASM fuzz tests skipped when the native binary was missing. CI now sets
  `CQ_HECS_REQUIRE_NATIVE=1`, which converts that skip into a failure.
- Stress tests conflated internal accounting with RSS and allowed absent
  measurement to pass. They now use an explicit `psutil` skip and separate the
  two quantities.
- Concurrency tests now use independent instances, timeouts, output
  verification and exception propagation.
- SVD tests now perform real truncation and distinguish a measured diagnostic
  from a certified error bound.
- The mutation harness now patches real source files, runs independent
  subprocess checks, restores files byte-for-byte, and rejects a broken
  baseline or a surviving mutant.

### P2 — CI did not enforce coverage or sanitizers

The reviewed workflow used unpinned dependencies, reported coverage without a
threshold or branch mode, and never enabled `CQ_ENABLE_SANITIZERS`. The
sanitizer option also appeared after the core object library, so it could not
have reached the core objects. It is now defined before all native targets and
the CI job proves the flags are present in `compile_commands.json`.

## SemVer decision

Target `2.2.0` is retained. The change set adds structured parse diagnostics and
explicit engine classification, and adds `record_completion()` for scheduler
users. The parser and scheduler changes correct invalid prior behaviour; they
are documented as corrections rather than new simulation capabilities. No
release tag has been created or published by this work.

## Remaining unverified surfaces

- **GitHub Actions on the pushed SHA:** the hardening commit
  `62559d2` passed all seven jobs (Linux/Windows native, ASan/UBSan, Python
  3.12–3.14, static/package) in run
  <https://github.com/timfromhcs/CQ-HECS/actions/runs/39952077909>. The final
  documentation commit is re-verified separately; see `TEST_MATRIX.md`.
- **Google Cloud Build:** `gcloud` is not installed in this environment, so the
  configured `cloudbuild.yaml` could not be invoked or observed locally. Status:
  **BLOCKED**, not passed.
- **Physical GPU acceleration:** the native CTest suite exercises the Vulkan
  code path where available, but no physical-device performance or correctness
  run was performed. Status: **NOT VERIFIED**. Do not describe CQ-HECS as
  GPU-accelerated on the basis of these tests.
- **Linux sanitizer execution:** the ASan/UBSan job passed in the GitHub Actions
  run above. Local Windows/MSVC cannot run it, so it is CI-only evidence.
