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
                "noise": {"type": "string", "enum": ["ideal", "mfit", "mfit2"], "default": "ideal"},
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
        "name": "cqhecs_sat_solve",
        "description": "Solve a DIMACS CNF soundly; UNKNOWN is a timeout, never UNSAT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cnf": {"type": "string"},
                "timeout": {"type": "number", "default": 5.0},
                "node_budget": {"type": "integer"},
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
        "name": "cqhecs_hardware",
        "description": "Summarize the committed real-QPU and independent-oracle evidence.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _ok(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text(value: Any) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, default=str)}]}


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


def _tool_sat(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.sat import parse_dimacs, solve

    formula = parse_dimacs(arguments["cnf"], source="mcp")
    result = solve(
        formula,
        timeout_seconds=float(arguments.get("timeout", 5.0)),
        node_budget=arguments.get("node_budget"),
    )
    return {
        "formula": {"num_vars": formula.num_vars, "num_clauses": formula.num_clauses},
        "result": result.to_dict(),
    }


def _tool_models(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cqhecs.sat import enumerate_models, parse_dimacs

    formula = parse_dimacs(arguments["cnf"], source="mcp")
    return enumerate_models(
        formula,
        limit=int(arguments.get("limit", 10)),
        timeout_seconds=float(arguments.get("timeout", 10.0)),
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


def _call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "cqhecs_run":
        return _text(_tool_run(arguments))
    if name == "cqhecs_analyze":
        return _text(_tool_analyze(arguments))
    if name == "cqhecs_sat_solve":
        return _text(_tool_sat(arguments))
    if name == "cqhecs_sat_models":
        return _text(_tool_models(arguments))
    if name == "cqhecs_hardware":
        return _text(_tool_hardware(arguments))
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
