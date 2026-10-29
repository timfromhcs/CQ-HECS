# CQ-HECS v2.5.0 Test Matrix & Evidence Ledger

Baseline source SHA: `74071b5519fe14dec54b7f893e3f2672198f66bb`.
Local platform: Windows 11 / CPython 3.14.6 / MSVC 19.44 / Vulkan SDK 1.4.357.

| Phase | Gate | Command / Target | Baseline Status | Candidate Status | Notes |
|---|---|---|---|---|---|
| L0 | Provenance & Live Repo | `git status`; `git rev-parse HEAD`; gh api | PASS | PASS | Branch: `agent/cq-hecs-v2.5.0-quantum-bridge` |
| L1 | Python compile | `python -m compileall -q cqhecs tests scripts python_bridge` | PASS (0 findings) | PASS (0 findings) | Bytecode verified across all modules |
| L1 | Fatal flake8 | `python -m flake8 cqhecs tests scripts python_bridge --count --select=E9,F` | PASS (0 findings) | PASS (0 findings) | Strict syntax and unused import check |
| L1 | Version consistency | `python scripts/check_version.py` | PASS (all 2.4.0) | PASS (all 2.5.0) | All surfaces report 2.5.0 |
| L1 | Silent truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS (0 patterns) | PASS (0 patterns) | Fail-closed invariants intact |
| L1 | Vulkan shaders | `python scripts/verify_vulkan_shaders.py` | PASS (12/12) | PASS (12/12) | SPIR-V 1.3 verified via glslangValidator |
| L2 | Native CTest | `ctest --test-dir build -C Release --output-on-failure` | PASS (19/19 in 16.55s) | PASS (19/19 in 16.44s) | MSVC 19.44 Release binaries |
| L3 | Full pytest suite | `CQ_HECS_REQUIRE_NATIVE=1 pytest tests/ -q` | PASS (420/420 in 55.40s) | PASS (452/452 in 59.97s) | 32 new tests added, 0 failures |
| L4 | Bridge & Noise tests | `pytest tests/test_hardware_bridge.py tests/test_noisy_density_matrix.py` | N/A | PASS (27/27 in 1.02s) | Independent oracles & Qiskit Aer differential tests |
| L5 | Mutation harness | `python scripts/run_mutation_tests.py` | PASS (14/14 killed) | PASS (16/16 killed, 100%) | 2 new mutants for bridge authorization and topology |
| L5 | Mutation meta-tests | `pytest tests/test_mutation_harness_meta.py` | PASS (10 passed) | PASS (10 passed, 48 subtests) | Full mutant harness meta-validation |
| L5 | Branch coverage | `python -m coverage run --branch ...; coverage report` | PASS (85%) | PASS (84%) | Minimum threshold >= 70% |
| L6 | Package build & twine | `python -m build; python -m twine check dist/*` | PASS (2.4.0) | PASS (2.5.0) | Pure-python wheel + sdist verified |
| L7 | Clean-wheel smoke | Clean isolated virtualenv install & CLI invocation | PENDING | PASS | `cq-hecs version` and `cq-hecs profile list` verified |
| L8 | Cloud CI | GitHub Actions on exact pushed candidate SHA | PENDING | PENDING | To be verified on PR push |
