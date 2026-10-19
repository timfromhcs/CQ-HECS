# CQ-HECS v2 Baseline Record

Recorded at the start of the v2 mission cycle, per the mission contract
(`GEMINI.md` §3). Everything below is from actual runs on the local machine;
nothing is copied from an earlier report.

## Start state

| Item | Value |
| :--- | :--- |
| Mission start SHA (audited reference) | `dd59c0c4e60e0ba7b951947985dccba288786db53`* |
| Live `main` when the mission branch was created | `dd59c0c` (merge of PR #1) |
| Mission branch | `agent/v2-correctness` (from `agent/v1-stable-hardening`, pushed) |
| Prior published release | `v0.2.0`, canonical version `0.2.0` |
| Working tree at start | clean (before this mission's own commits) |

\* The mission documents spell this SHA slightly differently
(`947985...` vs `947989...`); the merge commit of PR #1 on live `main` is
`dd59c0c` and is the reference that matters.

## Environment

| Item | Value |
| :--- | :--- |
| OS | Windows 11, build 10.0.26200 |
| CPU | AMD Family 25 Model 68 (Zen 3), x86_64 |
| Python | 3.14.6 |
| NumPy | 2.4.6 |
| Qiskit | 2.5.1 |
| Aer | 0.17.2 |
| Stim | 1.16.0 |
| Compiler | MSVC 19.44 (for the native core, via `build.bat`) |

## Baseline checks (run before any edits in this cycle)

| Check | Command | Result |
| :--- | :--- | :--- |
| Python tests | `python -m pytest tests/ -x -q --tb=short` | **209 passed**, 2 warnings (Qiskit deprecations in a test helper), 0 failed |
| Mutation harness | `python scripts/run_mutation_tests.py` | baseline OK, **7/7 mutants killed**, exit 0 |
| Version consistency | `python scripts/check_version.py` | OK, all surfaces report `0.2.0` (pre-bump) |

## CMake/CTest and shader validation

The native core was built previously in this cycle (a native engine binary is
discovered by the tests — `test_native_*`-style checks in
`tests/test_correctness_contracts.py` exercise it). The Windows build is driven
by `build.bat`; CI (`.github/workflows/ci.yml`) runs the MSVC build, CTest and
shader validation on every push. Between the branch creation and the latest
local commit, CI ran green on every pushed commit of
`agent/v1-stable-hardening` (PR #1 run:
<https://github.com/timfromhcs/CQ-HECS/actions/runs/39242815214>) and was
assumed green for early `agent/v2-correctness` pushes; the final validation
matrix in this cycle is the authoritative local record.

## Verification-level inventory at baseline

| Level | Status |
| :--- | :--- |
| CPU Python paths (A/B/C/D) | verified locally against Qiskit Statevector/Aer/Stim oracles |
| Native stabilizer engine | verified locally through the Python bridge test surface |
| Vulkan loader | enumerated on the local machine; **no compute dispatch demonstrated on a physical GPU** |
| Software Vulkan (Lavapipe) | CI tier only, not exercised locally in this cycle |
| Physical GPU execution | **never verified in this project cycle** |

## Baseline concerns from the audit (carried into Phase 1)

The ten items listed in `GEMINI.md` §0 were all re-verified against the live
branch. Their dispositions after this cycle are recorded in
`research/v2/METHOD_CATALOG.md` and `docs/ARCHITECTURE.md`; the headline
outcomes are: the invalid finite-shot TV bound was replaced with the
Weissman-style support-aware bound, the mutation harness was made to fail
closed on broken baselines and surviving mutants, and Path B's 16-qubit ceiling
was removed by vectorising the two-qubit gates (now 22 qubits, documented).
