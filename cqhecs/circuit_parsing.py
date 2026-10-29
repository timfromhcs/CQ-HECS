"""
Shared circuit parsing for the Four-Path backends.

All backends accept the same input forms and reject the same unsupported ones,
so a circuit that one path can execute another path can also execute. Parsing
lives here rather than being duplicated in each backend.

Supported input forms
---------------------
* a Qiskit ``QuantumCircuit`` (unitary operations plus terminal measurement),
* an OpenQASM 2.0/3.0 *source string* using the documented strict subset,
* a list of ``(name, qubits, params)`` tuples.

The QASM reader is deliberately strict and fails closed:

* every statement must be terminated by ``;``,
* only the documented declarations/instructions are accepted,
* unknown gates are rejected rather than skipped,
* register identities and offsets are preserved, so ``qreg a[2]; qreg b[3]``
  maps ``b[0]`` to global qubit 2, not to qubit 0,
* angle expressions are evaluated by a small dedicated parser - never by
  Python's ``eval`` - and must be finite.

Error categories match the native parser in ``src/qasm_parser.cpp``
(``missing_semicolon``, ``unsupported_gate``, ``invalid_parameter``, ...), so the
two implementations can be compared differentially.
"""

from __future__ import annotations

import math
import numbers
import re
from collections.abc import Iterable as _Iterable
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Parsed instruction: (gate_name_lowercase, qubit_indices, params)
Instruction = Tuple[str, List[int], List[float]]


class UnsupportedCircuitInputError(TypeError):
    """Raised when a circuit input form cannot be parsed."""


class QASMParseError(UnsupportedCircuitInputError):
    """
    Structured QASM rejection.

    Attributes:
        line: 1-based source line the problem was detected on (0 when the
            whole input is at fault, e.g. an oversized document).
        category: Machine-readable category, matching the native parser.
    """

    def __init__(self, message: str, line: int = 0, category: str = "syntax_error"):
        super().__init__(message)
        self.line = line
        self.category = category

    def __str__(self) -> str:  # pragma: no cover - formatting only
        if self.line:
            return f"line {self.line}: [{self.category}] {self.args[0]}"
        return f"[{self.category}] {self.args[0]}"


# ---------------------------------------------------------------------------
# Angle expressions
# ---------------------------------------------------------------------------

_MAX_ANGLE_LENGTH = 512
_MAX_ANGLE_DEPTH = 200

_NUMBER_LITERAL = re.compile(
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)


class _AngleExpression:
    """
    Recursive-descent evaluator for the documented angle grammar.

    Grammar (identical to ``src/qasm_angle.hpp``)::

        sum     := product (('+' | '-') product)*
        product := factor (('*' | '/') factor)*
        factor  := ('+' | '-') factor | '(' sum ')' | 'pi' | number

    No function calls, no names other than ``pi``, no implicit multiplication.
    The whole token must be consumed and the result must be finite.
    """

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.depth = 0

    def evaluate(self) -> float:
        if not self.text.strip():
            raise ValueError("empty angle expression")
        if len(self.text) > _MAX_ANGLE_LENGTH:
            raise ValueError("angle expression is too long")
        value = self._sum()
        self._skip_ws()
        if self.pos != len(self.text):
            raise ValueError(f"unexpected token at position {self.pos}")
        if not math.isfinite(value):
            raise ValueError("angle expression is not finite")
        return value

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _enter(self) -> None:
        self.depth += 1
        if self.depth > _MAX_ANGLE_DEPTH:
            raise ValueError("angle expression is nested too deeply")

    def _sum(self) -> float:
        self._enter()
        try:
            value = self._product()
            while True:
                self._skip_ws()
                if self.pos >= len(self.text) or self.text[self.pos] not in "+-":
                    return value
                op = self.text[self.pos]
                self.pos += 1
                rhs = self._product()
                value = value + rhs if op == "+" else value - rhs
                if not math.isfinite(value):
                    raise ValueError("angle expression overflowed")
        finally:
            self.depth -= 1

    def _product(self) -> float:
        value = self._factor()
        while True:
            self._skip_ws()
            if self.pos >= len(self.text) or self.text[self.pos] not in "*/":
                return value
            op = self.text[self.pos]
            self.pos += 1
            rhs = self._factor()
            if op == "*":
                value *= rhs
            else:
                if rhs == 0.0:
                    raise ValueError("division by zero in angle expression")
                value /= rhs
            if not math.isfinite(value):
                raise ValueError("angle expression overflowed")

    def _factor(self) -> float:
        self._skip_ws()
        if self.pos >= len(self.text):
            raise ValueError("unexpected end of angle expression")

        char = self.text[self.pos]
        if char in "+-":
            self.pos += 1
            value = self._factor()
            return -value if char == "-" else value

        if char == "(":
            self.pos += 1
            self._enter()
            try:
                value = self._sum()
            finally:
                self.depth -= 1
            self._skip_ws()
            if self.pos >= len(self.text) or self.text[self.pos] != ")":
                raise ValueError("unbalanced parenthesis in angle expression")
            self.pos += 1
            return value

        # ``pi`` is the only accepted identifier. ``nan``/``inf`` therefore
        # never become numeric values.
        if self.text.startswith("pi", self.pos):
            end = self.pos + 2
            if end < len(self.text) and (
                self.text[end].isalnum() or self.text[end] == "_"
            ):
                raise ValueError("unknown identifier in angle expression")
            self.pos = end
            return math.pi

        match = _NUMBER_LITERAL.match(self.text, self.pos)
        if match is None:
            raise ValueError(
                f"invalid number or identifier at position {self.pos}"
            )
        self.pos = match.end()
        try:
            value = float(match.group(0))
        except ValueError as exc:  # pragma: no cover - regex already validates
            raise ValueError("invalid numeric literal") from exc
        if not math.isfinite(value):
            raise ValueError("numeric literal is not finite")
        return value


def parse_angle_expression(text: str) -> float:
    """Evaluates one angle expression; raises ``ValueError`` when invalid."""
    return _AngleExpression(text).evaluate()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_circuit(circuit: Any) -> Tuple[List[Instruction], int]:
    """
    Normalises a circuit into ``(instructions, num_qubits)``.

    Supported inputs:
        * a Qiskit ``QuantumCircuit``
        * an OpenQASM 2.0/3.0 source string
        * a list of ``(name, qubits, params)`` tuples/lists

    Raises:
        UnsupportedCircuitInputError: For any other type, or for a malformed
            instruction list. Parsing never silently drops a gate.
        QASMParseError: For a QASM source that violates the documented subset.
    """
    # Qiskit circuit duck-typing first, so QASM strings stay on the string path.
    if hasattr(circuit, "data") and hasattr(circuit, "num_qubits"):
        instructions, num_qubits = _parse_qiskit(circuit)
    elif isinstance(circuit, str):
        instructions, num_qubits = _parse_qasm(circuit)
    elif isinstance(circuit, (list, tuple)):
        instructions, num_qubits = _parse_instruction_list(circuit)
    else:
        _raise_unsupported_input(circuit)
    # Composite gates (u3, ccx, cy, rzz, ...) are rewritten exactly into the
    # native gate set here, once, so every later stage sees the same circuit.
    from cqhecs.gate_lowering import GateLoweringError, lower_instructions

    try:
        return lower_instructions(instructions), num_qubits
    except GateLoweringError as exc:
        raise UnsupportedCircuitInputError(str(exc)) from exc


def _raise_unsupported_input(circuit: Any) -> None:
    raise UnsupportedCircuitInputError(
        f"Unsupported circuit input type {type(circuit).__name__!r}. "
        "Expected a Qiskit QuantumCircuit, an OpenQASM 2.0 string, or a list "
        "of (name, qubits, params) tuples."
    )


#: Qiskit operations that carry classical control flow. They are not unitary
#: gates and cannot be parsed into the flat instruction form.
_CONTROL_FLOW_OPS = frozenset({
    "if_else", "while_loop", "for_loop", "switch_case",
    "break_loop", "continue_loop",
})


def _sort_terminal_measurements(
    instructions: List[Instruction],
) -> List[Instruction]:
    """
    Sorts a terminal measurement suffix by qubit and removes exact duplicates.

    Measurements are terminal in every supported execution path, so their
    source order carries no semantics. The result contract renders the lowest
    measured qubit rightmost; normalising once here means the direct backends,
    the QASM reader and the Qiskit provider all agree.

    A mid-circuit measurement (one followed by a state-changing operation) is
    left exactly where it is; sorting it to the end would change the state the
    later gates see.
    """
    positions = [
        i for i, (name, _q, _p) in enumerate(instructions) if name == "measure"
    ]
    if not positions:
        return list(instructions)
    first = positions[0]
    suffix = instructions[first:]
    if not all(name == "measure" for name, _q, _p in suffix):
        return list(instructions)

    ordered = sorted(suffix, key=lambda item: item[1][0])
    deduplicated: List[Instruction] = []
    seen_qubits = set()
    for item in ordered:
        qubit = item[1][0]
        if qubit in seen_qubits:
            # A repeated terminal measurement of the same qubit yields the same
            # outcome; the flat IR carries no classical destination, so keeping
            # both would fabricate a second output bit.
            continue
        seen_qubits.add(qubit)
        deduplicated.append(item)
    return instructions[:first] + deduplicated


def _parse_qiskit(circuit: Any) -> Tuple[List[Instruction], int]:
    instructions: List[Instruction] = []
    for index, inst in enumerate(circuit.data):
        op = inst.operation
        name = op.name.lower()
        if name in _CONTROL_FLOW_OPS or getattr(op, "condition", None) is not None:
            raise UnsupportedCircuitInputError(
                f"Instruction {index} is the classically controlled operation "
                f"{name!r}. Dynamic circuits are not supported: mid-circuit "
                "measurement, reset and classical conditions must be rejected "
                "before simulation, not silently reordered."
            )
        qubits = [circuit.find_bit(q).index for q in inst.qubits]
        if name == "mcx":
            # Qiskit names every multi-controlled X "mcx"; the manifest keys
            # them by control count (c3x, c4x). Larger widths stay unknown and
            # are refused rather than approximated.
            name = f"c{len(qubits) - 1}x"
        if name == "measure":
            # The flat instruction triple carries qubit operands only, so a
            # nontrivial classical destination cannot be represented. The
            # QASM contract already requires `measure q[i] -> c[i]`; applying
            # the same rule here keeps both parsers truthful instead of
            # silently sampling a differently-labelled circuit.
            clbits = [circuit.find_bit(c).index for c in inst.clbits]
            if len(qubits) != 1 or len(clbits) != 1:
                raise UnsupportedCircuitInputError(
                    f"Instruction {index} (measure) must target exactly one "
                    f"qubit and one classical bit, got {len(qubits)} qubit(s) "
                    f"and {len(clbits)} classical bit(s)."
                )
            if qubits[0] != clbits[0]:
                raise UnsupportedCircuitInputError(
                    f"Instruction {index} measures qubit {qubits[0]} into "
                    f"classical bit {clbits[0]}. Classical-bit remapping is not "
                    "supported by parse_circuit()/the direct backends; use "
                    "CQHecsBackend (the Qiskit provider), which preserves "
                    "arbitrary (qubit, clbit) layouts."
                )
        raw_params = list(getattr(op, "params", []) or [])
        try:
            params = [float(p) for p in raw_params]
        except (TypeError, ValueError) as exc:
            raise UnsupportedCircuitInputError(
                f"Instruction {index} ({name!r}) has non-numeric parameters "
                f"{raw_params!r}. Symbolic or structured parameters cannot be "
                "simulated."
            ) from exc
        if not all(math.isfinite(value) for value in params):
            raise UnsupportedCircuitInputError(
                f"Instruction {index} ({name!r}) has a non-finite parameter "
                f"{params!r}. NaN/inf cannot be simulated."
            )
        instructions.append((name, qubits, params))
    return _sort_terminal_measurements(instructions), int(circuit.num_qubits)


#: Largest accepted qubit index for the flat instruction-list input. Parsing a
#: legal-but-unmaterialisable width is not the same as being able to simulate
#: it; this ceiling prevents an index such as 10**12 from creating a
#: correspondingly huge per-qubit object list downstream.
_MAX_INSTRUCTION_QUBIT_INDEX = 1 << 20


def _coerce_qubit_index(value: Any, instruction_index: int) -> int:
    """
    Accepts genuine integral indices only.

    ``int(value)`` used to turn ``1.7`` into ``1``, ``True`` into ``1`` and
    ``"2"`` into ``2``, silently simulating a different circuit. Booleans,
    floats (even integral ones), strings, complex values, NaN and infinity are
    rejected with a structured error. ``numbers.Integral`` deliberately includes
    NumPy integer scalars, which are a legitimate API type.
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise UnsupportedCircuitInputError(
            f"Instruction {instruction_index} has a non-integer qubit index "
            f"{value!r} (type {type(value).__name__}). Only integer indices are "
            "accepted; floats, booleans and strings are not coerced."
        )
    index = int(value)
    if index < 0:
        raise UnsupportedCircuitInputError(
            f"Instruction {instruction_index} has a negative qubit index "
            f"{index}."
        )
    if index >= _MAX_INSTRUCTION_QUBIT_INDEX:
        raise UnsupportedCircuitInputError(
            f"Instruction {instruction_index} has qubit index {index}, which "
            f"exceeds the parser ceiling "
            f"{_MAX_INSTRUCTION_QUBIT_INDEX - 1}. A legal index is not a "
            "simulable width."
        )
    return index


def _coerce_iterable(value: Any, instruction_index: int, what: str) -> List[Any]:
    """Rejects scalars/strings where a list of operands is required."""
    if isinstance(value, (str, bytes)) or not isinstance(value, _Iterable):
        raise UnsupportedCircuitInputError(
            f"Instruction {instruction_index} has {what} {value!r} "
            f"(type {type(value).__name__}); expected an iterable of values."
        )
    try:
        return list(value)
    except TypeError as exc:  # pragma: no cover - Iterable guarantees this
        raise UnsupportedCircuitInputError(
            f"Instruction {instruction_index} has an unreadable {what}: {value!r}"
        ) from exc


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
        if not name.strip():
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} has an empty gate name."
            )

        raw_qubits = _coerce_iterable(qubits, idx, "qubit operand list")
        q_indices = [_coerce_qubit_index(q, idx) for q in raw_qubits]

        raw_params = _coerce_iterable(params, idx, "parameter list")
        try:
            param_values = [float(p) for p in raw_params]
        except (TypeError, ValueError) as exc:
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} has non-numeric parameters: {params!r}"
            ) from exc
        if not all(math.isfinite(v) for v in param_values):
            raise UnsupportedCircuitInputError(
                f"Instruction {idx} has a non-finite parameter: {param_values!r}"
            )

        if q_indices:
            num_qubits = max(num_qubits, max(q_indices) + 1)
        instructions.append((name.lower(), q_indices, param_values))

    return _sort_terminal_measurements(instructions), num_qubits


# ---------------------------------------------------------------------------
# QASM reader
# ---------------------------------------------------------------------------

_MAX_SOURCE_BYTES = 16 * 1024 * 1024
_MAX_LINE_BYTES = 1 * 1024 * 1024
_MAX_REGISTER_SIZE = 1 << 20

_REGISTER_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_QREG_DECL = re.compile(rf"^(qreg|creg)\s+({_REGISTER_NAME})\s*\[\s*([0-9]+)\s*\]$")
_QUBIT_DECL = re.compile(rf"^(qubit|bit)\s*\[\s*([0-9]+)\s*\]\s+({_REGISTER_NAME})$")
_OPERAND = re.compile(rf"^({_REGISTER_NAME})\s*(?:\[\s*([0-9]+)\s*\])?$")
_GATE_HEAD = re.compile(rf"^({_REGISTER_NAME})")
_INCLUDE = re.compile(r'^include\s+"[^"]*"$')


class _QasmReader:
    """Stateful reader for the strict OpenQASM subset."""

    def __init__(self) -> None:
        self.instructions: List[Instruction] = []
        self.qregs: Dict[str, Tuple[int, int]] = {}
        self.cregs: Dict[str, Tuple[int, int]] = {}
        self.num_qubits = 0
        self.num_clbits = 0
        self.seen_header = False

    # -- declarations ---------------------------------------------------
    def declare(self, kind: str, name: str, size_text: str, line: int) -> None:
        target = self.qregs if kind in ("qreg", "qubit") else self.cregs
        all_names = self.qregs.keys() | self.cregs.keys()
        if name in all_names:
            raise QASMParseError(
                f"register {name!r} is declared more than once",
                line,
                "duplicate_register",
            )
        try:
            size = int(size_text)
        except ValueError as exc:  # pragma: no cover - regex restricts digits
            raise QASMParseError(
                f"invalid register size for {name!r}", line, "syntax_error"
            ) from exc
        if size <= 0 or size > _MAX_REGISTER_SIZE:
            raise QASMParseError(
                f"register {name!r} has invalid size {size}; expected "
                f"1..{_MAX_REGISTER_SIZE}",
                line,
                "invalid_register_size",
            )
        if target is self.qregs:
            offset = self.num_qubits
            self.num_qubits += size
        else:
            offset = self.num_clbits
            self.num_clbits += size
        target[name] = (offset, size)

    # -- operands -------------------------------------------------------
    def resolve(
        self, token: str, table: Dict[str, Tuple[int, int]], line: int
    ) -> List[int]:
        """
        Resolves one operand to global indices.

        A bare register expands to all of its indices; an indexed reference
        resolves to exactly one global index. Undeclared registers and
        out-of-range indices are hard errors.
        """
        match = _OPERAND.match(token.strip())
        if match is None:
            raise QASMParseError(
                f"invalid operand {token.strip()!r}", line, "invalid_operand"
            )
        name, index_text = match.group(1), match.group(2)
        if name not in table:
            raise QASMParseError(
                f"register {name!r} was not declared", line, "undeclared_register"
            )
        offset, size = table[name]
        if index_text is None:
            return list(range(offset, offset + size))
        index = int(index_text)
        if index >= size:
            raise QASMParseError(
                f"index {index} is out of range for register {name!r} "
                f"(size {size})",
                line,
                "index_out_of_range",
            )
        return [offset + index]

    def resolve_many(
        self, text: str, table: Dict[str, Tuple[int, int]], line: int
    ) -> List[int]:
        try:
            parts = _split_top_level(text, ",")
        except ValueError as exc:
            raise QASMParseError(
                f"unbalanced parentheses in operand list {text.strip()!r}",
                line,
                "syntax_error",
            ) from exc
        if not parts or any(not part.strip() for part in parts):
            raise QASMParseError(
                f"malformed operand list {text.strip()!r}", line, "invalid_operand"
            )
        indices: List[int] = []
        for part in parts:
            indices.extend(self.resolve(part, table, line))
        return indices

    # -- statements -----------------------------------------------------
    def statement(self, text: str, line: int) -> None:
        if text.startswith("OPENQASM"):
            # Match the native parser: everything after the header keyword is
            # the version token, and anything other than 2.0/3.0 (including an
            # empty or malformed token) is an unsupported version, not a
            # generic syntax error.
            version = text[len("OPENQASM"):].strip()
            if version not in ("2.0", "3.0"):
                raise QASMParseError(
                    f"unsupported OpenQASM version: {version}",
                    line,
                    "unsupported_version",
                )
            if self.seen_header:
                raise QASMParseError(
                    "duplicate OPENQASM header", line, "syntax_error"
                )
            self.seen_header = True
            return

        if text.startswith("include"):
            if not _INCLUDE.match(text):
                raise QASMParseError(
                    f"include expects exactly one quoted filename: {text!r}",
                    line,
                    "syntax_error",
                )
            return

        lowered = text.lower()
        if lowered.startswith(("if(", "if (", "for ", "while ", "box", "def ")):
            raise QASMParseError(
                f"unsupported OpenQASM construct: {text!r}",
                line,
                "unsupported_syntax",
            )

        first_word = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", text)
        if first_word is None:
            raise QASMParseError(
                f"statement does not start with an instruction: {text!r}",
                line,
                "syntax_error",
            )
        keyword = first_word.group(1)
        lower_keyword = keyword.lower()

        if lower_keyword in ("qreg", "creg", "qubit", "bit"):
            match = _QREG_DECL.match(text)
            if match is None:
                match = _QUBIT_DECL.match(text)
            if match is None:
                raise QASMParseError(
                    f"malformed register declaration: {text!r}",
                    line,
                    "syntax_error",
                )
            if match.re is _QREG_DECL:
                self.declare(match.group(1), match.group(2), match.group(3), line)
            else:
                self.declare(match.group(1), match.group(3), match.group(2), line)
            return

        if lower_keyword == "measure":
            self._measure(text, line)
            return

        self._gate(text, line)

    def _measure(self, text: str, line: int) -> None:
        body = text[len("measure"):].strip()
        arrow = body.split("->")
        if len(arrow) != 2:
            raise QASMParseError(
                f"measure expects 'measure <qubit> -> <clbit>': {text!r}",
                line,
                "syntax_error",
            )
        qubits = self.resolve(arrow[0], self.qregs, line)
        clbits = self.resolve(arrow[1], self.cregs, line)
        if len(qubits) != len(clbits):
            raise QASMParseError(
                f"measure width mismatch: {len(qubits)} qubit(s) -> "
                f"{len(clbits)} classical bit(s)",
                line,
                "width_mismatch",
            )
        if any(q != c for q, c in zip(qubits, clbits)):
            raise QASMParseError(
                "classical-bit remapping is not supported by the four-path "
                "simulator; use 'measure q[i] -> c[i]' so the requested "
                "classical index matches the qubit index",
                line,
                "unsupported_syntax",
            )
        # Measurements stay at their source position. Moving them to the end
        # would turn a mid-circuit measurement into a terminal one and change
        # the simulated state; the analyzer detects and refuses that case.
        for qubit in qubits:
            self.instructions.append(("measure", [qubit], []))

    def _gate(self, text: str, line: int) -> None:
        match = _GATE_HEAD.match(text)
        assert match is not None
        name = match.group(1)
        rest = text[match.end():]
        params_text: Optional[str] = None
        rest = rest.lstrip()
        if rest.startswith("("):
            close = _matching_paren(rest, 0)
            if close < 0:
                raise QASMParseError(
                    f"unbalanced '(' in statement: {text!r}", line, "syntax_error"
                )
            params_text = rest[1:close]
            rest = rest[close + 1:].strip()

        # The manifest is the shared syntax authority. Unknown names are a
        # hard ``unsupported_gate``; known-but-unimplemented names parse fine
        # and are refused later by capability-first routing.
        from cqhecs.gate_manifest import get_gate

        spec = get_gate(name)
        if spec is None:
            raise QASMParseError(
                f"unsupported or unknown gate: {name}", line, "unsupported_gate"
            )

        if not rest:
            raise QASMParseError(
                f"gate {name!r} has no qubit operands", line, "syntax_error"
            )

        if spec.barrier:
            qubits = self.resolve_many(rest, self.qregs, line)
            if not qubits:
                raise QASMParseError(
                    "barrier requires at least one qubit operand",
                    line,
                    "syntax_error",
                )
            self.instructions.append(("barrier", qubits, []))
            return

        params: List[float] = []
        if params_text is not None:
            if not params_text.strip():
                # ``rx()`` is a parameter-count violation, exactly as the
                # native parser classifies it.
                raise QASMParseError(
                    f"gate {name!r} expects {spec.max_params} parameter(s), "
                    "got 0",
                    line,
                    "parameter_count_mismatch",
                )
            try:
                parameter_tokens = _split_top_level(params_text, ",")
            except ValueError as exc:
                raise QASMParseError(
                    f"unbalanced parentheses in parameter list: {params_text!r}",
                    line,
                    "invalid_parameter",
                ) from exc
            for token in parameter_tokens:
                try:
                    params.append(parse_angle_expression(token))
                except ValueError as exc:
                    raise QASMParseError(
                        f"invalid parameter {token.strip()!r} for gate "
                        f"{name!r}: {exc}",
                        line,
                        "invalid_parameter",
                    ) from exc

        if not (spec.min_params <= len(params) <= spec.max_params):
            expected = (
                str(spec.min_params)
                if spec.min_params == spec.max_params
                else f"{spec.min_params}..{spec.max_params}"
            )
            raise QASMParseError(
                f"gate {name!r} expects {expected} parameter(s), got {len(params)}",
                line,
                "parameter_count_mismatch",
            )

        qubits = self.resolve_many(rest, self.qregs, line)
        if not qubits:
            raise QASMParseError(
                f"gate {name!r} has no qubit operands", line, "syntax_error"
            )
        # Whole-register operands expand to several gate applications, exactly
        # like the native parser: the flattened operand list must be a whole
        # multiple of the gate's arity and is then consumed in arity-sized
        # chunks. This also makes ``h b`` apply to every qubit of ``b``.
        if len(qubits) % spec.arity != 0:
            raise QASMParseError(
                f"gate {name!r} expects a multiple of {spec.arity} qubit(s), "
                f"got {len(qubits)}",
                line,
                "operand_count_mismatch",
            )
        for offset in range(0, len(qubits), spec.arity):
            self.instructions.append(
                (name.lower(), qubits[offset:offset + spec.arity], params)
            )

    # -- finish ---------------------------------------------------------
    def finish(self) -> Tuple[List[Instruction], int]:
        # Measurements were recorded in source order. When they form a terminal
        # suffix, normalise them by qubit so every backend renders the sampled
        # bitstring with qubit 0 rightmost regardless of source order. A
        # mid-circuit measurement is deliberately left in place: sorting it to
        # the end would silently change its semantics.
        return _sort_terminal_measurements(self.instructions), self.num_qubits


def _matching_paren(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_top_level(text: str, separator: str) -> List[str]:
    """Splits on `separator` outside parentheses; keeps empty fields visible."""
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses")
        if char == separator and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if depth != 0:
        raise ValueError("unbalanced parentheses")
    parts.append("".join(current))
    return parts


def _parse_qasm(source: str) -> Tuple[List[Instruction], int]:
    """Parses an OpenQASM 2.0/3.0 source string under the strict contract."""
    if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
        raise QASMParseError(
            f"QASM source exceeds the {_MAX_SOURCE_BYTES}-byte limit",
            0,
            "input_too_large",
        )

    reader = _QasmReader()

    # The contract is line-oriented, exactly like the native parser: one or
    # more ``;``-terminated statements per line, no statement continuation.
    # That keeps "missing semicolon" diagnosable at the offending line instead
    # of fusing two statements into one confusing operand error.
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        if len(raw_line.encode("utf-8")) > _MAX_LINE_BYTES:
            raise QASMParseError(
                "input line exceeds the 1 MiB limit", line_number, "line_too_long"
            )
        if "/*" in raw_line or "*/" in raw_line:
            raise QASMParseError(
                "block comments are not supported by this parser",
                line_number,
                "unsupported_syntax",
            )
        code = raw_line.split("//", 1)[0].strip()
        if not code:
            continue
        if not code.endswith(";"):
            raise QASMParseError(
                f"statement is not terminated by ';': {code!r}",
                line_number,
                "missing_semicolon",
            )
        for statement in code.split(";"):
            statement = statement.strip()
            if statement:
                reader.statement(statement, line_number)

    return reader.finish()
