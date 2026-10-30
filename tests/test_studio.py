"""HTTP and state tests for the local CQ-HECS Studio."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cqhecs.studio import StudioState, create_server

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def state():
    return StudioState(ROOT)


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
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}{path}", timeout=30) as response:
        return response.status, response.read()


def _post(server, path, payload):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_health_and_dataset_are_real(state):
    health = state.health()
    assert health["ok"] is True
    assert health["dataset"]["available"] is True
    assert health["dataset"]["jobs"] == 25
    assert health["model"]["id"] == "M-FIT-2"
    assert "P = NP" in " ".join(health["non_claims"])


def test_suite_has_twenty_five_jobs_and_tv_rows(state):
    suite = state.suite()
    assert len(suite["jobs"]) == 25
    assert all(job["qasm_sha256"] for job in suite["jobs"])
    evals = [job for job in suite["jobs"] if job["split"] == "EVAL"]
    assert len(evals) == 20
    assert all(job["tv_ideal"] is not None for job in evals)


def test_ideal_bell_is_exact(state):
    payload = state.simulate({"source": "preset:bell", "shots": 128, "seed": 7, "noise": "ideal"})
    assert payload["result"]["path"] == "A"
    assert payload["result"]["state"] == "EXACT"
    assert payload["num_qubits"] == 2
    assert {row["state"] for row in payload["outcomes"]} == {"00", "11"}


def test_noisy_bell_uses_mfit2(state):
    payload = state.simulate({"source": "preset:bell", "shots": 256, "seed": 7, "noise": "mfit2"})
    assert payload["result"]["state"] in ("CERTIFIED", "EXACT")
    assert sum(row["count"] for row in payload["outcomes"]) == 256
    assert payload["noise"]["mode"] == "mfit2"


def test_noise_comparison_prefers_mfit2_on_the_anomalous_ghz_job(state):
    payload = state.compare_noise({"job_id": "OQ-09"})
    assert payload["models"]["M-FIT-2"]["tv"] < payload["models"]["M-FIT"]["tv"]
    assert payload["models"]["measured"]["tv"] == 0.0


def test_sat_solve_and_sweep(state):
    sat = state.sat_solve({"cnf": "p cnf 2 2\n1 0\n-1 2 0\n", "timeout": 2})
    assert sat["result"]["status"] == "SAT"
    assert sat["result"]["model_verified"] is True
    sweep = state.sat_sweep({"sizes": [6], "ratios": [4.0], "trials": 1, "timeout": 1})
    assert len(sweep["rows"]) == 1
    assert "not a proof" in sweep["non_claim"]


def test_noise_override_and_node_budget(state):
    payload = state.compare_noise({"job_id": "OQ-09", "overrides": {"cx_depolarizing": 0.0}})
    assert "custom" in payload["models"]
    assert payload["models"]["custom"]["tv"] >= 0.0
    cnf = (ROOT / "benchmarks/sat/pigeonhole_6_5.cnf").read_text("utf-8")
    unknown = state.sat_solve({"cnf": cnf, "timeout": 5, "node_budget": 5})
    assert unknown["result"]["status"] == "UNKNOWN"
    assert "node budget" in unknown["result"]["note"]


def test_bad_input_is_refused_not_approximated(state):
    from cqhecs.studio.app import StudioError

    with pytest.raises(StudioError):
        state.simulate({"source": "not a circuit"})
    with pytest.raises(StudioError):
        state.simulate({"source": "preset:does-not-exist"})
    with pytest.raises(StudioError):
        state.compare_noise({"job_id": "OQ-99"})
    with pytest.raises(StudioError):
        state.sat_sweep({"sizes": [999], "ratios": [4.0], "trials": 1})


def test_http_surface(server):
    status, body = _get(server, "/")
    assert status == 200
    assert b"CQ-HECS Studio" in body
    status, body = _get(server, "/api/health")
    assert status == 200
    assert json.loads(body)["name"] == "CQ-HECS Studio"
    status, payload = _post(server, "/api/simulate", {"source": "preset:bell", "shots": 32})
    assert status == 200
    assert payload["num_qubits"] == 2
    status, payload = _post(server, "/api/sat/solve", {"cnf": "p cnf 1 1\n1 0\n", "timeout": 1})
    assert status == 200 and payload["result"]["status"] == "SAT"
    status, payload = _post(server, "/api/nope", {})
    assert status == 404
    status, body = _get(server, "/static/style.css")
    assert status == 200 and b"--cyan" in body
