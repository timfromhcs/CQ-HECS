# Wave E / E3 evidence: research record to the freeze state

Date 2026-11-22 (08:00 to 08:50 UTC). Branch `release/v7-stable`, HEAD `38e799b3650e74a47d3a72184da50b5a85d5bb8b`
(also `origin/release/v7-stable`, PR #55). Windows 11, Python 3.13.13 (PATH), Node 22.23.1. The working tree carried
uncommitted edits by other Wave E agents (workflows, SBOM and archive scripts, READMEs, docs, tests) while E3 worked,
so every "E3 re-run" row ran on `38e799b` plus those edits. No git add, commit, stash, checkout or push by E3. Read-only
`gh` queries only. No deployment, merge, release, upload, credential, QPU or spend. Version not changed.

## Files written (E3 owned area only)

`research/v7/EVIDENCE_LEDGER.md`, `TEST_MATRIX.md`, `BLOCKERS.md`, `SECURITY_AUDIT.md`, `LICENCE_REGISTER.md`,
`CLAIM_AUDIT.md`, `PACKAGING_AUDIT.md`, `BASELINE_V7.md`, `RELEASE_CANDIDATE_AUDIT.md`, `HYPOTHESES.md`, `FINDINGS.md`,
`LITERATURE_MAP.md`, `TASKS.md`, `EXECUTION_LOG.md` (V7 sections appended, older entries unchanged), new `FINAL_REPORT.md`
(DRAFT), and this file.

## Commands run by E3 and results

| Command | Result |
|---|---|
| `python scripts/check_version.py` | all surfaces report 7.0.0 |
| `python scripts/verify_no_silent_truncation.py` | PASS |
| `python scripts/qg_doc_consistency.py` | OK |
| `pytest tests/test_doc_consistency_v7.py tests/test_readme_languages.py -q` | 81 passed in 3.18 s |
| `python scripts/security_audit.py --history --json-out sec.json` | secrets_tree 0, secrets_history 0, history_commits_scanned 343, code 0, studio_mcp_contract 0, findings_total 0, actions_unpinned 0, actions_other 0, actions_inventory 41 |
| `pytest tests/test_property_security_audit.py tests/test_fuzz_requests.py tests/test_fuzz_dimacs_parser.py tests/test_resource_limits.py tests/test_fuzz_qasm_parser.py -q` | 181 passed in 35.7 s, no xfail |
| `flake8 cqhecs tests scripts python_bridge --count --select=E9,F`; `compileall -q` | 0 findings; compile exit 0 |
| `cd web && npm test` | 167 tests, 167 pass, 0 fail |
| `cd web && npm run build` | inconclusive: esbuild ended with `The service was stopped` (not diagnosed; possibly the 110 s command limit or a concurrent agent); not repeated to avoid disturbing `web/dist` |
| `python web/scripts/export_shared_conformance.py --check`; `pytest tests/test_web_shared_conformance.py tests/test_feature_coverage.py -q` | fixture current; 199 passed in 61 s (local qiskit 2.6.1) |
| `python scripts/skip_budget.py --junitxml freeze_junit.xml --check` | FAILED (134 skips vs 105; 7 unbudgeted reasons; `CQ_HECS_EXE not set` 6 > 4) |
| `sha256sum` of the five release artifacts in `b7/pkg` | all five equal the integrator's hashes |
| CycloneDX SBOM read, `inspect*.json` and three `smoke-*.json` read | EXE SBOM 13 components; wheel SBOM 23 (build venv); inspect 5 PASS; smoke 15 PASS, 14 PASS + 1 SKIPPED, 14 PASS + 1 SKIPPED |

Freeze logs read (not re-run): `freeze_pytest.txt` (4269 passed, 134 skipped, 1 deselected, 711.68 s, Python 3.13.13),
`mutation_freeze.txt` (95/95 killed), `lean_freeze_build.txt` (8711 jobs, exit 0), `freeze_web.txt` (unusable: `tsc` not
found because of how it was invoked; `web/node_modules/.bin/tsc` exists).

## Hosted CI for `38e799b` (read-only `gh run list`, `gh run view`, `gh api .../jobs/<id>/logs`, 08:38 UTC)

These facts were not in the task summary. They change the release-candidate audit: remote evidence exists and is red.

PR #55 head is `38e799b` (state OPEN, mergeable). Three workflow runs were attached to that SHA at 06:38 UTC:
`CQ-HECS Packaging Verification` (pull_request, run 44994613449, completed, **failure**), and
`Deterministic CI & Four-Path Architecture Validation` (pull_request run 44994613455 and push run 44994611308, both
still `in_progress` two hours after start).

| Job | Result | Detail |
|---|---|---|
| Static checks and package smoke | success | |
| Linux C++20 CPU-only (no Vulkan SDK) | success | |
| Linux ASan + UBSan native tests | success | `-fsanitize=address,undefined`, `halt_on_error=1`, `100% tests passed out of 9`; compiler gcc-12 per the install log (Clang not run) |
| Linux C++20, Vulkan and full Python suite | **failure** | CTest 26/26 on `llvmpipe` (lavapipe, software ICD) and 3/3 follow-up; then Python: 5 failed, 4413 passed, 35 skipped, 1 deselected (573.8 s) |
| Python 3.12, 3.13, 3.14 compatibility | **failure** (each) | 4 failed, 4241 passed, 158 skipped, 1 deselected on 3.12 (469 s); the same four tests |
| Web emulator (WASM core, tests, build, E2E) | success | |
| Windows C++20, Vulkan and full Python suite | **in progress** since 06:39 UTC | stuck in the step "Full Python suite" for about two hours when queried |
| Wheel and sdist (build, inspect, clean-venv smoke, SBOM) | **failure** | step "Install the wheel into a clean venv and smoke it": `[FAIL] studio_health_and_stop: OSError: [Errno 98] Address already in use` (13 PASS, 1 FAIL, 1 SKIPPED) |
| Windows onedir folder (PyInstaller) | success | |
| Native cq-hecs-cpu and cq-hecs-vulkan (MSVC) | **failure** | `CMake Error at CMakeLists.txt:2 (project): Generator Visual Studio 17 2022 could not find any instance of Visual Studio` on the hosted runner |
| SHA-256 manifest over all packaging artifacts | skipped | depends on the failed jobs |
| Vercel (preview) | success; "Vercel Preview Comments" success | not verified against the deployed bundle or its SHA |

The five Linux Python failures (the four also fail on the three compatibility lanes):

1. `tests/test_qg_replay.py::test_every_processed_number_is_reproduced_from_raw_counts`: manifest hash of
   `bmv_drift/bmv-drift-t2-YZ/counts.csv` differs from the recomputed one on Linux (cause not diagnosed by E3; a
   line-ending or checkout difference is the first suspect).
2. `tests/test_sat_external_isolated.py::test_abort_after_a_complete_result_is_recorded_and_result_is_reverified` and
3. `::test_native_abort_like_exit_code_is_reported_not_suppressed`: the tests expect the Windows status `0x40000409` and
   see exit code `9 = 0x9` (POSIX keeps only the low byte).
4. `tests/test_web_shared_conformance.py::FixtureIntegrity::test_committed_fixture_is_what_the_generator_produces`: the
   committed fixture header names `Qiskit 2.6.1`, the lanes install 2.6.2 (compat) or 2.5.1 (constrained 3.11), so the
   text comparison fails by version string.
5. (3.11 Vulkan lane only) `tests/test_native_cpu_only.py::test_core_reports_cpu_only_capability`:
   `undefined symbol: cq_core_build_capabilities` in the freshly built `_cq_hecs_core.cpython-311-x86_64-linux-gnu.so`.

Working-tree edits by other agents touch `tests/test_qg_replay.py`, `cqhecs/quantum_gravity/replay.py` and
`tests/test_sat_external_isolated.py`; whether they fix items 1 to 3 was not verified by E3 and is not claimed. The
SHA of any fix is unknown. The job logs were saved only in the session scratchpad (not in the repository).

## NOT_RUN by E3

A full Python suite, mutation sweep, Playwright, native build and CTest, a Lean rebuild, SPIR-V verification, any
`npm run build` completion, any rebuild of the release artifacts, any workflow dispatch, any comparison of the Vercel
preview with the SHA, any work on the Wave E tasks owned by E1, E4 and E5.

## Late additions (after the first pass)

While E3 was writing, other Wave E agents added `evidence/waveE_E1.md` (diagnosis of the same six hosted-CI failures, fixes
local and unpushed), `evidence/waveE_E4.md` (release workflow, BUILD-INFO and SBOM closure edits, unrun), `evidence/lean_freeze_axioms.txt`
and `evidence/waveE_E5_webgpu_real_adapter.json` (`RUN_PARTIAL`, one AMD RDNA2 adapter, 20 cases, worst TV 7.8e-8). E3 read E1, E4 and the E5
JSON and reflected them in B-V7-03, `RELEASE_CANDIDATE_AUDIT.md` 21.2.3 and `FINAL_REPORT.md`; E3 did not re-run any of them and did not
verify that the E1/E4 fixes work. `SKIP_BUDGET.json` was modified by another agent, not by E3.
After the edits: `pytest tests/test_doc_consistency_v7.py tests/test_readme_languages.py tests/test_feature_coverage.py -q` -> 268 passed.
