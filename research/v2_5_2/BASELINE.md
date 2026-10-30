# CQ-HECS v2.5.2 Baseline (L0)

## 1. Source and live repository (re-discovered 2026-10-30)

- Working branch: `claude/vigilant-ritchie-mscxry` (session branch), at start
  identical to `main`.
- Baseline SHA: `1be682a20ca3ccc9079893e0b150217a568a23e6` (merge of PR #16).
  `main` and tag `v2.5.1` both point to it.
- Working tree at start: clean, no untracked operator files.
- Latest published release: `v2.5.1` (2026-10-30T01:21:05Z, not draft, not
  prerelease). Previous: `v2.5.0`, `v2.4.0`.
- Open pull requests: none (PRs #12–#16 closed).
- Unmerged evidence found: commit `f013407` (`research/v2_5_1/RELEASE_AUDIT.md`)
  existed only on `claude/beautiful-rubin-3hcoym`. It is cherry-picked into
  this branch unchanged (`bd3de1a`) so the v2.5.1 audit reaches `main`.

## 2. Published v2.5.1 assets, independently re-hashed

Downloaded from the v2.5.1 release; `sha256sum -c sha256sums.txt`: all OK.
Sizes match `research/v2_5_1/RELEASE_AUDIT.md` (wheel 150956 B, sdist
219465 B, SBOM 1717 B, notes 5281 B).

The published wheel, installed in a clean CPython 3.11 venv, reproduces:

- CQ-V252-01: Path B `h t s h` → `P(0) = 0.8505`, state `EXACT` (correct 0.146);
- CQ-V252-02: `fake_manila` `sx` error 0.00025 → channel infidelity 0.000125.

It does not reproduce CQ-V252-03 (`native_engine = False`: the wheel ships no
native module and uses the Python tableau).

## 3. Local environment

- Linux x64 (kernel 6.18), Ubuntu 24.04 userland.
- CPython 3.13.17 (main venv): NumPy 2.5.4, Qiskit 2.6.1, Qiskit Aer 0.18.2,
  Stim 1.16.0, pytest 9.2.0, hypothesis 6.170.13, coverage 7.17.0 (latest
  releases, not the CI pins).
- CPython 3.11.17 with `constraints/ci-py311.txt` (Qiskit 2.5.1, Aer 0.17.2)
  for the pinned lane and the wheel smoke tests.
- GCC 13.3.0, CMake 3.28.3, Ninja; glslang 15.1.0; Vulkan device: llvmpipe
  (Mesa software ICD, LLVM 20.1.2). No physical GPU.

## 4. Baseline gates on `1be682a` (this environment)

| Gate | Result |
|---|---|
| `check_version.py` | PASS (all 2.5.1) |
| `flake8 --select=E9,F` | 0 |
| `verify_no_silent_truncation.py` | PASS |
| `verify_vulkan_shaders.py` | 12/12 |
| CTest (GCC Release) | 19/19; Vulkan contract on llvmpipe (software ICD) |
| Python suite, `CQ_HECS_REQUIRE_NATIVE=1` | 470 passed, 0 skipped |
| Branch coverage | 85 % |
| Mutation harness | 20/20 killed |

All baseline gates were green, yet the defects in FINDINGS.md were present:
the suite had no circuit whose probabilities distinguish `T` from `T†` on
Path B, no `swap` test on the native tableau, and no test of what the
profile's gate error means.
