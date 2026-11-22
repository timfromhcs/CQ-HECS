# Wave F2 hardening (F-08, F-09, F-10)

Status: SUPPORTED_IN_SCOPE (local unit/integration tests only; no live peer or network probe, NOT_RUN).

- F-08 (cqhecs/mcp_server.py): stdin is read with a bounded `readline` (`MAX_LINE_BYTES` = 32 MiB). An over-long line is
  drained in 1 MiB chunks without being kept and answered with JSON-RPC -32600 "(input_too_large)"; the server then
  continues. `circuit` and `cnf` schemas carry `maxLength` = `MAX_TEXT_CHARS` (16 Mi chars, equal to the parser's source cap) and
  `_call` refuses longer text with -32602 "(input_too_large)". The caps are ceilings, not a claim that inputs near them are
  cheap to solve.
- F-09 (cqhecs/studio/app.py `serve`, new `is_loopback_host`): a non-loopback `--host` prints a WARNING to stderr (remote clients
  still get `bad_host` because the allow-list is localhost-only). cli.py needed no change (it calls `serve`). Not a refusal.
- F-10 (cqhecs/studio/app.py `_read_json`): a non-digit, signed or negative `Content-Length` returns 400 `invalid_content_length`
  and closes the connection.

Tests: tests/test_wave_f2_hardening.py (16). The 3 MCP tests fail on the pre-fix mcp_server.py (verified); the Studio tests
fail on the pre-fix app.py at import (`is_loopback_host` missing), so the Content-Length case was not separately observed to
fail pre-fix (code reading only).
