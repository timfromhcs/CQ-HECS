# CQ-HECS v2.5.1 Baseline (L0)

## 1. Source and live repository (re-discovered 2026-10-30)

- Working branch: `claude/beautiful-rubin-3hcoym`, created from `main`.
- Baseline SHA: `a94ffb80a34203b2cc3d4d4b450f64ca91a822d6`
  (`docs: finalize v2.5.0 release audit and asset checksums`).
- Working tree at start: clean, no untracked operator files.
- Latest published release: `v2.5.0` (published 2026-10-30T00:00:04Z), tag on
  merge commit `bd2a1142a546589ceb6a5163c300c594561e7177` (PR #14).
- CI on the baseline SHA: run 40976919494, `success`.
- Open pull requests: none.

## 2. Published v2.5.0 assets, independently re-hashed

Downloaded from the v2.5.0 release and hashed locally with `sha256sum`. All
four match `sha256sums.txt` and `research/v2_5/RELEASE_AUDIT.md`:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `cqhecs-2.5.0-py3-none-any.whl` | 148116 | `ae69e7367d1ba62dd019f3f4330dfbf0207dd8bd418098eb93f9036fa6470874` |
| `cqhecs-2.5.0.tar.gz` | 212988 | `92e31ca3717e97b8a1f2534ad857b832bb0c1b433f81f8d24a1f737ed7b558c6` |
| `cqhecs-sbom.spdx.json` | 1717 | `6b6545008aad03cd7444f326627bf10a7f2d1bcdb9e405885f65cc4d1ed59552` |
| `RELEASE_NOTES_v2.5.0.md` | 6424 | `eb5ea65e89ddfda3847060914b3c20b006e8613955ce7c7d29c6c09dd7c70c49` |

The published `RELEASE_NOTES_v2.5.0.md` body describes v2.4.0 (see
FINDINGS CQ-V251-06).

## 3. Local environment

- Linux x64 (kernel 6.18), Ubuntu 24.04 userland.
- CPython 3.13.17; NumPy 2.4.6, Qiskit 2.5.1, Qiskit Aer 0.17.2, Stim 1.16.0,
  pytest 9.1.1, hypothesis 6.170.12, coverage 7.16.0 (pins from
  `constraints/ci-py311.txt`).
- GCC 13.3.0, CMake 3.28.3, Ninja; glslang 15.1.0; Vulkan device: llvmpipe
  (Mesa software ICD) — no physical GPU.

## 4. Baseline gates on `a94ffb8` (this environment)

| Gate | Result |
|---|---|
| `ctest --test-dir build --output-on-failure` | 19/19 PASS |
| `CQ_HECS_REQUIRE_NATIVE=1 coverage run --branch -m pytest tests/` | 452 passed, 0 skipped |
| Branch coverage | 84 % (`--fail-under=70` PASS) |
| `verify_vulkan_shaders.py` | 12/12 PASS |
| Python suite without native build (first run) | 398 passed, 54 skipped |

The baseline suite passes, yet the defects in FINDINGS.md reproduce on this
SHA and on the published v2.5.0 wheel: the existing differential test used a
mirror-symmetric Bell circuit with identical per-qubit noise, which cannot
detect a mirrored bit order.
