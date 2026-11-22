"""W4-06: doctor reports the optional SAT solver, and the Studio token can be supplied.

``doctor`` must name the optional solver (python-sat / CaDiCaL) instead of omitting it.
The Studio bearer token can come from ``CQ_HECS_STUDIO_TOKEN`` or
``CQ_HECS_STUDIO_TOKEN_FILE`` (never a CLI argument, so it does not appear in a process
listing); a caller-supplied token is not embedded in the printed launch URL.
"""
import argparse
import json

from cqhecs import cli
from cqhecs.studio import app as studio_app


def test_doctor_reports_the_optional_sat_solver(capsys):
    cli.cmd_doctor(argparse.Namespace(format="json"))
    report = json.loads(capsys.readouterr().out)
    component = report["components"].get("sat_solver")
    assert component is not None
    assert component["status"] in ("available", "not_available", "failed")


def test_studio_token_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("CQ_HECS_STUDIO_TOKEN", "env-token-123")
    monkeypatch.delenv("CQ_HECS_STUDIO_TOKEN_FILE", raising=False)
    server = studio_app.create_server(port=0)
    try:
        assert server.token == "env-token-123"
        assert server.token_ephemeral is False
        assert "#token=" not in studio_app.launch_url(server)
    finally:
        server.server_close()


def test_studio_token_comes_from_a_file(monkeypatch, tmp_path):
    token_file = tmp_path / "studio.token"
    token_file.write_text("file-token-456\n", encoding="utf-8")
    monkeypatch.delenv("CQ_HECS_STUDIO_TOKEN", raising=False)
    monkeypatch.setenv("CQ_HECS_STUDIO_TOKEN_FILE", str(token_file))
    server = studio_app.create_server(port=0)
    try:
        assert server.token == "file-token-456"
        assert server.token_ephemeral is False
    finally:
        server.server_close()


def test_an_empty_token_file_is_refused(monkeypatch, tmp_path):
    token_file = tmp_path / "empty.token"
    token_file.write_text("\n", encoding="utf-8")
    monkeypatch.delenv("CQ_HECS_STUDIO_TOKEN", raising=False)
    monkeypatch.setenv("CQ_HECS_STUDIO_TOKEN_FILE", str(token_file))
    try:
        studio_app.create_server(port=0)
    except studio_app.StudioError as exc:
        assert "empty" in str(exc)
    else:  # pragma: no cover - the guard must fire
        raise AssertionError("an empty token file must be refused")


def test_an_ephemeral_token_is_embedded_in_the_launch_url(monkeypatch):
    monkeypatch.delenv("CQ_HECS_STUDIO_TOKEN", raising=False)
    monkeypatch.delenv("CQ_HECS_STUDIO_TOKEN_FILE", raising=False)
    server = studio_app.create_server(port=0)
    try:
        assert server.token_ephemeral is True
        assert "#token=" in studio_app.launch_url(server)
    finally:
        server.server_close()
