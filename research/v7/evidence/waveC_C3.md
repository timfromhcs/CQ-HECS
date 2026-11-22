# Wave C / C3: W12 integration (QG plan on four surfaces, analyze on the service, calibration v3 policy)

Date: 2026-11-22. Owned area only. No QPU job, no Open Quantum call, no credit, no credential, no git
mutation, no version bump. Windows, Python 3.13.13, pytest 9.2.0.

## What changed
- `cqhecs/service.py`: `qg_plan_document`, `qg_experiment_params` (closed, bounded parameter sets),
  `qg_experiments_document`, `qg_backends_document`, `qg_paid_refusal`, `qg_preview_document`,
  `qg_run_local_document`, `qg_validate_document`, `qg_compare_document`, `qg_export_document`,
  `analysis_document`, `calibration_provenance`, `load_calibration`, `run_with_calibration`, `doctor_report`.
- CLI: `qg plan|compare|export|backends`; `analyze --explain` on `service.analysis_document`; `run --calibration
  FILE --uncovered-gates refuse|warn|ideal`; `doctor` on `service.doctor_report`.
- MCP: `cqhecs_qg_plan`, `_model_validate`, `_compare`, `_export`, `cqhecs_doctor`, and five
  `cqhecs_qg_openquantum_{discover,quote,submit,status,results}` typed refusals (isError); `cqhecs_run`
  accepts `calibration` and `uncovered_gates`. 21 tools.
- Studio: `GET /api/qg/v1/experiments|backends|evidence/{id}|exports/{id}`, `POST .../experiments/plan|compare`,
  paid routes `.../openquantum/quote|submit|jobs/*` as typed 403, `GET /api/diagnostics` (OpenAPI +
  `schemas/studio.openapi.json` regenerated), `simulate` with `noise=calibration_v3` returns `calibration{}`.
- `research/v7/FEATURE_COVERAGE.json/.md`, `research/v7/TASKS.md`.
- `hardware_bridge.py` was not changed (its `uncovered_gate_policy` already existed; wiring is in the service).

## QGRAVITY 9.1 / 9.2 audit (before -> after)
| Item | Before | After |
|---|---|---|
| GET experiments, backends | missing | done (local, typed) |
| GET evidence/{id}, exports/{id} | only a global evidence view | done, read-only, secret-free |
| POST experiments/compare, MCP compare/export/model_validate | missing | done; QPU/simulator sources reported NOT_COMPARED |
| POST openquantum/quote, submit, GET jobs/*; MCP discover/quote/submit/status/results | missing | typed refusal (403 / isError `QG_PAID_PATH_UNAVAILABLE`); separate quote and submit; no "run paid" tool |
| Bounded inputs | partly | closed parameter set, ranges, theta +-6.2832, steps <= 64, n <= 8, lattice <= 4 and dense link ceiling, shots <= 20000 |
| No network in local path | by convention | AST test: no socket/requests/http.client/urllib.request/openquantum import in service, mcp_server, studio/app, cli |
| Single spend ledger | by convention | refusals name `research/qg_2026/JOB_LEDGER.jsonl` and `scripts/run_qg_openquantum_campaign.py` as the only writer; HTTP test hashes JOB_LEDGER/QUOTE_LEDGER before and after |
Gaps left: paid discover/quote/submit/status/results are not implemented here (authorisation, quote ids, Spark
balance snapshot and the 25-Spark ceiling exist only in the runner script); request IDs/audit event IDs for
Studio are not added; CSRF stays covered by the existing loopback + token + Origin checks.

## Commands and results
- `python -m pytest tests/test_qg_surface_parity.py -q` -> 49 passed
- `python -m pytest tests/test_calibration_surfaces.py -q` -> 16 passed (one test repaired: logging goes to caplog)
- `python -m pytest tests/test_service_w12.py tests/test_feature_coverage.py -q` -> 7 + 187 passed
  (first run failed on 12 bare-status cells; the cells were fixed, the test stayed)
- `python -m pytest tests/test_mcp_protocol.py -q` -> 32 passed (sample table extended; paid tools get a
  separate refusal test because they are isError by design)
- Regression set: test_qg_surface_parity, test_calibration_surfaces, test_service_w12, test_feature_coverage,
  test_cross_surface_parity, test_execution_plan, test_schema_contracts, test_quantum_gravity_studio(+_ui),
  test_qg_execution_plan, test_mcp_protocol/server/cancel, test_cli_contract/reference/expect/maxsat_contract,
  test_studio, test_studio_security, test_v3_calibration_bridge, test_hardware_bridge,
  test_quantum_gravity_contracts/campaign -> 530 passed, 4 skipped
- `python -m pytest tests/test_doctor_and_token.py tests/test_cli_powershell.py tests/test_correctness_contracts.py` -> 75 passed, 14 skipped
- `python scripts/qg_doc_consistency.py` -> OK; `flake8 --select=E9,F` on the four edited modules -> 0

## NOT RUN
Full pytest suite; Windows EXE build and `tests/test_exe_smoke.py` (skipped without CQ_HECS_EXE; two new opt-in
tests added); web build/e2e; native/CTest; any live Open Quantum or QPU call; a measured (non-synthetic) v3
calibration (none exists in the tree, so provenance was exercised with the synthetic fake_manila profile only);
`openapi_spec_validator`.
