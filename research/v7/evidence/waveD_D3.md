# Wave D / D3: native Vulkan refusal, reproducible Windows binaries, release asset policy

Date: 2026-11-22. Branch release/v7-stable (HEAD 51969fd + working tree). Nothing committed, no workflow run, no publishing.

## P-03 native cq_hecs.exe without a Vulkan ICD (FIXED, tested on this machine)
- Defect: `vrts`/`ghz`/`echo`/`maxcut` ignored the result of `VulkanContext::initialize()`; with no ICD they printed an empty Device line, `Ground State: VERIFIED`, exit 0.
- Fix (`src/main.cpp`): `acquire_vulkan()`. No device -> stderr `REFUSED (vulkan_unavailable)`, `--json` prints `{"status":"refused","code":"vulkan_unavailable",...}`, exit code 3. `--cpu-reference` opts into a CPU run: stderr WARNING, `Device: NONE (... no Vulkan device used)`, `Backend: CPU reference` lines, JSON `"backend":"cpu_reference"`. Usage text documents exit 3 and the flag.
- Test: `tests/test_native_vulkan_refusal.py` (7 cases, env `VK_DRIVER_FILES`/`VK_ICD_FILENAMES` -> missing file). Result with the fixed build (own build dir, `CQ_HECS_BUILD_DIR` set): 7 passed. With a real device (AMD Radeon iGPU) `vrts` still exits 0 with the device identity.
- NOT_RUN: a red run against the pre-fix binary (no old binary was built; the defect is the one recorded in PACKAGING_AUDIT P-03). Without a built exe the test skips (fails when `CQ_HECS_REQUIRE_NATIVE=1`).
- Not covered: `qasm`, `stress`, `test` use the legacy `VulkanEngine` whose `initialize()` returns true in "software emulation mode" without a device. Unchanged; documented in docs/PACKAGING.md. Vulkan ctest suite not run.

## P-06 reproducible Windows binaries (DONE for the two built targets)
- `CMakeLists.txt` (MSVC, Release/RelWithDebInfo/MinSizeRel): `/Brepro` for compile and link, link `/PDBALTPATH:%_PDB%`. The generated vcxproj contains both.
- Build twice (fresh configure+build, Vulkan ON, targets cq_hecs and cq_hecs_core, two different build directories):
  - cq_hecs.exe  3d6ed355312bbb7c5c75c1cf2d4a28637c4dbb35e530e1921db2165d0ffba216 (both)
  - cq_hecs_core.dll 5796c2127bd59c7d145bd6673b2b804c221bc8803cfa55974b0d0c8fc0b537a6 (both)
- Not shown: control build without /Brepro, other targets, other machines/toolchains, CPU-only lane. build_exe.ps1: /Brepro not applicable (PyInstaller).

## P-07 release.yml asset policy (DEFINED + LINTED, workflows NOT run)
- release.yml now calls package.yml as a reusable workflow (`workflow_call` added to package.yml; no publish capability added) and uploads exactly: wheel, sdist, `cqhecs-<v>-windows-x64.zip`, `cq-hecs-cpu-<v>-windows-x64.zip`, `cq-hecs-vulkan-<v>-windows-x64.zip`, `cqhecs-<v>-wheel.cdx.json`, `cqhecs-<v>-windows-x64.cdx.json`, `SHA256SUMS` (regenerated over exactly those files, verified; each file also checked against package.yml's manifest). The old in-job rebuild, SPDX SBOM, sha256sums.txt and RELEASE_NOTES asset are gone (notes stay in the release body).
- Unchanged: triggers (push tags `v*`, push main), tag-if-not-exists (`git ls-remote`), required-CI gate, pinned SHAs, top-level `contents: read` (write only on the publishing job).
- Lint test: `tests/test_native_release_workflow.py` (16 cases: YAML parse (needs PyYAML, else skipped), SHA pins on all workflows, trigger set, permissions, asset list, README names assets). Result: 16 passed (after README update; first run had 1 expected failure on the README assertion before the edit).
- Risks (NOT_RUN): reusable-workflow call and artifact naming are unproven until a real run; package.yml's `concurrency: package-${{ github.ref }}` is evaluated in the caller context; Vulkan package smoke on hosted runner remains a warning-only step in package.yml.
- README release-asset paragraph rewritten; docs/PACKAGING.md updated (policy, P-03, P-06).

## P-08 scripts/package_release.ps1 (RESOLVED as legacy)
- Header marks it LEGACY (deletes dist\, differently named archive, never published); refuses to run without `-Legacy` (exit 2). Not removed because scripts/check_version.py reads it. No literal version strings added.
