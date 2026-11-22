"""D4 (W3-06): a gate the profile has no channel for must not run silently noiseless.

The noise model is built from ``gate_errors`` and the declared ``basis_gates``; a circuit
is not transpiled into that basis. Before this change a circuit using, say, ``h`` or ``t``
on a Faust-like profile ran with *no* channel while the result was still labelled
``NOISY_CLASSICAL`` under a profile id. These tests pin the three honest outcomes: warn
(record ``uncovered_gates``), refuse (raise before simulating) and ideal (accept on
purpose, still recorded).
"""
import pytest

from cqhecs.hardware_bridge import (
    FakeHardwareBackend,
    OutOfModelError,
    create_linear_profile,
)
from cqhecs.result import ExecutionMode


def test_uncovered_gates_lists_gates_outside_the_declared_basis():
    profile = create_linear_profile(3)
    uncovered = profile.uncovered_gates(
        [("h", [0], []), ("cx", [0, 1], []), ("rz", [1], [0.1]), ("t", [2], []), ("h", [2], [])]
    )
    assert uncovered == ["h", "t"]


def test_declared_basis_gates_are_covered():
    profile = create_linear_profile(3)
    circuit = [("x", [0], []), ("sx", [1], []), ("rz", [2], [0.2]), ("cx", [0, 1], []), ("measure", [0], [])]
    assert profile.uncovered_gates(circuit) == []


def test_warn_policy_runs_and_records_the_uncovered_gates():
    backend = FakeHardwareBackend(create_linear_profile(2))
    res = backend.run([("h", [0], []), ("cx", [0, 1], [])], shots=64, seed=1)
    assert res.uncovered_gates == ["h"]
    assert res.metadata["uncovered_gates"] == ["h"]
    assert res.metadata["uncovered_gate_policy"] == "warn"
    # The run is still labelled noisy; the point is that the missing channel is visible.
    assert res.execution_mode == ExecutionMode.NOISY_CLASSICAL


def test_a_covered_circuit_reports_no_uncovered_gates():
    backend = FakeHardwareBackend(create_linear_profile(2))
    res = backend.run([("x", [0], []), ("cx", [0, 1], [])], shots=32, seed=1)
    assert res.uncovered_gates == []
    assert res.metadata["uncovered_gates"] == []


def test_refuse_policy_raises_before_simulating():
    backend = FakeHardwareBackend(create_linear_profile(2), uncovered_gate_policy="refuse")
    with pytest.raises(OutOfModelError, match="no calibrated channel"):
        backend.run([("h", [0], [])], shots=16, seed=1)


def test_refuse_policy_still_runs_a_covered_circuit():
    backend = FakeHardwareBackend(create_linear_profile(2), uncovered_gate_policy="refuse")
    res = backend.run([("x", [0], []), ("cx", [0, 1], [])], shots=16, seed=1)
    assert res.uncovered_gates == []


def test_ideal_policy_records_the_choice_without_warning():
    backend = FakeHardwareBackend(create_linear_profile(2), uncovered_gate_policy="ideal")
    res = backend.run([("t", [0], [])], shots=16, seed=1)
    assert res.uncovered_gates == ["t"]
    assert res.metadata["uncovered_gate_policy"] == "ideal"


def test_an_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        FakeHardwareBackend(create_linear_profile(2), uncovered_gate_policy="maybe")


def test_the_result_document_includes_uncovered_gates():
    backend = FakeHardwareBackend(create_linear_profile(2))
    document = backend.run([("h", [0], [])], shots=8, seed=1).to_dict()
    assert document["uncovered_gates"] == ["h"]


def test_a_synthetic_linear_profile_claims_no_capture_timestamp():
    """A synthetic profile must not look like a dated device calibration (W3-07)."""
    assert create_linear_profile(3).capture_timestamp is None


def test_two_synthetic_linear_profiles_serialise_identically():
    assert create_linear_profile(4, name="lin").to_dict() == create_linear_profile(4, name="lin").to_dict()


def test_expectation_values_records_uncovered_gates():
    backend = FakeHardwareBackend(create_linear_profile(2))
    result = backend.expectation_values([("h", [0], [])], ["Z[0]"])
    assert result.metadata["uncovered_gates"] == ["h"]
