"""Property and fuzz tests for the OpenQASM 2.0 parser (W15 / C5).

The contract: any text either parses into instructions whose qubit indices are inside the declared
registers, or is refused with ``QASMParseError`` (a ``TypeError`` subclass carrying a category). No other
exception type escapes, no input hangs, and oversized or deeply nested input is refused, not truncated.
"""

from __future__ import annotations

import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cqhecs.circuit_parsing import (
    QASMParseError,
    UnsupportedCircuitInputError,
    parse_angle_expression,
    parse_circuit,
)

HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
FUZZ = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    derandomize=True,
)

_ALPHABET = "OPENQASM2.0;include\"qelib1.inc\"qregcreghxyzcxrzu123 \n[]()->,+-*/^pi0123456789meas"
_GATES = ["h", "x", "y", "z", "s", "t", "cx", "cz", "swap", "rx", "ry", "rz", "u3", "ccx", "measure", "barrier", "bogus"]


def _outcome(src):
    try:
        return parse_circuit(src)
    except UnsupportedCircuitInputError:
        return None


@FUZZ
@given(text=st.text(alphabet=_ALPHABET, max_size=300))
def test_noise_text_is_parsed_or_refused_with_a_typed_error(text):
    out = _outcome(text)
    if out is not None:
        instrs, n = out
        for _name, qubits, _params in instrs:
            assert all(0 <= q < max(n, 1) for q in qubits)


@FUZZ
@given(text=st.text(max_size=300))
def test_arbitrary_unicode_never_escapes_as_another_exception(text):
    _outcome(HEADER + text)
    _outcome(text)


@st.composite
def statements(draw):
    gate = draw(st.sampled_from(_GATES))
    arg = st.one_of(st.integers(-2, 6), st.sampled_from(["pi", "pi/2", "1e400", "-pi", "(1+2)", "9**9", "((("]))
    params = draw(st.lists(arg, max_size=3))
    qubits = draw(st.lists(st.integers(-1, 5), min_size=0, max_size=3))
    p = f"({','.join(map(str, params))})" if params else ""
    return f"{gate}{p} " + ",".join(f"q[{q}]" for q in qubits) + ";"


@FUZZ
@given(body=st.lists(statements(), max_size=8))
def test_structured_statements_are_parsed_or_refused(body):
    src = HEADER + "qreg q[4];\ncreg c[4];\n" + "\n".join(body)
    out = _outcome(src)
    if out is not None:
        instrs, n = out
        assert n == 4
        for _name, qubits, params in instrs:
            assert all(0 <= q < 4 for q in qubits)
            assert all(p == p and abs(p) != float("inf") for p in params)  # no NaN/inf angle slips through


@FUZZ
@given(data=st.data())
def test_mutating_a_valid_program_by_one_character_is_parsed_or_refused(data):
    base = HEADER + "qreg q[3];\ncreg c[3];\nh q[0];\ncx q[0],q[1];\nrz(pi/4) q[2];\nmeasure q[0] -> c[0];\n"
    i = data.draw(st.integers(0, len(base) - 1))
    ch = data.draw(st.text(min_size=0, max_size=1))
    _outcome(base[:i] + ch + base[i + 1:])


def test_valid_program_round_trip_shape():
    instrs, n = parse_circuit(HEADER + "qreg q[3];\ncreg c[3];\nh q[0];\ncx q[0],q[1];\nrz(pi/4) q[2];\n")
    assert n == 3
    assert [i[0] for i in instrs] == ["h", "cx", "rz"]
    assert instrs[2][2][0] == pytest.approx(3.141592653589793 / 4)


# ---------------------------------------------------------------- resource limits: refusal, never truncation
@pytest.mark.parametrize(
    "src,category",
    [
        (HEADER + "qreg q[1000000000];\nh q[0];", "invalid_register_size"),
        (HEADER + "qreg q[-1];", "syntax_error"),
        (HEADER + "qreg q[1];\nh q[99999999999999999999999];", "index_out_of_range"),
        (HEADER + "qreg q[1];\nh q[5];", "index_out_of_range"),
        (HEADER + "qreg q[1];\nrz(" + "(" * 5000 + "1" + ")" * 5000 + ") q[0];", "invalid_parameter"),
        (HEADER + "qreg q[1];\nrz(9**9**9) q[0];", "invalid_parameter"),
        (HEADER + "qreg q[1];\nh q[0];\x00", "missing_semicolon"),
        (HEADER + "qreg q[1];\n" + "a" * (2 * 1024 * 1024) + ";", None),
    ],
)
def test_resource_hostile_input_is_refused_with_a_typed_error(src, category):
    start = time.monotonic()
    with pytest.raises(QASMParseError) as info:
        parse_circuit(src)
    assert time.monotonic() - start < 10
    if category:
        assert info.value.category == category


def test_oversized_document_is_refused_not_truncated():
    big = HEADER + "qreg q[1];\n" + "h q[0];\n" * (3 * 1024 * 1024)  # > 16 MiB
    with pytest.raises(QASMParseError) as info:
        parse_circuit(big)
    assert info.value.line == 0  # the whole input is at fault


def test_a_very_long_but_legal_program_parses_completely_and_quickly():
    n = 100_000
    start = time.monotonic()
    instrs, nq = parse_circuit(HEADER + "qreg q[2];\n" + "h q[0];\n" * n)
    assert len(instrs) == n and nq == 2  # every gate kept: nothing silently dropped
    assert time.monotonic() - start < 20


@pytest.mark.parametrize("bad", [b"abc", 5, 1.5, object(), None])
def test_non_circuit_input_types_are_typed_refusals(bad):
    with pytest.raises(UnsupportedCircuitInputError):
        parse_circuit(bad)


@FUZZ
@given(text=st.text(alphabet="pi0123456789.+-*/()e ^", max_size=600))
def test_angle_expressions_are_a_finite_float_or_a_value_error(text):
    try:
        value = parse_angle_expression(text)
    except (ValueError, QASMParseError):
        return
    assert isinstance(value, float) and value == value and abs(value) != float("inf")


@pytest.mark.xfail(
    strict=True,
    reason="SEC-M2: python_bridge.qasm_engine evaluates QASM parameter text with eval() and builtins=None, which is escapable",
)
def test_legacy_bridge_parameter_text_cannot_call_into_the_os_module():
    import os

    from python_bridge.qasm_engine import QASMParser

    payload = (
        "[c for c in ().__class__.__base__.__subclasses__() if c.__name__=='_wrap_close']"
        "[0].__init__.__globals__['cpu_count']()"
    )
    assert QASMParser._eval_param_expr(payload) != float(os.cpu_count())
