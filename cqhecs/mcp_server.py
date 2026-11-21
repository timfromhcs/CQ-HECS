"""
Minimal MCP (Model Context Protocol) server for CQ-HECS.

It speaks newline-delimited JSON-RPC over stdio, exposes the simulator, the
sound SAT engine and the measured hardware evidence as tools, and has no
network listener. Start it with ``cq-hecs mcp``.

The server is intentionally small: no SDK, no extra dependency, and every
tool call returns a JSON text content block. Errors are JSON-RPC errors, not
crashes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_VERSION = "2024-11-05"

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cqhecs_run",
        "description": "Run a QASM circuit or a builtin preset through the CQ-HECS router.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "circuit": {"type": "string", "description": "OpenQASM 2.0 text or 'preset:bell'"},
                "shots": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 1024},
                "seed": {"type": "integer", "default": 42},
                "path": {"type": "string", "enum": ["auto", "A", "B", "C", "D"], "default": "auto"},
                "noise": {
                    "type": "string",
                    "default": "ideal",
                    "description": "ideal, mfit, mfit2, or device:<id> from cqhecs_devices",
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
            "properties": {"circuit": {"type": "string"}},
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
                "circuit": {"type": "string"},
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
                "cnf": {"type": "string"},
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
                "cnf": {"type": "string"},
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
                "cnf": {"type": "string"},
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
]


def _ok(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text(value: Any) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, default=str)}]}


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
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < low or parsed > high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return parsed


def _bounded_float(value: Any, name: str, low: float, high: float, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not (low <= parsed <= high):
        raise ValueError(f"{name} must be in [{low}, {high}]")
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
            "source": arguments["circuit"],
            "shots": arguments.get("shots", 1024),
            "seed": arguments.get("seed", 42),
            "path": arguments.get("path", "auto"),
            "noise": arguments.get("noise", "ideal"),
        }
    )


def _tool_analyze(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.circuit_analyzer import CircuitAnalyzer
    from cqhecs.circuit_library import build_builtin_circuit
    from cqhecs.circuit_parsing import parse_circuit

    source = arguments["circuit"]
    if source.startswith("preset:"):
        circuit = build_builtin_circuit(source[len("preset:") :])
    else:
        circuit = source
    instructions, n = parse_circuit(circuit)
    props = CircuitAnalyzer().analyze_instructions(instructions, n)
    return props.to_dict()


def _tool_plan(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.circuit_library import build_builtin_circuit
    from cqhecs.execution_plan import build_execution_plan

    source = arguments["circuit"]
    if source.startswith("preset:"):
        circuit = build_builtin_circuit(source[len("preset:") :])
    else:
        circuit = source
    plan = build_execution_plan(
        circuit,
        forced_path=arguments.get("force_path"),
        require_counts=bool(arguments.get("require_counts", False)),
    )
    return plan.to_dict()


def _tool_sat(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.sat import parse_dimacs, solve

    formula = parse_dimacs(arguments["cnf"], source="mcp")
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

    formula = parse_dimacs(arguments["cnf"], source="mcp")
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


def _tool_qg_preview(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.quantum_gravity.circuits import bmv_qasm, sha256_text

    theta = float(arguments["theta"])
    qasm = bmv_qasm(theta)
    return {
        "status": "OK",
        "execution_surface": "CLASSICAL_REFERENCE",
        "spend_credits": 0.0,
        "network": "none",
        "qasm": qasm,
        "qasm_sha256": sha256_text(qasm),
    }


def _tool_qg_run_local(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel

    model = BMVEffectivePhaseModel(
        theta=float(arguments["theta"]),
        local_phase_a=float(arguments.get("local_phase_a", 0.0)),
        local_phase_b=float(arguments.get("local_phase_b", 0.0)),
    )
    state = model.state()
    probabilities = {format(index, "02b"): float(abs(state[index]) ** 2) for index in range(4)}
    return {
        "status": "COMPLETED",
        "execution_surface": "CLASSICAL_REFERENCE",
        "precision": "f64",
        "probabilities": probabilities,
        "observables": {
            "concurrence": model.concurrence(),
            "negativity": model.negativity(),
            "entanglement_entropy": model.entropy(),
            "chsh_max": model.chsh_max(),
        },
        "limitations": ["finite two-qubit model; not a gravitational measurement"],
    }


def _call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "cqhecs_run":
        return _text(_tool_run(arguments))
    if name == "cqhecs_analyze":
        return _text(_tool_analyze(arguments))
    if name == "cqhecs_plan":
        return _text(_tool_plan(arguments))
    if name == "cqhecs_sat_solve":
        return _text(_tool_sat(arguments))
    if name == "cqhecs_sat_models":
        return _text(_tool_models(arguments))
    if name == "cqhecs_sat_count":
        from cqhecs.sat import count_models, parse_dimacs

        formula = parse_dimacs(arguments["cnf"], source="mcp")
        return _text({"result": count_models(
            formula,
            timeout_seconds=_bounded_float(arguments.get("timeout"), "timeout", *_TIMEOUT_RANGE, default=5.0),
            method=str(arguments.get("method", "dpll")),
        )})
    if name == "cqhecs_devices":
        from cqhecs.device_profiles import list_profiles, summary

        return _text({"devices": [summary(p) for p in list_profiles()]})
    if name == "cqhecs_hardware":
        return _text(_tool_hardware(arguments))
    if name == "cqhecs_qg_catalog":
        from cqhecs.quantum_gravity import catalog

        return _text(catalog())
    if name == "cqhecs_qg_circuit_preview":
        return _text(_tool_qg_preview(arguments))
    if name == "cqhecs_qg_run_local":
        return _text(_tool_qg_run_local(arguments))
    raise ValueError(f"unknown tool {name!r}")


def handle(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC message. Notifications return None."""
    method = message.get("method")
    request_id = message.get("id")
    if method is None:
        return None
    if method == "initialize":
        return _ok(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cq-hecs", "version": __import__("cqhecs").__version__},
            },
        )
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _ok(request_id, {})
    if method == "tools/list":
        return _ok(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            return _ok(request_id, _call(name, arguments))
        except Exception as exc:  # noqa: BLE001
            return _error(request_id, -32000, f"{type(exc).__name__}: {exc}")
    return _error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except Exception as exc:  # noqa: BLE001
            response = _error(None, -32700, f"parse error: {exc}")
        if response is not None:
            sys.stdout.write(json.dumps(response, default=str) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
