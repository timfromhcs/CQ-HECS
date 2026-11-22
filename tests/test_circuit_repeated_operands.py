"""C1-FIND-01: a gate with a repeated qubit operand is refused before any backend runs."""
import itertools

import pytest

from cqhecs.circuit_parsing import QASMParseError, UnsupportedCircuitInputError, parse_circuit
from cqhecs.gate_manifest import MANIFEST, repeated_operands, signature_errors

MULTI = sorted(n for n, s in MANIFEST.items() if s.arity >= 2 and not s.barrier)


def _params(spec):
    return ", ".join(["0.5"] * spec.min_params)


def _qasm(name, ops):
    spec = MANIFEST[name]
    head = f"{name}({_params(spec)})" if spec.min_params else name
    n = max(ops) + 1
    return f'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[{n}];\n{head} ' + ",".join(f"q[{o}]" for o in ops) + ";\n"


def _patterns(arity):
    # every operand tuple over `arity` slots that uses a repeated qubit
    return [t for t in itertools.product(range(arity), repeat=arity) if len(set(t)) < arity]


def test_manifest_has_multi_qubit_gates():
    assert {"cx", "cz", "swap", "ccx", "cswap", "crx", "c3x", "c4x"} <= set(MULTI)


@pytest.mark.parametrize("name", MULTI)
def test_qasm_refuses_every_repeated_operand_pattern(name):
    spec = MANIFEST[name]
    for ops in _patterns(spec.arity):
        with pytest.raises(QASMParseError) as info:
            parse_circuit(_qasm(name, ops))
        assert info.value.category == "repeated_operand"
        assert info.value.line == 4


@pytest.mark.parametrize("name", MULTI)
def test_instruction_list_refuses_every_repeated_operand_pattern(name):
    spec = MANIFEST[name]
    params = [0.5] * spec.min_params
    for ops in _patterns(spec.arity):
        with pytest.raises(UnsupportedCircuitInputError):
            parse_circuit([(name, list(ops), params)])
        assert signature_errors(name, ops, params)


@pytest.mark.parametrize("name", MULTI)
def test_distinct_operands_are_still_accepted(name):
    spec = MANIFEST[name]
    ops = list(range(spec.arity))
    instrs, n = parse_circuit([(name, ops, [0.5] * spec.min_params)])
    assert n == spec.arity and len(instrs) >= 1


@pytest.mark.parametrize("path", [None, "A", "B", "C"])
def test_router_refuses_cx_q0_q0_on_every_path(path):
    from cqhecs.router import EntanglementAdaptiveRouter

    kwargs = {} if path is None else {"preferred_path": path}
    with pytest.raises(UnsupportedCircuitInputError):
        EntanglementAdaptiveRouter().route_and_execute(_qasm("cx", (0, 0)), shots=8, seed=1, **kwargs)


def test_repeated_operands_helper():
    assert repeated_operands([0, 1, 0, 1, 2]) == (0, 1)
    assert repeated_operands([3, 4]) == ()
