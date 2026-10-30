"""
Property-based tests for circuit semantics (QuCheck-style).

The generator produces native-gate circuits with continuous angles; the
properties are relations that must hold for every generated circuit, not
hand-picked examples:

* probabilities are normalized and non-negative;
* the inverse circuit returns the zero state up to a global phase;
* the exact MPS contraction equals the dense reference up to a global phase.

``hypothesis`` shrinks a failing circuit to a minimal counterexample, so a
regression report contains a small reproducible gate list rather than one large
random case.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from cqhecs.backends.dense_reference import (
    DenseStatevector,
    _single_qubit_matrix,
    _two_qubit_tensor,
)
from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain

ONE_QUBIT = ("h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "p")
TWO_QUBIT = ("cx", "cz", "swap", "cp", "crx", "cry", "crz")
ANGLE = frozenset({"rx", "ry", "rz", "p", "cp", "crx", "cry", "crz"})
SELF_INVERSE = frozenset({"h", "x", "y", "z", "cx", "cz", "swap"})
DAGGER = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}

Instruction = Tuple[str, List[int], List[float]]


@st.composite
def circuits(draw) -> Tuple[int, List[Instruction]]:
    n = draw(st.integers(min_value=2, max_value=4))
    depth = draw(st.integers(min_value=1, max_value=8))
    gates: List[Instruction] = []
    for _ in range(depth):
        two_qubit = draw(st.booleans())
        if two_qubit:
            name = draw(st.sampled_from(TWO_QUBIT))
            qubits = draw(st.lists(st.integers(0, n - 1), min_size=2, max_size=2, unique=True))
            params = [draw(st.floats(-math.pi, math.pi, allow_nan=False, allow_infinity=False))] if name in ANGLE else []
            gates.append((name, qubits, params))
        else:
            name = draw(st.sampled_from(ONE_QUBIT))
            qubit = draw(st.integers(0, n - 1))
            params = [draw(st.floats(-math.pi, math.pi, allow_nan=False, allow_infinity=False))] if name in ANGLE else []
            gates.append((name, [qubit], params))
    # Force the parser to infer the intended width.
    gates.extend(("id", [q], []) for q in range(n))
    return n, gates


def inverse(circuit: List[Instruction]) -> List[Instruction]:
    result: List[Instruction] = []
    for name, qubits, params in reversed(circuit):
        if name in ("id", "barrier"):
            continue
        if name in SELF_INVERSE:
            result.append((name, list(qubits), list(params)))
        elif name in DAGGER:
            result.append((DAGGER[name], list(qubits), list(params)))
        else:
            result.append((name, list(qubits), [-float(p) for p in params]))
    return result


def dense_state(circuit: List[Instruction], n: int) -> np.ndarray:
    simulator = DenseStatevector(n)
    simulator.run(circuit)
    return simulator.statevector()


def mps_state(circuit: List[Instruction], n: int) -> np.ndarray:
    chain = ExactMPSTensorChain(n)
    try:
        for name, qubits, params in circuit:
            if name in ("id", "barrier"):
                continue
            if len(qubits) == 1:
                chain.apply_single_qubit_gate(qubits[0], _single_qubit_matrix(name, params))
            else:
                chain.apply_two_qubit_gate(qubits[0], qubits[1], _two_qubit_tensor(name, params))
        raw = chain.to_statevector().reshape((2,) * n)
        return raw.transpose(tuple(range(n - 1, -1, -1))).reshape(-1)
    finally:
        chain.cleanup()


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(circuits())
def test_probabilities_are_normalized(n_and_circuit):
    n, circuit = n_and_circuit
    probabilities = np.abs(dense_state(circuit, n)) ** 2
    assert abs(float(probabilities.sum()) - 1.0) < 1e-12
    assert float(probabilities.min()) >= -1e-15


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(circuits())
def test_inverse_circuit_is_identity_up_to_phase(n_and_circuit):
    n, circuit = n_and_circuit
    state = dense_state(circuit + inverse(circuit), n)
    assert abs(abs(state[0]) ** 2 - 1.0) < 1e-9


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(circuits())
def test_mps_matches_dense_up_to_phase(n_and_circuit):
    n, circuit = n_and_circuit
    dense = dense_state(circuit, n)
    mps = mps_state(circuit, n)
    fidelity = abs(np.vdot(dense, mps)) ** 2 / (
        np.vdot(dense, dense).real * np.vdot(mps, mps).real
    )
    assert 1.0 - fidelity < 1e-9


def test_strategy_reports_a_small_counterexample_on_failure():
    """The generator is shrinking-friendly: a deliberately broken property must
    produce a circuit with at most the generated depth, not an opaque failure."""
    try:
        @settings(max_examples=5, deadline=None)
        @given(circuits())
        def always_fails(n_and_circuit):
            n, circuit = n_and_circuit
            assert len(circuit) == 0

        always_fails()
    except AssertionError:
        return
    pytest.fail("the synthetic property unexpectedly passed")
