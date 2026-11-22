# Wave A / A1 evidence (MCP, service layer, Studio guard, OpenAPI)

Environment: Windows 11, Python 3.13.13, pytest 9.2.0, jsonschema 4.26.0. No network spend (one public MCP spec page fetched to confirm field names).

## Studio guard reconcile (origin/codex/hcspnp-studio-guard)
- `git diff origin/main...origin/codex/hcspnp-studio-guard` reviewed. Every behaviour is already present in the tree: Host/Origin allow-lists, bearer token on /api/, JSON-only POST, bounded drains, token in URL fragment, `app.js` AUTH_TOKEN, bridge `_reject` (here with B-008 `_drain_declared`), `launch_url` (with W4-06 env/file token).
- `tests/test_studio_security.py` equals the branch copy (`diff --strip-trailing-cr` empty); 21 tests pass.
- Result: nothing to port. No code changed for this item.

## W4-01 / W4-05 (cqhecs/mcp_server.py)
- tests/test_mcp_cancel.py 6 passed (in-process gated worker; one real stdio test with a pigeonhole 10/9 solve: ping answered mid-solve, CANCELLED in < 5 s, verdict null).
- tests/test_mcp_protocol.py 22 passed (negotiation, legacy shape exact, annotations at 2025-03-26, title+outputSchema+structuredContent at 2025-06-18, text mirror equality, jsonschema validation of every tool's structuredContent).
- Deviation recorded: spec says a cancelled request SHOULD get no response; this server sends a typed CANCELLED result. Honest limit: compute is abandoned, not stopped.
- NOT RUN / not claimed: protocol revisions newer than 2025-06-18 (the plan's 2026-07-28 text is unconfirmed).

## W4-03 (cqhecs/service.py, `cq-hecs plan`)
- tests/test_cross_surface_parity.py 9 passed: service == CLI == MCP == Studio plan for 6 corpus cases incl. forced-path refusal and require_counts; typed errors per surface.
- Allow-list of envelope keys: CLI {schema_version, version}, Studio {schema_version}.
- Not migrated to the service: `cq-hecs analyze --explain` still calls build_execution_plan directly (same function, same output).

## W4-04 (cqhecs/studio/openapi.py, schemas/studio.openapi.json)
- tests/test_schema_contracts.py: 13 passed, 1 skipped (openapi_spec_validator not installed: NOT RUN).
- Route-drift guard: every non-qg route literal in app.py is documented; committed JSON equals the generator output.
- /api/v1 aliases tested for byte-equal responses and for token enforcement.
- Document lives in `schemas/` (owned area), not `docs/openapi/` as PLAN_V6 listed; move on request.

## Subsystem run
`pytest tests/test_studio.py test_studio_security test_mcp_server test_mcp_cancel test_mcp_protocol test_schema_contracts test_cross_surface_parity test_cli_contract test_cli_expect test_cli_reference test_cli_powershell test_execution_plan test_hardware_bridge test_doctor_and_token test_quantum_gravity_studio` -> 203 passed, 14 skipped (test_cli_powershell skips: no PowerShell harness condition). Full suite NOT RUN (per rules).
