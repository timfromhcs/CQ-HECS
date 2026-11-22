# Wave D, agent D2: SEC-M1, SEC-L1..L5, P-01

Status: FIXED locally, uncommitted (per hard rules). No version bump, no schema change (error shapes unchanged, openapi not regenerated: NOT_NEEDED).

| Finding | Fix | Where |
|---|---|---|
| SEC-M1 | `MAX_DIMACS_VARS = 1_000_000`, header refused with `CNFFormatError` before any allocation. One constant shared by CLI (usage exit 2), Studio (typed 4xx), MCP (isError/-32602), service, Python API, since all parse through `parse_dimacs`. Value justified in a comment: 10M vars took 0.7 s / hundreds of MB, 10**13 raised MemoryError. | `cqhecs/sat.py` |
| SEC-L4 | tokens validated against ASCII `-?[0-9]+`; `1_0`, `+1`, U+0661 refused | `cqhecs/sat.py` |
| SEC-L5 | `int_to_decimal_string` (exact via `decimal.Decimal(int)`, no process-global `set_int_max_str_digits`); used by both count backends | `cqhecs/sat.py` |
| SEC-L1 | `random` must be an object; `sizes`/`ratios` must be lists, element errors typed | `cqhecs/studio/app.py` |
| SEC-L2 | `RecursionError` in `_read_json` -> 400 `invalid_json` | `cqhecs/studio/app.py` |
| SEC-L3 | non-object `params` for `tools/call` -> -32602 | `cqhecs/mcp_server.py` |
| P-01 | `StudioPortError` raised by `serve()` on `OSError` at bind; `cmd_studio` logs it and returns `EXIT_ENVIRONMENT` (4), JSON code `studio_port_unavailable`. Also `allow_reuse_address = os.name != "nt"`: on Windows SO_REUSEADDR lets a second server bind an occupied port silently. | `studio/app.py`, `cli.py` |

xfail markers removed (assertions unchanged except the SEC-L5 test, which now asserts the stronger COUNTED + exact digits instead of "UNKNOWN or COUNTED"): test_fuzz_requests (SEC-L1 x4, L2, L3 x3), test_fuzz_dimacs_parser (L4 x3), test_resource_limits (M1, L5).
New tests: Studio/MCP/CLI cap refusals, int_to_decimal_string exactness, occupied-port CLI exit (Windows exclusive-bind blocker).

Run (targeted): 182 passed (fuzz_requests, fuzz_dimacs_parser, resource_limits, property_cancellation); 798 passed, 15 skipped (cli_contract, fuzz_sat, mcp_*, sat_*, schema_contracts, service_w12, studio, studio_security).
NOT_RUN: full suite, POSIX EADDRINUSE path (Windows host only; the code catches the generic OSError so both are covered by construction), SECURITY_AUDIT.md status table (not in owned area).
Note: the cap is enforced in `parse_dimacs`; a `CNF(...)` built directly in Python is not capped.
