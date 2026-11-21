"""W4-04: the ExecutionPlan document is published as a JSON Schema.

The schema is the shared contract for the plan across Python, CLI, MCP and Studio. These
tests keep the schema and the live document in step: a field added or removed without the
schema fails, and (when ``jsonschema`` is installed) a real document validates.
"""
import json
from pathlib import Path

import pytest

from cqhecs.execution_plan import PLAN_SCHEMA_VERSION, build_execution_plan

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "schemas" / "execution_plan.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

CIRCUITS = [
    [("h", [0], []), ("cx", [0, 1], []), ("measure", [0], [])],
    [("h", [0], []), ("t", [0], []), ("cx", [0, 1], [])],
]


def test_schema_declares_exactly_the_plan_fields():
    document = build_execution_plan(CIRCUITS[0]).to_dict()
    assert set(document) == set(SCHEMA["properties"])
    assert set(SCHEMA["required"]) == set(document)


def test_the_schema_is_a_closed_json_schema():
    assert SCHEMA["$schema"].startswith("https://json-schema.org")
    assert SCHEMA["additionalProperties"] is False
    assert SCHEMA["properties"]["schema_version"]["const"] == PLAN_SCHEMA_VERSION


def test_a_forced_refusal_document_still_matches_the_schema():
    document = build_execution_plan(CIRCUITS[1], forced_path="A").to_dict()
    assert set(document) == set(SCHEMA["properties"])
    assert document["refusal"] is not None


@pytest.mark.parametrize("circuit", CIRCUITS)
def test_a_real_document_validates_when_jsonschema_is_available(circuit):
    jsonschema = pytest.importorskip("jsonschema")
    document = build_execution_plan(circuit).to_dict()
    jsonschema.validate(instance=document, schema=SCHEMA)


# ---------------------------------------------------------------------------
# W4-04: OpenAPI 3.1 for the Studio and the /api/v1 aliases
# ---------------------------------------------------------------------------
import re
import threading
import urllib.error
import urllib.request

from cqhecs.studio import create_server
from cqhecs.studio import app as studio_app
from cqhecs.studio.openapi import ROUTES, build_openapi

OPENAPI_PATH = ROOT / "schemas" / "studio.openapi.json"


def test_committed_openapi_equals_the_generated_document():
    assert json.loads(OPENAPI_PATH.read_text(encoding="utf-8")) == build_openapi()


def test_openapi_is_3_1_and_every_route_is_listed_under_both_prefixes():
    doc = build_openapi()
    assert doc["openapi"].startswith("3.1")
    for method, path, *_ in ROUTES:
        for prefix in ("/api", "/api/v1"):
            assert method in doc["paths"][prefix + path]
    assert doc["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"


def test_every_route_the_handler_serves_is_in_the_document():
    source = (ROOT / "cqhecs" / "studio" / "app.py").read_text(encoding="utf-8")
    served = set(re.findall(r'path == "(/api/(?!qg/)[^"]+)"', source))
    served |= {"/api/omniwave/{action}"} if 'startswith("/api/omniwave/")' in source else set()
    documented = {"/api" + path for _, path, *_ in ROUTES}
    assert served <= documented, sorted(served - documented)


def test_openapi_validates_when_the_validator_is_available():
    validator = pytest.importorskip("openapi_spec_validator", reason="optional")
    validator.validate(build_openapi())


@pytest.fixture(scope="module")
def studio():
    httpd = create_server(port=0, root=ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _request(server, method, path, body=None, token=True):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {server.token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def test_canonical_api_path_only_rewrites_the_v1_alias():
    assert studio_app.canonical_api_path("/api/v1/health") == "/api/health"
    assert studio_app.canonical_api_path("/api/v1/sat/solve") == "/api/sat/solve"
    assert studio_app.canonical_api_path("/api/health") == "/api/health"
    assert studio_app.canonical_api_path("/api/qg/v1/catalog") == "/api/qg/v1/catalog"
    assert studio_app.canonical_api_path("/api/v1") == "/api/v1"


def test_v1_aliases_return_exactly_what_the_original_routes_return(studio):
    for path in ("/health", "/devices", "/noise", "/reference"):
        old = _request(studio, "GET", "/api" + path)
        new = _request(studio, "GET", "/api/v1" + path)
        assert old == new and old[0] == 200, path
    body = {"source": "preset:bell"}
    old = _request(studio, "POST", "/api/plan", body)
    new = _request(studio, "POST", "/api/v1/plan", body)
    assert old == new and old[0] == 200
    cnf = {"cnf": "p cnf 1 1\n1 0\n"}
    assert _request(studio, "POST", "/api/v1/sat/solve", cnf)[1]["result"]["status"] == "SAT"


def test_the_v1_alias_is_not_a_way_around_the_token(studio):
    assert _request(studio, "GET", "/api/v1/health", token=False)[0] == 401
    assert _request(studio, "POST", "/api/v1/plan", {"source": "preset:bell"}, token=False)[0] == 401


def test_openapi_is_served_from_both_prefixes(studio):
    for path in ("/api/openapi.json", "/api/v1/openapi.json"):
        status, doc = _request(studio, "GET", path)
        assert status == 200 and doc == build_openapi()


def test_unknown_v1_route_is_a_typed_404(studio):
    status, doc = _request(studio, "GET", "/api/v1/nope")
    assert status == 404 and doc["error"]["code"] == "not_found"
