# v3.2.0 release audit

**Audited:** 2026-10-30, after publication. Every asset was downloaded from the
release and its SHA-256 recomputed independently.
**Result:** PASS. Each digest matches `sha256sums.txt` and GitHub's own asset
digest. The Windows build is not covered by `sha256sums.txt`, because the release
workflow does not build it; its digest is recorded here and matches GitHub's.

## 1. Source and CI

| Item | Value |
| :--- | :--- |
| Tag | `v3.2.0` → `2b61ab5e8b713984222ecf31eba51e22c017f961` (merge of PR #31) |
| Release | https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.2.0 (published 2026-10-30T20:07:47Z, not a draft or pre-release) |
| Required CI on the tag SHA | https://github.com/timfromhcs/CQ-HECS/actions/runs/41119586695 — success, 7/7 jobs |
| Release pipeline | https://github.com/timfromhcs/CQ-HECS/actions/runs/41119586305 — success |
| PR head `2a5b121` | push 41118133654 and pull_request 41118141253, both success; same tree as the tag (`239033a`) |
| Linux lane | 676 passed, 3 skipped (opt-in exe smoke), 1 opt-in slow gate deselected; branch coverage 83 %; CTest 21/21 |

## 2. Assets (independently recomputed SHA-256)

| Asset | Bytes | SHA-256 | `sha256sums.txt` | GitHub digest |
| :--- | ---: | :--- | :---: | :---: |
| `cqhecs-3.2.0-py3-none-any.whl` | 256 213 | `275f7ed66f8d4456066be2d87456a489ff0d0ef60a29027b8c58131ad5571fa5` | ✓ | ✓ |
| `cqhecs-3.2.0.tar.gz` | 373 236 | `fd6eecb9f681135b4fe7c0682288d6764b90f4402852e9d884483543b8ed7697` | ✓ | ✓ |
| `cqhecs-sbom.spdx.json` | 1 717 | `5a45bac1592b7f7fc395b57f13f268e84181c46707ecaa3d8a69e10acda49fc0` | ✓ | ✓ |
| `RELEASE_NOTES_v3.2.0.md` | 5 595 | `1fd32ade424bd6a62bef7a3ca4db8043f6c42e2ec523a79e1a76860394153417` | ✓ | ✓ |
| `sha256sums.txt` | 360 | `0d9ad08b8c4d1d5b17d998e24404ea93351f61987dfa7a5b5c0f089ab86b4ffc` | — | ✓ |
| `cqhecs-3.2.0-windows-x64.zip` | 77 287 990 | `ff7266d5a8ca51c2a5b6dec46d143257e14a3453972c24699ca3d5b1f45283a7` | not listed (built locally) | ✓ |

## 3. Content checks

- Windows build: built by `scripts/build_exe.ps1` (PyInstaller 6.21, onedir)
  in a clean Python 3.14 venv that held only `cqhecs` (from tree `239033a`),
  `qiskit-aer` and PyInstaller. The script's own smoke tests passed: `version`,
  `sat solve` (pigeonhole → UNSAT), `run name:bell`, and Studio `/api/health`
  started from `%TEMP%`. The **downloaded** zip was then unpacked into a fresh
  folder and passed `tests/test_exe_smoke.py`, 3/3. Zip entries use forward
  slashes. The binary is unsigned.
- Wheel: installed into a clean venv from the downloaded file;
  `cq-hecs version` → `3.2.0`; `cq-hecs selftest` → PASS.
- Credential scan of the wheel, sdist and Windows zip: none of them contains an
  entry named `apikey`, `sdk-key-*`, `quantumrings.conf`, `.openquantum` or
  `QUANTUM_RUN`.

## 4. Open items

- Provider keys (IBM, Open Quantum) must be rotated by the owner. That happens
  at the providers and cannot be done from this repository.
- The 8 queued IonQ pilot jobs are not collected.
