"""Offline tests for scripts/verify_deployment.py using a local fake server."""
from __future__ import annotations

import importlib.util
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "verify_deployment", Path(__file__).resolve().parents[1] / "scripts" / "verify_deployment.py"
)
vd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vd)

SHA = "a" * 40


def _serve(routes: dict[str, tuple[int, bytes]]):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status, body = routes.get(self.path, (404, b"nope"))
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


@pytest.fixture
def serve():
    servers = []

    def make(routes):
        srv, url = _serve(routes)
        servers.append(srv)
        return url

    yield make
    for s in servers:
        s.shutdown()
        s.server_close()


SHELL = b'<html><script type="module" src="/assets/main-x.js"></script></html>'


def test_match(serve):
    url = serve({"/": (200, SHELL), "/assets/main-x.js": (200, f'a="7.0.0";b="{SHA}"'.encode())})
    assert vd.verify(url, SHA, "7.0.0")[0] == 0


def test_wrong_sha(serve):
    url = serve({"/": (200, SHELL), "/assets/main-x.js": (200, f'a="7.0.0";b="{"b" * 40}"'.encode())})
    assert vd.verify(url, SHA, "7.0.0")[0] == 1


def test_wrong_version(serve):
    url = serve({"/": (200, SHELL), "/assets/main-x.js": (200, f'a="6.9.0";b="{SHA}"'.encode())})
    assert vd.verify(url, SHA, "7.0.0")[0] == 1


def test_protection_page_is_not_a_pass(serve):
    url = serve({"/": (401, b"<title>Log in to Vercel</title>")})
    assert vd.verify(url, SHA, "7.0.0")[0] == 3


def test_unreachable():
    assert vd.verify("http://127.0.0.1:9", SHA, "7.0.0")[0] == 2


def test_no_script(serve):
    url = serve({"/": (200, b"<html></html>")})
    assert vd.verify(url, SHA, "7.0.0")[0] == 2


def test_cli_rejects_short_sha():
    assert vd.main(["http://127.0.0.1:9", "--sha", "abc"]) == 2
