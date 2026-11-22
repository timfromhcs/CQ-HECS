# Packaging audit

This file has two parts. Part 1 is the current record for the 7.0.0 release candidate (`38e799b`, written by E3 on
2026-11-22). Part 2 is the original C2 record of a 5.0.0 dirty-tree build, kept unchanged as history; its hashes,
version and "dirty tree" statements do **not** describe the candidate.

# Part 1: candidate `38e799b` (7.0.0)

## Provenance

* Source commit: `38e799b3650e74a47d3a72184da50b5a85d5bb8b`, branch `release/v7-stable`, PR #55. The integrator
  built the artifacts from that commit (`evidence/waveE_E2.md`: `artifacts_built_from` `38e799b`). E3 did not
  rebuild anything; E3 re-hashed the files and read the reports (below).
* The artifacts are **not published**: no `v7.0.0` tag or release exists. The working tree at the time of writing
  carries uncommitted Wave E edits (workflow, SBOM script, archive script, docs), so these files are not artifacts
  of whatever the final freeze SHA will be. **They will be rebuilt at the final freeze SHA and every hash below
  will change** (the zip layer is deterministic, native binaries reproduce on MSVC per D3, but the sources
  differ).
* Build interpreter for the EXE folder: CPython 3.11 (SBOM component `CPython runtime 3.11`). Other facts of the
  build machine are those of the Windows 11 / MSVC 19.44 / Vulkan SDK 1.4.357 / AMD iGPU host in `TEST_MATRIX.md`.

## Artifacts and hashes

Verified by E3 with `sha256sum` against both the individual files and the `SHA256SUMS` in the same folder
(scratchpad `b7/pkg`, not in the repository): all five match the integrator's figures.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `cqhecs-7.0.0-py3-none-any.whl` | 470 897 | `a65d66ce9983307904463e2eb051040706c7ba0231c18ea4d106d6d707ab4f78` |
| `cqhecs-7.0.0.tar.gz` | 777 556 | `0a6220b56d8c35c7d75a5be951516ca9b8ccbb92e911af18c85c3beda7a3e656` |
| `cqhecs-7.0.0-windows-x64.zip` (onedir EXE folder) | 76 514 929 | `b088ec5239ec42e6814d957c16db50ffc806da106d96f88604f776585205f490` |
| `cq-hecs-cpu-7.0.0-windows-x64.zip` | 67 204 | `7a98816b7375332045499cb56243ef92793a2a207005519de8a86632e0272d70` |
| `cq-hecs-vulkan-7.0.0-windows-x64.zip` | 345 372 | `76b3b085a892ebe1645bd545b1c871fd78c7edf786d8c3cd3eb02a5b3c0c34d8` |

Also produced: two CycloneDX 1.5 SBOMs, two licence inventories, `inspect*.json`, three smoke reports, and a
`SHA256SUMS`. The `SHA256SUMS` file lists the five artifacts above plus the two SBOMs, two licence inventories and
`inspect-zips.json` (10 lines). E3 re-hashed the five artifact lines and they match; the five JSON lines were not re-hashed.

## What was checked, with the results E3 read

| Check | Report | Result |
|---|---|---|
| Wheel and sdist content inspection | `inspect.json` | wheel 102 members PASS, sdist 262 members PASS, no findings |
| Folder and native zip inspection | `inspect-zips.json` | EXE folder 263 members, cpu zip 12, vulkan zip 15: all PASS, no findings |
| Wheel in a clean venv, run from outside the repo, not elevated | `smoke-wheel.json` | 15 PASS |
| Onedir folder copied to a temp directory, not elevated | `smoke-onedir.json` | 14 PASS, 1 SKIPPED (`import_location`, meaningless for a frozen app) |
| The released zip extracted elsewhere, not elevated | `smoke-exe-indep.json` | 14 PASS, 1 SKIPPED (same) |
| SBOM format | `*.cdx.json` | CycloneDX 1.5; EXE SBOM 13 components, wheel SBOM 23 (see below) |

`studio_port_conflict` passes in all three reports (it was PARTIAL in the 5.0.0 record: P-01 is fixed).

## Findings for this candidate

| ID | Severity | Finding | Status |
|---|---|---|---|
| PK7-01 | P2 | The wheel SBOM is the build venv, not the dependency closure: 23 components including `setuptools` 79.0.1 and its vendored `autocommand` 2.2.2 declared `LGPLv3`, `wheel`, `qiskit` 2.6.2, `scipy` 1.17.1 (EXE SBOM: 2.5.1, 1.16.3). The file must not be published as built. | OPEN at the commit; an uncommitted `--closure-of` change is in the tree and unverified (SECURITY_AUDIT SEC-P2-2) |
| PK7-02 | P2 | The EXE SBOM is accurate for 13 components but marks `CPython runtime 3.11` as `UNVERIFIED`, lists `python-dateutil` under a free-text `Dual License`, and omits VC++ runtime DLLs and the vendored libraries in scipy and qiskit-aer | OPEN (SEC-P2-3, LICENCE_REGISTER) |
| PK7-03 | P1 for publication | `release.yml` pastes `RELEASE_NOTES.md` (still the 4.0.0 notes) into the release body | OPEN (B-V7-12) |
| PK7-04 | P1 for a release decision | `package.yml` ran once on the PR at `38e799b` (run 44994613449): Windows onedir PASS; wheel clean-venv smoke FAIL (`studio_health_and_stop`, `Address already in use` on Linux); native MSVC FAIL (`Visual Studio 17 2022` not found on the runner); manifest SKIPPED. `release.yml` and `nightly.yml` have not run; the reusable-workflow call and the artifact merge are therefore unproven. Release asset policy is linted only (16 tests) | OPEN (B-V7-09, B-V7-15) |
| PK7-05 | P2 | Clean-machine installation is NOT_RUN: everything ran on the build host (Python, Vulkan SDK, MSVC installed) as a non-administrator | OPEN (B-V7-05) |
| PK7-06 | P2 | The SBOM `typing_extensions` is 4.12.2 while `constraints/ci-py311.txt` pins 4.15.0: the local build did not honour that constraint for this package, so the local artifacts are not an exact image of the CI lane | OPEN, noted; the hosted `package.yml` run is the reference |
| PK7-07 | P3 | Not exercised: Vulkan loader absent on the frozen app (the loader cannot be removed from this host), Python 3.11-3.13 installs of the wheel, Linux and macOS, code signing, an installer, upgrade over a previous version, a vulnerability scan of bundled packages (the SBOM is an inventory only) | NOT_RUN |

## Status of the 5.0.0 findings (Part 2) at the candidate

| ID | Part-2 finding | Status at `38e799b` | Evidence |
|---|---|---|---|
| P-01 | Studio on an occupied port printed a raw `PermissionError` | FIXED (`StudioPortError`, exit 4) | `waveD_D2.md`; `studio_port_conflict` PASS in the three smoke reports |
| P-02 | `build_exe.ps1` polled `/api/health` without a token | FIXED in C2 | `waveC_C2.md` |
| P-03 | Native `cq_hecs.exe vrts` without a Vulkan ICD printed `VERIFIED`, exit 0 | FIXED for `vrts`, `ghz`, `echo`, `maxcut` (typed refusal, exit 3); `qasm`, `stress`, `test` unchanged | `waveD_D3.md`; B-V7-08 |
| P-04 | PyInstaller from a general interpreter pulls unrelated packages | MITIGATED (clean venv; the EXE SBOM has 13 components) | `waveC_C2.md` |
| P-05 | Third-party licence files missing from the bundle | FIXED (`licences/`, `THIRD_PARTY_NOTICES.txt`) | `waveC_C2.md` |
| P-06 | Native binaries not bit-reproducible | FIXED for `cq_hecs.exe` and `cq_hecs_core.dll` on MSVC (`/Brepro`), one machine; other targets and the CPU-only lane not shown | `waveD_D3.md` |
| P-07 | README named a zip that `release.yml` did not upload | FIXED by policy: `release.yml` consumes the `package.yml` assets; unproven until a hosted run | `waveD_D3.md`; B-V7-09 |
| P-08 | Legacy `package_release.ps1` | RESOLVED as legacy (refuses to run without `-Legacy`) | `waveD_D3.md` |
| P-09 | Bootloader licence and unverified runtime components | recorded | `LICENCE_REGISTER.md` |

## Honest naming (unchanged)

The Windows application is a folder (PyInstaller onedir) shipped as a zip, not a single-file executable and not an
installer. `cq-hecs-cpu` is a CPU-only library (`cq_hecs_core.dll`). `cq-hecs-vulkan` is the native Vulkan CLI and
libraries; it is not the Python simulator and says nothing about Paths A to D.

---

# Part 2: history, the C2 record of the 5.0.0 dirty-tree build (superseded, unchanged)

# Packaging audit (W14 / T6-07, agent C2, 2026-11-22), history

Scope: build every distributable from the current tree, inspect it, smoke it from a temporary directory
outside the repository, and record what is and is not established. Nothing was published, tagged,
signed or uploaded. No QPU, Open Quantum or credential was used. The version was not changed (5.0.0).

## Provenance of the build

* Base commit: `ace3c1acdb22c2d06cd151a18de0b4fe8fe33fd7` (branch `release/v7-stable`).
* Dirty state: **dirty**. Other agents were editing the tree in parallel (66 modified or untracked paths
  at snapshot time, listed in the scratch snapshot, mostly docs, `cqhecs/cli.py`, `cqhecs/studio/app.py`,
  `cqhecs/service.py`, `cqhecs/mcp_server.py`, tests and web). Builds therefore ran from a **file-level
  copy of the working tree** taken with `git ls-files -co --exclude-standard`, excluding `research/`,
  `web/node_modules` and `formal/`. These are *not* artifacts of commit `ace3c1ac`; they are artifacts of
  that commit plus the uncommitted edits present at snapshot time, and they must be rebuilt at freeze.
* Interpreter: CPython 3.14.6 (Windows 11 Pro 10.0.26200, AMD Radeon integrated GPU, Vulkan SDK 1.4.357,
  MSVC 19.44 / Visual Studio 2022, CMake 4.4.0). The CI target Python 3.11 was not run.

## Artifacts produced (scratch directory, not in the repository)

| Artifact | Size | SHA-256 |
|---|---:|---|
| `cqhecs-5.0.0-py3-none-any.whl` | 467 465 | `705d6b1a4bdbb72f3c1e8276e8a499f69cc42ecdebbe244926c2b6ff53f97a4f` |
| `cqhecs-5.0.0.tar.gz` (normalised) | 762 799 | `586fa060213580a77e1ae5d275267b6a7b547ed15bcf9861d129e875f7525b31` |
| `cqhecs-5.0.0-windows-x64.zip` (onedir folder, 864 files, 194 MB unpacked) | 77 698 251 | `2c1a90ba24f5a9ef95e8f092f2f1d13c5835aa20df7363e9b5f56242cbc1e7f3` |
| `cq-hecs-cpu-5.0.0-windows-x64.zip` | 68 537 | `3266eed58e5d358af15f3afa6694fdc51ee5ff17bbbbeee1ad35bc94b13ce0e0` |
| `cq-hecs-vulkan-5.0.0-windows-x64.zip` | 352 435 | `13c6babe23b40a1e0fcfe1c37040acf70f635a5127c511cd22f62f0223152f2a` |

A `SHA256SUMS` manifest over all of these, four CycloneDX 1.5 SBOMs, four licence inventories, four smoke
reports and `inspect.json` were generated and the manifest verified (`make_manifest.py --verify`: OK, 18
files). The three CycloneDX files checked were valid against the CycloneDX 1.5 strict JSON schema
(`cyclonedx-python-lib` validator).

Reproducibility, measured: the wheel built twice with `SOURCE_DATE_EPOCH` and, in a separate build, once
more in the earlier snapshot, gave the same SHA-256. The setuptools sdist differed between identical builds
(build-time mtimes and gzip header); `package_archive.py --normalize-targz` makes two builds identical.
Re-zipping an unchanged onedir folder reproduces the zip hash. The native DLLs and exes are **not**
bit-reproducible (two builds of the same sources gave different `cq_hecs_core.dll` hashes); only the zip
step is deterministic.

## What was verified (and how)

1. **Wheel and sdist** (`python -m build`). Inspect: wheel 102 members, sdist 256 members, PASS (required
   Studio assets including `qg.js`, Studio data, entry point and licence present; no research raw files,
   no credential-named or key files, no bytecode, no test trees in the wheel, no developer path or token
   shapes). The wheel carries no `schemas/` directory by design: `schemas/studio.openapi.json` is generated
   from `cqhecs.studio.openapi` and is in the sdist (`MANIFEST.in`).
2. **Clean venv, outside the repo, PYTHONPATH unset** (`package_smoke.py`): wheel venv 14 PASS, 1 PARTIAL,
   0 FAIL; import location confirmed in `site-packages`; version, `doctor`, Bell circuit, SAT (verified model),
   OMNIWAVE UNSAT with `DRAT_CHECKED`, `qg catalog`, offline `qg run-local`, Studio health (401 without
   token, 200 with token, `qg.js` served), forceful and graceful stop with all 3 processes of the tree gone
   and the port released, MCP `initialize` + `tools/list` (21 tools) + clean EOF exit. The sdist was also
   installed in a clean venv: `version`, `qg run-local` and `qg.js` presence passed.
3. **Onedir folder** built in a *clean* venv (numpy, qiskit, qiskit-aer, pyinstaller only), copied to a
   temp directory and smoked as a non-administrator process (`is_admin=False`): 13 PASS, 1 PARTIAL,
   1 SKIPPED (import location is not meaningful for a frozen app), 0 FAIL. Studio tree was 1 process; both
   stop paths left nothing alive. The opt-in `tests/test_exe_smoke.py` also passed against that copy
   (`CQ_HECS_EXE` set): 6 passed.
4. **Native**: CPU-only lane 15/15 ctest, Vulkan lane 26/26 ctest (twice: ad hoc build trees and through
   `package_native.ps1`). `cq-hecs-cpu` package: capability call returned `{"cpu_core": true,
   "vulkan_linked": false}`, no Vulkan loader marker in any binary, no CLI inside. `cq-hecs-vulkan` package:
   capability call returned `vulkan_linked: true`; `cq_hecs.exe ghz --shots 16` ran on the integrated AMD GPU
   with 0 parity violations. No machine path (home directory, repository, scratch) was found in any native
   binary.

## What was NOT verified

* **Clean-machine installation: NOT_RUN.** No clean Windows VM. Everything ran on the build machine
  (Python, Vulkan SDK and MSVC installed), from a temp dir, with a fresh venv or an extracted copy, as a
  non-administrator. A missing Visual C++ redistributable, missing system DLL, antivirus or SmartScreen
  behaviour, or per-user profile differences would not have been noticed. Status: **PARTIAL**
  (temp-dir + clean-venv + non-admin only).
* **Hosted CI**: `.github/workflows/package.yml` has never run (it is a definition). Its Python 3.11 / Linux
  / hosted-Windows paths, the `download-artifact` merge and the `pyinstaller==6.22.3` pin are unexercised.
  Only the YAML parse, action pinning, least privilege and absence of publishing steps are checked, by
  `tests/test_packaging.py`.
* **Vulkan absent on the frozen app**: the loader cannot be removed from this machine, so the
  `vulkan_loader: not_available` state of the packaged exe was NOT_RUN end to end. The code path exists
  (`cqhecs/service.py`, `record("vulkan_loader", "not_available", ...)`).
* Python 3.11-3.13 installs of the wheel, Linux/macOS, code signing, an installer, upgrade-over-previous.
* Vulnerability scan of the bundled dependencies (the SBOM is an inventory only).
* Native libraries vendored inside the numpy/scipy/qiskit-aer wheels (`*.libs`) are not individually
  inventoried; the CPython and MSVC runtime components are `UNVERIFIED` in the SBOM.

## Findings

| ID | Severity | Category | Finding | Reproducer / evidence | Status |
|---|---|---|---|---|---|
| P-01 | medium | UX / RELEASE | Studio on an occupied port exits 1 with a raw `PermissionError: [WinError 10013]` traceback, not a typed message. (Windows reports an exclusive-bind conflict as 10013, not 10048.) | `package_smoke.py` check `studio_port_conflict` = PARTIAL in the wheel venv and the onedir folder: bind a listener, run `cq-hecs studio --no-browser --port <that port>`. | OPEN. Owner: `cqhecs/cli.py` / `cqhecs/studio/app.py` (outside C2 area). The process does exit non-zero and does not hang. |
| P-02 | high (fixed) | RELEASE | The old `build_exe.ps1` Studio smoke polled `/api/health` without a token; the Studio is token-gated (401), so the script's own gate would have failed. | Observed 401 with the new driver before the token was supplied. | FIXED in `scripts/build_exe.ps1` (now runs `package_smoke.py`, which sends a throwaway Bearer token and asserts 401 without it). |
| P-03 | medium | HARDWARE / UX | Native `cq_hecs.exe vrts` with no usable Vulkan ICD (`VK_DRIVER_FILES` and `VK_ICD_FILENAMES` set to a nonexistent file) prints an empty device line (`[other, vendor 0x0 ...]`, empty `Selection:`), reports `Ground State: VERIFIED` and exits 0: it does not say that no Vulkan device was found. | Run from a temp dir with the two environment variables pointing to `C:\does\not\exist.json`. | OPEN. Owner: `src/` native CLI (outside C2 area). The CPU-only package is typed honestly by construction. |
| P-04 | medium | RELEASE | A PyInstaller build from the general development interpreter pulls in unrelated installed packages (hooks for transformers, pydantic, gi, anyio were processed) and would ship them. | First onedir attempt, aborted. | MITIGATED: `build_exe.ps1` documents and CI uses a clean venv; Aer is bundled only if importable; `--paths` makes the source tree win over any installed copy. |
| P-05 | medium | RELEASE / licence | PyInstaller copies almost no third-party licence files into the bundle (only numpy's dist-info), so BSD/Apache/MIT notices were missing from the shipped folder. | Listing of `_internal/*.dist-info` before the fix. | FIXED: `scripts/package_notices.py` writes `licences/` and `THIRD_PARTY_NOTICES.txt` into the folder (11 bundled distributions plus the PyInstaller bootloader licence). |
| P-06 | low | RELEASE | Native binaries are not bit-reproducible (PE timestamps); only archive layout is deterministic. | Two builds, different DLL hashes. | OPEN, documented. Adding `/Brepro` to the MSVC link would be a CMake change (not in C2 area). |
| P-07 | low | DOCS | `README.md` (lines ~182 and ~452) states that `cqhecs-<version>-windows-x64.zip` is on the release page, but `release.yml` uploads only the wheel, sdist, `sha256sums.txt`, SPDX SBOM and notes. The exe zip is not published by the workflow. | `grep` of `release.yml` asset lists. | OPEN. `release.yml` was left unchanged on purpose (it publishes); the integrator decides whether to add the onedir and native zips and the CycloneDX files. |
| P-08 | low | DOCS | `scripts/package_release.ps1` (legacy, copies `build\bin\Release` and `docs\ARCHITECTURE.md`) produces `CQ-HECS-v<ver>-Windows-x64.zip`, a different naming scheme from every other artifact. It was not exercised or changed. | Read only. | OPEN: superseded by `package_native.ps1`; candidate for removal at freeze. |
| P-09 | info | LICENCE | The shipped exe embeds the PyInstaller bootloader (GPL-2.0-or-later WITH Bootloader-exception; exception text read). CPython and the VC runtime DLLs are UNVERIFIED in the SBOM. | `research/v7/LICENCE_REGISTER.md`, packaging section. | Recorded. |

## Honest naming

* The Windows application is a **folder** (PyInstaller onedir) distributed as a zip; it is not a
  single-file executable and not an installer. The zip name is kept as `cqhecs-<v>-windows-x64.zip`
  because the README already refers to it; the name does not say "onedir" (the contents do:
  `cq-hecs/cq-hecs.exe` + `_internal/`).
* `cq-hecs-cpu` is a CPU-only **library** (`cq_hecs_core.dll`), not a program.
* `cq-hecs-vulkan` is the Vulkan native build (`cq_hecs.exe` VRTS-300 CLI plus DLLs). It is not the Python
  simulator and says nothing about the four Python paths.

## Files added or changed by C2

`scripts/build_exe.ps1` (rewritten), `scripts/package_smoke.py`, `scripts/package_inspect.py`,
`scripts/package_archive.py`, `scripts/package_notices.py`, `scripts/package_native.ps1`,
`scripts/package_native_smoke.py`, `scripts/sbom_cyclonedx.py`, `scripts/make_manifest.py`, `MANIFEST.in`,
`pyproject.toml` (one line: `license-files`; version untouched), `.github/workflows/package.yml`,
`tests/test_packaging.py` (30 tests), `docs/PACKAGING.md`, `research/v7/LICENCE_REGISTER.md` (appended
section), this file, `research/v7/evidence/waveC_C2.md`.
