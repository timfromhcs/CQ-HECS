"""Studio Quantum Gravity Lab page: static assets are served and honour the lab's hard rules."""

from __future__ import annotations

import re
import threading
import urllib.request
from pathlib import Path

import pytest

from cqhecs.studio import create_server

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "cqhecs" / "studio" / "static"


@pytest.fixture(scope="module")
def server():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _fetch(server, path):
    request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}{path}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


def test_qg_script_and_view_are_served(server):
    status, ctype, body = _fetch(server, "/static/qg.js")
    assert status == 200 and "javascript" in ctype and "qgStudioMount" in body
    _, _, index = _fetch(server, "/")
    assert 'id="view-qg"' in index and 'data-view="qg"' in index and "/static/qg.js" in index
    assert index.index("/static/app.js") < index.index("/static/qg.js")


def test_qg_script_has_no_credential_or_provider_path():
    src = (STATIC / "qg.js").read_text(encoding="utf-8")
    assert not re.search(r"OPENQUANTUM|client_secret|client_id|api[_-]?key|localStorage|sessionStorage", src, re.I)
    assert "innerHTML" not in src  # every value is set with textContent
    assert "eval(" not in src and "new Function" not in src
    # Only the read-only/local qg family is called.
    for path in re.findall(r"/api/[a-z0-9/_-]+", src):
        assert path.startswith("/api/qg/v1/"), path
    assert "STUDIO_NO_PROVIDER_SUBMISSION" in src and "spend_credits: 0" in src


def test_every_qg_tab_has_a_panel_function():
    src = (STATIC / "qg.js").read_text(encoding="utf-8")
    tabs = re.findall(r'\["([a-z]+)", "[A-Z][^"]+"\]', src.split("const TABS")[1].split("];")[0])
    assert len(tabs) == 8
    for tab in tabs:
        assert re.search(rf"function {tab}\(\)", src), tab
