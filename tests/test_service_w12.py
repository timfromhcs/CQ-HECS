"""W12: analyze --explain and diagnostics run on the shared service."""
from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import pytest

from cqhecs import service
from cqhecs.cli import main as cli_main
from cqhecs.studio import create_server

ROOT = Path(__file__).resolve().parent.parent


def test_analyze_json_is_the_service_document(capsys):
    assert cli_main(["--format", "json", "analyze", "name:ghz8", "--explain"]) == 0
    cli = json.loads(capsys.readouterr().out)
    from cqhecs.circuit_library import build_builtin_circuit

    expected = service.analysis_document(build_builtin_circuit("ghz8"), explain=True)
    assert cli["analysis"] == expected["analysis"] and cli["plan"] == expected["plan"]
    assert set(cli) == {"schema_version", "version", "analysis", "plan"}


def test_analyze_uses_the_service_and_not_a_private_planner(monkeypatch, capsys):
    calls = []
    real = service.analysis_document

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(service, "analysis_document", spy)
    assert cli_main(["--format", "json", "analyze", "name:bell", "--explain"]) == 0
    capsys.readouterr()
    assert len(calls) == 1 and calls[0]["explain"] is True


def test_analyze_without_explain_has_no_plan(capsys):
    assert cli_main(["--format", "json", "analyze", "name:bell"]) == 0
    assert "plan" not in json.loads(capsys.readouterr().out)


def test_analyze_planning_options_imply_a_plan_and_a_forced_refusal_stays_a_refusal(capsys):
    assert cli_main(["--format", "json", "analyze", "name:bell", "--force-path", "D", "--require-counts"]) == 0
    plan = json.loads(capsys.readouterr().out)["plan"]
    assert plan["would_execute"] is False and plan["refusal"]["code"]


def test_analyze_text_mode_still_prints_the_explanation(capsys):
    assert cli_main(["analyze", "name:bell", "--explain"]) == 0
    out = capsys.readouterr().out
    assert "Recommended" in out and "Selected path" in out


def test_doctor_cli_and_service_agree(capsys):
    report = service.doctor_report("1.0")
    assert cli_main(["--format", "json", "doctor"]) in (0, 3, 4, 5)  # exit code reflects probe failures only
    cli = json.loads(capsys.readouterr().out)
    assert "failed" not in cli
    assert set(cli["components"]) == set(report["components"])
    assert cli["backends"] == report["backends"]
    assert any("not exercised" in n or "No statement" in n for n in report["notes"])


@pytest.fixture(scope="module")
def server():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def test_studio_diagnostics_route_serves_the_doctor_report_with_the_token(server):
    base = f"http://127.0.0.1:{server.server_address[1]}"
    request = urllib.request.Request(base + "/api/diagnostics", headers={"Authorization": f"Bearer {server.token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read())
    assert {"vulkan_loader", "native_binding", "numpy"} <= set(body["components"])
    assert set(body["backends"]) == {"A", "B", "C", "D"}
    # the /api/v1 alias reaches the same handler
    alias = urllib.request.Request(base + "/api/v1/diagnostics", headers={"Authorization": f"Bearer {server.token}"})
    with urllib.request.urlopen(alias, timeout=60) as response:
        assert set(json.loads(response.read())["components"]) == set(body["components"])
    bare = urllib.request.Request(base + "/api/diagnostics")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(bare, timeout=10)
    assert err.value.code == 401
