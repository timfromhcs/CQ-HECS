# Wave C / C2 evidence: packaging (W14 / T6-07)

Date: 2026-11-22. Base commit `ace3c1acdb22c2d06cd151a18de0b4fe8fe33fd7`, working tree DIRTY (other agents editing in
parallel); builds ran from a file-level copy of the tree (`git ls-files -co --exclude-standard`, minus `research/`,
`web/node_modules`, `formal/`). Full narrative and findings: `research/v7/PACKAGING_AUDIT.md`; user docs: `docs/PACKAGING.md`.
Environment: Windows 11 Pro 10.0.26200, CPython 3.14.6, MSVC 19.44 (VS 2022), CMake 4.4.0, Vulkan SDK 1.4.357, AMD Radeon iGPU.
Scratch dirs (outside the repo): `...\scratchpad\{src2,dist2,venv_wheel2,venv_sdist,venv_build,exe_out,exe_work,native_cpu,native_vk,native_pkg,native_out,bundle}`.

## Commands and results

| # | Command (abridged) | Result |
|---|---|---|
| 1 | `SOURCE_DATE_EPOCH=1767225600 python -m build --outdir dist2` (twice, dist2/dist3) | wheel hash identical both times `705d6b1a...f97a4f`; sdist differed (mtimes) |
| 2 | `package_archive.py --normalize-targz` on both sdists | identical `586fa060...b7525b31` |
| 3 | `package_inspect.py dist2/*.whl dist2/*.tar.gz --marker scratchpad` | wheel PASS (102 members), sdist PASS (256). Before `MANIFEST.in` the sdist FAILED (`schemas/studio.openapi.json` missing): fixed |
| 4 | `python -m venv venv_wheel2; pip install dist2/*.whl`; `package_smoke.py --cmd ...cq-hecs.exe --python ...` from `/tmp`, PYTHONPATH unset | 14 PASS, 1 PARTIAL (`studio_port_conflict`), 0 FAIL |
| 5 | `pip install dist2/*.tar.gz` in clean venv; `cq-hecs version`, `qg run-local`, `qg.js` present | PASS |
| 6 | clean build venv (numpy, qiskit 2.6.2, qiskit-aer 0.18.4, pyinstaller 6.22.3); `build_exe.ps1 -Python venv_build -OutDir exe_out -WorkDir exe_work` | built; smoke of a temp-dir copy: 13 PASS, 1 PARTIAL (`studio_port_conflict`), 1 SKIPPED (`import_location`), 0 FAIL; is_admin=False; zip `2c1a90ba...c1e7f3` |
| 7 | `CQ_HECS_EXE=<copy of exe_out/cq-hecs>/cq-hecs.exe pytest tests/test_exe_smoke.py` | 6 passed |
| 8 | `package_inspect.py exe_out/cq-hecs --marker scratchpad` (864 members) | PASS |
| 9 | re-zip the unchanged folder with `package_archive.py` | identical hash to the zip from the build |
| 10 | `cmake -DCQ_ENABLE_VULKAN=OFF` + build + `ctest -C Release` (own tree native_cpu; again via `package_native.ps1`) | 15/15 passed (twice) |
| 11 | `cmake -DCQ_ENABLE_VULKAN=ON` + build + `ctest -C Release` (native_vk; again via `package_native.ps1`) | 26/26 passed (twice) |
| 12 | `dumpbin /dependents cq_hecs_core.dll` (CPU lane) | no `vulkan-1.dll`; needs MSVCP140/VCRUNTIME140 |
| 13 | `package_native_smoke.py cq-hecs-cpu-5.0.0-windows-x64.zip --kind cpu` | PASS 5/5: `{"cpu_core": true, "vulkan_linked": false}`, no loader marker, no CLI |
| 14 | `package_native_smoke.py cq-hecs-vulkan-5.0.0-windows-x64.zip --kind vulkan` | PASS 4/4: `vulkan_linked: true`; `cq_hecs.exe ghz --shots 16 --json` -> `{"zeros":10,"ones":6,"non_parity":0,"success":true}` |
| 15 | `cq_hecs.exe vrts` with `VK_DRIVER_FILES`/`VK_ICD_FILENAMES` -> nonexistent file | exit 0, empty device line, `Ground State: VERIFIED` (finding P-03: not a typed refusal) |
| 16 | `sbom_cyclonedx.py` x4, `package_notices.py`, `make_manifest.py --out` then `--verify` | SBOMs written (7, 13, 1, 1 components); CycloneDX 1.5 strict-schema validation of 3 files: VALID; manifest verify OK (18 files) |
| 17 | `pytest tests/test_packaging.py` | 30 passed |
| 18 | `flake8 scripts/package_*.py scripts/sbom_cyclonedx.py scripts/make_manifest.py tests/test_packaging.py --select=E9,F` | 0 |
| 19 | YAML parse of `.github/workflows/package.yml` | ok; all `uses:` pinned to 40-hex SHAs (download-artifact v8.0.2 SHA read via `git ls-remote`) |

## Artifact SHA-256 (see SHA256SUMS in the scratch `bundle/`)

```
705d6b1a4bdbb72f3c1e8276e8a499f69cc42ecdebbe244926c2b6ff53f97a4f  cqhecs-5.0.0-py3-none-any.whl
586fa060213580a77e1ae5d275267b6a7b547ed15bcf9861d129e875f7525b31  cqhecs-5.0.0.tar.gz
2c1a90ba24f5a9ef95e8f092f2f1d13c5835aa20df7363e9b5f56242cbc1e7f3  cqhecs-5.0.0-windows-x64.zip
3266eed58e5d358af15f3afa6694fdc51ee5ff17bbbbeee1ad35bc94b13ce0e0  cq-hecs-cpu-5.0.0-windows-x64.zip
13c6babe23b40a1e0fcfe1c37040acf70f635a5127c511cd22f62f0223152f2a  cq-hecs-vulkan-5.0.0-windows-x64.zip
```

## NOT RUN / PARTIAL

* Clean-machine (VM) verification: NOT_RUN. Temp-dir + clean-venv + non-admin on the build machine only: PARTIAL.
* `.github/workflows/package.yml` on hosted runners: NOT_RUN.
* Packaged exe with the Vulkan loader absent: NOT_RUN (loader cannot be removed here).
* Python 3.11/3.12/3.13 wheel installs, Linux, macOS, code signing, installer, upgrade: NOT_RUN.
* Full pytest suite: not run (targeted only, as instructed). No QPU, Open Quantum, credential or paid call.
* Open defects handed to owners: P-01 (Studio port-conflict traceback), P-03 (native CLI without ICD), P-06, P-07, P-08.
