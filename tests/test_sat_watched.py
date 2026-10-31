"""Two-watched-literal propagation: differential and edge-case tests.

The watched engine must agree with the scan-based reference engine on every
formula, preserve the same search order, and keep the UNSAT certificate path
independent of the propagation data structure.
"""

from __future__ import annotations

import itertools

import pytest

from cqhecs.sat import (
    CNF,
    SAT,
    UNKNOWN,
    UNSAT,
    check_refutation,
    parse_dimacs,
    random_3sat,
    solve,
)


def _brute_force(formula: CNF) -> bool:
    for values in itertools.product((False, True), repeat=formula.num_vars):
        assignment = {index + 1: value for index, value in enumerate(values)}
        if formula.is_satisfied(assignment):
            return True
    return False


@pytest.mark.parametrize("seed", range(120))
def test_watched_matches_scan_and_brute_force(seed):
    num_vars = 1 + seed % 7
    ratio = (0.5, 1.0, 2.0, 3.0, 4.26, 6.0)[seed % 6]
    formula = random_3sat(max(3, num_vars), int(round(ratio * max(3, num_vars))), seed=seed)
    expected = _brute_force(formula)
    scanned = solve(formula, timeout_seconds=5.0, certify=False)
    watched = solve(formula, timeout_seconds=5.0, certify=False, propagation="watched")
    assert scanned.status in (SAT, UNSAT)
    assert watched.status == scanned.status
    assert (watched.status == SAT) is expected
    if watched.status == SAT:
        assert watched.model_verified
        assert formula.is_satisfied(watched.assignment)
    assert watched.engine == "dpll-watched"


def test_watched_unsat_certificate_is_independently_checked():
    result = solve(
        parse_dimacs("p cnf 2 4\n1 2 0\n-1 2 0\n1 -2 0\n-1 -2 0\n"),
        timeout_seconds=5.0,
        propagation="watched",
    )
    assert result.status == UNSAT
    assert result.certified
    assert result.certificate is not None
    assert check_refutation(
        ((1, 2), (-1, 2), (1, -2), (-1, -2)), result.certificate
    )
    # The checker must reject a certificate for a different formula.
    assert not check_refutation(((1, 2),), result.certificate)


def test_watched_pigeonhole_matches_reference():
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "benchmarks" / "sat" / "pigeonhole_6_5.cnf"
    formula = parse_dimacs(path.read_text("utf-8"))
    watched = solve(formula, timeout_seconds=10.0, propagation="watched")
    assert watched.status == UNSAT
    assert watched.certified
    assert watched.conflicts > 0
    assert watched.propagations > 0
    assert watched.nodes > 0
    assert check_refutation(formula.clauses, watched.certificate)


@pytest.mark.parametrize(
    "text",
    [
        "p cnf 0 0\n",
        "p cnf 1 1\n1 0\n",
        "p cnf 1 2\n1 0\n-1 0\n",
        "p cnf 2 1\n0\n",
        "p cnf 2 1\n1 -1 0\n",
        "p cnf 3 2\n1 2 0\n2 3 0\n",
        "p cnf 4 4\n1 2 0\n-2 3 0\n-3 4 0\n-4 -1 0\n",
    ],
)
def test_watched_edge_cases(text):
    formula = parse_dimacs(text)
    scanned = solve(formula, timeout_seconds=5.0, certify=False)
    watched = solve(formula, timeout_seconds=5.0, certify=False, propagation="watched")
    assert watched.status == scanned.status
    if watched.status == SAT:
        assert watched.model_verified
        assert formula.is_satisfied(watched.assignment)


def test_watched_node_budget_is_unknown_not_unsat():
    formula = random_3sat(20, 100, seed=13)
    result = solve(formula, timeout_seconds=5.0, node_budget=1, propagation="watched")
    assert result.status == UNKNOWN
    assert result.assignment is None
    assert "node budget" in result.note


def test_watched_determinism():
    formula = random_3sat(25, 110, seed=11)
    first = solve(formula, timeout_seconds=5.0, certify=False, propagation="watched")
    second = solve(formula, timeout_seconds=5.0, certify=False, propagation="watched")
    assert first.status == second.status
    assert first.decisions == second.decisions
    assert first.propagations == second.propagations
    assert first.nodes == second.nodes


def test_watched_rejects_unknown_propagation_name():
    with pytest.raises(ValueError, match="propagation"):
        solve(parse_dimacs("p cnf 1 1\n1 0\n"), propagation="magic")


def test_partial_assignment_does_not_satisfy_negative_literal():
    formula = parse_dimacs("p cnf 1 1\n-1 0\n")
    assert formula.is_satisfied({}) is False
    assert formula.is_satisfied({1: True}) is False
    assert formula.is_satisfied({1: False}) is True
    assert formula.first_unsatisfied({}) == 0
    assert formula.first_unsatisfied({1: False}) is None


def test_watched_conflict_on_initial_units_and_empty_clause():
    assert parse_dimacs("p cnf 2 1\n1 1 0\n").clauses == ((1,),)
    assert solve(parse_dimacs("p cnf 2 2\n1 0\n-1 0\n"), propagation="watched").status == UNSAT
    assert solve(parse_dimacs("p cnf 2 1\n0\n"), propagation="watched").status == UNSAT
