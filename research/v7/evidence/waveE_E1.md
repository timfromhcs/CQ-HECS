# Wave E / E1: PR #55 required-CI repair (head 38e799b)

Source: `gh pr checks 55`, `gh api .../actions/jobs/<id>/logs` (runs 44994611308 push, 44994613455 pull_request, 44994613449 packaging). Nothing was pushed; the effect on remote CI is NOT_RUN until the integrator pushes.

| # | Failing job(s) | First real error (from log) | Root cause | Fix |
|---|---|---|---|---|
| 1 | Linux full, py3.12/3.13/3.14 | tests/test_qg_replay: 50 `manifest:*counts.csv` digest mismatches | Evidence manifests hash CRLF working-tree bytes; Git stores/Linux materialises csv/md as LF | `cqhecs/quantum_gravity/replay.py::_manifest_digest`: for .csv/.md only, also accept the CRLF-canonical digest; json/png stay strict. Two regression tests (LF checkout passes; tampered csv still detected). |
| 2 | same | test_sat_external_isolated x2: expected `0x40000409`, got `0x9` | POSIX truncates exit status to 8 bits; adapter correctly reports what the OS returned | Test derives the expected hex per platform (`_ABORT_HEX`). Product code unchanged. |
| 3 | same | test_web_shared_conformance fixture "stale": `Qiskit 2.6.1` vs `2.6.2` (compat) / pinned 2.5.1 | Oracle version string is provenance but was compared byte-for-byte | Compare with the Qiskit version normalised; all other bytes still compared. Verified locally with qiskit 2.6.1 (py3.13) and 2.5.1 (py3.14). |
| 4 | Linux full only | test_native_cpu_only::test_core_reports_cpu_only_capability: undefined symbol cq_core_build_capabilities | Glob `*cq_hecs_core*` matched the nanobind extension `_cq_hecs_core.cpython-311-*.so` first | Match exactly `(lib)?cq_hecs_core.(dll|so|dylib)`. Ran locally (Windows): passes. |
| 5 | package.yml native MSVC | CMake: Generator "Visual Studio 17 2022" could not find any instance of Visual Studio | windows-latest now ships VS 2026 | `scripts/package_native.ps1`: `-Generator` default empty; precedence -Generator, `$env:CQ_CMAKE_GENERATOR`, vswhere (17/18, only if this CMake lists it), fallback VS 17 2022. Function exercised locally (auto -> VS 18 2026 here; override/explicit verified). Test in tests/test_packaging.py. |
| 6 | package.yml wheel/sdist smoke | studio_health_and_stop: `OSError: [Errno 98]` | Post-kill `sock.bind(port)` fails on Linux because of TIME_WAIT connections of the stopped server | `scripts/package_smoke.py::port_is_free` sets SO_REUSEADDR on POSIX only (still refuses a live listener). Regression test uses a live listener then a TIME_WAIT port. |

Not changed: ci.yml, package.yml, constraints/ (no workflow-level defect found).

## Verification run locally (Windows, py3.13)
tests/test_qg_replay.py, test_sat_external_isolated.py, test_web_shared_conformance.py, test_packaging.py, test_native_release_workflow.py: all pass (see wrap-up counts); test_native_cpu_only reports-capability: pass; flake8 E9,F clean.

## Status of items not verifiable here
* Windows full suite (ci.yml windows-native): still `in_progress` at the time of reading (job in "Full Python suite"); final state NOT_RUN/unknown.
* Linux-only behaviour (items 2, 6) reasoned from the log, not executed on Linux.
