# CQ-HECS v2.2.0 baseline and audit

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

- **GitHub Actions on the pushed SHA:** pending at the time this baseline file
  was written; the final audit records the run link after the push.
- **Google Cloud Build:** `gcloud` is not installed in this environment, so the
  configured `cloudbuild.yaml` could not be invoked or observed locally. Status:
  **BLOCKED**, not passed.
- **Physical GPU acceleration:** the native CTest suite exercises the Vulkan
  code path where available, but no physical-device performance or correctness
  run was performed. Status: **NOT VERIFIED**. Do not describe CQ-HECS as
  GPU-accelerated on the basis of these tests.
- **Linux sanitizer execution:** the job is defined in CI; local Windows/MSVC
  cannot run ASan/UBSan. Status: **NOT RUN LOCALLY**, pending the CI job.
