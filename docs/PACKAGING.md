# Packaging and verification

How CQ-HECS is packaged, what each artifact is, how to rebuild and check it, and what has **not** been
verified. The evidence for a given build is in `research/v7/PACKAGING_AUDIT.md` and
`research/v7/evidence/waveC_C2.md`.

## Artifacts

| Artifact | Built by | What it is | What it is not |
|---|---|---|---|
| `cqhecs-<v>-py3-none-any.whl` | `python -m build` | The Python package: `cqhecs` and `python_bridge`, Studio static files (including `qg.js`) and data, console script `cq-hecs`. Needs Python >= 3.11, NumPy, Qiskit. | Not self-contained; no native code, no Vulkan, no Aer/Stim/python-sat (optional extras). |
| `cqhecs-<v>.tar.gz` | `python -m build` | Source distribution, includes `schemas/studio.openapi.json` and the tests. `MANIFEST.in` excludes `research/`, `web/`, `audit/`, `formal/`. | Not a source snapshot of the repository. |
| `cqhecs-<v>-windows-x64.zip` | `scripts/build_exe.ps1` | A **PyInstaller onedir application folder** (`cq-hecs/cq-hecs.exe` plus `_internal/`), zipped. Extract before use. Third-party licence files are in `licences/` and `THIRD_PARTY_NOTICES.txt`. | **Not a single-file app.** One-file mode is deliberately not used (see below). Not an installer. Not signed. |
| `cq-hecs-cpu-<v>-windows-x64.zip` | `scripts/package_native.ps1` | CPU-only native C-ABI library `cq_hecs_core.dll` (+ import library, headers). No Vulkan code; it does not import the Vulkan loader. | **A library, not a program**: it has no command line. |
| `cq-hecs-vulkan-<v>-windows-x64.zip` | `scripts/package_native.ps1` | The Vulkan native build: `cq_hecs.exe` (VRTS-300 command line), `cq_hecs.dll`, `cq_hecs_core.dll`. Needs a Vulkan loader and driver. | Not the Python simulator; the four Python paths do not run in it. A GPU is not required to load the libraries, but is for the compute paths. |
| `*.cdx.json`, `*.licences.json` | `scripts/sbom_cyclonedx.py` | CycloneDX 1.5 SBOM and licence inventory of each artifact's dependency set. | Not a vulnerability audit. Licences the metadata does not state are `UNVERIFIED`. |
| `SHA256SUMS` | `scripts/make_manifest.py` | `sha256sum`-format manifest of every file above (sorted, LF, no timestamp). | Not a signature. Anyone who can replace a file can replace the manifest. |

## Release asset policy (P-07)

`.github/workflows/release.yml` publishes EXACTLY the artifacts `package.yml` builds, by calling it
as a reusable workflow (`workflow_call`) on the same commit; nothing is rebuilt at publish time.
The published set is:

`cqhecs-<v>-py3-none-any.whl`, `cqhecs-<v>.tar.gz`, `cqhecs-<v>-windows-x64.zip`,
`cq-hecs-cpu-<v>-windows-x64.zip`, `cq-hecs-vulkan-<v>-windows-x64.zip`,
`cqhecs-<v>-wheel.cdx.json`, `cqhecs-<v>-windows-x64.cdx.json` and `SHA256SUMS`.

The release job checks each file against `package.yml`'s own manifest (byte identity), then writes a
new `SHA256SUMS` over exactly the published files (not the licence/smoke/inspect JSONs, which stay
workflow artifacts) and verifies it. Triggers (`v*` tags; `main` pushes that create the tag only when
`v<scripts/version.py>` does not exist yet), the required-CI gate, pinned actions and least
privilege (`contents: write` only on the publishing job) are unchanged. The SPDX SBOM and
`sha256sums.txt` of `scripts/generate_sbom_and_checksums.py` are no longer published (the script
remains, unused by the workflow). `tests/test_native_release_workflow.py` lints this offline (YAML
parse, SHA pins, trigger set, asset list); the workflows themselves have NOT been run.
`scripts/package_release.ps1` is legacy (P-08): it deletes `dist\` and produces a differently named
archive that is never published; it now refuses to run without `-Legacy`.

Release hardening (E4; see `docs/RELEASE_PROCESS.md`): a release commit must be an ancestor of
`origin/main`; the release is created as a draft, its uploaded assets are downloaded back and verified
against the uploaded `SHA256SUMS`, and only then promoted; a published release is never modified.
Build identity: `scripts/package_archive.py` adds `BUILD-INFO.json` (version, source SHA, build date from
`SOURCE_DATE_EPOCH`, builder) to the EXE and native zips when `GITHUB_SHA`/`CQHECS_SOURCE_SHA` is set;
wheel and sdist are untouched. `scripts/sbom_cyclonedx.py` records the source revision on the SBOM root and
supports `--closure-of cqhecs`, which lists only the wheel's runtime dependency closure (not venv
tooling such as setuptools' vendored `jaraco`/`autocommand`). `package.yml` must pass `--closure-of
cqhecs` in its wheel SBOM step (HANDOFF: not part of this change; `release.yml` rejects a wheel SBOM that
lists venv tooling until it does). None of this has run in hosted CI.

Why not one-file: a 518 MB one-file build failed to extract `bcrypt` at run time on the reference
Windows machine. Onedir avoids the self-extraction step.

## Rebuild

```powershell
# Python wheel + sdist (byte-reproducible wheel with a fixed build time; sdist is normalised)
$env:SOURCE_DATE_EPOCH = "1767225600"
python -m build --outdir pkg
python scripts/package_archive.py --normalize-targz pkg/cqhecs-<v>.tar.gz
python scripts/package_inspect.py pkg/*.whl pkg/*.tar.gz

# Windows onedir: use a CLEAN venv holding only numpy, qiskit, (qiskit-aer) and pyinstaller.
# A general environment drags unrelated packages (transformers, pydantic, ...) into the bundle.
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1 -Python <clean-venv>\Scripts\python.exe -OutDir <out> -WorkDir <work>

# Native CPU-only and Vulkan (MSVC; the Vulkan lane needs the Vulkan SDK)
powershell -ExecutionPolicy Bypass -File scripts/package_native.ps1 -OutDir <out> -WorkDir <work>

# SBOM, licence inventory, manifest
python scripts/sbom_cyclonedx.py --name cqhecs --version <v> --metadata-root <site-packages> --exclude cqhecs --out pkg/cqhecs-<v>-wheel.cdx.json --licences-out pkg/cqhecs-<v>-wheel.licences.json
python scripts/make_manifest.py pkg --out pkg/SHA256SUMS
python scripts/make_manifest.py pkg --verify pkg/SHA256SUMS
```

Windows native binaries are reproducible (P-06): `CMakeLists.txt` passes MSVC `/Brepro` (compile and
link) and `/PDBALTPATH:%_PDB%` in Release-type configurations. Two independent configure+build runs of
the Vulkan lane from different build directories gave byte-identical `cq_hecs.exe`
(`3d6ed355...ba216`) and `cq_hecs_core.dll` (`5796c212...537a6`) with VS 2022 MSVC on the build
machine. Not shown: reproducibility across machines or toolchain versions, a control build without
`/Brepro`, or the other DLLs/LIBs of the full target set (only `cq_hecs` and `cq_hecs_core` were built).
`build_exe.ps1` (PyInstaller) is not covered: `/Brepro` does not apply to it.

All of these take explicit output and work directories so that parallel builds do not collide.
Archives are deterministic (sorted entries, fixed timestamp, no owner data): rebuilding the zip from an
unchanged folder gives the same SHA-256.

## Smoke tests

`scripts/package_smoke.py --cmd <cq-hecs|cq-hecs.exe>` runs from a fresh temporary directory outside
the repository with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and credential-like variables removed.
It checks: not elevated, import location (venv only), `version`, `doctor` (typed `vulkan_loader`
state), a Bell circuit, SAT with a verified model, OMNIWAVE `UNSAT` with a checked DRAT proof,
`qg catalog`, the offline `qg run-local` model, Studio start / authenticated health / 401 without a
token / forceful and graceful stop with every process of the tree gone and the port released,
Studio on an occupied port (must exit non-zero, not hang), and MCP `initialize` + `tools/list` + clean
EOF exit. A check that cannot run is `SKIPPED`; a check that passed with a caveat is `PARTIAL`.

`scripts/package_native_smoke.py <zip> --kind cpu|vulkan` extracts a native zip into a temp directory,
loads `cq_hecs_core` with ctypes and compares `cq_core_build_capabilities()` with the expected
`{"cpu_core": true, "vulkan_linked": false|true}`; the CPU package must contain no Vulkan loader
marker and no command-line program.

## Vulkan absent is a typed state

* Python surfaces: `cq-hecs doctor` reports `vulkan_loader` as `available`, `not_available` or `failed`
  and states that the Python backends run on CPU.
* `cq-hecs-cpu`: Vulkan is absent by construction; the capability call says `vulkan_linked: false`.
* `cq-hecs-vulkan` / `cq_hecs.exe` (P-03, fixed): `vrts`, `ghz`, `echo` and `maxcut` need a usable
  Vulkan device. Without one (for example `VK_DRIVER_FILES`/`VK_ICD_FILENAMES` pointing at a missing
  file) they print `REFUSED (vulkan_unavailable)` to stderr (plus `{"status":"refused","code":
  "vulkan_unavailable",...}` on stdout with `--json`) and exit with code 3. The CPU reference path
  runs only with the explicit `--cpu-reference` flag, prints a warning, and labels the output
  (`Device: NONE ... no Vulkan device used`, JSON `"backend":"cpu_reference"`). Test:
  `tests/test_native_vulkan_refusal.py` (skips without a built `cq_hecs.exe`; fails when
  `CQ_HECS_REQUIRE_NATIVE=1`). Other commands (`qasm`, `stress`, `test`) still use the legacy
  engine whose initialisation succeeds without a device; they are not covered by this fix.

## What this does not establish

* **Clean-machine installation is NOT_RUN.** No clean Windows VM was available. Everything was run
  from a temporary directory with a fresh venv or an extracted copy, as a non-administrator, on the
  build machine. That machine has Python, the Vulkan SDK and the MSVC toolchain installed, so a missing
  Visual C++ runtime or a missing system DLL would not have been noticed.
* The native zips link the dynamic MSVC runtime (`VCRUNTIME140.dll`, `MSVCP140.dll`); the Visual C++
  2015-2022 x64 redistributable is required on the target machine.
* Nothing is code-signed; SmartScreen or antivirus reputation is unevaluated.
* Hosted CI (`package.yml`) has not run: it is a definition, not evidence.
* Linux and macOS packaging are not covered (the Python wheel is pure Python; the CI job installs it
  on Linux, which is a CI-only claim until it runs).
* No hardware, QPU or provider call is made by any packaging step.
