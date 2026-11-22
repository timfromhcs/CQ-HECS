"""W4-03: the ExecutionPlan is the same document on every surface.

Python service, ``cq-hecs plan``, MCP ``cqhecs_plan`` and Studio ``/api/plan`` share one
implementation (``cqhecs.service``). Each surface wraps the plan in its own envelope; those
envelope keys are the only allowed differences (ALLOWED_ENVELOPE). The plan itself, including its
digest, must be byte-identical.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cqhecs import service
from cqhecs.cli import main as cli_main
from cqhecs.mcp_server import handle
from cqhecs.studio import StudioState

ROOT = Path(__file__).resolve().parent.parent

#: envelope keys per surface that are not part of the plan document.
ALLOWED_ENVELOPE = {
    "cli": {"schema_version", "version"},
    "studio": {"schema_version"},
}

CORPUS = [
    {"source": "preset:bell"},
    {"source": "preset:ghz8"},
    {"source": "preset:low_t_rank4"},
    {"source": "preset:qft4", "path": "A"},
    {"source": "preset:bell", "path": "C"},
    {"source": "preset:bell", "require_counts": True},
]


def _cli(capsys, case):
    argv = ["--format", "json", "plan", case["source"]]
    if case.get("path"):
        argv += ["--force-path", case["path"]]
    if case.get("require_counts"):
        argv.append("--require-counts")
    assert cli_main(argv) == 0
    document = json.loads(capsys.readouterr().out)
    assert set(document) - {"plan"} <= ALLOWED_ENVELOPE["cli"]
    return document["plan"]


def _mcp(case):
    args = {"circuit": case["source"]}
    if case.get("path"):
        args["force_path"] = case["path"]
    if case.get("require_counts"):
        args["require_counts"] = True
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "cqhecs_plan", "arguments": args}})
    assert "error" not in response and not response["result"].get("isError")
    return json.loads(response["result"]["content"][0]["text"])


def _studio(case):
    document = StudioState(ROOT).plan(case)
    assert set(document) - {"plan"} <= ALLOWED_ENVELOPE["studio"]
    return document["plan"]


@pytest.mark.parametrize("case", CORPUS, ids=lambda c: json.dumps(c, sort_keys=True))
def test_plan_is_identical_on_every_surface(case, capsys):
    expected = service.plan_document(
        case["source"], force_path=case.get("path"), require_counts=case.get("require_counts", False)
    )
    assert _cli(capsys, case) == expected
    assert _mcp(case) == expected
    assert _studio(case) == expected


def test_invalid_path_is_a_typed_error_on_every_surface(capsys):
    with pytest.raises(service.ServiceError) as err:
        service.plan_document("preset:bell", force_path="Z")
    assert err.value.code == "invalid_path"
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "cqhecs_plan",
                                  "arguments": {"circuit": "preset:bell", "force_path": "Z"}}})
    assert response["error"]["code"] == -32602
    from cqhecs.studio.app import StudioError

    with pytest.raises(StudioError) as studio_err:
        StudioState(ROOT).plan({"source": "preset:bell", "path": "Z"})
    assert studio_err.value.code == "invalid_path"


def test_unknown_preset_is_typed():
    with pytest.raises(service.ServiceError) as err:
        service.resolve_circuit_source("preset:no-such-circuit")
    assert err.value.code == "unknown_preset"


def test_cli_text_mode_prints_the_explanation(capsys):
    assert cli_main(["plan", "name:bell"]) == 0
    assert "Selected path" in capsys.readouterr().out
