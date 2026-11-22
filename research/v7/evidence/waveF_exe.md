# Wave F - Windows onedir EXE local build evidence

Source: HEAD f880d0a plus uncommitted working-tree changes (scripts/build_exe.ps1 fix below; other files modified by other agents). Not a clean-SHA release build.
Host: Windows 11 Pro 10.0.26200, Python 3.13.13 (build venv), PyInstaller 6.22.3, numpy 2.5.5, qiskit 2.6.2. qiskit-aer NOT installed (build ran without it; `cq-hecs verify` would report it missing). CI uses Python 3.11 with constraints/ci-py311.txt and qiskit-aer, so this is not an identical environment.

## Defect found and fixed
scripts/build_exe.ps1: the optional `qiskit_aer` probe (`& $Python -c "import qiskit_aer" 2>$null`) aborted the whole build under `$ErrorActionPreference = "Stop"` in Windows PowerShell 5.1 whenever qiskit-aer was absent (native stderr became a terminating NativeCommandError). Hidden in CI because CI installs aer. Fix: relax the preference around the probe and use `2>&1 | Out-Null`. Verified: build now completes without aer.

## Commands and results
- Clean venv (scratchpad), `pip install numpy qiskit pyinstaller==6.22.3`.
- `powershell -File scripts/build_exe.ps1 -Python <venv> -OutDir <out> -WorkDir <work>`: exit 0. Built-in smoke on a copy in a temp dir, PYTHONPATH scrubbed: 14 PASS, 0 FAIL, 1 SKIPPED (import_location: frozen app, no --python). Checks include version `cq-hecs 7.0.0`, doctor, Bell, SAT+DRAT (DRAT_CHECKED), QG offline, Studio health/stop/port-conflict (exit 4, typed message), MCP initialize (21 tools).
- Licence notices: "0 entries without a licence file", 245 files in zip.
- Zip SHA-256 (no BUILD-INFO, as produced by build_exe.ps1 without a source SHA): 4c44af764d4ae99431b971dd35a4557e7756758d54804e7f823da1484fb640fa
- `cq-hecs.exe version` from a temp dir: `cq-hecs 7.0.0`. `cq-hecs.exe selftest --cases 4`: Result PASS, exit 0.
- `CQ_HECS_EXE=<exe> pytest tests/test_exe_smoke.py`: 6 passed (23 s).
- Studio manual run (`studio --port 58231`): LISTEN only on 127.0.0.1:58231 (netstat), HTTP 200 on 127.0.0.1. Process then stopped.
- BUILD-INFO: build_exe.ps1 only embeds it if CQHECS_SOURCE_SHA / GITHUB_SHA or --source-sha is given to package_archive.py (the release workflow does this). Tested by re-archiving with `--source-sha f880d0a5...` and SOURCE_DATE_EPOCH=1767225600: BUILD-INFO.json present (version 7.0.0, source_sha, build_date 2026-01-01Z, builder local), 246 entries, testzip OK; two runs byte-identical (SHA-256 270656e49d0f982c3c54e3b5e34e8f1335b57ff85938748ebec332cd14ee04d9). That hash is of a local re-archive, not a release artifact.

## NOT_RUN
- Clean-machine / no-Python-installed test (host has Python; smoke only proves repo is off path and env scrubbed).
- Build with qiskit-aer and on Python 3.11 with CI constraints; byte-reproducibility of PyInstaller output across two builds.
- SBOM/licence inventory for the EXE, SHA256SUMS manifest, release workflow, final freeze-SHA build (this build is from a dirty tree).
- Code signing (not performed; package is unsigned per docs/PACKAGING.md).
