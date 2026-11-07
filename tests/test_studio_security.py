"""Security tests for the local CQ-HECS Studio HTTP server.

The Studio binds to loopback, but a web page open in the user's browser can still reach a
loopback server (cross-site "simple" POST, DNS rebinding). These tests pin the guard:
Host and Origin allow-lists, a per-launch bearer token on every /api/ route, JSON-only
POST bodies, bounded bodies, and clean shutdown.
"""

from __future__ import annotations

import http.client
import json
import socket
import threading
from pathlib import Path

import pytest

from cqhecs.studio import create_server
from cqhecs.studio.app import MAX_BODY, launch_url

ROOT = Path(__file__).parent.parent
CNF = "p cnf 2 2\n1 2 0\n-1 0\n"


@pytest.fixture()
def server():
    httpd = create_server(port=0, root=ROOT)
    calls = []
    real = httpd.state.sat_solve

    def recording(body):
        calls.append(body)
        return real(body)

    httpd.state.sat_solve = recording
    httpd.calls = calls
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def port_of(server):
    return server.server_address[1]


def request(server, method, path, *, headers=None, body=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port_of(server), timeout=20)
    hdrs = {"Host": host if host is not None else f"127.0.0.1:{port_of(server)}"}
    hdrs.update(headers or {})
    try:
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, raw
    finally:
        conn.close()


def raw_post(server, path, body, *, headers=None, pause=0.05, read_timeout=10):
    """POST with the body sent in a *second* segment after a pause, the way a slow client or proxy does.

    A server that answers and closes before the body has arrived leaves unread data in its socket;
    Linux then answers with a TCP RST and the client can lose the response. Returns the status code or
    raises ConnectionResetError / ConnectionError if the response was lost.
    """
    head = {"Host": f"127.0.0.1:{port_of(server)}", "Content-Length": str(len(body)), "Connection": "close"}
    head.update(headers or {})
    raw_head = (f"POST {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in head.items()) + "\r\n").encode()
    with socket.create_connection(("127.0.0.1", port_of(server)), timeout=read_timeout) as sock:
        sock.sendall(raw_head)
        import time as _time

        _time.sleep(pause)
        try:
            sock.sendall(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the server already answered; what matters is whether the answer survives
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    data = b"".join(chunks)
    if not data.startswith(b"HTTP/1."):
        raise ConnectionError("no response received")
    return int(data.split(b" ", 2)[1])


def auth(server):
    return {"Authorization": f"Bearer {server.token}"}


JSON = {"Content-Type": "application/json"}
SOLVE = json.dumps({"cnf": CNF, "engine": "watched", "timeout_seconds": 5}).encode()


def test_token_is_unpredictable_and_differs_per_server():
    a, b = create_server(port=0, root=ROOT), create_server(port=0, root=ROOT)
    try:
        assert len(a.token) >= 32 and a.token != b.token
    finally:
        for s in (a, b):
            s.server_close()


def test_a_foreign_host_header_is_refused_for_every_route(server):
    for path in ("/", "/api/health", "/static/app.js"):
        status, _, _ = request(server, "GET", path, headers=auth(server), host="evil.example:%d" % port_of(server))
        assert status == 400, path
    status, _, _ = request(server, "GET", "/api/health", headers=auth(server), host="127.0.0.1")  # port missing
    assert status == 400


@pytest.mark.parametrize("name", ["127.0.0.1", "localhost"])
def test_loopback_names_with_the_right_port_are_accepted(server, name):
    status, _, _ = request(server, "GET", "/api/health", headers=auth(server), host=f"{name}:{port_of(server)}")
    assert status == 200


def test_api_routes_need_the_token_but_static_files_do_not(server):
    assert request(server, "GET", "/api/health")[0] == 401
    assert request(server, "GET", "/api/health", headers={"Authorization": "Bearer wrong"})[0] == 401
    assert request(server, "GET", "/api/health", headers={"Authorization": "Bearer " + "x" * len(server.token)})[0] == 401
    assert request(server, "GET", "/api/health", headers={"Authorization": "Basic abc"})[0] == 401
    assert request(server, "GET", "/api/health", headers=auth(server))[0] == 200
    status, headers, body = request(server, "GET", "/")
    assert status == 200 and b"CQ-HECS" in body
    assert server.token.encode() not in body, "the token must never be embedded in served files"
    assert headers.get("cache-control") == "no-store"
    assert request(server, "GET", "/static/app.js")[0] == 200


def test_every_get_route_that_reads_local_state_is_protected(server):
    for path in ("/api/suite", "/api/noise", "/api/research", "/api/devices", "/api/hardware", "/api/omniwave/status", "/api/reference"):
        assert request(server, "GET", path)[0] == 401, path


def test_cross_site_simple_post_does_not_reach_the_solver(server):
    """The CSRF case: a web page posts text/plain with no custom headers."""
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={"Content-Type": "text/plain", "Origin": "https://evil.example"}, body=SOLVE)
    assert status in (401, 403)
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={"Content-Type": "text/plain"}, body=SOLVE)
    assert status == 401
    assert server.calls == [], "an unauthenticated request must not start a solver job"


def test_a_valid_token_with_a_foreign_origin_is_still_refused(server):
    for origin in ("https://evil.example", "null", f"http://127.0.0.1:{port_of(server) + 1}"):
        status, _, _ = request(server, "POST", "/api/sat/solve", headers={**auth(server), **JSON, "Origin": origin}, body=SOLVE)
        assert status == 403, origin
    assert server.calls == []
    ok = request(server, "POST", "/api/sat/solve", headers={**auth(server), **JSON, "Origin": f"http://127.0.0.1:{port_of(server)}"}, body=SOLVE)
    assert ok[0] == 200 and len(server.calls) == 1


def test_post_must_be_json(server):
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={**auth(server), "Content-Type": "text/plain"}, body=SOLVE)
    assert status == 415
    status, _, _ = request(server, "POST", "/api/sat/solve", headers=auth(server), body=SOLVE)  # no content type
    assert status == 415
    assert server.calls == []
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={**auth(server), "Content-Type": "application/json; charset=utf-8"}, body=SOLVE)
    assert status == 200


def test_malformed_and_oversized_bodies_are_typed_refusals(server):
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={**auth(server), **JSON}, body=b"{not json")
    assert status == 400
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={**auth(server), **JSON}, body=b"[1,2]")
    assert status == 400
    big = b'{"cnf": "' + b"1" * (MAX_BODY + 10) + b'"}'
    status, _, _ = request(server, "POST", "/api/sat/solve", headers={**auth(server), **JSON}, body=big)
    assert status == 413
    assert server.calls == []


def test_a_flood_of_rejected_requests_never_loses_a_response(server):
    """Early rejections must read the request body first, or Linux resets the connection (seen in the hardware bridge)."""
    codes = [raw_post(server, "/api/sat/solve", b"x" * 1024, headers={"Content-Type": "application/json"}) for _ in range(40)]
    assert set(codes) == {401}
    codes = [raw_post(server, "/api/sat/solve", b"x" * 1024, headers={"Content-Type": "application/json", "Origin": "https://evil.example", **auth(server)}) for _ in range(20)]
    assert set(codes) == {403}
    codes = [raw_post(server, "/api/sat/solve", b"x" * 1024, headers={"Content-Type": "text/plain", **auth(server)}) for _ in range(20)]
    assert set(codes) == {415}


def test_an_oversized_body_gets_its_413_even_when_it_arrives_late(server):
    big = b'{"cnf": "' + b"1" * (MAX_BODY + 10) + b'"}'
    codes = [raw_post(server, "/api/sat/solve", big, headers={"Content-Type": "application/json", **auth(server)}) for _ in range(5)]
    assert set(codes) == {413}
    assert server.calls == []


def test_options_never_grants_cross_origin_access(server):
    status, headers, _ = request(
        server, "OPTIONS", "/api/sat/solve",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert status in (401, 403, 405, 501)
    assert not any(k.startswith("access-control-") for k in headers)
    _, headers, _ = request(server, "GET", "/api/health", headers={**auth(server), "Origin": "https://evil.example"})
    assert not any(k.startswith("access-control-") for k in headers)


def test_launch_url_carries_the_token_only_in_the_fragment(server):
    url = launch_url(server)
    base, _, fragment = url.partition("#")
    assert base == f"http://127.0.0.1:{port_of(server)}/"
    assert fragment == f"token={server.token}"
    assert "token" not in base


def test_the_frontend_reads_the_fragment_and_sends_a_bearer_header():
    js = (ROOT / "cqhecs" / "studio" / "static" / "app.js").read_text(encoding="utf-8")
    assert "location.hash" in js and "Authorization" in js and "Bearer" in js
    first_hash_write = js.index("replaceState")
    assert js.index("location.hash") < first_hash_write, "read the token before any code rewrites the fragment"


def test_the_port_is_released_on_shutdown():
    httpd = create_server(port=0, root=ROOT)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))

def _responses_on_one_keepalive_connection(server, head_headers, body, wait=0.6):
    """Send one POST on a keep-alive connection and count the HTTP responses that come back."""
    head = {"Host": f"127.0.0.1:{port_of(server)}", "Content-Length": str(len(body))}
    head.update(head_headers)
    raw = (f"POST /api/sat/solve HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in head.items()) + "\r\n").encode() + body
    with socket.create_connection(("127.0.0.1", port_of(server)), timeout=wait) as sock:
        sock.sendall(raw)
        data = b""
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
        except (socket.timeout, TimeoutError):
            pass
        except ConnectionResetError:
            pass
    return data.count(b"HTTP/1.1 ") + data.count(b"HTTP/1.0 ")


def test_the_body_of_a_rejected_post_is_never_parsed_as_another_request(server):
    """Request smuggling on a keep-alive connection: a rejected request must not leave its body to be read as the next request."""
    smuggled = (
        f"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port_of(server)}\r\n"
        f"Authorization: Bearer {server.token}\r\n\r\n"
    ).encode()
    # no token -> 401, wrong content type with a token -> 415, foreign origin -> 403
    assert _responses_on_one_keepalive_connection(server, {"Content-Type": "application/json"}, smuggled) == 1
    assert _responses_on_one_keepalive_connection(server, {"Content-Type": "text/plain", **auth(server)}, smuggled) == 1
    assert _responses_on_one_keepalive_connection(server, {"Content-Type": "application/json", "Origin": "https://evil.example", **auth(server)}, smuggled) == 1


def test_the_body_of_an_oversized_post_is_never_parsed_as_another_request(server):
    smuggled = (
        f"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port_of(server)}\r\n"
        f"Authorization: Bearer {server.token}\r\n\r\n"
    ).encode()
    body = smuggled + b" " * (MAX_BODY + 10 - len(smuggled))
    assert _responses_on_one_keepalive_connection(server, {"Content-Type": "application/json", **auth(server)}, body) == 1


def test_the_frontend_removes_the_token_from_the_address_bar_after_reading_it():
    """Master P1 step 3: use the fragment only for the first hand-off, then strip it (history, bookmarks, screenshots)."""
    js = (ROOT / "cqhecs" / "studio" / "static" / "app.js").read_text(encoding="utf-8")
    start = js.index("const AUTH_TOKEN")
    block = js[start: js.index("})();", start)]
    assert "replaceState" in block and "location.pathname" in block
    assert block.index("exec(location.hash)") < block.index("replaceState")
