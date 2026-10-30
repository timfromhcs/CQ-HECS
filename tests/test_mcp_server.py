"""Stdio MCP server contract tests (no network)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _session(messages):
    proc = subprocess.Popen(
        [sys.executable, "-m", "cqhecs.mcp_server"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        responses = []
        for message in messages:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            responses.append(json.loads(proc.stdout.readline()))
        return responses
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_initialize_and_tool_list():
    init, tools = _session([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ])
    assert init["result"]["serverInfo"]["name"] == "cq-hecs"
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert {"cqhecs_run", "cqhecs_sat_solve", "cqhecs_hardware"} <= names


def test_run_and_sat_tools_return_content():
    run, sat = _session([
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "cqhecs_run", "arguments": {"circuit": "preset:bell", "shots": 64}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve", "arguments": {"cnf": "p cnf 1 1\n1 0\n"}}},
    ])
    payload = json.loads(run["result"]["content"][0]["text"])
    assert payload["result"]["path"] == "A"
    sat_payload = json.loads(sat["result"]["content"][0]["text"])
    assert sat_payload["result"]["status"] == "SAT"
    assert sat_payload["result"]["model_verified"] is True


def test_unknown_tool_is_a_jsonrpc_error():
    (response,) = _session([
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "does_not_exist", "arguments": {}}},
    ])
    assert response["error"]["code"] == -32000


def test_sat_models_and_hardware_tools():
    models, hardware = _session([
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "cqhecs_sat_models",
                    "arguments": {"cnf": "p cnf 2 1\n1 2 0\n", "limit": 10}}},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "cqhecs_hardware", "arguments": {}}},
    ])
    enumerated = json.loads(models["result"]["content"][0]["text"])
    assert enumerated["status"] == "COMPLETE"
    assert enumerated["count"] == 3
    evidence = json.loads(hardware["result"]["content"][0]["text"])
    by_id = {row["id"]: row for row in evidence["datasets"]}
    for backend in ("ibm_fez", "ibm_kingston", "ibm_marrakesh"):
        row = by_id[f"r-ibm-1 / {backend} 10k"]
        assert row["shots"] == 10000
        assert row["verdict"] == "SUPPORTED"
