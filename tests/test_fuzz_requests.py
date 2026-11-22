"""Fuzz and property tests for the request surfaces (W15 / C5).

Covers the Studio ``StudioState`` operations, the Studio HTTP layer (size, type, range, path traversal,
framing) and the stdio MCP ``handle`` / ``StdioServer``.

Contract under test: a hostile or malformed request ends in a *typed* refusal (HTTP 4xx, JSON-RPC error,
or ``isError`` tool result). It never returns partial data as complete, never crashes the server, and
never reads a file the caller names.

Known defects found by this suite are pinned as ``xfail(strict=True)`` with their finding id from
``research/v7/SECURITY_AUDIT.md``; the strict flag makes the test fail loudly once the defect is fixed so
the marker gets removed rather than rotting.
"""

from __future__ import annotations

import http.client
import io
import json
import threading
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cqhecs import mcp_server
from cqhecs.circuit_parsing import UnsupportedCircuitInputError
from cqhecs.sat import CNFFormatError
from cqhecs.studio import StudioState, create_server
from cqhecs.studio.app import MAX_BODY, StudioError

ROOT = Path(__file__).parent.parent

#: Failures the HTTP layer maps to 4xx. Anything else raised by an operation becomes a 500.
TYPED = (StudioError, CNFFormatError, ValueError, TypeError, UnsupportedCircuitInputError)

FUZZ = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture],
    derandomize=True,
)

_scalar = st.one_of(
    st.none(), st.booleans(), st.integers(-(2**70), 2**70),
    st.floats(allow_nan=True, allow_infinity=True), st.text(max_size=40),
)
_json = st.recursive(
    _scalar,
    lambda c: st.one_of(st.lists(c, max_size=4), st.dictionaries(st.text(max_size=8), c, max_size=4)),
    max_leaves=12,
)


@pytest.fixture(scope="module")
def state():
    return StudioState(ROOT)


def _typed_or_ok(fn, request):
    try:
        out = fn(request)
    except TYPED:
        return None
    assert isinstance(out, dict)
    return out


# --------------------------------------------------------------------------- StudioState fuzz
@FUZZ
@given(
    num_vars=_json,
    clauses=_json,
    engine=st.one_of(st.sampled_from(["dpll", "watched", "omniwave", "cadical", "x"]), _scalar),
    node_budget=_json,
)
def test_sat_solve_clause_requests_are_typed_or_ok(state, num_vars, clauses, engine, node_budget):
    req = {"num_vars": num_vars, "clauses": clauses, "engine": engine, "node_budget": node_budget, "timeout": 0.05}
    out = _typed_or_ok(state.sat_solve, req)
    if out is not None:
        assert out["result"]["status"] in {"SAT", "UNSAT", "UNKNOWN"}


@FUZZ
@given(cnf=st.one_of(st.text(max_size=300), _json), method=_json)
def test_sat_count_cnf_requests_are_typed_or_ok(state, cnf, method):
    out = _typed_or_ok(state.sat_count, {"cnf": cnf, "method": method, "timeout": 0.05})
    if out is not None:
        assert "result" in out


@FUZZ
@given(source=_json, shots=_json, seed=_json, path=_json, noise=_json)
def test_simulate_requests_are_typed_or_ok(state, source, shots, seed, path, noise):
    _typed_or_ok(state.simulate, {"source": source, "shots": shots, "seed": seed, "path": path, "noise": noise})


@FUZZ
@given(source=_json, path=_json, extra=st.dictionaries(st.text(max_size=8), _json, max_size=3))
def test_plan_requests_are_typed_or_ok(state, source, path, extra):
    _typed_or_ok(state.plan, {**extra, "source": source, "path": path})


@pytest.mark.parametrize(
    "name",
    ["../../pyproject.toml", "..\\..\\pyproject.toml", "/etc/passwd", "C:\\Windows\\win.ini", "", "bell\x00", "%2e%2e/%2e%2e/x"],
)
def test_preset_names_never_resolve_to_files(state, name):
    with pytest.raises(StudioError):
        state.preset(name)


@pytest.mark.parametrize(
    "key", ["path", "file", "cnf_path", "filename", "out", "output", "json_out", "proof_out", "source_path"]
)
def test_requests_cannot_name_a_file_to_read_or_write(state, tmp_path, key):
    """No request key is a file path. A planted file must neither be read nor change the answer."""
    planted = tmp_path / "planted.cnf"
    planted.write_text("p cnf 1 1\n1 0\n", encoding="utf-8")
    cnf = "p cnf 1 2\n1 0\n-1 0\n"
    baseline = state.sat_solve({"cnf": cnf, "timeout": 0.5})
    out = state.sat_solve({"cnf": cnf, key: str(planted), "timeout": 0.5})
    assert out["result"]["status"] == baseline["result"]["status"] == "UNSAT"
    assert planted.read_text(encoding="utf-8") == "p cnf 1 1\n1 0\n"  # never rewritten
    with pytest.raises(StudioError):  # a request with only a path-like key is not a formula
        state.sat_solve({key: str(planted)})


# --------------------------------------------------------------------------- known defects (strict xfail)
@pytest.mark.xfail(strict=True, reason="SEC-L1: `random` that is not an object raises AttributeError -> HTTP 500, not a typed 4xx")
@pytest.mark.parametrize("bad", ["x", [1], 5])
def test_random_spec_must_be_an_object(state, bad):
    with pytest.raises(TYPED):
        state.sat_solve({"random": bad, "timeout": 0.05})


@pytest.mark.xfail(strict=True, reason="SEC-L1: `sizes` that is not a list is refused only by accident of int(); contract is a StudioError")
def test_sweep_sizes_must_be_a_list(state):
    with pytest.raises(StudioError):
        state.sat_sweep({"sizes": 5})


# --------------------------------------------------------------------------- HTTP layer
@pytest.fixture(scope="module")
def server():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _http(server, method, path, body=None, headers=None, token=True, content_type="application/json"):
    port = server.server_address[1]
    hdrs = {"Host": f"127.0.0.1:{port}"}
    if token:
        hdrs["Authorization"] = f"Bearer {server.token}"
    if content_type and body is not None:
        hdrs["Content-Type"] = content_type
    hdrs.update(headers or {})
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


@pytest.mark.parametrize("body", [b"\xff\xfe\x00", b"{", b"[]", b'"x"', b"null", b"1", b'{"a":{"a":1'])
def test_malformed_bodies_are_400(server, body):
    status, raw = _http(server, "POST", "/api/sat/solve", body)
    assert status == 400, raw
    assert json.loads(raw)["error"]["code"]


def test_oversized_body_is_413_and_server_survives(server):
    status, _ = _http(server, "POST", "/api/sat/solve", b'{"cnf":"' + b"a" * (MAX_BODY + 10) + b'"}')
    assert status == 413
    assert _http(server, "GET", "/api/health")[0] == 200


@pytest.mark.xfail(strict=True, reason="SEC-L2: deeply nested JSON raises RecursionError inside json.loads -> HTTP 500, not 400")
def test_deeply_nested_json_is_a_typed_400(server):
    status, raw = _http(server, "POST", "/api/sat/solve", b"[" * 200_000 + b"]" * 200_000)
    assert status == 400, raw


@pytest.mark.parametrize("length", ["abc", "-5", "1e3", " ", "99999999999999999999"])
def test_hostile_content_length_never_500s(server, length):
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.putrequest("POST", "/api/sat/solve")
        conn.putheader("Host", f"127.0.0.1:{port}")
        conn.putheader("Authorization", f"Bearer {server.token}")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", length)
        conn.endheaders()
        try:
            resp = conn.getresponse()
            resp.read()
            assert resp.status < 500, resp.status
        except (http.client.HTTPException, OSError):
            pass  # the server may close a malformed request; it must not hang or crash
    finally:
        conn.close()
    assert _http(server, "GET", "/api/health")[0] == 200


@pytest.mark.parametrize(
    "path",
    [
        "/static/../pyproject.toml", "/static/..%2fpyproject.toml", "/static/%2e%2e/%2e%2e/pyproject.toml",
        "/static/..\\pyproject.toml", "/static//etc/passwd", "/static/", "/static/app.py", "/static/%00",
        "/../pyproject.toml",
    ],
)
def test_static_path_traversal_is_never_served(server, path):
    status, raw = _http(server, "GET", path, token=False)
    assert status in (400, 404), (status, raw[:80])
    assert b"[project]" not in raw and b"root:" not in raw


@FUZZ
@given(body=st.binary(max_size=400))
def test_random_bytes_to_every_post_route_never_5xx(server, body):
    for route in ("/api/sat/solve", "/api/sat/count", "/api/simulate", "/api/plan"):
        status, _ = _http(server, "POST", route, body)
        assert status < 500, (route, status)


# --------------------------------------------------------------------------- MCP
def _call(name, arguments):
    return mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        mcp_server._Session(),
    )


@FUZZ
@given(message=_json)
def test_mcp_handle_never_raises_on_arbitrary_messages(message):
    resp = mcp_server.handle(message, mcp_server._Session())
    assert resp is None or isinstance(resp, dict)


@FUZZ
@given(
    method=st.sampled_from(["initialize", "tools/list", "tools/call", "ping", "notifications/initialized", "x"]),
    params=st.one_of(st.none(), st.dictionaries(st.text(max_size=8), _json, max_size=4)),
    rid=st.one_of(st.integers(), st.text(max_size=5), st.none()),
)
def test_mcp_object_params_never_raise(method, params, rid):
    msg = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        msg["params"] = params
    resp = mcp_server.handle(msg, mcp_server._Session())
    assert resp is None or isinstance(resp, dict)


@pytest.mark.xfail(strict=True, reason="SEC-L3: tools/call with non-object params raises AttributeError out of handle(); stdio maps it to -32603, not -32602")
@pytest.mark.parametrize("params", [[1], "x", 5])
def test_mcp_non_object_params_are_invalid_params(params):
    resp = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}, mcp_server._Session())
    assert resp["error"]["code"] == -32602


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("cqhecs_run", {"circuit": "preset:bell", "shots": 10**9}),
        ("cqhecs_run", {"circuit": "preset:bell", "shots": -1}),
        ("cqhecs_run", {"circuit": 5}),
        ("cqhecs_sat_solve", {"cnf": "p cnf 2 1\n9 0\n"}),
        ("cqhecs_sat_solve", {"cnf": "x" * 300_000}),
        ("cqhecs_sat_solve", {"cnf": "p cnf 1 1\n1 0\n", "timeout": 1e9}),
        ("cqhecs_sat_models", {"cnf": "p cnf 3 0\n", "limit": 10**9}),
        ("cqhecs_plan", {"circuit": "preset:bell", "force_path": "Z"}),
    ],
)
def test_mcp_out_of_range_inputs_are_typed_refusals(name, arguments):
    resp = _call(name, arguments)
    assert "error" in resp or resp["result"].get("isError") is True, resp


def test_mcp_stdout_is_only_json_rpc_lines():
    """Every line the stdio server writes parses as a JSON-RPC object; diagnostics never reach stdout."""
    out = io.StringIO()
    srv = mcp_server.StdioServer(out)
    for msg in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "nope"},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "cqhecs_devices", "arguments": {}}},
        [1, 2],
    ):
        srv.dispatch(msg)
    srv.drain(timeout=30)
    lines = [ln for ln in out.getvalue().split("\n") if ln]
    assert lines
    for ln in lines:
        assert json.loads(ln)["jsonrpc"] == "2.0"
