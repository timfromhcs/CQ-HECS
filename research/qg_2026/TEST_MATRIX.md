# TEST_MATRIX.md

| Layer | Command | Status | Result |
|---|---|---|---|
| Collect | `pytest tests/ --collect-only -q` | DONE | 2819/2820 collected, 1 deselected |
| Version | `python scripts/check_version.py` | DONE | exit 0, 5.0.0 consistent |
| Focused baseline | `pytest tests/test_reference.py tests/test_provenance.py tests/test_execution_plan.py tests/test_path_d_pauli_observables.py -q` | DONE | 268 passed |
| QG BMV oracle | `pytest tests/test_quantum_gravity_bmv.py -q` | DONE | 21 passed |
| QG SYK oracle | `pytest tests/test_quantum_gravity_syk.py -q` | DONE | 24 passed |
| QG contracts | `pytest tests/test_quantum_gravity_contracts.py -q` | DONE | 16 passed |
| QG runner | `pytest tests/test_quantum_gravity_campaign.py -q` | DONE | 6 passed |
| QG focused regression | BMV+SYK+contracts+runner + reference/provenance/execution/path_d | DONE | 335 passed |
| QG generate/validate | `python scripts/run_qg_openquantum_campaign.py generate\|validate` | DONE | status OK, digests match |
| QG Studio API | `pytest tests/test_quantum_gravity_studio.py -q` | DONE | 5 passed |
| QG MCP tools | `pytest tests/test_mcp_server.py -q` | DONE | 9 passed (incl. `cqhecs_qg_*`) |
| QG CLI | `pytest tests/test_cli_contract.py -q` | DONE | 37 passed (incl. `qg` commands) |
| Studio + security regression | `pytest tests/test_studio.py tests/test_studio_security.py -q` | DONE | 37 passed |
| CLI smoke | `python -m cqhecs.cli selftest --cases 2` | DONE | PASS |
| Full Python suite | `pytest tests/ -q` | NOT_RUN | M13 |
| Native CTest | `cmake … && ctest` | NOT_RUN | M10 |
| Web unit | `cd web && npm test` | NOT_RUN | M9 |
| Web E2E + axe | `npm run e2e` | NOT_RUN | M9 |
| Mutation | `python scripts/run_mutation_tests.py` | NOT_RUN | M13 |
| OQ doctor/discover | `python scripts/run_qg_openquantum_campaign.py doctor` | BLOCKED | B-1 |
| OQ quote/submit | (runner) | BLOCKED | B-1 |

Rule: an unavailable gate is `NOT_RUN`/`BLOCKED`, never green by inference.
