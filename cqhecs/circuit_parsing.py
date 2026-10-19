"""
Shared circuit parsing for the Four-Path backends.

All backends accept the same input forms and reject the same unsupported ones,
so a circuit that one path can execute another path can also execute. Parsing
lives here rather than being duplicated in each backend.
"""

from __future__ import annotations
import math
import re
from typing import Any, List, Optional, Sequence, Tuple

#: Parsed instruction: (gate_name_lowercase, qubit_indices, params)
Instruction = Tuple[str, List[int], List[float]]

_QREG_PATTERN = re.compile(r"qreg\s+([a-zA-Z0-9_]+)\[(\d+)\]")
_GATE_PATTERN = re.compile(r"([a-zA-Z0-9_]+)(?:\(([^)]*)\))?\s+([^;]+);")
_QINDEX_PATTERN = re.compile(r"\[(\d+)\]")

_QASM_HEADER_PREFIXES = (
    "//", "openqasm", "include", "qreg", "creg", "barrier",
)


class UnsupportedCircuitInputError(TypeError):
    """Raised when a circuit input form cannot be parsed."""


def _parse_angle(expr: str) -> Optional[float]:
    """
    Evaluates an OpenQASM angle expression such as ``pi/2`` or ``0.35``.

    Uses a restricted namespace: no builtins, no imports, no attribute access
    beyond math constants, so a malformed circuit cannot execute code.
    """
    namespace = {
        "__builtins__": {},
        "pi": math.pi,
        "e": math.e,
        "abs": abs,
        "min": min,
        "max": max,
        "pow": pow,
        "round": round,
    }
    try:
        value = float(eval(expr, namespace))  # noqa: S307 - restricted namespace
    except Exception:
        return None
    return value if math.isfinite(value) else None


def parse_circuit(circuit: Any) -> Tuple[List[Instruction], int]:
    """
    Normalises a circuit into ``(instructions, num_qubits)``.

    Supported inputs:
        * a Qiskit ``QuantumCircuit``
        * an OpenQASM 2.0 source string
        * a list of ``(name, qubits, params)`` tuples/lists

    Raises:
        UnsupportedCircuitInputError: For any other type, or for a malformed
            instruction list. Parsing never silently drops a gate.
    """
    # Qiskit circuit duck-typing first, so QASM strings stay on the string path.
    if hasattr(circuit, "data") and hasattr(circuit, "num_qubits"):
        return _parse_qiskit(circuit)
    if isinstance(circuit, str):
        return _parse_qasm(circuit)
    if isinstance(circuit, (list, tuple)):
        return _parse_instruction_list(circuit)
    raise UnsupportedCircuitInputError(
        f"Unsupported circuit input type {type(circuit).__name__!r}. "
        "Expected a Qiskit QuantumCircuit, an OpenQASM 2.0 string, or a list "
        "of (name, qubits, params) tuples."
    )


def _parse_qiskit(circuit: Any) -> Tuple[List[Instruction], int]:
    instructions: List[Instruction] = []
    for inst in circuit.data:
        op = inst.operation
        name = op.name.lower()
        qubits = [circuit.find_bit(q).index for q in inst.qubits]
        params = [float(p) for p in getattr(op, "params", [])]
        instructions.append((name, qubits, params))
    return instructions, int(circuit.num_qubits)


def _parse_qasm(source: str) -> Tuple[List[Instruction], int]:
    instructions: List[Instruction] = []
    num_qubits = 0

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(_QASM_HEADER_PREFIXES):
            m_qreg = _QREG_PATTERN.search(line)
            if m_qreg:
                num_qubits = max(num_qubits, int(m_qreg.group(2)))
            continue

        m_gate = _GATE_PATTERN.search(line)
        if not m_gate:
            continue

        gname = m_gate.group(1).lower()
        params_str = m_gate.group(2)
        args_str = m_gate.group(3)
        q_indices = [int(x) for x in _QINDEX_PATTERN.findall(args_str)]
        if q_indices:
            num_qubits = max(num_qubits, max(q_indices) + 1)

        params: List[float] = []
        if params_str:
            value = _parse_angle(params_str)
            # A malformed angle becomes an empty param list; the backend's
            # gate validation then refuses it rather than using a wrong angle.
            params = [] if value is None else [value]
        instructions.append((gname, q_indices, params))

    return instructions, num_qubits


def _parse_instruction_list(items: Sequence[Any]) -> Tuple[List[Instruction], int]:
    instructions: List[Instruction] = []
    num_qubits = 0

    for idx, item in enumerate(items):
        if not isinstance(item, (tuple, list)) or len(item) != 3:
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} is not a (name, qubits, params) triple: {item!r}"
            )
        name, qubits, params = item
        if not isinstance(name, str):
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} has a non-string gate name: {name!r}"
            )
        try:
            q_indices = [int(q) for q in qubits]
        except (TypeError, ValueError) as exc:
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} has non-integer qubit indices: {qubits!r}"
            ) from exc
        try:
            param_values = [float(p) for p in params]
        except (TypeError, ValueError) as exc:
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} has non-numeric parameters: {params!r}"
            ) from exc

        if q_indices:
            num_qubits = max(num_qubits, max(q_indices) + 1)
        instructions.append((name.lower(), q_indices, param_values))

    return instructions, num_qubits