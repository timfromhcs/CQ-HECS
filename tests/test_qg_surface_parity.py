"""W12 / T6-01 / QGRAVITY 9.1-9.2: the QG plan envelope is one document on every surface.

Python service, ``cq-hecs qg plan``, MCP ``cqhecs_qg_plan`` and Studio ``/api/qg/v1/experiments/plan``
must return the same envelope dict and the same digest. The rest of the file checks the local QG API
and MCP surface: bounded, typed, quote/submit split, no network in the local path, one spend ledger.
"""
from __future__ import annotations

import ast
import hashlib
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cqhecs import service
from cqhecs.cli import main as cli_main
from cqhecs.mcp_server import TOOLS, handle
from cqhecs.studio import StudioState, create_server
from cqhecs.studio.app import StudioError

ROOT = Path(__file__).resolve().parent.parent

CORPUS = [
    {"experiment": "bmv", "theta": 0.7},
    {"experiment": "bmv", "theta": 1.5707963267948966},
    {"experiment": "syk", "n": 4, "seed": 20260101, "scale": 0.5, "t": 1.0, "steps": 2},
    {"experiment": "gauge", "rows": 1, "cols": 1, "t": 0.5, "steps": 1},
    {"experiment": "bmv", "theta": 0.7, "force_path": "C"},
    {"experiment": "syk", "n": 4, "force_path": "D"},  # forced Path D cannot give counts -> refusal, not reroute
]
PARAM_KEYS = ("theta", "n", "seed", "scale", "t", "steps", "rows", "cols")


def _service(case):
    params = {k: case[k] for k in PARAM_KEYS if k in case}
    return service.qg_plan_document(case["experiment"], params, force_path=case.get("force_path"))


def _cli(capsys, case):
    argv = ["--format", "json", "qg", "plan", "--experiment", case["experiment"]]
    for key in PARAM_KEYS:
        if key in case:
            argv += [f"--{key}", str(case[key])]
    if case.get("force_path"):
        argv += ["--force-path", case["force_path"]]
    assert cli_main(argv) == 0
    document = json.loads(capsys.readouterr().out)
    assert set(document) - {"qg_plan", "digest", "parameters"} == {"schema_version"}
    document.pop("schema_version")
    return document


def _mcp(case):
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "cqhecs_qg_plan", "arguments": dict(case)}})
    assert "error" not in response and not response["result"].get("isError"), response
    return json.loads(response["result"]["content"][0]["text"])


def _studio(case):
    request = {k: v for k, v in case.items() if k != "force_path"}
    if case.get("force_path"):
        request["path"] = case["force_path"]
    document = StudioState(ROOT).qg_plan(request)
    assert set(document) - {"qg_plan", "digest", "parameters"} == {"schema_version"}
    document.pop("schema_version")
    return document


@pytest.mark.parametrize("case", CORPUS, ids=lambda c: json.dumps(c, sort_keys=True))
def test_qg_plan_is_identical_on_every_surface(case, capsys):
    expected = _service(case)
    assert _cli(capsys, case) == expected
    assert _mcp(case) == expected
    assert _studio(case) == expected
    assert len(expected["digest"]) == 64
    assert expected["qg_plan"]["physical_execution"] is False


def test_the_digest_is_the_digest_of_the_embedded_envelope():
    document = _service(CORPUS[0])
    canonical = json.dumps(document["qg_plan"], sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == document["digest"]


def test_the_forced_path_d_refusal_is_a_refusal_not_a_reroute():
    document = _service(CORPUS[-1])
    assert document["qg_plan"]["engine"] is None
    assert document["qg_plan"]["would_execute"] is False


@pytest.mark.parametrize("bad", [
    {"experiment": "bmv", "theta": 7.0},
    {"experiment": "bmv", "theta": float("nan")},
    {"experiment": "bmv", "theta": True},
    {"experiment": "syk", "n": 99},
    {"experiment": "syk", "steps": 0},
    {"experiment": "gauge", "rows": 4, "cols": 4},  # inside the range, over the dense link ceiling
    {"experiment": "bmv", "bogus": 1},
])
def test_bad_parameters_are_typed_refusals_on_every_surface(bad):
    params = {k: v for k, v in bad.items() if k != "experiment"}
    with pytest.raises(service.ServiceError) as err:
        service.qg_plan_document(bad["experiment"], params)
    code = err.value.code
    assert code in {"invalid_parameter", "resource_limit"}
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "cqhecs_qg_plan", "arguments": dict(bad)}})
    assert response["error"]["code"] == -32602 and code in response["error"]["message"]
    with pytest.raises(StudioError) as studio_err:
        StudioState(ROOT).qg_plan(dict(bad))
    assert studio_err.value.code == code


def test_unknown_experiment_is_typed():
    with pytest.raises(service.ServiceError) as err:
        service.qg_plan_document("loop-quantum-gravity")
    assert err.value.code == "unknown_experiment" and err.value.status == 404


def test_cli_rejects_out_of_range_without_a_traceback(capsys):
    assert cli_main(["qg", "plan", "--experiment", "bmv", "--theta", "99"]) != 0
    assert "Traceback" not in capsys.readouterr().err


# --- 9.1 local API over HTTP ------------------------------------------------------------------

@pytest.fixture(scope="module")
def server():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _http(server, method, path, payload=None, *, token=True):
    headers = {"Authorization": f"Bearer {server.token}"} if token else {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_http_plan_route_returns_the_same_document(server):
    status, body = _http(server, "POST", "/api/qg/v1/experiments/plan", {"experiment": "bmv", "theta": 0.7})
    assert status == 200
    body.pop("schema_version")
    assert body == _service(CORPUS[0])


def test_http_plan_requires_the_token(server):
    status, _ = _http(server, "POST", "/api/qg/v1/experiments/plan", {"experiment": "bmv"}, token=False)
    assert status == 401


def test_http_plan_bad_parameter_is_a_typed_400(server):
    status, body = _http(server, "POST", "/api/qg/v1/experiments/plan", {"experiment": "bmv", "theta": 50})
    assert status == 400 and body["error"]["code"] == "invalid_parameter"


@pytest.mark.parametrize("path", [
    "/api/qg/v1/experiments", "/api/qg/v1/backends", "/api/qg/v1/evidence/bmv",
    "/api/qg/v1/evidence/syk", "/api/qg/v1/evidence/gauge",
    "/api/qg/v1/exports/bmv?theta=0.5", "/api/qg/v1/exports/syk", "/api/qg/v1/exports/gauge",
])
def test_http_get_routes_are_served(server, path):
    status, body = _http(server, "GET", path)
    assert status == 200, body
    assert "OPENQUANTUM_CLIENT_SECRET" not in json.dumps(body)


def test_http_experiments_and_backends_describe_ranges_and_availability(server):
    _, experiments = _http(server, "GET", "/api/qg/v1/experiments")
    assert {e["experiment_id"] for e in experiments["experiments"]} == {"bmv", "syk", "gauge"}
    _, backends = _http(server, "GET", "/api/qg/v1/backends")
    by_surface = {b["surface"]: b["status"] for b in backends["backends"]}
    assert by_surface["OPENQUANTUM_QPU"] == "UNAVAILABLE" and by_surface["CLASSICAL_REFERENCE"] == "AVAILABLE"
    assert isinstance(backends["credentials_present"], bool)


def test_http_unknown_experiment_and_bad_export_params_are_typed(server):
    status, body = _http(server, "GET", "/api/qg/v1/evidence/bogus")
    assert status == 404 and body["error"]["code"] == "unknown_experiment"
    status, body = _http(server, "GET", "/api/qg/v1/exports/bmv?theta=abc")
    assert status == 400 and body["error"]["code"] == "invalid_parameter"
    status, body = _http(server, "GET", "/api/qg/v1/exports/bmv?nope=1")
    assert status == 400 and body["error"]["code"] == "invalid_parameter"


def test_http_compare_keeps_provenance_separate_and_never_mixes_qpu(server):
    status, body = _http(server, "POST", "/api/qg/v1/experiments/compare", {"theta": 0.7, "shots": 256})
    assert status == 200
    sources = body["sources"]
    assert sources["reference"]["surface"] == "CLASSICAL_REFERENCE"
    assert sources["cq_hecs"]["surface"] == "CQ_HECS_CPU"
    assert sources["openquantum_qpu"]["status"] == "NOT_COMPARED"
    assert body["total_variation_reference_vs_cq_hecs"] is not None
    assert body["spend_credits"] == 0.0 and body["network"] == "none"


LEDGER_FILES = ("JOB_LEDGER.jsonl", "QUOTE_LEDGER.json")


def _ledger_state():
    state = {}
    for name in LEDGER_FILES:
        path = ROOT / "research" / "qg_2026" / name
        state[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return state


@pytest.mark.parametrize("method,path,payload", [
    ("POST", "/api/qg/v1/openquantum/quote", {"experiment": "bmv"}),
    ("POST", "/api/qg/v1/openquantum/submit", {"preparation_id": "x", "paid": True}),
    ("GET", "/api/qg/v1/openquantum/jobs/abc", None),
    ("GET", "/api/qg/v1/openquantum/jobs/abc/results", None),
])
def test_http_paid_routes_are_typed_403_and_touch_no_ledger(server, method, path, payload):
    before = _ledger_state()
    status, body = _http(server, method, path, payload)
    assert status == 403
    assert body["error"]["code"] == "qg_paid_path_unavailable"
    assert body["status"] == "UNAVAILABLE" and body["spend_credits"] == 0.0 and body["network"] == "none"
    assert _ledger_state() == before


# --- 9.2 MCP -----------------------------------------------------------------------------------

def test_mcp_paid_tools_exist_as_separate_quote_and_submit_and_never_a_run_paid():
    names = {t["name"] for t in TOOLS}
    assert {"cqhecs_qg_openquantum_quote", "cqhecs_qg_openquantum_submit"} <= names
    assert not any("run_paid" in n or n.endswith("openquantum_run") for n in names)


def test_mcp_qg_tool_names_cover_the_contract():
    names = {t["name"] for t in TOOLS}
    required = {
        "cqhecs_qg_catalog", "cqhecs_qg_model_validate", "cqhecs_qg_circuit_preview", "cqhecs_qg_run_local",
        "cqhecs_qg_compare", "cqhecs_qg_export", "cqhecs_qg_plan",
        "cqhecs_qg_openquantum_discover", "cqhecs_qg_openquantum_quote", "cqhecs_qg_openquantum_submit",
        "cqhecs_qg_openquantum_status", "cqhecs_qg_openquantum_results",
    }
    assert required <= names


def test_mcp_qg_tools_cap_their_inputs_in_the_schema():
    by_name = {t["name"]: t for t in TOOLS}
    for name in ("cqhecs_qg_plan", "cqhecs_qg_export"):
        props = by_name[name]["inputSchema"]["properties"]
        assert props["steps"]["maximum"] == service.QG_MAX_STEPS and props["n"]["maximum"] == 8
        assert props["theta"]["maximum"] == service.QG_THETA_BOUND
    assert by_name["cqhecs_qg_compare"]["inputSchema"]["properties"]["shots"]["maximum"] == 20000


def _call(name, arguments):
    return handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments}})


@pytest.mark.parametrize("name,args", [
    ("cqhecs_qg_model_validate", {"experiment": "syk", "n": 99}),
    ("cqhecs_qg_compare", {"theta": 99}),
    ("cqhecs_qg_compare", {"theta": 0.5, "shots": 10**9}),
    ("cqhecs_qg_export", {"experiment": "gauge", "rows": 4, "cols": 4}),
])
def test_mcp_qg_tools_reject_out_of_range_input_with_32602(name, args):
    assert _call(name, args)["error"]["code"] == -32602


def test_mcp_validate_and_export_are_secret_free_and_digested():
    export = json.loads(_call("cqhecs_qg_export", {"experiment": "bmv", "theta": 0.5})["result"]["content"][0]["text"])
    assert len(export["bundle_sha256"]) == 64 and export["qg_plan_digest"] == _service(
        {"experiment": "bmv", "theta": 0.5})["digest"]
    text = json.dumps(export).lower()
    assert "secret" not in text and "token" not in text and "password" not in text
    validate = json.loads(_call("cqhecs_qg_model_validate", {"experiment": "gauge"})["result"]["content"][0]["text"])
    assert validate["status"] == "OK" and validate["model"]


# --- no network in the local path; one spend ledger ---------------------------------------------

LOCAL_FILES = ("cqhecs/service.py", "cqhecs/mcp_server.py", "cqhecs/studio/app.py", "cqhecs/cli.py")
FORBIDDEN_MODULES = {"socket", "requests", "httpx", "aiohttp", "http.client", "urllib.request", "ssl", "openquantum"}


def _imports(path):
    tree = ast.parse((ROOT / path).read_text("utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


@pytest.mark.parametrize("path", LOCAL_FILES)
def test_local_surfaces_import_no_network_or_provider_module(path):
    bad = {m for m in _imports(path) if m in FORBIDDEN_MODULES or m.split(".")[0] in {"openquantum", "requests", "httpx"}}
    assert not bad, f"{path} imports {sorted(bad)}"


def test_local_surfaces_never_write_the_spend_ledger():
    for path in LOCAL_FILES:
        text = (ROOT / path).read_text("utf-8")
        for line in text.splitlines():
            if "JOB_LEDGER" in line or "QUOTE_LEDGER" in line:
                assert "write" not in line and "open(" not in line and "append" not in line, (path, line)


def test_the_paid_refusal_names_the_single_ledger_writer():
    doc = service.qg_paid_refusal("quote")
    assert doc["spend_ledger"].endswith("JOB_LEDGER.jsonl")
    assert "run_qg_openquantum_campaign.py" in doc["ledger_writer"]
    with pytest.raises(service.ServiceError):
        service.qg_paid_refusal("run_paid_job")
