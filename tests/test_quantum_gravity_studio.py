"""Studio `/api/qg/v1/*` routes: local-only, credential-free Quantum Gravity endpoints."""

from __future__ import annotations

import json
import math
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cqhecs.studio import StudioState, create_server

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def server():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _get(server, path):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}",
        headers={"Authorization": f"Bearer {server.token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def _post(server, path, payload):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {server.token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_state_qg_health_catalog_models():
    state = StudioState(ROOT)
    health = state.qg_health()
    assert health["ok"] is True
    assert health["campaign"] == "qg-2026-01"
    assert health["network"] == "local-only"
    assert "OPENQUANTUM_QPU" in health["execution_surfaces"]

    catalog = state.qg_catalog()
    assert catalog["schema"] == "cqhecs.qg.catalog.v1"

    models = state.qg_models()
    assert models["bmv"]["model_id"] == "qg.bmv.zz.v1"
    assert models["syk"]["model_id"] == "qg.syk.q4.v1"


def test_state_run_local_matches_oracle():
    state = StudioState(ROOT)
    payload = state.qg_run_local({"theta": math.pi / 2})
    assert payload["status"] == "COMPLETED"
    assert payload["execution_surface"] == "CLASSICAL_REFERENCE"
    assert abs(payload["observables"]["concurrence"] - 1.0) < 1e-9
    assert abs(sum(payload["probabilities"].values()) - 1.0) < 1e-12


def test_state_run_local_rejects_out_of_range():
    from cqhecs.studio.app import StudioError

    state = StudioState(ROOT)
    with pytest.raises(StudioError):
        state.qg_run_local({"theta": 1e9})


def test_http_qg_routes(server):
    status, health = _get(server, "/api/qg/v1/health")
    assert status == 200 and health["ok"] is True

    status, catalog = _get(server, "/api/qg/v1/catalog")
    assert status == 200 and catalog["schema"] == "cqhecs.qg.catalog.v1"

    status, models = _get(server, "/api/qg/v1/models")
    assert status == 200 and "bmv" in models

    status, preview = _post(server, "/api/qg/v1/experiments/preview", {"theta": 0.5})
    assert status == 200
    assert preview["spend_credits"] == 0.0
    assert preview["network"] == "none"
    assert preview["qasm_sha256"]

    status, run = _post(server, "/api/qg/v1/experiments/run-local", {"theta": 0.0})
    assert status == 200 and run["status"] == "COMPLETED"
    assert run["observables"]["concurrence"] < 1e-12

    status, validated = _post(server, "/api/qg/v1/experiments/validate", {"theta": 0.25})
    assert status == 200 and validated["status"] == "OK"


def test_http_qg_invalid_request_is_refused(server):
    status, body = _post(server, "/api/qg/v1/experiments/run-local", {"theta": "not-a-number"})
    assert status == 400
    assert body["error"]["code"] == "invalid_request"
