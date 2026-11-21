# Licence and dataset-terms register (W3-20)

Rule (AGENTS_V6.md §4 safety, PLAN_V6 decision 13): no new dependency, external
comparator or dataset may be added before its licence/terms are opened and recorded here.
An entry whose licence has not been opened this session stays `UNVERIFIED` on purpose —
guessing an SPDX identifier is a false claim. GPL tools are never vendored; external
solvers/checkers run as separate optional processes.

| Component | URL | Opened | SPDX | Usage | Notes |
|---|---|---|---|---|---|
| CQ-HECS (this repository) | https://github.com/timfromhcs/CQ-HECS | 2026-11-21 (LICENSE, pyproject) | Apache-2.0 | Shipped source | Declared in `pyproject.toml` and root `LICENSE`. |
| NumPy | https://numpy.org/ | not opened | UNVERIFIED | Runtime dependency | `numpy>=1.24.0` in `pyproject.toml`. |
| Qiskit | https://github.com/Qiskit/qiskit | not opened | UNVERIFIED | Runtime dependency; test oracle | `qiskit>=0.45.0`. Used for circuit parsing (Qiskit objects) and the Path B dense baseline benchmark. |
| python-sat (CaDiCaL adapter) | https://github.com/pysathq/pysat | not opened | UNVERIFIED | Optional `[sat]` extra | Optional; the SAT tests that need it are NOT RUN without it. |
| Qiskit Aer | https://github.com/Qiskit/qiskit-aer | not opened | UNVERIFIED | Dev/test oracle | `[dev]` extra; adversarial A/B oracle. |
| Stim | https://github.com/quantumlib/stim | not opened | UNVERIFIED | Dev/test oracle (Clifford) | `[dev]` extra. |
| pytest | https://github.com/pytest-dev/pytest | not opened | UNVERIFIED | Dev/test | `[dev]` extra. |
| Hypothesis | https://github.com/HypothesisWorks/hypothesis | not opened | UNVERIFIED | Dev/test (property/fuzz) | `[dev]` extra. |
| coverage.py | https://github.com/nedbat/coveragepy | not opened | UNVERIFIED | Dev/test | `[dev]` extra. |
| flake8 | https://github.com/PyCQA/flake8 | not opened | UNVERIFIED | Dev/lint | `[dev]` extra. |
| nanobind | https://github.com/wjakob/nanobind | not opened | UNVERIFIED | Dev/native bindings | `[dev]` extra. |
| qiskit-ibm-runtime | https://github.com/Qiskit/qiskit-ibm-runtime | not opened | UNVERIFIED | Dev (calibration import) | `[dev]` extra; calibration-import path only. |
| psutil | https://github.com/giampaolo/psutil | not opened | UNVERIFIED | Benchmark | `[benchmark]` extra. |
| rich | https://github.com/Textualize/rich | not opened | UNVERIFIED | Benchmark | `[benchmark]` extra. |
| CaDiCaL | https://github.com/arminbiere/cadical | not opened | UNVERIFIED | External solver baseline (process) | Never vendored; optional adapter only. |
| Kissat | https://github.com/arminbiere/kissat | not opened | UNVERIFIED | External solver baseline (planned) | Not integrated yet. |
| drat-trim | https://github.com/marijnheule/drat-trim | not opened | UNVERIFIED | External DRAT checker lane (planned) | Optional process; lane NOT RUN here. |
| cake_lpr (CakeML LRAT checker) | https://github.com/tanyongkiam/cake_lpr | not opened | UNVERIFIED | External LRAT checker lane (planned) | Optional process; lane NOT RUN here. |
| Lean 4 / Mathlib | https://github.com/leanprover/lean4 | not opened | UNVERIFIED | Formalisation lane (planned) | Pinned toolchain required before use. |
| mqt-ddsim / quimb / cotengra | https://github.com/cda-tum/mqt-ddsim | not opened | UNVERIFIED | Prototype comparators (Wave 9) | Not integrated; comparator experiments only. |
| Mitiq | https://github.com/unitaryfoundation/mitiq | not opened | UNVERIFIED | Reference only | Reported GPL-3.0 elsewhere; **never bundled**; any ZNE would be clean-room. |
| SAT Competition instances | https://satcompetition.github.io/ | not opened | UNVERIFIED | Benchmark inputs (planned) | Redistribution terms must be checked before any instance is committed. |
| Open Quantum result datasets | https://docs.openquantum.com/ | provider terms, not opened | UNVERIFIED | Historical eval data (`research/v3`, `research/qg_2026`) | Redact credentials; confirm redistribution terms before any external use. |

## Release-checklist implications

- Before v6.0.0, open every `UNVERIFIED` row that ships in the wheel/sdist or runs in a CI
  lane, record the date and SPDX, and confirm there is no copyleft conflict with Apache-2.0.
- No `UNVERIFIED` dataset may be redistributed with the release artifacts.
