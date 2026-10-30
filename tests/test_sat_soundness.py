"""Soundness tests for the supported SAT engine (``cqhecs.sat``)."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from cqhecs.sat import (
    CNF,
    CNFFormatError,
    SAT,
    UNKNOWN,
    UNSAT,
    load_dimacs,
    parse_dimacs,
    random_3sat,
    solve,
)


BENCH = Path(__file__).parent.parent / "benchmarks" / "sat"


def brute_force(formula: CNF) -> bool:
    for values in itertools.product((False, True), repeat=formula.num_vars):
        assignment = {index + 1: value for index, value in enumerate(values)}
        if formula.is_satisfied(assignment):
            return True
    return False


def test_random_small_formulas_match_brute_force():
    for num_vars in (3, 4, 5, 6):
        for ratio in (1.0, 2.0, 3.0, 4.26, 6.0):
            for trial in range(8):
                formula = random_3sat(num_vars, max(1, int(round(ratio * num_vars))), seed=1000 * num_vars + trial)
                expected = brute_force(formula)
                result = solve(formula, timeout_seconds=5.0)
                assert result.status in (SAT, UNSAT)
                assert (result.status == SAT) is expected
                if result.status == SAT:
                    assert result.model_verified
                    assert formula.is_satisfied(result.assignment)


def test_pigeonhole_is_unsat_with_checked_certificate():
    result = solve(load_dimacs(BENCH / "pigeonhole_6_5.cnf"), timeout_seconds=10.0)
    assert result.status == UNSAT
    assert result.model_verified is False
    assert result.certified is True
    assert "certificate checked" in result.note


def test_contradictory_units_and_empty_clause():
    assert solve(parse_dimacs("p cnf 2 2\n1 0\n-1 0\n"), 1.0).status == UNSAT
    assert solve(parse_dimacs("p cnf 2 1\n0\n"), 1.0).status == UNSAT
    assert solve(parse_dimacs("p cnf 0 0\n"), 1.0).status == SAT


def test_node_budget_is_unknown_not_unsat():
    formula = load_dimacs(BENCH / "pigeonhole_6_5.cnf")
    result = solve(formula, timeout_seconds=10.0, node_budget=5)
    assert result.status == UNKNOWN
    assert result.assignment is None
    assert "node budget" in result.note


def test_uf50_never_claims_a_false_unsat():
    formula = load_dimacs(BENCH / "uf50_hard.cnf")
    result = solve(formula, timeout_seconds=5.0)
    assert result.status in (SAT, UNSAT, UNKNOWN)
    if result.status == SAT:
        assert result.model_verified
        assert formula.is_satisfied(result.assignment)
    elif result.status == UNSAT:
        assert result.model_verified is False
    else:
        assert result.assignment is None


def test_determinism():
    formula = random_3sat(30, 128, seed=7)
    first = solve(formula, timeout_seconds=5.0)
    second = solve(formula, timeout_seconds=5.0)
    assert first.status == second.status
    assert first.decisions == second.decisions
    assert first.nodes == second.nodes
    assert first.formula_sha256 == second.formula_sha256


@pytest.mark.parametrize(
    "text",
    [
        "1 2 0\n",
        "p cnf 2 3\n1 0\n",
        "p cnf 2 1\n3 0\n",
        "p cnf 2 1\n1 1 0\n",
        "p cnf 2 1\n1 2\n",
    ],
)
def test_malformed_dimacs_is_rejected(text):
    with pytest.raises(CNFFormatError):
        parse_dimacs(text)


def test_enumeration_is_reported_not_hidden():
    result = solve(parse_dimacs("p cnf 3 1\n1 2 3 0\n"), 1.0)
    assert result.status == SAT
    assert len(result.assignment) == 3
