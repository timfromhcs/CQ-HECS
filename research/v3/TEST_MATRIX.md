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
| Real I/O (W4) | — | BLOCKED (network policy) |
