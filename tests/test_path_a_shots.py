"""D1 (W3-01): Path A must not silently truncate the requested shot count.

Before this change ``StabilizerTableauSimulator.sample`` capped a wide
(``n > 30``) non-all-equal circuit at 100 re-measurements and disclosed it only in the
``sampled_shots`` metadata. That is a wrong number on a result — a caller asking for 1000
shots got 100. The sampler now draws every requested shot, or refuses with
:class:`PathAShotBudgetError`; truncated counts are only produced when the caller passes an
explicit ``max_resample_shots``.
"""
import pytest

from cqhecs.backends.path_a_stabilizer import (
    MAX_RESAMPLE_WORK,
    PathAShotBudgetError,
    StabilizerTableauSimulator,
)


def _h_all(n: int) -> StabilizerTableauSimulator:
    sim = StabilizerTableauSimulator(n)
    for q in range(n):
        sim.apply_h(q)
    return sim


def test_a_wide_circuit_draws_every_requested_shot():
    sim = _h_all(32)
    counts, sampled = sim.sample(shots=250, seed=1)
    assert sampled == 250, "a 32-qubit run must not be capped at 100 shots"
    assert sum(counts.values()) == 250


def test_the_old_default_cap_would_have_hidden_the_truncation():
    # 300 requested, 32 qubits: the historical cap returned 100.
    sim = _h_all(32)
    _, sampled = sim.sample(shots=300, seed=2)
    assert sampled == 300


def test_a_run_above_the_work_budget_refuses_and_draws_nothing():
    n = 400
    sim = _h_all(n)
    # work = shots * n must exceed the stated budget.
    shots = MAX_RESAMPLE_WORK // n + 10
    with pytest.raises(PathAShotBudgetError, match="budget"):
        sim.sample(shots=shots, seed=3)


def test_an_explicit_cap_truncates_and_is_disclosed():
    sim = StabilizerTableauSimulator(32, max_resample_shots=50)
    for q in range(32):
        sim.apply_h(q)
    counts, sampled = sim.sample(shots=300, seed=4)
    assert sampled == 50
    assert sum(counts.values()) == 50


def test_the_budget_error_is_a_value_error():
    # Callers that already catch ValueError must keep working.
    assert issubclass(PathAShotBudgetError, ValueError)
