# Licence and dataset-terms register (W3-20, updated W15 / C5)

Rule (AGENTS_V6.md §4 safety, PLAN_V6 decision 13): no new dependency, external
comparator or dataset may be added before its licence/terms are opened and recorded here.
An entry whose licence has not been opened stays `UNVERIFIED` on purpose —
guessing an SPDX identifier is a false claim. GPL tools are never vendored; external
solvers/checkers run as separate optional processes.

Evidence basis for the 2026-11-22 update: the `License` / `License-Expression` field of the **installed
distribution metadata** (`importlib.metadata`) on the audit host, and the `license` field of
`web/package-lock.json`. That is the licence the maintainer declared in the package that is installed
here, not a reading of the upstream LICENSE file; a metadata field can be coarse (NumPy lists the
licences of everything bundled in its wheel) or non-SPDX (`Apache 2.0`, `Apache 2`). Rows say which.
Nothing here is legal advice.

| Component | URL | Opened | SPDX | Usage | Notes |
|---|---|---|---|---|---|
| CQ-HECS (this repository) | https://github.com/timfromhcs/CQ-HECS | 2026-11-21 (LICENSE, pyproject) | Apache-2.0 | Shipped source | Declared in `pyproject.toml`, `web/package.json`, `web/wasm/Cargo.toml` and root `LICENSE`. |
| NumPy | https://numpy.org/ | 2026-11-22 installed metadata, 2.5.0 | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` (as declared) | Runtime dependency | `numpy>=1.24.0`. Compound expression covers code bundled in the wheel; all permissive. |
| Qiskit | https://github.com/Qiskit/qiskit | 2026-11-22 installed metadata, 2.6.1 | Apache-2.0 | Runtime dependency; test oracle | `qiskit>=0.45.0`. |
| python-sat (CaDiCaL adapter) | https://github.com/pysathq/pysat | not opened (not installed on the audit host) | UNVERIFIED | Optional `[sat]` extra | Optional; the SAT tests that need it are NOT RUN without it. |
| Qiskit Aer | https://github.com/Qiskit/qiskit-aer | 2026-11-22 installed metadata, 0.18.2 | `Apache 2.0` (non-SPDX spelling; Apache-2.0 intended, classifier says Apache Software License) | Dev/test oracle | `[dev]` extra; adversarial A/B oracle. |
| Stim | https://github.com/quantumlib/stim | 2026-11-22 installed metadata, 1.16.0 | `Apache 2` (non-SPDX spelling; Apache-2.0 intended) | Dev/test oracle (Clifford) | `[dev]` extra. |
| pytest | https://github.com/pytest-dev/pytest | 2026-11-22 installed metadata, 9.2.0 | MIT | Dev/test | `[dev]` extra. |
| Hypothesis | https://github.com/HypothesisWorks/hypothesis | 2026-11-22 installed metadata, 6.170.14 | **MPL-2.0** | Dev/test (property/fuzz) | `[dev]` extra, never shipped in the wheel. MPL-2.0 is file-level copyleft: using it as a test tool imposes nothing on Apache-2.0 sources; do not vendor or modify its files. |
| coverage.py | https://github.com/nedbat/coveragepy | 2026-11-22 installed metadata, 7.17.0 | Apache-2.0 | Dev/test | `[dev]` extra. |
| flake8 | https://github.com/PyCQA/flake8 | 2026-11-22 installed metadata, 7.5.0 | MIT | Dev/lint | `[dev]` extra. |
| nanobind | https://github.com/wjakob/nanobind | not opened (not installed on the audit host) | UNVERIFIED | Dev/native bindings | `[dev]` extra. |
| qiskit-ibm-runtime | https://github.com/Qiskit/qiskit-ibm-runtime | not opened (not installed on the audit host) | UNVERIFIED | Dev (calibration import) | `[dev]` extra; calibration-import path only. |
| psutil | https://github.com/giampaolo/psutil | 2026-11-22 installed metadata, 7.2.2 | BSD-3-Clause | Benchmark | `[benchmark]` extra. |
| rich | https://github.com/Textualize/rich | 2026-11-22 installed metadata, 15.0.0 | MIT | Benchmark | `[benchmark]` extra. |
| Web runtime packages (CodeMirror family: `codemirror`, `@codemirror/{lang-javascript,language,legacy-modes,state,theme-one-dark,view}`, `@lezer/highlight`) | https://codemirror.net/ | 2026-11-22 `web/package-lock.json` | MIT (all) | Shipped in the web bundle | Versions pinned by the lockfile (e.g. `@codemirror/view` 6.43.15). |
| Vite, TypeScript, `@webgpu/types`, `@playwright/test` | https://vite.dev/ | 2026-11-22 `web/package-lock.json` | MIT (vite 6.4.5), Apache-2.0 (typescript 5.9.3, playwright 1.64.1), BSD-3-Clause (`@webgpu/types` 0.1.74) | Web build/test only | Dev dependencies; not part of the shipped bundle. |
| `@axe-core/playwright` | https://github.com/dequelabs/axe-core-npm | 2026-11-22 `web/package-lock.json`, 4.14.0 | **MPL-2.0** | Web accessibility tests only | Dev dependency; file-level copyleft, do not vendor. |
| Web lockfile, all 93 lockfile entries (root included) | n/a | 2026-11-22 `web/package-lock.json` | MIT 83, Apache-2.0 5, MPL-2.0 2, BSD-3-Clause 2, ISC 1 | Transitive | No GPL/AGPL/LGPL entry. The two MPL-2.0 packages in the lockfile are `axe-core` and `@axe-core/playwright` 4.14.0, both marked `dev: true` in the lockfile. `license` is the field the package declares; it was not independently verified per package. |
| Rust crate `cqhecs-web-core` | in-repo (`web/wasm`) | 2026-11-22 `Cargo.lock` | Apache-2.0 | Shipped WASM core | `Cargo.lock` lists this crate only: no third-party Rust dependency. |
| CaDiCaL | https://github.com/arminbiere/cadical | not opened | UNVERIFIED | External solver baseline (process) | Never vendored; optional adapter only. |
| Kissat | https://github.com/arminbiere/kissat | not opened | UNVERIFIED | External solver baseline (planned) | Not integrated yet. |
| drat-trim | https://github.com/marijnheule/drat-trim | not opened | UNVERIFIED | External DRAT checker lane (planned) | Optional process; lane NOT RUN here. |
| cake_lpr (CakeML LRAT checker) | https://github.com/tanyongkiam/cake_lpr | not opened | UNVERIFIED | External LRAT checker lane (planned) | Optional process; lane NOT RUN here. |
| Lean 4 / Mathlib | https://github.com/leanprover/lean4 | not opened | UNVERIFIED | Formalisation lane (planned) | Pinned toolchain required before use. |
| mqt-ddsim / quimb / cotengra | https://github.com/cda-tum/mqt-ddsim | not opened | UNVERIFIED | Prototype comparators (Wave 9) | Not integrated; comparator experiments only. |
| Mitiq | https://github.com/unitaryfoundation/mitiq | not opened | UNVERIFIED | Reference only | Reported GPL-3.0 elsewhere; **never bundled**; any ZNE would be clean-room. |
| SAT Competition instances | https://satcompetition.github.io/ | not opened | UNVERIFIED | Benchmark inputs (planned) | Redistribution terms must be checked before any instance is committed. |
| Open Quantum result datasets | https://docs.openquantum.com/ | provider terms, not opened | UNVERIFIED | Historical eval data (`research/v3`, `research/qg_2026`) | Redact credentials; confirm redistribution terms before any external use. |

## Compatibility reading (W15)

- Everything that ships in the wheel and the web bundle and was opened this session is permissive
  (Apache-2.0, MIT, BSD-3-Clause, and NumPy's permissive compound). No copyleft was found in the shipped
  set that was opened.
- The two MPL-2.0 packages (Hypothesis, axe-core/playwright) are test-time tools. They are not imported
  by `cqhecs/` or bundled into `web/dist`. Keeping them out of the wheel and bundle keeps this true.
- `python_bridge` ships in the wheel (`pyproject.toml` package find) alongside `cqhecs`; its licence is the
  project's Apache-2.0.
- Not opened, therefore not claimed: python-sat, nanobind, qiskit-ibm-runtime, every external solver or
  checker, Lean/Mathlib, the comparators and all datasets.

## Release-checklist implications

- Before v6.0.0, open every `UNVERIFIED` row that ships in the wheel/sdist or runs in a CI
  lane, record the date and SPDX, and confirm there is no copyleft conflict with Apache-2.0.
- No `UNVERIFIED` dataset may be redistributed with the release artifacts.
- The SBOM (`scripts/generate_sbom_and_checksums.py`) is the machine-readable twin of this table; any
  mismatch between the two is a defect in one of them.

## Packaging toolchain and frozen bundle (C2, W14 / T6-07, 2026-11-22)

Opened this session: each distribution's own `METADATA` (and, where noted, its licence file) in the clean
build venv used for the Windows onedir folder. `scripts/sbom_cyclonedx.py` writes the same facts as a
CycloneDX 1.5 inventory; `scripts/package_notices.py` copies each bundled distribution's licence files
into the folder (`licences/`, `THIRD_PARTY_NOTICES.txt`).

| Component | Source of the statement | SPDX / declared | Usage | Notes |
|---|---|---|---|---|
| PyInstaller 6.22.3 (bootloader embedded in `cq-hecs.exe`) | `COPYING.txt` in its dist-info, opened; SPDX header line `GPL-2.0-or-later WITH Bootloader-exception` | GPL-2.0-or-later with Bootloader exception | Build tool; its bootloader is part of the shipped exe | The exception text (unlimited permission to embed the compiled bootloader in combinations distributed without restriction) was read. The rest of PyInstaller is not shipped. `COPYING.txt` is copied into the folder. |
| pyinstaller-hooks-contrib 2026.10 | METADATA classifiers | Apache-2.0 OR GPL-2.0 (classifiers) | Build time only | Not shipped; licence file not opened. |
| altgraph 0.17.5, pefile 2024.8.26 | METADATA License field | MIT | Build time only | Not shipped. |
| scipy 1.18.1 | METADATA Trove classifier only (`BSD License`) | BSD (no SPDX id stated) | Bundled in the onedir folder (Qiskit dependency) | Wheel vendors native libraries under `scipy.libs`; not individually inventoried. |
| qiskit-aer 0.18.4 | METADATA License field (`Apache 2.0`) | Apache-2.0 (free text) | Bundled in the onedir folder; used only by `cq-hecs verify` | Vendors native libraries under `qiskit_aer.libs`; not individually inventoried. |
| rustworkx 0.18.1, stevedore 5.10.0, qiskit 2.6.2 | METADATA License-Expression | Apache-2.0 | Bundled | |
| dill 0.4.1, psutil 7.2.2, python-dateutil 4.0.0 | METADATA | BSD-3-Clause | Bundled | |
| typing_extensions 4.16.0 | METADATA License-Expression | PSF-2.0 | Bundled | |
| tzdata 2026.6 | METADATA License field | Apache-2.0 | Bundled | |
| numpy 2.5.5 | METADATA License-Expression | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Bundled | 17 licence files copied. |
| CPython 3.14.6 runtime, Microsoft Visual C++ runtime DLLs (in the onedir folder) | not opened | UNVERIFIED | Bundled / required at run time | Listed as `UNVERIFIED` components in the SBOM; open before a release. |
| `cq-hecs-cpu` / `cq-hecs-vulkan` native zips | in-repo sources | Apache-2.0 (project) | Shipped | No third-party library is vendored; they need the MSVC 2015-2022 x64 runtime installed on the target. |
| `build` 1.5.0, `cyclonedx-python-lib` 11.12.0 | installed metadata | MIT, Apache-2.0 | Packaging tools (not shipped) | `cyclonedx-python-lib` was used only to validate the SBOMs against the CycloneDX 1.5 JSON schema. |


## Reconciliation for the 7.0.0 candidate build (E3, 2026-11-22)

Why this section exists. The "Packaging toolchain and frozen bundle" table above records the C2 build of the
**5.0.0 dirty tree** on CPython 3.14.6 in an unconstrained venv. Every version in it (numpy 2.5.5, qiskit 2.6.2,
qiskit-aer 0.18.4, scipy 1.18.1, stevedore 5.10.0, python-dateutil 4.0.0, typing_extensions 4.16.0, tzdata
2026.6) was read from that venv's `dist-info` folders, so none is invented, but none is the version set of the
candidate build. That table is kept as history and is **superseded for the release** by this section.

Source: the CycloneDX 1.5 SBOMs of the `38e799b` artifacts, produced by the integrator's build
(`cqhecs-7.0.0-windows-x64.cdx.json` for the EXE folder, `cqhecs-7.0.0-wheel.cdx.json` for the wheel), opened by
E3 on 2026-11-22 from the session scratchpad (they are not in the repository), cross-read with
`constraints/ci-py311.txt` and `package.yml`. The licence strings are the SBOM's own, taken from each
distribution's `METADATA` in the build venv. Hashes of the artifacts: `PACKAGING_AUDIT.md`. These SBOMs will be
regenerated at the final freeze SHA; any difference is a defect in this table.

### Windows onedir EXE folder (`cqhecs-7.0.0-windows-x64.cdx.json`, 13 components)

| Component | Version in the SBOM | Licence string in the SBOM | Status |
|---|---|---|---|
| CPython runtime | 3.11 | UNVERIFIED | UNVERIFIED (PSF-2.0 expected; not claimed) |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | matches `ci-py311.txt`; licence opened at other numpy versions in C2 |
| scipy | 1.16.3 | `BSD License` (Trove classifier only) | matches `ci-py311.txt`; no SPDX id; vendored native libraries in `scipy.libs` not inventoried |
| qiskit | 2.5.1 | Apache-2.0 | matches `ci-py311.txt` |
| qiskit-aer | 0.17.2 | `Apache 2.0` (free text) | matches `ci-py311.txt`; vendored native libraries in `qiskit_aer.libs` not inventoried |
| rustworkx | 0.18.1 | Apache-2.0 | matches `ci-py311.txt` |
| dill | 0.4.1 | BSD-3-Clause | matches `ci-py311.txt` |
| stevedore | 5.9.0 | Apache-2.0 | matches `ci-py311.txt` |
| psutil | 7.2.2 | BSD-3-Clause | matches `ci-py311.txt` |
| python-dateutil | 2.9.0.post0 | `Dual License` (free text, no SPDX id) | matches `ci-py311.txt`; text not opened, so the actual licences are UNVERIFIED |
| six | 1.17.0 | MIT | not in `ci-py311.txt` (a transitive dependency of python-dateutil); new compared with the C2 table |
| typing_extensions | 4.12.2 | Python Software Foundation License | **differs from `ci-py311.txt` (4.15.0)**: the local build did not take that pin; PSF-2.0 by the declared name |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later WITH Bootloader-exception | OPENED in C2 at the same version (exception text read); `COPYING.txt` copied to `licences/` |

Not in the candidate EXE SBOM although the C2 table listed it: `tzdata`. The VC++ runtime DLLs the folder may
contain are not listed as a component at all (the C2 SBOM listed them as `UNVERIFIED`; this one does not).

### Wheel SBOM (`cqhecs-7.0.0-wheel.cdx.json`, 23 components): inaccurate

The wheel SBOM lists the **build venv**, not the runtime dependency closure of `cqhecs`: it contains `setuptools`
79.0.1 (`UNVERIFIED`) together with the packages setuptools vendors (`autocommand` 2.2.2, `backports.tarfile`,
`importlib_metadata`, `inflect`, `jaraco.*`, `more-itertools`, `packaging`, `platformdirs`, `tomli`, `typeguard`,
`zipp`), `wheel`, and runtime-looking packages at versions different from the EXE SBOM (`qiskit` 2.6.2 and
`scipy` 1.17.1 here, against 2.5.1 and 1.16.3 in the EXE SBOM). The consequences:

- **`autocommand` 2.2.2 is listed as `LGPLv3`.** It is vendored inside setuptools, a build tool, and is not a
  dependency of `cqhecs` or part of the wheel. Read as a dependency list, the wheel SBOM would claim an LGPL-3.0
  component that does not ship, so the file as built must not be published. This is SEC-P2-2 in `SECURITY_AUDIT.md`.
- The versions of numpy, qiskit, scipy and stevedore in that file describe a different environment from the one
  the EXE was frozen from.

An uncommitted edit adds `--closure-of cqhecs` to `scripts/sbom_cyclonedx.py` for exactly this purpose. E3 has not
run it; the freeze rebuild must show a wheel SBOM with numpy, qiskit, scipy (via qiskit), rustworkx, stevedore,
dill, python-dateutil, six, typing_extensions, psutil only as applicable, and no setuptools-vendored entries.

### Corrections to this register made by the reconciliation

- `python-dateutil 4.0.0` and `typing_extensions 4.16.0` in the C2 table are 3.14-venv versions; the candidate has
  2.9.0.post0 and 4.12.2.
- The CPython runtime is 3.11 in the candidate (the C2 table said 3.14.6).
- Main-table versions (numpy 2.5.0, qiskit 2.6.1, aer 0.18.2, and so on) are those of the Python 3.13 audit host,
  not of any shipped artifact; they back the licence statement for the distribution, not a version claim.

### Still open (SEC-P2-3)

CPython and VC++ runtime licences; vendored native libraries in scipy and qiskit-aer; the actual text behind
python-dateutil's `Dual License`; python-sat, qiskit-ibm-runtime, sympy and nanobind (CI and dev only, not
shipped); every external solver, checker, comparator and dataset row marked `UNVERIFIED` above. No `UNVERIFIED`
dataset ships with the artifacts.
