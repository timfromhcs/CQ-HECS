# v3.5.0 release audit

**Audited:** 2026-10-31, after publication. Every asset was downloaded from the
release, and its SHA-256 was recomputed independently.
**Result:** PASS. Every digest matches `sha256sums.txt` (where the asset is listed there) and GitHub's own asset digest.

## 1. Source and CI

| Item | Value |
| :--- | :--- |
| Tag | `v3.5.0` → `725d2c35615b9ccf6f7fdc77cf0992bbc890b66c` (merge of PR #37), tree `afa366e` |
| Release | https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.5.0 (published 2026-10-31T06:39:49Z, not a draft) |
| Required CI on the tag SHA | https://github.com/timfromhcs/CQ-HECS/actions/runs/41176768213: success, 8/8 jobs |
| Release pipeline | https://github.com/timfromhcs/CQ-HECS/actions/runs/41176768187: success |
| PR head `9d13095` | 18/18 checks: 8 CI jobs on both push and pull_request, the Vercel build and the preview. Same tree as the tag (`afa366e`) |
| Linux lane | 1669 passed, 4 skipped (opt-in exe tests), 1 opt-in slow gate deselected. Branch coverage 84 %, `cqhecs/omniwave/*` 79–100 %. CTest 21/21. Mutation 54/54 |
| Vulkan in CI | `test_vulkan_compute_contract` on llvmpipe: `PASS omniwave BCP on GPU (29100 cells, 0 mismatches)` |
| Windows lane | 1573 passed, 50 skipped. CTest 21/21. Mutation 54/54 |
| Web | Unit tests, WASM build and 13 Playwright + axe tests in CI. The same 13 tests also pass against production (`E2E_BASE_URL=https://cq-hecs-web.vercel.app`), whose bundle reports source SHA `725d2c3` (deployment `dpl_3UnqEcDSXToopPPE6DJyYPKLW5Qq`) |

## 2. Assets (SHA-256 recomputed independently)

| Asset | Bytes | SHA-256 | `sha256sums.txt` | GitHub digest |
| :--- | ---: | :--- | :---: | :---: |
| `cqhecs-3.5.0-py3-none-any.whl` | 298 903 | `0bbd84acc74bd32c2ea0c9a9d4614d226dcec90d525c186a9a31845c19746c94` | ✓ | ✓ |
| `cqhecs-3.5.0.tar.gz` | 426 591 | `349e4394c2e9d92ec3a53b8d2d99970f3af4d95e485e3b8aaf321655bb946a05` | ✓ | ✓ |
| `cqhecs-sbom.spdx.json` | 1 717 | `cc58efb16383c47c899f7c512b920656c93ba71bd798246b4cc31981fa28b67e` | ✓ | ✓ |
| `RELEASE_NOTES_v3.5.0.md` | 10 368 | `0ac3a135466d6ba64b2bd6546f12e0c1ed2fc0947d149cb3ed2e833c8678b0ab` | ✓ | ✓ |
| `sha256sums.txt` | 360 | `fe51e63e12729156ae6d8328dffac69c20b557d0a2a4a7beabffe4932f3a45f6` | — | ✓ |
| `cqhecs-3.5.0-windows-x64.zip` | 77 376 589 | `f0ddbeb50c876d4549d5c8a0a7ec7fdbbcc7d8351591eb242c4a9584c366627a` | not listed (built locally) | ✓ |

## 3. Content checks

- **Windows build:**
  - Built with `scripts/build_exe.ps1` (PyInstaller onedir) from tree `afa366e`, the tag tree, in a clean Python 3.14 venv.
  - The script's smoke tests passed: version, SAT, **OMNIWAVE** (pigeonhole 6/5 → UNSAT `DRAT_CHECKED`), Bell, `--device iqm_garnet`, and Studio `/api/health` from `%TEMP%`.
  - The **downloaded** zip, unpacked into a fresh folder, passed `tests/test_exe_smoke.py` 4/4 and the OMNIWAVE pigeonhole run.
  - The binary is unsigned. It does not bundle the native library, so in the exe OMNIWAVE `vulkan` mode reports itself unavailable.
- **Wheel:** installed into a clean venv from the downloaded file.
  - `cq-hecs version` → `3.5.0`.
  - `cq-hecs selftest` → PASS.
  - `sat solve --engine omniwave` on `x ∧ ¬x` → UNSAT `DRAT_CHECKED`.
  - The wheel contains `cqhecs/omniwave/*` and `cqhecs/studio/omniwave_lab.py`.
- **Credentials:**
  - No asset has an entry named `apikey`, `sdk-key`, `quantumrings.conf`, `.openquantum` or `QUANTUM_RUN`.
  - The Open Quantum client ID occurs in no asset content (zip, wheel, sdist and text assets were scanned).
  - It occurs in no tracked file and in no commit in the history (`git log --all -S`).

## 4. Open items

- Rotate the Open Quantum key at https://www.openquantum.com/keys. Its balance is 0, but the key is still valid.
- Rotate the IBM key from earlier runs.
- `T-M2-03`: the Lean builds of the ETH artifacts were not re-run (`BLOCKERS.md` B-01).
- `T-M5-05`: the SAT Competition subset is deferred (B-03).
