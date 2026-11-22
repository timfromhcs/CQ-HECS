"""Model enumeration and exact MaxSAT contracts, cross-checked by brute force."""

from __future__ import annotations

import itertools

import pytest

from cqhecs.sat import CNF, enumerate_models, max_sat, parse_dimacs, random_3sat


def _brute_force_models(formula: CNF):
    models = set()
    for bits in itertools.product((False, True), repeat=formula.num_vars):
        assignment = {var: bits[var - 1] for var in range(1, formula.num_vars + 1)}
        if formula.is_satisfied(assignment):
            models.add(tuple(sorted(assignment.items())))
    return models


def _brute_force_max_weight(formula: CNF, weights):
    best = -1.0
    for bits in itertools.product((False, True), repeat=formula.num_vars):
        score = sum(
            weight
            for clause, weight in zip(formula.clauses, weights)
            if any(bits[abs(lit) - 1] == (lit > 0) for lit in clause)
        )
        best = max(best, score)
    return best


# (x1 or x2) and (x3 or not x3): 3 models on x1/x2 times 2 on x3 = 6 models.
SIX_MODELS = "p cnf 3 2\n1 2 0\n3 -3 0\n"


def test_complete_enumeration_matches_brute_force():
    formula = parse_dimacs(SIX_MODELS)
    result = enumerate_models(formula, limit=100, timeout_seconds=10)
    assert result["status"] == "COMPLETE"
    assert result["complete"] is True
    assert result["count"] == 6
    found = {tuple(sorted(model.items())) for model in result["models"]}
    assert found == _brute_force_models(formula)
    assert all(formula.is_satisfied(model) for model in result["models"])


def test_limit_is_reported_and_not_complete():
    result = enumerate_models(parse_dimacs(SIX_MODELS), limit=4, timeout_seconds=10)
    assert result["status"] == "LIMIT"
    assert result["complete"] is False
    assert result["count"] == 4
    assert len({tuple(sorted(m.items())) for m in result["models"]}) == 4


def test_unsat_formula_is_complete_with_zero_models():
    result = enumerate_models(parse_dimacs("p cnf 1 2\n1 0\n-1 0\n"), limit=5)
    assert result["status"] == "COMPLETE"
    assert result["count"] == 0


def test_zero_limit_is_refused():
    with pytest.raises(ValueError):
        enumerate_models(parse_dimacs(SIX_MODELS), limit=0)


@pytest.mark.parametrize("seed", range(25))
def test_random_enumeration_counts_agree_with_brute_force(seed):
    formula = random_3sat(6, 18, seed=seed)
    result = enumerate_models(formula, limit=1 << 6, timeout_seconds=10)
    assert result["status"] == "COMPLETE"
    found = {tuple(sorted(model.items())) for model in result["models"]}
    assert found == _brute_force_models(formula)


def test_weighted_max_sat_optimum():
    # x1 and not x1 conflict; weight decides which side wins.
    formula = parse_dimacs("p cnf 2 3\n1 0\n-1 0\n2 0\n")
    result = max_sat(formula, [1.0, 5.0, 2.0])
    assert result["status"] == "OPTIMAL"
    assert result["satisfied_weight"] == 7.0
    assert result["total_weight"] == 8.0
    assert result["assignment"][1] is False and result["assignment"][2] is True
    assert result["unsatisfied_clauses"] == [0]


@pytest.mark.parametrize("seed", range(10))
def test_max_sat_matches_brute_force_on_overconstrained_formulas(seed):
    formula = random_3sat(7, 60, seed=seed)
    weights = [1.0 + (index * 7 + seed) % 5 for index in range(formula.num_clauses)]
    result = max_sat(formula, weights)
    assert result["satisfied_weight"] == pytest.approx(_brute_force_max_weight(formula, weights))


def test_max_sat_refuses_large_instances_and_bad_weights():
    with pytest.raises(ValueError, match="limited to 20 variables"):
        max_sat(random_3sat(21, 40, seed=1))
    formula = parse_dimacs(SIX_MODELS)
    with pytest.raises(ValueError):
        max_sat(formula, [1.0])
    with pytest.raises(ValueError):
        max_sat(formula, [1.0, -1.0])


# --- typed MaxSAT contract (limit is never an optimum) --------------------------
from cqhecs.sat import MAXSAT_CONTRACT, max_sat_checked  # noqa: E402


def test_max_sat_checked_optimal_matches_max_sat_and_is_uncertified():
    formula = parse_dimacs("p cnf 2 3\n1 0\n-1 0\n2 0\n")
    got = max_sat_checked(formula, [1.0, 5.0, 2.0])
    ref = max_sat(formula, [1.0, 5.0, 2.0])
    assert got["status"] == "OPTIMAL" and got["contract"] == MAXSAT_CONTRACT
    assert got["satisfied_weight"] == ref["satisfied_weight"] == 7.0
    assert got["optimality_certificate"] is None
    assert got["trust"] == "EXHAUSTIVE_ENUMERATION_REVERIFIED"


def test_max_sat_checked_limit_is_unknown_not_optimal_and_does_not_raise():
    got = max_sat_checked(random_3sat(21, 40, seed=1))
    assert got["status"] == "UNKNOWN" and got["limit_reached"] is True
    assert got["satisfied_weight"] is None and got["assignment"] is None
    assert got["trust"] == "NONE" and "no optimum is claimed" in got["reason"]
    raised = False
    try:
        max_sat(random_3sat(21, 40, seed=1))
    except ValueError:
        raised = True
    assert raised


def test_max_sat_checked_raises_only_on_malformed_weights():
    formula = parse_dimacs("p cnf 1 2\n1 0\n-1 0\n")
    with pytest.raises(ValueError):
        max_sat_checked(formula, [1.0])
    with pytest.raises(ValueError):
        max_sat_checked(formula, [1.0, -1.0])
    with pytest.raises(ValueError):
        max_sat_checked(formula, [1.0, float("nan")])


@pytest.mark.parametrize("seed", range(20))
def test_max_sat_checked_agrees_with_brute_force(seed):
    formula = random_3sat(6, 30, seed=seed)
    got = max_sat_checked(formula)
    best = 0
    for bits in range(1 << 6):
        a = {v: bool((bits >> (v - 1)) & 1) for v in range(1, 7)}
        best = max(best, sum(any(a[abs(l)] == (l > 0) for l in c) for c in formula.clauses))
    assert got["status"] == "OPTIMAL" and got["satisfied_weight"] == best
