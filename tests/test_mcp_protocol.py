"""W4-05: MCP protocol negotiation, tool annotations, outputSchema and structuredContent.

Field names follow the MCP 2025-06-18 server/tools text (title, annotations, outputSchema,
structuredContent). Legacy mode (2024-11-05, and any connection that never negotiates) keeps the old
shape exactly.
"""
from __future__ import annotations

import json

import pytest

from cqhecs import mcp_server
from cqhecs.mcp_server import _Session, handle


def _init(version):
    session = _Session()
    reply = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": version}}, session)
    return session, reply["result"]


def _tools(session):
    return handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)["result"]["tools"]


@pytest.mark.parametrize("requested,expected", [
    ("2025-06-18", "2025-06-18"),
    ("2025-03-26", "2025-03-26"),
    ("2024-11-05", "2024-11-05"),
    ("2030-01-01", "2025-06-18"),  # unknown/newer: the newest version this server supports
    ("garbage", "2025-06-18"),
])
def test_version_negotiation(requested, expected):
    session, result = _init(requested)
    assert result["protocolVersion"] == expected == session.version


def test_initialize_without_a_version_stays_legacy():
    session = _Session()
    reply = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, session)
    assert reply["result"]["protocolVersion"] == "2024-11-05"
    assert handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, session)["result"]["protocolVersion"] == "2024-11-05"


def test_legacy_mode_tool_shape_is_unchanged():
    session, _ = _init("2024-11-05")
    for tool in _tools(session):
        assert set(tool) == {"name", "description", "inputSchema"}
    reply = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "cqhecs_devices", "arguments": {}}}, session)
    assert "structuredContent" not in reply["result"]


def test_2025_03_26_adds_annotations_only():
    session, _ = _init("2025-03-26")
    for tool in _tools(session):
        assert "outputSchema" not in tool and "title" not in tool
        ann = tool["annotations"]
        assert ann["readOnlyHint"] is True and ann["destructiveHint"] is False
        assert ann["idempotentHint"] is True and ann["openWorldHint"] is False
        assert ann["title"]


def test_2025_06_18_adds_title_and_output_schema_for_every_tool():
    session, _ = _init("2025-06-18")
    tools = _tools(session)
    assert {t["name"] for t in tools} == {t["name"] for t in mcp_server.TOOLS}
    for tool in tools:
        assert tool["title"] and tool["outputSchema"]["type"] == "object"
        assert "annotations" in tool


SAMPLE_ARGS = {
    "cqhecs_run": {"circuit": "preset:bell", "shots": 16},
    "cqhecs_analyze": {"circuit": "preset:bell"},
    "cqhecs_plan": {"circuit": "preset:bell"},
    "cqhecs_sat_solve": {"cnf": "p cnf 1 1\n1 0\n"},
    "cqhecs_sat_count": {"cnf": "p cnf 2 1\n1 2 0\n"},
    "cqhecs_sat_models": {"cnf": "p cnf 2 1\n1 2 0\n"},
    "cqhecs_devices": {},
    "cqhecs_hardware": {},
    "cqhecs_qg_catalog": {},
    "cqhecs_qg_circuit_preview": {"theta": 0.5},
    "cqhecs_qg_run_local": {"theta": 0.5},
    "cqhecs_doctor": {},
    "cqhecs_qg_plan": {"experiment": "bmv", "theta": 0.5},
    "cqhecs_qg_model_validate": {"experiment": "bmv", "theta": 0.5},
    "cqhecs_qg_compare": {"theta": 0.5, "shots": 256},
    "cqhecs_qg_export": {"experiment": "bmv", "theta": 0.5},
}
#: Paid Open Quantum tools are typed refusals (isError) in this build, so they have no success sample.
PAID_TOOLS = {f"cqhecs_qg_openquantum_{a}" for a in ("discover", "quote", "submit", "status", "results")}


def test_every_tool_has_a_sample_so_the_next_test_cannot_miss_one():
    assert set(SAMPLE_ARGS) | PAID_TOOLS == {t["name"] for t in mcp_server.TOOLS}
    assert not set(SAMPLE_ARGS) & PAID_TOOLS


@pytest.mark.parametrize("name", sorted(PAID_TOOLS))
def test_paid_tools_are_typed_refusals_that_spend_nothing(name):
    session, _ = _init("2025-06-18")
    reply = handle({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                    "params": {"name": name, "arguments": {}}}, session)
    result = reply["result"]
    assert result["isError"] is True
    payload = result["structuredContent"]
    assert payload["status"] == "UNAVAILABLE" and payload["code"] == "QG_PAID_PATH_UNAVAILABLE"
    assert payload["spend_credits"] == 0.0 and payload["network"] == "none"


@pytest.mark.parametrize("name", sorted(SAMPLE_ARGS))
def test_structured_content_mirrors_text_and_satisfies_the_output_schema(name):
    session, _ = _init("2025-06-18")
    schema = {t["name"]: t["outputSchema"] for t in _tools(session)}[name]
    reply = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": name, "arguments": SAMPLE_ARGS[name]}}, session)
    result = reply["result"]
    assert not result.get("isError"), result
    structured = result["structuredContent"]
    assert json.loads(result["content"][0]["text"]) == structured  # text mirror
    for key in schema["required"]:
        assert key in structured, f"{name} lacks required {key!r}"
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(structured, schema)


def test_tool_errors_carry_no_structured_content_and_bad_arguments_stay_32602():
    session, _ = _init("2025-06-18")
    err = handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                  "params": {"name": "cqhecs_analyze", "arguments": {"circuit": "not a circuit"}}}, session)
    assert err["result"]["isError"] is True and "structuredContent" not in err["result"]
    bad = handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                  "params": {"name": "cqhecs_sat_solve", "arguments": {}}}, session)
    assert bad["error"]["code"] == -32602
    notobj = handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                     "params": {"name": "cqhecs_devices", "arguments": "x"}}, session)
    assert notobj["error"]["code"] == -32602
