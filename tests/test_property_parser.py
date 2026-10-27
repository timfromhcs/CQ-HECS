"""CQ-14: property tests for the strict instruction-list parser.

Deterministic settings keep CI repeatable; Hypothesis shrinks any failure to a
minimal example, which is then kept as a normal regression test.
"""

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from cqhecs.circuit_parsing import UnsupportedCircuitInputError, parse_circuit

SETTINGS = settings(max_examples=200, deadline=None, derandomize=True)

valid_index = st.integers(min_value=0, max_value=127)
valid_angle = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)


@SETTINGS
@given(valid_index, valid_index, valid_angle)
def test_integral_indices_round_trip(q0, q1, theta):
    parsed, width = parse_circuit(
        [("h", [q0], []), ("rx", [q1], [theta])]
    )
    assert parsed[0][1] == [q0]
    assert parsed[1][1] == [q1]
    assert width == max(q0, q1) + 1
    assert parsed[1][2][0] == theta


@SETTINGS
@given(valid_index)
def test_numpy_integer_indices_are_accepted(index):
    parsed, width = parse_circuit([("h", [np.int64(index)], [])])
    assert parsed[0][1] == [index]
    assert width == index + 1


@SETTINGS
@given(
    st.one_of(
        st.booleans(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.text(),
        st.integers(min_value=-10**6, max_value=-1),
        st.integers(min_value=1 << 20, max_value=1 << 40),
        st.complex_numbers(allow_nan=True, allow_infinity=True),
    )
)
def test_invalid_qubit_indices_are_rejected(value):
    with pytest.raises(UnsupportedCircuitInputError):
        parse_circuit([("h", [value], [])])


@SETTINGS
@given(st.one_of(st.integers(), st.floats(), st.text(), st.none()))
def test_non_nested_or_scalar_operand_lists_are_rejected(value):
    with pytest.raises(UnsupportedCircuitInputError):
        parse_circuit([("h", value, [])])


@SETTINGS
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["h", "x", "rz", "cx"]),
            st.lists(valid_index, min_size=1, max_size=2),
            st.lists(valid_angle, max_size=1),
        ),
        max_size=12,
    )
)
def test_random_valid_instruction_lists_never_crash(items):
    # Arity/parameter errors are also structured input errors; the property is
    # that no raw TypeError/IndexError/OverflowError escapes.
    try:
        parse_circuit(items)
    except UnsupportedCircuitInputError:
        pass
