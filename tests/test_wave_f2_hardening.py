"""Wave F2 hardening regressions: F-08 (MCP size caps), F-09 (non-loopback warning), F-10 (Content-Length)."""
from __future__ import annotations

import io
import json
import socket
import threading
from pathlib import Path

import pytest

from cqhecs import mcp_server
from cqhecs.studio import create_server
from cqhecs.studio.app import is_loopback_host, serve

ROOT = Path(__file__).parent.parent


# ---- F-08 -----------------------------------------------------------------
def _run_mcp(text: str) -> list:
    out = io.StringIO()
    assert mcp_server.main(stdin=io.StringIO(text), stdout=out) == 0
    return [json.loads(x) for x in out.getvalue().splitlines() if x.strip()]


def test_mcp_oversize_line_gets_typed_error_and_server_continues(monkeypatch):
    monkeypatch.setattr(mcp_server, "MAX_LINE_BYTES", 1000)
    monkeypatch.setattr(mcp_server, "_read_bounded_line",
                        lambda s, limit=1000, _r=mcp_server._read_bounded_line: _r(s, limit))
    huge = '{"jsonrpc":"2.0","id":1,"method":"ping","pad":"' + "x" * 50_000 + '"}\n'
    ping = '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
    replies = _run_mcp(huge + ping)
    assert replies[0]["error"]["code"] == -32600
    assert "input_too_large" in replies[0]["error"]["message"]
    assert replies[1]["id"] == 2 and "result" in replies[1]


def test_mcp_text_argument_over_cap_is_refused(monkeypatch):
    monkeypatch.setattr(mcp_server, "MAX_TEXT_CHARS", 100)
    for tool, key in (("cqhecs_run", "circuit"), ("cqhecs_sat_solve", "cnf")):
        reply = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": tool, "arguments": {key: "c " + "x" * 500}}})
        assert reply["error"]["code"] == -32602
        assert "input_too_large" in reply["error"]["message"]


def test_mcp_schemas_declare_max_length():
    for tool in mcp_server.TOOLS:
        props = tool["inputSchema"].get("properties", {})
        for key in ("circuit", "cnf"):
            if key in props:
                assert props[key]["maxLength"] == mcp_server.MAX_TEXT_CHARS, (tool["name"], key)


# ---- F-09 -----------------------------------------------------------------
@pytest.mark.parametrize("host,loop", [("127.0.0.1", True), ("localhost", True), ("::1", True),
                                       ("0.0.0.0", False), ("::", False), ("192.168.1.5", False), ("", False)])
def test_is_loopback_host(host, loop):
    assert is_loopback_host(host) is loop


def test_serve_warns_loudly_on_non_loopback(monkeypatch, capsys):
    class Boom(Exception):
        pass

    class Fake:
        server_address = ("0.0.0.0", 1)
        token_ephemeral = False
        state = type("S", (), {"dataset": type("D", (), {"note": ""})()})()

        def serve_forever(self, poll_interval=0.25):
            raise KeyboardInterrupt

        def shutdown(self): pass
        def server_close(self): pass

    monkeypatch.setattr("cqhecs.studio.app.create_server", lambda *a, **k: Fake())
    serve(host="0.0.0.0", port=1, open_browser=False)
    err = capsys.readouterr().err
    assert "WARNING" in err and "non-loopback" in err


# ---- F-10 -----------------------------------------------------------------
@pytest.fixture()
def studio():
    httpd = create_server(port=0, root=ROOT)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd
    httpd.shutdown(); httpd.server_close(); t.join(timeout=5)


@pytest.mark.parametrize("value", ["abc", "-5", "+7", "1.5", "0x10"])
def test_bad_content_length_is_400_typed(studio, value):
    port = studio.server_address[1]
    token = getattr(studio, "token", None)
    raw = (f"POST /api/sat/solve HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
           f"Content-Type: application/json\r\nContent-Length: {value}\r\n"
           + (f"Authorization: Bearer {token}\r\n" if token else "") + "Connection: close\r\n\r\n{}")
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(raw.encode())
        data = b""
        while chunk := s.recv(65536):
            data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    status = int(head.split()[1])
    assert status == 400, head
    assert json.loads(body)["error"]["code"] == "invalid_content_length"
