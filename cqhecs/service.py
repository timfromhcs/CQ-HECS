"""
Shared service layer (W4-03).

One implementation of the operations that the Python API, the ``cq-hecs`` CLI, the stdio MCP server
and the local Studio all expose. Each surface keeps only its own envelope (argparse, JSON-RPC, HTTP);
the document inside the envelope is produced here, so the four surfaces cannot drift.

Currently shared: circuit-source resolution and the dry-run ``ExecutionPlan``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

VALID_PATHS = ("A", "B", "C", "D")


class ServiceError(ValueError):
    """A typed, caller-facing failure. ``code`` is stable; surfaces map it to their own error shape."""

    def __init__(self, message: str, *, code: str = "invalid_request", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def resolve_circuit_source(source: Any, *, strict: bool = False) -> Any:
    """Turn a surface-level circuit string into something the parser accepts.

    ``preset:<name>`` builds a builtin circuit, ``qasm:<text>`` and OpenQASM text pass through. With
    ``strict`` anything else is refused (Studio); otherwise it is passed on and the parser decides.
    """
    if not isinstance(source, str):
        raise ServiceError("circuit source must be a string", code="invalid_source")
    if source.startswith("preset:"):
        from cqhecs.circuit_library import build_builtin_circuit

        name = source[len("preset:"):]
        try:
            return build_builtin_circuit(name)
        except (KeyError, ValueError) as exc:
            raise ServiceError(f"unknown preset {name!r}", code="unknown_preset", status=404) from exc
    if source.startswith("qasm:"):
        return source[len("qasm:"):]
    if strict and "OPENQASM" not in source and "qreg" not in source:
        raise ServiceError(
            "source must be 'preset:<name>' or an OpenQASM 2.0 string", code="invalid_source"
        )
    return source


def normalize_force_path(path: Optional[str]) -> Optional[str]:
    """``None``/``auto`` mean no forced path; otherwise A-D (case-insensitive) or a typed error."""
    if path is None:
        return None
    value = str(path).upper()
    if value == "AUTO":
        return None
    if value not in VALID_PATHS:
        raise ServiceError("path must be auto, A, B, C or D", code="invalid_path")
    return value


def plan_object(
    source: Any,
    *,
    force_path: Optional[str] = None,
    require_counts: bool = False,
    max_memory_bytes: Optional[int] = None,
    strict: bool = False,
    analyzer: Any = None,
    **limits: Any,
) -> Any:
    """The dry-run :class:`~cqhecs.execution_plan.ExecutionPlan`. Allocates no simulator state."""
    from cqhecs.execution_plan import build_execution_plan

    circuit = resolve_circuit_source(source, strict=strict) if isinstance(source, str) else source
    kwargs: Dict[str, Any] = dict(
        forced_path=normalize_force_path(force_path),
        require_counts=bool(require_counts),
        max_memory_bytes=max_memory_bytes,
    )
    if analyzer is not None:
        kwargs["analyzer"] = analyzer
    kwargs.update(limits)
    return build_execution_plan(circuit, **kwargs)


def plan_document(source: Any, **kwargs: Any) -> Dict[str, Any]:
    """The dry-run ExecutionPlan as a plain dict (see :func:`plan_object`)."""
    return plan_object(source, **kwargs).to_dict()
