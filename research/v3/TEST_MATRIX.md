# CQ-HECS v3 Test Matrix (in progress)

Base: `main` = `a65c35b` (v2.5.2). Environment as in
`research/v2_5_2/BASELINE.md` §3, plus `qiskit-ibm-runtime` 0.51.0.

## W1 + W2 (local, working tree before the first v3 commit)

| Gate | Command | Result |
|---|---|---|
| Fatal lint | `flake8 cqhecs tests scripts python_bridge --select=E9,F` | 0 |
| Versions | `python scripts/check_version.py` | PASS (2.5.2; v3 not versioned yet) |
| Silent truncation | `python scripts/verify_no_silent_truncation.py` | PASS |
| Python suite + native | `CQ_HECS_REQUIRE_NATIVE=1 coverage run --branch -m pytest tests/` | 504 passed, 0 skipped |
| Coverage | `coverage report` | 86 % (`calibration_import.py` 90 %, `hardware_bridge.py` 86 %) |
| New tests without qiskit-ibm-runtime | clean venv (numpy, qiskit, qiskit-aer, pytest) | 17 passed, 3 skipped with reason |
| New tests, pinned CPython 3.11 lane | `constraints/ci-py311.txt` incl. qiskit-ibm-runtime 0.51.0 | 21/21 |
| Mutation | `python scripts/run_mutation_tests.py` | 27/27 killed |
| All shipped snapshots | `test_all_shipped_snapshots_import` | 68/68 import, noise models with and without relaxation |
| Aer channel parity | `test_every_gate_channel_matches` (manila, quito, lagos) | max SuperOp diff ≤ 1e-12 (observed ≤ 1.6e-15) |
| Aer circuit parity | `test_random_basis_circuits_match_aer_density_matrix`, 12 circuits × 3 backends | TV ≤ 1e-12 + Aer trace loss (preregistered 1e-9 not met on manila, E-V3-02) |
| Real I/O (W4) | `python scripts/run_reference_evaluation.py --bootstrap 5000` | R-IO-5, 14 unique circuits: median ΔTV −0.015660, CI [−0.032546, 0.000000], pooled `INCONCLUSIVE`; Bell+GHZ (exploratory) −0.031797, CI [−0.054182, −0.017122] |
| W4 integrity | `python -m pytest tests/test_reference.py -q` | 24 passed |
| W4 CLI contract | `python -m pytest tests/test_cli_reference.py -q` | 4 passed |
| W4 dataset digest | `sha256sum tests/data/quantum_noise_transfer/*.json` | 5/5 match `SHA256SUMS`; combined `8069ad50…12a3` |
| R-IO-6 registration | `cq-hecs reference list` | 4 pinned files at revision `b9dd86b`; not evaluated (≥20 qubits) |
| Full Python suite | `python -m pytest tests/ -q` | 540 passed, 4 skipped (qiskit-ibm-runtime not installed) |
| Coverage | `python -m coverage run --branch -m pytest tests/` + `coverage report` | 88 % total; `reference.py` 81 % |
| Mutation | `python scripts/run_mutation_tests.py` | 35/35 killed (mutants 34–35 cover the selftest inverse relation and channel composition order) |
| Native | `ctest --test-dir build -C Release` | 19/19 passed |
| Selftest | `cq-hecs selftest --cases 8` | 11/11 checks PASS |
| Property-based circuits | `python -m pytest tests/test_property_circuits.py -q` | 4 passed (Hypothesis shrinking) |
| Selftest contract | `python -m pytest tests/test_selftest.py -q` | 8 passed |
