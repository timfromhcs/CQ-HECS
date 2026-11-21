"""OpenAPI 3.1 description of the local Studio API (W4-04).

The document is generated from ``ROUTES`` so it cannot be edited by hand into disagreement with
itself; ``tests/test_schema_contracts.py`` checks that every route here is served, that every route
the handler serves is here, and that the committed copy ``schemas/studio.openapi.json`` equals
``build_openapi()``. Every route is served under ``/api/...`` (the original paths) and under the
``/api/v1/...`` alias; both reach the same handler.

Request bodies are described by the fields the server reads; ``additionalProperties`` stays open
because the Studio ignores unknown keys rather than refusing them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from cqhecs import __version__

#: (method, path under /api, summary, request-body properties or None, request required)
ROUTES: List[Tuple[str, str, str, Any, Tuple[str, ...]]] = [
    ("get", "/health", "Server and dataset status", None, ()),
    ("get", "/openapi.json", "This OpenAPI 3.1 document", None, ()),
    ("get", "/suite", "Preregistered evaluation suite summary", None, ()),
    ("get", "/noise", "Noise models and calibration profile summary", None, ()),
    ("get", "/research", "Research notes and claim boundaries", None, ()),
    ("get", "/devices", "Measured device noise profiles", None, ()),
    ("get", "/hardware", "Committed real-QPU evidence summary", None, ()),
    ("get", "/reference", "Registered reference datasets", None, ()),
    ("get", "/preset", "A builtin circuit as OpenQASM (query: name)", None, ()),
    ("get", "/omniwave/status", "OMNIWAVE lab status", None, ()),
    ("post", "/simulate", "Run a circuit through the router", {
        "source": {"type": "string", "description": "preset:<name> or an OpenQASM 2.0 string"},
        "shots": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 1024},
        "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647, "default": 42},
        "path": {"type": "string", "enum": ["auto", "A", "B", "C", "D"], "default": "auto"},
        "noise": {"type": "string", "default": "ideal"},
    }, ()),
    ("post", "/plan", "Dry-run ExecutionPlan (schema: execution_plan.schema.json)", {
        "source": {"type": "string", "default": "preset:bell"},
        "path": {"type": "string", "enum": ["auto", "A", "B", "C", "D"], "default": "auto"},
        "require_counts": {"type": "boolean", "default": False},
    }, ()),
    ("post", "/noise/compare", "Compare ideal and noisy output for a dataset job", {
        "job_id": {"type": "string"},
    }, ()),
    ("post", "/sat/solve", "Solve a DIMACS CNF soundly", {
        "cnf": {"type": "string"},
        "timeout": {"type": "number", "minimum": 0.01, "maximum": 30.0, "default": 5.0},
        "node_budget": {"type": "integer"},
        "engine": {"type": "string", "default": "dpll"},
    }, ()),
    ("post", "/sat/count", "Exact model count of a DIMACS CNF", {
        "cnf": {"type": "string"},
        "timeout": {"type": "number", "minimum": 0.01, "maximum": 30.0, "default": 5.0},
        "method": {"type": "string", "default": "dpll"},
    }, ()),
    ("post", "/sat/sweep", "Random 3-SAT phase-transition sweep", {
        "sizes": {"type": "array", "items": {"type": "integer"}},
        "ratios": {"type": "array", "items": {"type": "number"}},
        "trials": {"type": "integer", "minimum": 1, "maximum": 20, "default": 3},
        "timeout": {"type": "number", "minimum": 0.01, "maximum": 5.0, "default": 1.0},
    }, ()),
    ("post", "/omniwave/{action}", "OMNIWAVE lab action (start, pause, resume, cancel)", {}, ()),
    ("post", "/reload", "Reload datasets and return health", None, ()),
]


def _op(method: str, path: str, summary: str, props: Any, required: Tuple[str, ...]) -> Dict[str, Any]:
    op: Dict[str, Any] = {
        "operationId": (method + path.replace("/", "_").replace("{", "").replace("}", "")).rstrip("_"),
        "summary": summary,
        "security": [{"bearerAuth": []}],
        "responses": {
            "200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}},
            "401": {"$ref": "#/components/responses/Error"},
            "default": {"$ref": "#/components/responses/Error"},
        },
    }
    if path == "/omniwave/{action}":
        op["parameters"] = [{"name": "action", "in": "path", "required": True,
                             "schema": {"type": "string", "enum": ["start", "pause", "resume", "cancel"]}}]
    if path == "/preset":
        op["parameters"] = [{"name": "name", "in": "query", "required": False,
                             "schema": {"type": "string", "default": "bell"}}]
    if method == "post":
        schema: Dict[str, Any] = {"type": "object", "properties": props or {}, "additionalProperties": True}
        if required:
            schema["required"] = list(required)
        op["requestBody"] = {"required": False, "content": {"application/json": {"schema": schema}}}
        op["responses"]["415"] = {"$ref": "#/components/responses/Error"}
    return op


def build_openapi() -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    for method, path, summary, props, required in ROUTES:
        for prefix in ("/api/v1", "/api"):
            item = paths.setdefault(prefix + path, {})
            op = _op(method, path, summary, props, required)
            if prefix == "/api":
                op["operationId"] += "_legacy"
                op["summary"] += " (original path; same handler as /api/v1)"
                op["deprecated"] = False
            item[method] = op
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "CQ-HECS Studio local API",
            "version": __version__,
            "description": (
                "Loopback-only API of the local Studio. Every /api route needs the per-launch bearer token "
                "(or CQ_HECS_STUDIO_TOKEN / CQ_HECS_STUDIO_TOKEN_FILE), an allowed Host, no foreign Origin, "
                "and application/json POST bodies. /api/v1/... is an alias of /api/... ; the Quantum Gravity "
                "routes under /api/qg/v1 are versioned separately and not listed here."
            ),
        },
        "servers": [{"url": "http://127.0.0.1:8765"}],
        "paths": paths,
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            "responses": {
                "Error": {
                    "description": "Typed error",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "required": ["error"],
                        "properties": {"error": {
                            "type": "object",
                            "required": ["code", "message"],
                            "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
                        }},
                    }}},
                }
            },
        },
    }


def render() -> str:
    """The committed form: ``schemas/studio.openapi.json``."""
    import json

    return json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":  # python -m cqhecs.studio.openapi > schemas/studio.openapi.json
    import sys

    sys.stdout.write(render())
