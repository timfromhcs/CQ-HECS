"""Studio ExecutionPlan panel: static contract checks plus a real-browser run (Chromium from web/node_modules)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cqhecs.studio import create_server
from cqhecs.studio.app import launch_url

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "cqhecs" / "studio" / "static"
E2E = ROOT / "tests" / "studio_ui_e2e.mjs"


def _plan_source() -> str:
    src = (STATIC / "app.js").read_text(encoding="utf-8")
    start = src.index("/* -------------------------------------------------------------------- plan */")
    end = src.index("function renderCircuit(payload)")
    return src[start:end]


def test_plan_panel_is_in_the_circuit_view():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="plan-panel"' in html and 'id="plan-run"' in html and 'id="plan-output"' in html
    view = html.split('id="view-circuit"')[1].split('id="view-noise"')[0]
    assert 'id="plan-panel"' in view
    assert "ESTIMATES" in html  # the panel says the figures are estimates before any plan exists


def test_plan_code_uses_the_plan_route_and_text_content_only():
    code = _plan_source()
    assert set(re.findall(r"/api/[a-z0-9/_-]+", code)) == {"/api/plan"}
    assert "innerHTML" not in code and "insertAdjacentHTML" not in code and "outerHTML" not in code
    assert "document.write" not in code and "eval(" not in code and "new Function" not in code
    assert not re.search(r"localStorage|sessionStorage|document\.cookie", code)
    assert not re.search(r"OPENQUANTUM|client_secret|api[_-]?key|password", code, re.I)
    # The bearer flow is the shared api() helper; the panel never touches the token itself.
    assert "AUTH_TOKEN" not in code and "Authorization" not in code
    assert code.count("ESTIMATE") >= 4
    assert "plan.refusal" in code and '"alert"' in code


def test_plan_static_assets_carry_no_secrets():
    for name in ("app.js", "index.html", "style.css", "qg.js"):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"Bearer [A-Za-z0-9_-]{20,}|BEGIN (RSA |EC )?PRIVATE KEY|sk-[A-Za-z0-9]{20,}", text), name


def test_plan_panel_controls_are_native_and_keyboard_reachable():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<button class="primary" id="plan-run" type="button">' in html
    assert 'tabindex="0"' in html.split('id="plan-output"')[1].split(">")[0]


def _node() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    for pkg in ("@playwright/test", "@axe-core/playwright"):
        if not (ROOT / "web" / "node_modules" / pkg).is_dir():
            return None
    return node


@pytest.mark.skipif(_node() is None, reason="node or web/node_modules (Playwright, axe) not installed: NOT_RUN")
def test_plan_panel_and_qg_tab_keyboard_in_real_browser():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        proc = subprocess.run(
            [_node(), str(E2E), launch_url(httpd)], cwd=str(ROOT), capture_output=True, text=True, timeout=240, check=False,
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
        assert lines, f"no result line; stdout={proc.stdout[-500:]!r} stderr={proc.stderr[-800:]!r}"
        result = json.loads(lines[-1])
        assert result["ok"], result["failures"]
        assert result["checks"] >= 30
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_plan_route_needs_the_bearer_token():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{httpd.server_address[1]}/api/plan",
            data=b'{"source": "preset:bell"}', method="POST", headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(request, timeout=10)
        assert err.value.code in (401, 403)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
