"""Cancellation-race properties for the stdio MCP server (W15 / C5).

Invariants: every ``tools/call`` id is answered exactly once; a cancelled call is answered with a typed
``CANCELLED`` result and never a verdict; a worker that finishes after its cancel never produces a second
response; a cancel for an unknown or finished id is a no-op; capacity is enforced with a typed ``SERVER_BUSY``.
"""

from __future__ import annotations

import io
import json
import threading
import time

import pytest

from cqhecs import mcp_server


class _Out(io.StringIO):
    """Thread-safe-enough sink: StdioServer serialises its own writes under a lock."""

    def lines(self):
        return [json.loads(ln) for ln in self.getvalue().split("\n") if ln]


def _call_msg(rid, name="cqhecs_devices"):
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": {}}}


def _cancel_msg(rid, reason=None):
    params = {"requestId": rid}
    if reason:
        params["reason"] = reason
    return {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": params}


def _payload(response):
    return json.loads(response["result"]["content"][0]["text"])


@pytest.fixture()
def slow_tool(monkeypatch):
    """Replace the tool dispatcher with one that blocks until released."""
    gate = threading.Event()
    started = threading.Event()

    def fake_call(name, arguments):
        started.set()
        gate.wait(timeout=20)
        return {"verdict": "SAT-SHOULD-NEVER-BE-REPORTED-AFTER-CANCEL"}

    monkeypatch.setattr(mcp_server, "_call", fake_call)
    yield gate, started
    gate.set()


def test_cancelled_call_is_answered_once_with_no_verdict_and_late_result_is_dropped(slow_tool):
    gate, started = slow_tool
    out = _Out()
    srv = mcp_server.StdioServer(out)
    srv.dispatch(_call_msg(7))
    assert started.wait(5)
    srv.dispatch(_cancel_msg(7, "user pressed stop"))
    gate.set()
    srv.drain(timeout=10)
    time.sleep(0.2)  # let the worker run its (discarded) completion path
    lines = out.lines()
    assert [ln["id"] for ln in lines] == [7]
    body = _payload(lines[0])
    assert body["status"] == "CANCELLED" and body["verdict"] is None
    assert lines[0]["result"]["isError"] is True
    assert "SAT-SHOULD-NEVER" not in out.getvalue()


def test_double_cancel_answers_once(slow_tool):
    gate, started = slow_tool
    out = _Out()
    srv = mcp_server.StdioServer(out)
    srv.dispatch(_call_msg(1))
    assert started.wait(5)
    for _ in range(5):
        srv.dispatch(_cancel_msg(1))
    gate.set()
    srv.drain(timeout=10)
    assert len(out.lines()) == 1


@pytest.mark.parametrize("rid", [999, "never-sent", None, [1], {"a": 1}, 1.5])
def test_cancel_of_unknown_id_is_a_silent_noop(rid):
    out = _Out()
    srv = mcp_server.StdioServer(out)
    srv.dispatch(_cancel_msg(rid))
    assert out.getvalue() == ""


@pytest.mark.parametrize("params", [None, [], "x", 5, {}, {"reason": "no id"}])
def test_malformed_cancel_notifications_are_ignored(params):
    out = _Out()
    srv = mcp_server.StdioServer(out)
    msg = {"jsonrpc": "2.0", "method": "notifications/cancelled"}
    if params is not None:
        msg["params"] = params
    srv.dispatch(msg)
    assert out.getvalue() == ""


def test_cancel_after_completion_is_a_noop():
    out = _Out()
    srv = mcp_server.StdioServer(out)
    srv.dispatch(_call_msg(3))
    srv.drain(timeout=30)
    deadline = time.monotonic() + 10
    while not out.getvalue() and time.monotonic() < deadline:
        time.sleep(0.01)
    srv.dispatch(_cancel_msg(3))
    lines = out.lines()
    assert len(lines) == 1 and lines[0]["id"] == 3
    assert "CANCELLED" not in out.getvalue()


def test_duplicate_inflight_id_is_refused_and_original_survives(slow_tool):
    gate, started = slow_tool
    out = _Out()
    srv = mcp_server.StdioServer(out)
    srv.dispatch(_call_msg(5))
    assert started.wait(5)
    srv.dispatch(_call_msg(5))
    gate.set()
    srv.drain(timeout=10)
    time.sleep(0.2)
    lines = out.lines()
    assert any(ln.get("error", {}).get("code") == -32600 for ln in lines)
    assert sum(1 for ln in lines if "result" in ln) == 1


def test_capacity_is_enforced_with_typed_server_busy(slow_tool):
    gate, started = slow_tool
    out = _Out()
    srv = mcp_server.StdioServer(out, max_inflight=2)
    srv.dispatch(_call_msg(1))
    srv.dispatch(_call_msg(2))
    assert started.wait(5)
    srv.dispatch(_call_msg(3))
    busy = [ln for ln in out.lines() if ln["id"] == 3]
    assert len(busy) == 1
    body = _payload(busy[0])
    assert body["reason"] == "SERVER_BUSY" and body["verdict"] is None
    assert busy[0]["result"]["isError"] is True
    gate.set()
    srv.drain(timeout=10)


def test_cancelled_but_abandoned_workers_still_count_toward_capacity(slow_tool):
    gate, started = slow_tool
    out = _Out()
    srv = mcp_server.StdioServer(out, max_inflight=1)
    srv.dispatch(_call_msg(1))
    assert started.wait(5)
    srv.dispatch(_cancel_msg(1))
    srv.dispatch(_call_msg(2))
    answers = {ln["id"]: ln for ln in out.lines()}
    assert _payload(answers[1])["status"] == "CANCELLED"
    assert _payload(answers[2])["reason"] == "SERVER_BUSY"  # the abandoned thread is still alive
    gate.set()
    srv.drain(timeout=10)


@pytest.mark.parametrize("round_", range(40))
def test_cancel_racing_completion_never_double_answers(monkeypatch, round_):
    """Fire the cancel while the worker is finishing: exactly one answer, either result or CANCELLED."""

    def quick(name, arguments):
        time.sleep(0.001 * (round_ % 5))
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_call", quick)
    out = _Out()
    srv = mcp_server.StdioServer(out)
    srv.dispatch(_call_msg(round_))
    time.sleep(0.0005 * (round_ % 7))
    srv.dispatch(_cancel_msg(round_))
    srv.drain(timeout=10)
    time.sleep(0.05)
    lines = [ln for ln in out.lines() if ln["id"] == round_]
    assert len(lines) == 1, lines
    body = _payload(lines[0])
    assert body.get("status") == "CANCELLED" or body.get("ok") is True


def test_many_ids_in_parallel_each_answered_exactly_once(monkeypatch):
    def quick(name, arguments):
        time.sleep(0.005)
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_call", quick)
    out = _Out()
    srv = mcp_server.StdioServer(out, max_inflight=64)
    ids = list(range(32))
    for i in ids:
        srv.dispatch(_call_msg(i))
    for i in ids[::2]:
        srv.dispatch(_cancel_msg(i))
    srv.drain(timeout=20)
    time.sleep(0.2)
    seen = [ln["id"] for ln in out.lines()]
    assert sorted(seen) == ids
