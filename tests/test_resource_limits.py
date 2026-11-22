"""Resource-limit contracts: a budget ends in a typed refusal, never partial data (W15 / C5).

Covers the SAT counting/solving budgets, the separator (variable elimination) preflight, ``max_sat_checked``,
and circuit routing at hostile sizes. Defects found here are pinned ``xfail(strict=True)`` with a finding id
from ``research/v7/SECURITY_AUDIT.md``.
"""

from __future__ import annotations

import itertools
import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cqhecs import sat, sat_separator
from cqhecs.router import EntanglementAdaptiveRouter
from cqhecs.sat import CNF, count_models, max_sat_checked, random_3sat, solve

FUZZ = settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    derandomize=True,
)


def _brute_count(n, clauses):
    total = 0
    for bits in itertools.product([False, True], repeat=n):
        if all(any(bits[abs(l) - 1] == (l > 0) for l in c) for c in clauses):
            total += 1
    return total


@st.composite
def small_formulas(draw, max_vars=7):
    n = draw(st.integers(1, max_vars))
    lit = st.integers(1, n).flatmap(lambda v: st.sampled_from([v, -v]))
    clauses = draw(st.lists(st.lists(lit, min_size=1, max_size=4, unique_by=abs), max_size=10))
    return n, [tuple(c) for c in clauses]


# --------------------------------------------------------------------------- separator preflight
@FUZZ
@given(data=small_formulas(), budget=st.integers(1, 64), preflight=st.booleans())
def test_separator_is_exact_or_unknown_never_partial(data, budget, preflight):
    n, clauses = data
    out = sat_separator.count_by_elimination(n, clauses, max_table_entries=budget, preflight=preflight)
    if out["status"] == sat_separator.COUNTED:
        assert out["count"] == _brute_count(n, clauses)
    else:
        assert out["status"] == sat_separator.UNKNOWN
        assert out["count"] is None
        assert out.get("reason")


def test_preflight_refuses_before_allocating_any_table():
    formula = random_3sat(60, 255, seed=7)
    out = sat_separator.count_by_elimination(
        formula.num_vars, formula.clauses, max_table_entries=1024, preflight=True
    )
    assert out["status"] == sat_separator.UNKNOWN and out["count"] is None
    assert out["max_table"] == 0  # nothing was materialised
    assert out["predicted_table_bound"] > 1024
    assert "preflight" in out["reason"]


def test_count_models_separator_refuses_a_wide_formula_without_a_partial_count():
    formula = random_3sat(70, 298, seed=11)
    out = count_models(formula, timeout_seconds=5, method="separator", separator_max_table_entries=2048)
    assert out["status"] == "UNKNOWN"
    assert out["count"] is None


@pytest.mark.parametrize("method", ["dpll", "separator", "auto"])
def test_count_models_timeout_is_unknown_with_no_count(method):
    formula = random_3sat(90, 380, seed=3)
    out = count_models(formula, timeout_seconds=0.05, method=method, separator_max_table_entries=4096)
    assert out["status"] == "UNKNOWN"
    assert out["count"] is None


def test_count_models_rejects_bad_arguments():
    f = CNF(num_vars=2, clauses=((1, 2),))
    with pytest.raises(ValueError):
        count_models(f, method="nope")
    with pytest.raises(ValueError):
        count_models(f, timeout_seconds=0)


# --------------------------------------------------------------------------- SAT budgets
def test_solve_timeout_is_unknown_with_no_model():
    formula = random_3sat(150, 639, seed=5)
    result = solve(formula, timeout_seconds=0.05)
    assert result.status == "UNKNOWN"
    assert result.assignment is None and not result.certified and not result.model_verified


def test_solve_node_budget_is_unknown_with_no_model():
    formula = random_3sat(120, 511, seed=9)
    result = solve(formula, timeout_seconds=20, node_budget=5)
    assert result.status == "UNKNOWN" and result.assignment is None


# --------------------------------------------------------------------------- max_sat_checked
def test_max_sat_above_limit_is_unknown_without_optimum():
    formula = random_3sat(25, 100, seed=1)
    out = max_sat_checked(formula, max_vars=20)
    assert out["status"] == "UNKNOWN" and out["limit_reached"] is True
    assert out["assignment"] is None and out["satisfied_weight"] is None
    assert out["optimality_certificate"] is None and out["trust"] == "NONE"


def test_max_sat_limit_boundary_is_inclusive():
    f = random_3sat(6, 12, seed=2)
    assert max_sat_checked(f, max_vars=6)["status"] == "OPTIMAL"
    assert max_sat_checked(f, max_vars=5)["status"] == "UNKNOWN"


@pytest.mark.parametrize("weights", [[-1.0, 1.0], [float("nan"), 1.0], [1.0], [1.0, 1.0, 1.0]])
def test_max_sat_rejects_bad_weights(weights):
    f = CNF(num_vars=2, clauses=((1,), (-1, 2)))
    with pytest.raises(ValueError):
        max_sat_checked(f, weights)


@FUZZ
@given(data=small_formulas(max_vars=6), seed=st.integers(0, 10**6))
def test_max_sat_optimum_matches_brute_force(data, seed):
    n, clauses = data
    rnd = random.Random(seed)
    weights = [float(rnd.randint(1, 5)) for _ in clauses]
    out = max_sat_checked(CNF(num_vars=n, clauses=tuple(clauses)), weights, max_vars=8)
    best = 0.0
    for bits in itertools.product([False, True], repeat=n):
        best = max(best, sum(w for c, w in zip(clauses, weights) if any(bits[abs(l) - 1] == (l > 0) for l in c)))
    assert out["status"] == "OPTIMAL"
    assert out["satisfied_weight"] == pytest.approx(best)
    # the reported assignment really achieves the reported weight
    a = out["assignment"]
    got = sum(w for c, w in zip(clauses, weights) if any(a[abs(l)] == (l > 0) for l in c))
    assert got == pytest.approx(out["satisfied_weight"])


# --------------------------------------------------------------------------- circuits
def _dense(n, depth, seed=1):
    rnd = random.Random(seed)
    ins = []
    for _ in range(depth):
        ins += [("rx", [q], [rnd.random() * 3]) for q in range(n)]
        order = list(range(n))
        rnd.shuffle(order)
        ins += [("cx", [order[i], order[i + 1]], []) for i in range(0, n - 1, 2)]
    return ins


def test_unresolved_circuit_carries_no_counts_probabilities_or_state():
    result = EntanglementAdaptiveRouter().route_and_execute(_dense(60, 20), shots=16, seed=1)
    if result.state.value != "UNRESOLVED":
        pytest.skip("host resolved the circuit; the property is about the refusal path")
    d = result.to_dict()
    assert d["unresolved"] is True
    assert not d["counts"] and d["probabilities"] is None
    assert d["metadata"].get("reason")


def test_forced_path_that_cannot_run_raises_instead_of_rerouting():
    from cqhecs.router import UnsupportedCircuitError

    with pytest.raises(UnsupportedCircuitError):
        EntanglementAdaptiveRouter().route_and_execute(_dense(30, 4), shots=8, seed=1, preferred_path="B")


@pytest.mark.parametrize("shots", [0, -1])
def test_non_positive_shots_are_refused(shots):
    with pytest.raises(ValueError):
        EntanglementAdaptiveRouter().route_and_execute(_dense(2, 1), shots=shots, seed=1)


# --------------------------------------------------------------------------- fixed defects (formerly strict xfail)
def test_formula_declaring_an_absurd_variable_count_is_a_typed_refusal():
    """SEC-M1: refused on the header, before the solver allocates anything."""
    for header in ("p cnf 10000000000000 0\n", f"p cnf {sat.MAX_DIMACS_VARS + 1} 0\n"):
        with pytest.raises(sat.CNFFormatError):
            sat.parse_dimacs(header)
    # the cap itself is accepted (header only: no allocation is done here)
    assert sat.parse_dimacs(f"p cnf {sat.MAX_DIMACS_VARS} 0\n").num_vars == sat.MAX_DIMACS_VARS


def test_count_too_large_to_serialise_is_typed():
    """SEC-L5: a count over 4300 digits is an exact decimal string, not a ValueError."""
    formula = sat.parse_dimacs("p cnf 20000 1\n1 0\n")
    out = count_models(formula, timeout_seconds=5)
    assert out["status"] == "COUNTED"
    assert isinstance(out["count"], str) and out["count"].isdigit()
    import decimal

    assert len(out["count"]) > 4300  # really beyond the int<->str limit
    assert decimal.Decimal(out["count"]) == decimal.Decimal(1 << 19999)  # exact: Decimal(int) is not rounded


def test_int_to_decimal_string_is_exact_beyond_the_conversion_limit():
    import decimal

    for exponent in (0, 10, 11_999, 12_000, 20_000, 100_000):
        value = (1 << exponent) + 7
        text = sat.int_to_decimal_string(value)
        assert text.isdigit() and decimal.Decimal(text) == decimal.Decimal(value)
