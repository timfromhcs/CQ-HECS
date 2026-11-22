"""W4-01: threaded MCP tool execution and the cancel contract.

A cancelled call is answered once with status CANCELLED and no verdict; the worker's late result is
discarded. Pure-Python compute is abandoned, not stopped, so the tests assert the contract (one typed
answer, the read loop stays live) and never that the computation stopped.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from cqhecs import mcp_server

ROOT = Path(__file__).resolve().parent.parent


def _lines(buf: io.StringIO):
    return [json.loads(x) for x in buf.getvalue().splitlines() if x.strip()]


def _wait(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@pytest.fixture()
def gated(monkeypatch):
    """_call blocks on an Event so tests control when a tool finishes."""
    gate = threading.Event()

    def slow(name, arguments):
        if name == "cqhecs_devices":
            gate.wait(10)
            return {"devices": ["late"]}
        return real(name, arguments)

    real = mcp_server._call
    monkeypatch.setattr(mcp_server, "_call", slow)
    yield gate
    gate.set()


def _call_msg(i, name="cqhecs_devices"):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": {}}}


def test_the_read_loop_stays_responsive_while_a_tool_runs(gated):
    out = io.StringIO()
    server = mcp_server.StdioServer(out, session=mcp_server._Session())
    server.dispatch(_call_msg(1))
    server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert [r["id"] for r in _lines(out)] == [2]  # ping answered while id 1 is still running
    gated.set()
    assert _wait(lambda: len(_lines(out)) == 2)
    assert {r["id"] for r in _lines(out)} == {1, 2}


def test_cancel_answers_once_with_cancelled_and_discards_the_late_result(gated):
    out = io.StringIO()
    server = mcp_server.StdioServer(out, session=mcp_server._Session())
    server.dispatch(_call_msg(7))
    server.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled",
                     "params": {"requestId": 7, "reason": "user"}})
    (reply,) = _lines(out)
    assert reply["id"] == 7 and reply["result"]["isError"] is True
    body = json.loads(reply["result"]["content"][0]["text"])
    assert body["status"] == "CANCELLED" and body["verdict"] is None and body["compute"] == "abandoned"
    gated.set()  # the abandoned worker now finishes
    assert _wait(lambda: not server._inflight)
    assert len(_lines(out)) == 1, "the late result must never be reported"
    assert "late" not in out.getvalue()


def test_cancel_of_an_unknown_or_finished_request_is_ignored():
    out = io.StringIO()
    server = mcp_server.StdioServer(out, session=mcp_server._Session())
    server.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 99}})
    server.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}})
    server.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": "junk"})
    assert _lines(out) == []


def test_cancelled_result_carries_structured_content_only_in_new_mode(gated):
    out = io.StringIO()
    session = mcp_server._Session()
    session.version = "2025-06-18"
    server = mcp_server.StdioServer(out, session=session)
    server.dispatch(_call_msg(3))
    server.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}})
    (reply,) = _lines(out)
    assert reply["result"]["structuredContent"]["status"] == "CANCELLED"


def test_duplicate_inflight_id_and_overload_are_typed(gated):
    out = io.StringIO()
    server = mcp_server.StdioServer(out, max_inflight=2, session=mcp_server._Session())
    server.dispatch(_call_msg(1))
    server.dispatch(_call_msg(1))  # same id still running
    assert _lines(out)[-1]["error"]["code"] == -32600
    server.dispatch(_call_msg(2))
    server.dispatch(_call_msg(3))  # third concurrent call exceeds the bound
    busy = _lines(out)[-1]
    assert busy["id"] == 3 and busy["result"]["isError"] is True
    payload = json.loads(busy["result"]["content"][0]["text"])
    assert payload["status"] == "UNKNOWN" and payload["verdict"] is None and payload["reason"] == "SERVER_BUSY"


def _pigeonhole(pigeons, holes):
    var = lambda p, h: p * holes + h + 1  # noqa: E731
    clauses = [[var(p, h) for h in range(holes)] for p in range(pigeons)]
    for h in range(holes):
        for a in range(pigeons):
            for b in range(a + 1, pigeons):
                clauses.append([-var(a, h), -var(b, h)])
    body = "".join(" ".join(map(str, c)) + " 0\n" for c in clauses)
    return f"p cnf {pigeons * holes} {len(clauses)}\n{body}"


def test_end_to_end_cancel_over_stdio_never_returns_a_verdict():
    proc = subprocess.Popen([sys.executable, "-m", "cqhecs.mcp_server"], cwd=ROOT, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        def send(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        send({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "cqhecs_sat_solve",
                         "arguments": {"cnf": _pigeonhole(10, 9), "timeout": 20.0}}})
        send({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        ping = json.loads(proc.stdout.readline())
        assert ping["id"] == 2  # answered while the solver is still running
        t0 = time.monotonic()
        send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
        reply = json.loads(proc.stdout.readline())
        assert time.monotonic() - t0 < 5.0
        assert reply["id"] == 1
        body = json.loads(reply["result"]["content"][0]["text"])
        assert body["status"] == "CANCELLED" and body["verdict"] is None
    finally:
        proc.kill()
        proc.wait(timeout=10)
