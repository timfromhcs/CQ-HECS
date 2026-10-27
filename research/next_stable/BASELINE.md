# Baseline — next Stable after v2.2.1

Captured: 2026-10-26, before source edits in `research/next_stable/`.
Repository: `https://github.com/timfromhcs/CQ-HECS`
Baseline commit: `9fe014b5509096ebe203ebae26cc146cb13b0a69` (`main`)
Latest published release at capture: `v2.2.1` (non-draft, non-prerelease)
Canonical version: `2.2.1`

## Worktree state at capture

```
M GEMINI.md
```

`GEMINI.md` contained pre-existing operator changes and was preserved untouched
by this work. It is not part of the release commit.

## Environment

| Item | Value |
| :--- | :--- |
| OS | Windows 11 Pro (win32) |
| Python | 3.14.6 |
| C++ toolchain | MSVC 19.44 (Visual Studio 2022, C++20) |
| CMake generator | Visual Studio multi-config, Release |
| Vulkan SDK | 1.4.357.0 (`glslangValidator` available) |
| Native extension | `build/bin/Release/_cq_hecs_core.cp314-win_amd64.pyd` |
| Physical GPU dispatch | not exercised by this baseline |

## Baseline commands

| Command | Result |
| :--- | :--- |
| `python scripts/version.py` | `2.2.1` |
| `python scripts/check_version.py` | OK, all surfaces `2.2.1` |
| `python -m compileall -q cqhecs tests scripts python_bridge` | exit 0 |
| `python -m pytest tests/ -q` | **310 passed** |
| `cmake --build build --config Release` | exit 0 |
| `ctest --test-dir build -C Release --output-on-failure` | **14/14 passed** |
| `python scripts/verify_no_silent_truncation.py` | PASS |
| `python scripts/verify_vulkan_shaders.py` | 12/12 shaders compile |
| `python scripts/run_mutation_tests.py` | 11/11 mutants killed, baseline clean |
| `python -m build` | wheel + sdist `2.2.1` built |

## Baseline test inventory

CTest at capture: `test_reversibility`, `test_ghz300`,
`test_constraint_solver`, `cq_hecs_cpp_hardening` (`test_engine_cpp`),
`cq_hecs_full_verification` (`cq_hecs test`), `test_bitexact_and_stress`,
`test_exact_algebra`, `test_stabilizer`, `test_hybrid_mps`,
`test_stress_limits`, `test_exact_ring`, `test_stabilizer_extreme`,
`test_300q_stress`, `test_qasm_contract`.

The baseline was green but not truthful: several tests asserted
implementation artefacts (exact 50/50 shot splits, bond-dimension-only GHZ
classification, planner metadata) rather than state-dependent quantum results.
Those gaps are itemised in `FINDINGS.md`.

## Cycle 2 — post-merge baseline (2026-10-27)

Captured after PR #7 was merged and before the cycle-2 fixes.

| Item | Value |
| :--- | :--- |
| Base SHA | `812da806d9b4528f1c4f8ccd3cbb7b37b6f009ce` (`main`) |
| Feature branch | `agent/cq-hecs-v2.2.2-stable-hardening` |
| Latest published release | `v2.2.1`; no `v2.2.2` tag/release at capture |
| Canonical version | `2.2.2` (already bumped by PR #7, unreleased) |
| Worktree | pre-existing `GEMINI.md` operator changes plus the cycle-2 edits |
| Platform | Windows 11 Pro; Python 3.14.6; MSVC 19.44; CMake Release; Vulkan SDK 1.4.357.0 |

Baseline gates on the merged tree at the start of cycle 2 matched the cycle-1
record (`311` Python tests, `17/17` CTest). The CQ regression suites and the
rebuilt native parser raise the final counts to `366` Python tests and `18/18`
CTest; exact commands and timings are in `TEST_MATRIX.md`.
