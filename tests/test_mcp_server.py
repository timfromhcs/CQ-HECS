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


def test_unknown_tool_is_invalid_params():
    (response,) = _session([
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "does_not_exist", "arguments": {}}},
    ])
    assert response["error"]["code"] == -32602


def test_missing_required_argument_is_invalid_params():
    (response,) = _session([
        {"jsonrpc": "2.0", "id": 51, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve", "arguments": {}}},
    ])
    assert response["error"]["code"] == -32602
    assert "cnf" in response["error"]["message"]


def test_a_tool_that_fails_returns_iserror_not_a_transport_error():
    (response,) = _session([
        {"jsonrpc": "2.0", "id": 52, "method": "tools/call",
         "params": {"name": "cqhecs_analyze", "arguments": {"circuit": "this is not a circuit"}}},
    ])
    assert "error" not in response
    assert response["result"]["isError"] is True
    assert response["result"]["content"][0]["type"] == "text"


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


def test_devices_tool_and_device_noise_run():
    devices, run = _session([
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "cqhecs_devices", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
         "params": {"name": "cqhecs_run",
                    "arguments": {"circuit": "preset:bell", "shots": 2000, "noise": "device:ibm_fez"}}},
    ])
    ids = {d["id"] for d in json.loads(devices["result"]["content"][0]["text"])["devices"]}
    assert "ibm_fez" in ids
    payload = json.loads(run["result"]["content"][0]["text"])
    assert sum(payload["result"]["counts"].values()) == 2000


def test_sat_count_tool_and_certification():
    counted, solved = _session([
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
         "params": {"name": "cqhecs_sat_count", "arguments": {"cnf": "p cnf 4 1\n1 2 0\n"}}},
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve", "arguments": {"cnf": "p cnf 1 2\n1 0\n-1 0\n"}}},
    ])
    assert json.loads(counted["result"]["content"][0]["text"])["result"]["count"] == "12"
    result = json.loads(solved["result"]["content"][0]["text"])["result"]
    assert result["certification"] == "TREE_RESOLUTION_CHECKED" and result["contract_version"] == "1.2"


def test_sat_solve_tool_with_the_watched_engine():
    (reply,) = _session([
        {"jsonrpc": "2.0", "id": 13, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve",
                    "arguments": {"cnf": "p cnf 2 4\n1 2 0\n-1 2 0\n1 -2 0\n-1 -2 0\n",
                                  "engine": "watched"}}},
    ])
    data = json.loads(reply["result"]["content"][0]["text"])
    assert data["result"]["status"] == "UNSAT"
    assert data["result"]["certification"] == "TREE_RESOLUTION_CHECKED"
    assert data["result"]["engine"] == "dpll-watched"


def test_sat_solve_tool_with_the_omniwave_engine():
    (reply,) = _session([
        {"jsonrpc": "2.0", "id": 12, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve",
                    "arguments": {"cnf": "p cnf 2 4\n1 2 0\n-1 2 0\n1 -2 0\n-1 -2 0\n", "engine": "omniwave"}}},
    ])
    data = json.loads(reply["result"]["content"][0]["text"])
    assert data["result"]["status"] == "UNSAT" and data["result"]["certification"] == "DRAT_CHECKED"
    assert data["result"]["engine"] == "omniwave" and data["omniwave"]["covered"] == 1.0


def test_out_of_range_timeout_is_refused_not_run_unbounded():
    (reply,) = _session([
        {"jsonrpc": "2.0", "id": 20, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve", "arguments": {"cnf": "p cnf 1 1\n1 0\n", "timeout": 1e9}}},
    ])
    assert "error" in reply and "timeout" in reply["error"]["message"]


def test_out_of_range_omniwave_shapes_are_refused():
    (reply,) = _session([
        {"jsonrpc": "2.0", "id": 21, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve",
                    "arguments": {"cnf": "p cnf 1 1\n1 0\n", "engine": "omniwave", "waves": 9999}}},
    ])
    assert "error" in reply and "waves" in reply["error"]["message"]


def test_out_of_range_models_limit_is_refused():
    (reply,) = _session([
        {"jsonrpc": "2.0", "id": 22, "method": "tools/call",
         "params": {"name": "cqhecs_sat_models", "arguments": {"cnf": "p cnf 1 1\n1 0\n", "limit": 0}}},
    ])
    assert "error" in reply and "limit" in reply["error"]["message"]


def test_an_in_range_timeout_is_still_accepted():
    (reply,) = _session([
        {"jsonrpc": "2.0", "id": 23, "method": "tools/call",
         "params": {"name": "cqhecs_sat_solve", "arguments": {"cnf": "p cnf 1 1\n1 0\n", "timeout": 2.0}}},
    ])
    assert json.loads(reply["result"]["content"][0]["text"])["result"]["status"] == "SAT"


def test_qg_tools_are_local_and_correct():
    catalog, preview, run = _session([
        {"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {"name": "cqhecs_qg_catalog", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {"name": "cqhecs_qg_circuit_preview", "arguments": {"theta": 0.5}}},
        {"jsonrpc": "2.0", "id": 16, "method": "tools/call", "params": {"name": "cqhecs_qg_run_local", "arguments": {"theta": 1.5707963267948966}}},
    ])
    cat = json.loads(catalog["result"]["content"][0]["text"])
    assert cat["schema"] == "cqhecs.qg.catalog.v1"
    prev = json.loads(preview["result"]["content"][0]["text"])
    assert prev["spend_credits"] == 0.0 and prev["network"] == "none" and prev["qasm_sha256"]
    local = json.loads(run["result"]["content"][0]["text"])
    assert local["execution_surface"] == "CLASSICAL_REFERENCE"
    assert abs(local["observables"]["concurrence"] - 1.0) < 1e-9
