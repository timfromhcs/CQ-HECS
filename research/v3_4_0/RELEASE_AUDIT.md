# v3.4.0 release audit

**Audited:** 2026-10-30, after publication. Every asset was downloaded from the
release and its SHA-256 recomputed independently.
**Result:** PASS. Every digest matches `sha256sums.txt` (where listed) and
GitHub's own asset digest.

## 1. Source and CI

| Item | Value |
| :--- | :--- |
| Tag | `v3.4.0` → `0ce73f8c9c94c79e3cea405079066e8de64afe1d` (merge of PR #35) |
| Release | https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.4.0 (published 2026-10-30T22:24:37Z, not a draft) |
| Required CI on the tag SHA | https://github.com/timfromhcs/CQ-HECS/actions/runs/41136795967: success, 8/8 jobs |
| Release pipeline | https://github.com/timfromhcs/CQ-HECS/actions/runs/41136795965: success |
| PR head `57b6790` | 18/18 checks (8 CI jobs × push/PR, plus Vercel build and preview); same tree as the tag (`5a6b213`) |
| Linux lane | 698 passed, 4 skipped (opt-in exe tests), 1 opt-in slow gate deselected; branch coverage 83 %; CTest 21/21; mutation 44/44 |
| Web | `npm test` 14/14 (Qiskit fixtures, M-FIT-2 noise exactness on 30 cases, SAT vs brute force, i18n); production deployment `dpl_G2ymMFMk9JjyrRrcxziuZ8VHuQKg` at https://cq-hecs-web.vercel.app built from `0ce73f8` |

## 2. Assets (independently recomputed SHA-256)

| Asset | Bytes | SHA-256 | `sha256sums.txt` | GitHub digest |
| :--- | ---: | :--- | :---: | :---: |
| `cqhecs-3.4.0-py3-none-any.whl` | 263 838 | `5d651586ad45d98d94089cd450863090cc75de27b6a1a70609c1e92e42f0ac42` | ✓ | ✓ |
| `cqhecs-3.4.0.tar.gz` | 384 755 | `3504f322dc1068bfe19b1906f1a53527d710179e2c24ea492e1c1495f52bfb51` | ✓ | ✓ |
| `cqhecs-sbom.spdx.json` | 1 717 | `9c72b1cd8ec9d5601bf8d3fc77feead599ecc5c79b80a7779b3b470c2ef65048` | ✓ | ✓ |
| `RELEASE_NOTES_v3.4.0.md` | 8 591 | `e7b6198cff66d322dee932b80d764bcd596df430e571696360708888ba7c6f32` | ✓ | ✓ |
| `sha256sums.txt` | 360 | `858a55b9c9a0122abc6b3b494398a3b45d9cb7a032121ffcaaff2c4bec61067a` | — | ✓ |
| `cqhecs-3.4.0-windows-x64.zip` | 77 302 062 | `64a3d51286bc51ae9942abc89e4d748f522c663e0d9ba3aceeae9ecca0cc9098` | not listed (built locally) | ✓ |

## 3. Content checks

- **Windows build:** `scripts/build_exe.ps1` (PyInstaller onedir) in a clean
  Python 3.14 venv holding only `cqhecs` 3.4.0, `qiskit-aer` and PyInstaller.
  It was built from tree `b235ec0`, which differs from the tag only in
  `README.md`. The script's smoke tests passed: version, SAT, Bell, a Bell
  run with `--device iqm_garnet`, and Studio `/api/health` from `%TEMP%`. The
  **downloaded** zip, unpacked into a fresh folder, passed
  `tests/test_exe_smoke.py` 4/4, including `devices` and `run --device`.
  The binary is unsigned.
- **Wheel:** installed into a clean venv from the downloaded file;
  `cq-hecs version` → `3.4.0`, `cq-hecs selftest` → PASS, `cq-hecs devices`
  lists all five measured profiles.
- **Credentials:** no asset has an entry named `apikey`, `sdk-key-*`,
  `quantumrings.conf`, `.openquantum` or `QUANTUM_RUN`. The Open Quantum key
  values used for `r-iqm-1` occur in no asset, no tracked file and no commit in
  the history (`git log -S`).

## 4. Measurement provenance

`r-iqm-1` (IQM Garnet, 25 × 500 shots) was preregistered in commit `67b4032`
before submission and spent the full 25 Spark credits, with no Full credits.
The Open Quantum balance after the run: Spark 0, Full 0.

## 5. Open items

- Rotate the Open Quantum key used for `r-iqm-1` at
  https://www.openquantum.com/keys. The balance is 0, but the key is still valid.
- Rotate the IBM key from earlier runs.
