# CQ-HECS v2.5.0 Baseline (L0)

## 1. Source and live repository

- Baseline locked: 2026-10-30 00:06 UTC.
- Working branch: `agent/cq-hecs-v2.5.0-quantum-bridge`.
- Upstream base: `main` at `74071b5519fe14dec54b7f893e3f2672198f66bb`.
- Latest published release: `v2.4.0` (published 2026-10-29T22:48:17Z, PR #13 merged).
- Remote URL: `https://github.com/timfromhcs/CQ-HECS.git`.
- GitHub CLI auth: logged in as `timfromhcs`.
- Pre-existing operator work: `GEMINI.md` modified (preserved operator mission document).
- Live release assets for `v2.4.0` independently verified on GitHub:
  - `cqhecs-2.4.0-py3-none-any.whl` (sha256 `9d4f44831e19e8557e83cf0aa1f2163c47a5fceb2cf2df72d8387a3ce06cd79f`)
  - `cqhecs-2.4.0.tar.gz` (sha256 `680efadc130bd5950fc079c319ce7b1acc6d6c62e379628fad530a1d1fa76425`)
  - `cqhecs-sbom.spdx.json` (sha256 `2068477ec6bc15f4eba39c5734d09a4fb71e9766b147d155b269b53c423889e2`)
  - `RELEASE_NOTES_v2.4.0.md` (sha256 `6f72bf02ff41f8473d53cba7c8883d3d647b719fd4e24213fba71c95078ae8fd`)
  - `sha256sums.txt`

## 2. Local environment

- OS: Windows 11 (`Windows-11-10.0.26200-SP0`).
- Python: CPython 3.14.6 (`C:\Program Files\Python314\python.exe`).
- Packages: NumPy 2.4.6, Qiskit 2.5.1, Qiskit Aer 0.17.2, Stim 1.16.0, pytest 9.1.1, hypothesis 6.170.12, coverage 7.16.0.
- Compiler & build tools: MSVC 19.44 / Visual Studio 2022 Community, CMake 4.4.0, Ninja 1.13.2.
- Vulkan SDK: 1.4.357.0 with `glslangValidator.EXE`.
- Git: 2.54.0.windows.1, GitHub CLI 2.97.0.

## 3. Baseline gate execution on SHA `74071b5`

All executed locally on the baseline commit:
- Python test suite (`CQ_HECS_REQUIRE_NATIVE=1`): **420/420 PASS** in 55.40s.
- Native CTest (MSVC Release): **19/19 PASS** in 16.55s.
- Mutation test harness: **14/14 killed** (100.0%).
- Vulkan 1.3 compute shaders: **12/12 PASS** with 0 warnings / 0 errors.
- Flake8 static analysis (`cqhecs tests scripts python_bridge --count --select=E9,F`): **0 findings**.
- Silent truncation audit (`scripts/verify_no_silent_truncation.py`): **PASS**, no patterns found.
- Version consistency (`scripts/check_version.py`): **PASS**, all report `2.4.0`.
- Package build (`build` & `twine check`): **PASS** for sdist and wheel.

## 4. Live research snapshot (OpenAI Math & SOTA emulators)

- `openai/math` main commit: `7ef5c0cc5ca4b0e072b7a050fca09ab24bc6fa3a` (2026-10-26T21:18:03Z).
- Qiskit BackendV2 fake provider architecture: uses `Target` with instruction properties (error, duration) for noise modeling.
- Hardware execution boundary: physical QPU dispatch must be explicit, authenticated, and never silently simulated.
