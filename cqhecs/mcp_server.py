"""
Minimal MCP (Model Context Protocol) server for CQ-HECS.

It speaks newline-delimited JSON-RPC over stdio, exposes the simulator, the
sound SAT engine and the measured hardware evidence as tools, and has no
network listener. Start it with ``cq-hecs mcp``.

The server is intentionally small: no SDK, no extra dependency, and every
tool call returns a JSON text content block. Errors are JSON-RPC errors, not
crashes.

Protocol (W4-05): the client's ``protocolVersion`` is negotiated against
``SUPPORTED_PROTOCOL_VERSIONS``. ``2024-11-05`` (also the mode before any
``initialize``) is the legacy shape. ``2025-03-26`` adds tool annotations.
``2025-06-18`` adds tool titles, ``outputSchema`` and ``structuredContent``
(always mirrored as a JSON text block). 2025-06-18 is the newest text this
server has been checked against; newer revisions are not claimed.

Execution (W4-01): ``tools/call`` runs on a worker thread so the read loop stays
responsive and ``notifications/cancelled`` is honoured. A cancelled call is answered
exactly once with ``status: CANCELLED`` and never a verdict. Pure-Python compute is
abandoned, not stopped: the worker finishes on its own bounded timeout and its late
result is discarded. (The spec says a cancelled request SHOULD get no response;
this server answers anyway so a caller always gets a typed CANCELLED, never a
silent hang. A client that cancelled may ignore it.)
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LEGACY_PROTOCOL_VERSION = "2024-11-05"
#: Kept for callers that imported it: the version used before/without negotiation.
PROTOCOL_VERSION = LEGACY_PROTOCOL_VERSION
#: Upper bound on tool calls running at once.
MAX_INFLIGHT = 8
#: At EOF, how long to wait for in-flight calls before giving up on them.
EOF_DRAIN_SECONDS = 60.0

_TOOL_TITLES = {
    "cqhecs_run": "Run a circuit",
    "cqhecs_analyze": "Analyze a circuit",
    "cqhecs_plan": "Plan a circuit (dry run)",
    "cqhecs_sat_solve": "Solve a CNF",
    "cqhecs_sat_count": "Count CNF models",
    "cqhecs_sat_models": "Enumerate CNF models",
    "cqhecs_devices": "List device profiles",
    "cqhecs_hardware": "Hardware evidence summary",
    "cqhecs_qg_catalog": "Quantum Gravity catalog",
    "cqhecs_qg_circuit_preview": "Quantum Gravity circuit preview",
    "cqhecs_qg_run_local": "Quantum Gravity local run",
    "cqhecs_doctor": "Execution environment diagnostics",
    "cqhecs_qg_plan": "Quantum Gravity plan (dry run)",
    "cqhecs_qg_model_validate": "Quantum Gravity model validation",
    "cqhecs_qg_compare": "Quantum Gravity reference vs CQ-HECS compare",
    "cqhecs_qg_export": "Quantum Gravity evidence export",
    "cqhecs_qg_openquantum_discover": "Open Quantum discover (UNAVAILABLE)",
    "cqhecs_qg_openquantum_quote": "Open Quantum quote (UNAVAILABLE)",
    "cqhecs_qg_openquantum_submit": "Open Quantum submit (UNAVAILABLE)",
    "cqhecs_qg_openquantum_status": "Open Quantum status (UNAVAILABLE)",
    "cqhecs_qg_openquantum_results": "Open Quantum results (UNAVAILABLE)",
}
#: Every tool is local, deterministic for fixed arguments, and changes nothing outside the process.
_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
#: The minimum each tool's structuredContent must satisfy: a floor of required keys, not a closed schema,
#: so results can grow without breaking clients.
_OUTPUT_REQUIRED = {
    "cqhecs_run": ["result"],
    "cqhecs_analyze": [],
    "cqhecs_plan": ["schema_version", "plan_digest", "selected_path"],
    "cqhecs_sat_solve": ["formula", "result"],
    "cqhecs_sat_count": ["result"],
    "cqhecs_sat_models": ["status"],
    "cqhecs_devices": ["devices"],
    "cqhecs_hardware": ["datasets"],
    "cqhecs_qg_catalog": ["schema"],
    "cqhecs_qg_circuit_preview": ["status", "qasm", "qasm_sha256"],
    "cqhecs_qg_run_local": ["status", "probabilities", "observables"],
    "cqhecs_doctor": ["components", "failed"],
    "cqhecs_qg_plan": ["qg_plan", "digest"],
    "cqhecs_qg_model_validate": ["status", "model"],
    "cqhecs_qg_compare": ["status", "sources"],
    "cqhecs_qg_export": ["bundle_sha256", "qg_plan_digest"],
    "cqhecs_qg_openquantum_discover": ["status", "code"],
    "cqhecs_qg_openquantum_quote": ["status", "code"],
    "cqhecs_qg_openquantum_submit": ["status", "code"],
    "cqhecs_qg_openquantum_status": ["status", "code"],
    "cqhecs_qg_openquantum_results": ["status", "code"],
}
#: Kept for callers that imported it: the version used before/without negotiation.
PROTOCOL_VERSION = LEGACY_PROTOCOL_VERSION
#: Upper bound on tool calls running at once (running + abandoned-after-cancel).
MAX_INFLIGHT = 8
#: At EOF, how long to wait for in-flight calls before giving up on them.
EOF_DRAIN_SECONDS = 60.0

_TOOL_TITLES = {
    "cqhecs_run": "Run a circuit",
    "cqhecs_analyze": "Analyze a circuit",
    "cqhecs_plan": "Plan a circuit (dry run)",
    "cqhecs_sat_solve": "Solve a CNF",
    "cqhecs_sat_count": "Count CNF models",
    "cqhecs_sat_models": "Enumerate CNF models",
    "cqhecs_devices": "List device profiles",
    "cqhecs_hardware": "Hardware evidence summary",
    "cqhecs_qg_catalog": "Quantum Gravity catalog",
    "cqhecs_qg_circuit_preview": "Quantum Gravity circuit preview",
    "cqhecs_qg_run_local": "Quantum Gravity local run",
    "cqhecs_qg_plan": "Quantum Gravity plan (dry run)",
    "cqhecs_qg_model_validate": "Quantum Gravity model validation",
    "cqhecs_qg_compare": "Quantum Gravity reference vs CQ-HECS compare",
    "cqhecs_qg_export": "Quantum Gravity evidence export",
    "cqhecs_qg_openquantum_discover": "Open Quantum discover (UNAVAILABLE)",
    "cqhecs_qg_openquantum_quote": "Open Quantum quote (UNAVAILABLE)",
    "cqhecs_qg_openquantum_submit": "Open Quantum submit (UNAVAILABLE)",
    "cqhecs_qg_openquantum_status": "Open Quantum status (UNAVAILABLE)",
    "cqhecs_qg_openquantum_results": "Open Quantum results (UNAVAILABLE)",
}
#: Every tool is local, deterministic for fixed arguments, and changes nothing outside the process.
_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
#: Closed-world minimum each tool's structuredContent must satisfy. Deliberately a floor (required keys),
#: not a full schema: extra keys are allowed so the result can grow without breaking clients.
_OUTPUT_REQUIRED = {
    "cqhecs_run": ["result"],
    "cqhecs_analyze": [],
    "cqhecs_plan": ["schema_version", "plan_digest", "selected_path"],
    "cqhecs_sat_solve": ["formula", "result"],
    "cqhecs_sat_count": ["result"],
    "cqhecs_sat_models": ["status"],
    "cqhecs_devices": ["devices"],
    "cqhecs_hardware": ["datasets"],
    "cqhecs_qg_catalog": ["schema"],
    "cqhecs_qg_circuit_preview": ["status", "qasm", "qasm_sha256"],
    "cqhecs_qg_run_local": ["status", "probabilities", "observables"],
    "cqhecs_qg_plan": ["qg_plan", "digest"],
    "cqhecs_qg_model_validate": ["status", "model"],
    "cqhecs_qg_compare": ["status", "sources"],
    "cqhecs_qg_export": ["bundle_sha256", "qg_plan_digest"],
    "cqhecs_qg_openquantum_discover": ["status", "code"],
    "cqhecs_qg_openquantum_quote": ["status", "code"],
    "cqhecs_qg_openquantum_submit": ["status", "code"],
    "cqhecs_qg_openquantum_status": ["status", "code"],
    "cqhecs_qg_openquantum_results": ["status", "code"],
}

#: F-08: bound one stdin line and every QASM/DIMACS text argument. The text cap equals the circuit
#: parser's own source cap; the line cap leaves room for JSON escaping and the envelope.
MAX_TEXT_CHARS = 16 * 1024 * 1024
MAX_LINE_BYTES = 32 * 1024 * 1024
_TEXT_ARGS = ("circuit", "cnf")

THETA: Dict[str, Any] = {"type": "number", "minimum": -6.2832, "maximum": 6.2832}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cqhecs_run",
        "description": "Run a QASM circuit or a builtin preset through the CQ-HECS router.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "circuit": {"type": "string", "maxLength": MAX_TEXT_CHARS, "description": "OpenQASM 2.0 text or 'preset:bell'"},
                "shots": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 1024},
                "seed": {"type": "integer", "default": 42},
                "path": {"type": "string", "enum": ["auto", "A", "B", "C", "D"], "default": "auto"},
                "noise": {
                    "type": "string",
                    "default": "ideal",
                    "description": "ideal, mfit, mfit2, calibration_v3 (with 'calibration'), or device:<id> from cqhecs_devices",
                },
                "calibration": {
                    "type": "object",
                    "description": "with noise=calibration_v3: a cqhecs.calibration/3.0 record (or an unchanged v1/v2 profile)",
                },
                "uncovered_gates": {
                    "type": "string", "enum": ["refuse", "warn", "ideal"], "default": "warn",
                    "description": "policy for gates the calibration has no channel for",
                },
            },
            "required": ["circuit"],
        },
    },
    {
        "name": "cqhecs_analyze",
        "description": "Statically analyze a circuit and return its recommended path.",
        "inputSchema": {
            "type": "object",
            "properties": {"circuit": {"type": "string", "maxLength": MAX_TEXT_CHARS}},
            "required": ["circuit"],
        },
    },
    {
        "name": "cqhecs_plan",
        "description": (
            "Dry-run ExecutionPlan: selected path, candidate paths with capability "
            "blockers, heuristic resource estimates and typed refusals. Allocates "
            "no simulator state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "circuit": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                "force_path": {"type": "string", "enum": ["A", "B", "C", "D"]},
                "require_counts": {"type": "boolean"},
            },
            "required": ["circuit"],
        },
    },
    {
        "name": "cqhecs_sat_solve",
        "description": "Solve a DIMACS CNF soundly; UNKNOWN is a timeout, never UNSAT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cnf": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                "timeout": {"type": "number", "default": 5.0},
                "node_budget": {"type": "integer"},
                "engine": {
                    "type": "string",
                    "enum": ["dpll", "watched", "cadical", "omniwave"],
                    "default": "dpll",
                    "description": "watched is the built-in DPLL with two-watched-literal propagation; "
                    "cadical needs the optional python-sat extra; omniwave is the experimental "
                    "multi-front engine. For both, UNSAT is reported only with a DRAT proof checked by cqhecs.drat",
                },
                "waves": {"type": "integer", "default": 4, "description": "omniwave only"},
                "workers": {"type": "integer", "default": 2, "description": "omniwave only"},
                "bcp": {"type": "string", "enum": ["scalar", "batch", "vulkan"], "default": "scalar",
                        "description": "omniwave only; vulkan results are verified against the CPU reference"},
                "branch": {"type": "string", "enum": ["auto", "jw", "bfs"], "default": "auto",
                           "description": "omniwave only; auto uses BFS on parity-heavy formulas and JW elsewhere"},
            },
            "required": ["cnf"],
        },
    },
    {
        "name": "cqhecs_sat_count",
        "description": "Exact model count (#SAT) of a DIMACS CNF; UNKNOWN when the budget runs out.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cnf": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                "timeout": {"type": "number", "default": 5.0},
                "method": {"type": "string", "enum": ["dpll", "separator", "auto"], "default": "dpll"},
            },
            "required": ["cnf"],
        },
    },
    {
        "name": "cqhecs_sat_models",
        "description": "Enumerate up to N models of a DIMACS CNF.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cnf": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                "limit": {"type": "integer", "default": 10},
                "timeout": {"type": "number", "default": 10.0},
            },
            "required": ["cnf"],
        },
    },
    {
        "name": "cqhecs_devices",
        "description": "List measured QPU noise profiles (M-FIT-2) usable as cqhecs_run device.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cqhecs_hardware",
        "description": "Summarize the committed real-QPU and independent-oracle evidence.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cqhecs_qg_catalog",
        "description": "Quantum Gravity lab: theories, models, observables, execution surfaces and limits (local, no network, no spend).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cqhecs_qg_circuit_preview",
        "description": "Generate the BMV effective-phase QASM and its SHA-256. Local only; never quotes or spends.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "theta": {"type": "number", "minimum": -6.2832, "maximum": 6.2832, "description": "coupling phase (radians)"},
            },
            "required": ["theta"],
        },
    },
    {
        "name": "cqhecs_qg_run_local",
        "description": "Run the exact two-qubit BMV model locally (CLASSICAL_REFERENCE) and return probabilities and entanglement observables. No network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "theta": {"type": "number", "minimum": -6.2832, "maximum": 6.2832},
                "local_phase_a": {"type": "number"},
                "local_phase_b": {"type": "number"},
            },
            "required": ["theta"],
        },
    },
    {
        "name": "cqhecs_doctor",
        "description": (
            "Execution environment report (same probes as `cq-hecs doctor`): optional dependencies, native "
            "binding, Vulkan loader, path capabilities. Reports what could be loaded; nothing is run on a GPU."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cqhecs_qg_plan",
        "description": (
            "Dry-run QG ExecutionPlan envelope (cqhecs.qg.execution_plan/1) with its digest: the generic "
            "ExecutionPlan of the compiled circuit plus engine and precision. Classical route only; "
            "never plans, quotes or spends a QPU job. Allocates no simulator state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "experiment": {"type": "string", "enum": ["bmv", "syk", "gauge"], "default": "bmv"},
                "theta": THETA,
                "n": {"type": "integer", "minimum": 2, "maximum": 8},
                "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
                "scale": {"type": "number", "minimum": 1e-6, "maximum": 10},
                "t": {"type": "number", "minimum": 0, "maximum": 50},
                "steps": {"type": "integer", "minimum": 1, "maximum": 64},
                "rows": {"type": "integer", "minimum": 1, "maximum": 4},
                "cols": {"type": "integer", "minimum": 1, "maximum": 4},
                "force_path": {"type": "string", "enum": ["A", "B", "C", "D"]},
                "require_counts": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "cqhecs_qg_model_validate",
        "description": "Validate a QG model instance (bmv, syk, gauge) and return its manifest. No execution, no network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "experiment": {"type": "string", "enum": ["bmv", "syk", "gauge"], "default": "bmv"},
                "theta": THETA,
                "local_phase_a": THETA,
                "local_phase_b": THETA,
                "n": {"type": "integer", "minimum": 2, "maximum": 8},
                "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
                "scale": {"type": "number", "minimum": 1e-6, "maximum": 10},
                "rows": {"type": "integer", "minimum": 1, "maximum": 4},
                "cols": {"type": "integer", "minimum": 1, "maximum": 4},
            },
        },
    },
    {
        "name": "cqhecs_qg_compare",
        "description": (
            "Compare the exact BMV reference with the CQ-HECS router on the same QASM, with separate "
            "provenance per source. Open Quantum sources are reported NOT_COMPARED. No network."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "theta": THETA,
                "shots": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 4096},
                "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647, "default": 42},
            },
            "required": ["theta"],
        },
    },
    {
        "name": "cqhecs_qg_export",
        "description": "Secret-free evidence bundle for a local QG experiment: parameters, validation, plan, digests.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "experiment": {"type": "string", "enum": ["bmv", "syk", "gauge"], "default": "bmv"},
                "theta": THETA,
                "n": {"type": "integer", "minimum": 2, "maximum": 8},
                "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
                "scale": {"type": "number", "minimum": 1e-6, "maximum": 10},
                "t": {"type": "number", "minimum": 0, "maximum": 50},
                "steps": {"type": "integer", "minimum": 1, "maximum": 64},
                "rows": {"type": "integer", "minimum": 1, "maximum": 4},
                "cols": {"type": "integer", "minimum": 1, "maximum": 4},
            },
        },
    },
] + [
    {
        "name": "cqhecs_qg_openquantum_" + _action,
        "description": (
            "Open Quantum " + _action + ": UNAVAILABLE in this build. Always returns a typed refusal, "
            "contacts nothing and spends nothing. Quote and submit are separate steps in "
            "scripts/run_qg_openquantum_campaign.py under the single 25-Spark ledger."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    }
    for _action in ("discover", "quote", "submit", "status", "results")
]


def _ok(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text(value: Any) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, default=str)}]}


class _Session:
    """Negotiated protocol state for one stdio connection (one process serves one client)."""

    def __init__(self) -> None:
        self.version = LEGACY_PROTOCOL_VERSION

    @property
    def annotations(self) -> bool:
        return self.version >= "2025-03-26"

    @property
    def structured(self) -> bool:
        return self.version >= "2025-06-18"


_SESSION = _Session()


def negotiate_protocol(requested: Any) -> str:
    """The client's version if supported; the newest supported one if not; legacy if it sent none."""
    if not isinstance(requested, str):
        return LEGACY_PROTOCOL_VERSION
    if requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return SUPPORTED_PROTOCOL_VERSIONS[0]


def _tool_descriptors(session: "_Session") -> List[Dict[str, Any]]:
    """TOOLS rendered for the negotiated version: legacy fields only unless the client can read more."""
    rendered: List[Dict[str, Any]] = []
    for tool in TOOLS:
        entry = dict(tool)
        title = _TOOL_TITLES.get(tool["name"], tool["name"])
        if session.structured:
            entry["title"] = title
            entry["outputSchema"] = {
                "type": "object",
                "properties": {},
                "required": list(_OUTPUT_REQUIRED.get(tool["name"], [])),
            }
        if session.annotations:
            entry["annotations"] = {"title": title, **_TOOL_ANNOTATIONS}
        rendered.append(entry)
    return rendered


def _wrap_result(payload: Dict[str, Any], session: "_Session") -> Dict[str, Any]:
    """Text block always; ``structuredContent`` (same object) when the negotiated version has it."""
    result = _text(payload)
    if session.structured and isinstance(payload, dict):
        result["structuredContent"] = json.loads(json.dumps(payload, default=str))
    return result


class ToolArgumentsError(ValueError):
    """A tool call had missing or invalid arguments -> JSON-RPC -32602 (invalid params)."""


def _require(arguments: Dict[str, Any], key: str) -> Any:
    if key not in arguments or arguments[key] is None:
        raise ToolArgumentsError(f"missing required argument {key!r}")
    return arguments[key]



#: Server-side input bounds, matched to the Studio's (cqhecs/studio/app.py). A
#: model may send anything; the server refuses out-of-range values instead of
#: passing them to an engine that would run unbounded (D7).
_TIMEOUT_RANGE = (0.01, 30.0)
_WAVES_RANGE = (1, 16)
_WORKERS_RANGE = (1, 8)
_MODELS_LIMIT_RANGE = (1, 1000)
_NODE_BUDGET_RANGE = (1, 10_000_000)


def _bounded_int(value: Any, name: str, low: int, high: int, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolArgumentsError(f"{name} must be an integer") from exc
    if parsed < low or parsed > high:
        raise ToolArgumentsError(f"{name} must be in [{low}, {high}]")
    return parsed


def _bounded_float(value: Any, name: str, low: float, high: float, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ToolArgumentsError(f"{name} must be a number") from exc
    if not (low <= parsed <= high):
        raise ToolArgumentsError(f"{name} must be in [{low}, {high}]")
    return parsed


def _optional_node_budget(value: Any) -> Any:
    if value is None:
        return None
    return _bounded_int(value, "node_budget", *_NODE_BUDGET_RANGE, default=_NODE_BUDGET_RANGE[0])



def _tool_run(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.studio import StudioState

    state = StudioState(ROOT)
    return state.simulate(
        {
            "source": _require(arguments, "circuit"),
            "shots": arguments.get("shots", 1024),
            "seed": arguments.get("seed", 42),
            "path": arguments.get("path", "auto"),
            "noise": arguments.get("noise", "ideal"),
            "calibration": arguments.get("calibration"),
            "uncovered_gates": arguments.get("uncovered_gates", "warn"),
        }
    )


def _tool_analyze(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.circuit_analyzer import CircuitAnalyzer
    from cqhecs.circuit_library import build_builtin_circuit
    from cqhecs.circuit_parsing import parse_circuit

    source = _require(arguments, "circuit")
    if source.startswith("preset:"):
        circuit = build_builtin_circuit(source[len("preset:") :])
    else:
        circuit = source
    instructions, n = parse_circuit(circuit)
    props = CircuitAnalyzer().analyze_instructions(instructions, n)
    return props.to_dict()


def _tool_plan(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs import service

    try:
        return service.plan_document(
            _require(arguments, "circuit"),
            force_path=arguments.get("force_path"),
            require_counts=bool(arguments.get("require_counts", False)),
        )
    except service.ServiceError as exc:
        raise ToolArgumentsError(str(exc)) from exc


def _tool_sat(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.sat import parse_dimacs, solve

    formula = parse_dimacs(_require(arguments, "cnf"), source="mcp")
    timeout = _bounded_float(arguments.get("timeout"), "timeout", *_TIMEOUT_RANGE, default=5.0)
    if arguments.get("engine", "dpll") == "cadical":
        from cqhecs.sat_external import solve_external

        result = solve_external(formula, timeout_seconds=timeout)
    elif arguments.get("engine") == "omniwave":
        from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine

        engine = OmniwaveEngine(formula, OmniwaveConfig(
            waves=_bounded_int(arguments.get("waves"), "waves", *_WAVES_RANGE, default=4),
            workers=_bounded_int(arguments.get("workers"), "workers", *_WORKERS_RANGE, default=2),
            timeout_seconds=timeout, bcp=str(arguments.get("bcp", "scalar")),
            branch=str(arguments.get("branch", "auto")),
        ))
        result = engine.run()
        return {
            "formula": {
                "num_vars": formula.num_vars,
                "num_clauses": formula.num_clauses,
                "sha256": formula.sha256,
                "original_sha256": formula.original_sha256,
            },
            "result": result.to_dict(),
            "omniwave": engine.snapshot(),
        }
    else:
        result = solve(
            formula,
            timeout_seconds=timeout,
            node_budget=_optional_node_budget(arguments.get("node_budget")),
            propagation="watched" if arguments.get("engine") == "watched" else "scan",
        )
    return {
        "formula": {
            "num_vars": formula.num_vars,
            "num_clauses": formula.num_clauses,
            "sha256": formula.sha256,
            "original_sha256": formula.original_sha256,
        },
        "result": result.to_dict(),
    }


def _tool_models(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.sat import enumerate_models, parse_dimacs

    formula = parse_dimacs(_require(arguments, "cnf"), source="mcp")
    return enumerate_models(
        formula,
        limit=_bounded_int(arguments.get("limit"), "limit", *_MODELS_LIMIT_RANGE, default=10),
        timeout_seconds=_bounded_float(arguments.get("timeout"), "timeout", *_TIMEOUT_RANGE, default=10.0),
    )


def _tool_hardware(_arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.studio.app import HARDWARE_EVALUATIONS

    root = ROOT / "research/v4/evidence"
    out: Dict[str, Any] = {"datasets": []}
    for name, shots, relative in HARDWARE_EVALUATIONS:
        path = ROOT / relative
        if path.is_file():
            payload = json.loads(path.read_text("utf-8"))
            out["datasets"].append(
                {
                    "id": name,
                    "backend": payload.get("backend"),
                    "shots": shots,
                    "verdict": payload.get("aggregate", {}).get("verdict"),
                    "median_delta_tv": payload.get("aggregate", {}).get("median_delta_tv"),
                    "n_eval": payload.get("aggregate", {}).get("n_eval"),
                }
            )
    for name, path in (
        ("pnp_emulability", root / "pnp_emulability/summary.json"),
        ("pnp_sat_oracles", root / "pnp_sat_oracles/summary.json"),
    ):
        if path.is_file():
            payload = json.loads(path.read_text("utf-8"))
            out[name] = payload.get("verdict", payload.get("verdict"))
    return out


def _service(fn: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Call a shared-service function; a typed caller error becomes -32602 (invalid params)."""
    from cqhecs import service

    try:
        return fn(*args, **kwargs)
    except service.ServiceError as exc:
        raise ToolArgumentsError(f"{exc} ({exc.code})") from exc


def _tool_qg_preview(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs import service

    p = _service(service.qg_experiment_params, "bmv", {"theta": _require(arguments, "theta")})
    return service.qg_preview_document(p["theta"])


def _tool_qg_run_local(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs import service

    _require(arguments, "theta")
    p = _service(service.qg_experiment_params, "bmv", dict(arguments))
    return service.qg_run_local_document(p["theta"], p["local_phase_a"], p["local_phase_b"])


def _tool_qg_plan(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs import service

    params = {k: v for k, v in arguments.items() if k not in ("experiment", "force_path", "require_counts")}
    return _service(
        service.qg_plan_document,
        arguments.get("experiment", "bmv"),
        params,
        force_path=arguments.get("force_path"),
        require_counts=bool(arguments.get("require_counts", True)),
    )


def _call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run one tool and return its raw payload (the transport envelope is added by ``_wrap_result``)."""
    if not isinstance(arguments, dict):
        raise ToolArgumentsError("arguments must be an object")
    for key in _TEXT_ARGS:
        value = arguments.get(key)
        if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
            raise ToolArgumentsError(f"{key} exceeds the {MAX_TEXT_CHARS}-character limit (input_too_large)")
    if name == "cqhecs_run":
        return _tool_run(arguments)
    if name == "cqhecs_analyze":
        return _tool_analyze(arguments)
    if name == "cqhecs_plan":
        return _tool_plan(arguments)
    if name == "cqhecs_sat_solve":
        return _tool_sat(arguments)
    if name == "cqhecs_sat_models":
        return _tool_models(arguments)
    if name == "cqhecs_sat_count":
        from cqhecs.sat import count_models, parse_dimacs

        formula = parse_dimacs(_require(arguments, "cnf"), source="mcp")
        return {"result": count_models(
            formula,
            timeout_seconds=_bounded_float(arguments.get("timeout"), "timeout", *_TIMEOUT_RANGE, default=5.0),
            method=str(arguments.get("method", "dpll")),
        )}
    if name == "cqhecs_devices":
        from cqhecs.device_profiles import list_profiles, summary

        return {"devices": [summary(p) for p in list_profiles()]}
    if name == "cqhecs_hardware":
        return _tool_hardware(arguments)
    if name == "cqhecs_qg_catalog":
        from cqhecs.quantum_gravity import catalog

        return catalog()
    if name == "cqhecs_qg_circuit_preview":
        return _tool_qg_preview(arguments)
    if name == "cqhecs_qg_run_local":
        return _tool_qg_run_local(arguments)
    if name == "cqhecs_doctor":
        from cqhecs import service

        return service.doctor_report("1.0")
    if name == "cqhecs_qg_plan":
        return _tool_qg_plan(arguments)
    if name in ("cqhecs_qg_model_validate", "cqhecs_qg_export"):
        from cqhecs import service

        fn = service.qg_validate_document if name.endswith("validate") else service.qg_export_document
        rest = {k: v for k, v in arguments.items() if k != "experiment"}
        return _service(fn, arguments.get("experiment", "bmv"), rest)
    if name == "cqhecs_qg_compare":
        from cqhecs import service

        _require(arguments, "theta")
        theta = _service(service.qg_experiment_params, "bmv", {"theta": arguments["theta"]})["theta"]
        return _service(
            service.qg_compare_document, theta,
            shots=_bounded_int(arguments.get("shots"), "shots", 1, 20000, 4096),
            seed=_bounded_int(arguments.get("seed"), "seed", 0, 2**31 - 1, 42),
        )
    if name.startswith("cqhecs_qg_openquantum_"):
        from cqhecs import service

        return _service(service.qg_paid_refusal, name[len("cqhecs_qg_openquantum_"):])
    raise ToolArgumentsError(f"unknown tool {name!r}")


def _initialize_result(params: Dict[str, Any], session: "_Session") -> Dict[str, Any]:
    session.version = negotiate_protocol(params.get("protocolVersion"))
    return {
        "protocolVersion": session.version,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "cq-hecs", "version": __import__("cqhecs").__version__},
    }


def handle(message: Dict[str, Any], session: Optional["_Session"] = None) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC message synchronously. Notifications return None."""
    session = session or _SESSION
    if not isinstance(message, dict):
        return _error(None, -32600, "invalid request: expected a JSON object")
    method = message.get("method")
    request_id = message.get("id")
    if method is None:
        return None
    if method == "initialize":
        params = message.get("params")
        return _ok(request_id, _initialize_result(params if isinstance(params, dict) else {}, session))
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _ok(request_id, {})
    if method == "tools/list":
        return _ok(request_id, {"tools": _tool_descriptors(session)})
    if method == "tools/call":
        params = message.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return _error(request_id, -32602, "invalid params: expected an object")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            payload = _call(name, arguments)
            result = _wrap_result(payload, session)
            if isinstance(payload, dict) and payload.get("code") == "QG_PAID_PATH_UNAVAILABLE":
                result["isError"] = True  # a typed refusal is a tool failure, never a success
            return _ok(request_id, result)
        except ToolArgumentsError as exc:
            # Invalid or missing arguments are a protocol error (invalid params).
            return _error(request_id, -32602, str(exc))
        except Exception as exc:  # noqa: BLE001
            # A tool that ran but failed returns a successful response flagged isError,
            # so the caller sees the tool failure instead of a transport error (W4-02).
            return _ok(request_id, {"isError": True, "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}]})
    return _error(request_id, -32601, f"method not found: {method}")


def _cancelled_result(request_id: Any, reason: Optional[str], session: "_Session") -> Dict[str, Any]:
    payload = {
        "status": "CANCELLED",
        "verdict": None,
        "reason": reason or "cancelled by the client",
        "compute": "abandoned",
        "note": "no result is reported; pure-Python compute is abandoned, not stopped, and ends at its own timeout",
    }
    result = _text(payload)
    result["isError"] = True
    if session.structured:
        result["structuredContent"] = payload
    return _ok(request_id, result)


class StdioServer:
    """Newline-delimited JSON-RPC over a text stream, with threaded ``tools/call`` and cancellation."""

    def __init__(self, stdout: Any, max_inflight: int = MAX_INFLIGHT, session: Optional["_Session"] = None) -> None:
        self._stdout = stdout
        self._max_inflight = max_inflight
        self._session = session or _SESSION
        self._lock = threading.Lock()  # guards _inflight and every stdout write
        #: request key -> {"thread", "answered"}; removed once the worker ends.
        self._inflight: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _key(request_id: Any) -> str:
        return json.dumps(request_id, sort_keys=True, default=str)

    def write(self, response: Dict[str, Any]) -> None:
        with self._lock:
            self._write(response)

    def _write(self, response: Dict[str, Any]) -> None:
        self._stdout.write(json.dumps(response, default=str) + "\n")
        self._stdout.flush()

    def _run_call(self, key: str, message: Dict[str, Any]) -> None:
        try:
            response = handle(message, self._session)
        except Exception as exc:  # noqa: BLE001
            response = _error(message.get("id"), -32603, f"internal error: {exc}")
        with self._lock:
            entry = self._inflight.pop(key, None)
            # A cancelled call was already answered: its late result is discarded, never reported.
            if entry is not None and not entry["answered"] and response is not None:
                self._write(response)

    def _cancel(self, params: Dict[str, Any]) -> None:
        if "requestId" not in params:
            return
        key = self._key(params["requestId"])
        with self._lock:
            entry = self._inflight.get(key)
            if entry is None or entry["answered"]:
                return  # unknown or already finished: nothing to cancel
            entry["answered"] = True
            self._write(_cancelled_result(params["requestId"], params.get("reason"), self._session))

    def dispatch(self, message: Any) -> None:
        if isinstance(message, dict) and message.get("method") == "notifications/cancelled":
            params = message.get("params")
            self._cancel(params if isinstance(params, dict) else {})
            return
        if isinstance(message, dict) and message.get("method") == "tools/call" and message.get("id") is not None:
            key = self._key(message["id"])
            with self._lock:
                if key in self._inflight:
                    self._write(_error(message["id"], -32600, "duplicate in-flight request id"))
                    return
                live = sum(1 for e in self._inflight.values() if e["thread"].is_alive())
                if live >= self._max_inflight:
                    busy = _text({"status": "UNKNOWN", "verdict": None, "reason": "SERVER_BUSY",
                                  "max_inflight": self._max_inflight})
                    busy["isError"] = True
                    self._write(_ok(message["id"], busy))
                    return
                thread = threading.Thread(target=self._run_call, args=(key, message), daemon=True)
                self._inflight[key] = {"thread": thread, "answered": False}
                thread.start()
            return
        response = handle(message, self._session)
        if response is not None:
            self.write(response)

    def drain(self, timeout: float = EOF_DRAIN_SECONDS) -> None:
        """At EOF: let running calls finish (bounded); cancelled/abandoned ones are not waited for."""
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                pending = [e["thread"] for e in self._inflight.values() if not e["answered"]]
            if not pending:
                return
            pending[0].join(timeout=0.1)


def _read_bounded_line(stream: Any, limit: int = MAX_LINE_BYTES) -> Optional[tuple]:
    """Read one line with a hard cap. Returns None at EOF, else (line, too_long); an over-long
    line is drained in bounded chunks and never accumulated (F-08)."""
    chunk = stream.readline(limit + 1)
    if chunk == "" or chunk == b"":
        return None
    if len(chunk) <= limit or chunk.endswith("\n"):
        return chunk, False
    while True:  # drop the remainder of the oversize line without keeping it
        rest = stream.readline(1 << 20)
        if rest == "" or rest.endswith("\n"):
            break
    return "", True


def main(stdin: Any = None, stdout: Any = None) -> int:
    server = StdioServer(stdout or sys.stdout)
    stream = stdin if stdin is not None else sys.stdin
    while True:
        got = _read_bounded_line(stream)
        if got is None:
            break
        line, too_long = got
        if too_long:
            server.write(_error(None, -32600, f"request line exceeds {MAX_LINE_BYTES} bytes (input_too_large)"))
            continue
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except Exception as exc:  # noqa: BLE001
            server.write(_error(None, -32700, f"parse error: {exc}"))
            continue
        try:
            server.dispatch(message)
        except Exception as exc:  # noqa: BLE001
            server.write(_error(None, -32603, f"internal error: {exc}"))
    server.drain()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
