"""#SAT contract: exact counts against brute force, big integers, budgets."""

from __future__ import annotations

import itertools
import json

import pytest

from cqhecs.sat import CNF, COUNTED, UNKNOWN, count_models, parse_dimacs, random_3sat


def brute_force_count(formula: CNF) -> int:
    return sum(
        1
        for bits in itertools.product((False, True), repeat=formula.num_vars)
        if formula.is_satisfied({v: bits[v - 1] for v in range(1, formula.num_vars + 1)})
    )


@pytest.mark.parametrize("seed", range(120))
def test_random_counts_match_brute_force(seed):
    n = 4 + seed % 9
    formula = random_3sat(n, 2 + (seed * 7) % (5 * n), seed=seed)
    result = count_models(formula)
    assert result["status"] == COUNTED
    assert int(result["count"]) == brute_force_count(formula)
    assert result["satisfiable"] == (int(result["count"]) > 0)


def test_zero_one_and_all():
    assert count_models(parse_dimacs("p cnf 1 2\n1 0\n-1 0\n"))["count"] == "0"
    assert count_models(parse_dimacs("p cnf 3 3\n1 0\n2 0\n3 0\n"))["count"] == "1"
    assert count_models(parse_dimacs("p cnf 5 0\n"))["count"] == str(2 ** 5)


def test_huge_counts_are_exact_and_survive_json():
    # 200 variables, no constraint on 100 of them, x_i -> x_{i+1} chains on the rest.
    clauses = "".join(f"-{i} {i + 1} 0\n" for i in range(1, 100))
    formula = parse_dimacs(f"p cnf 200 99\n{clauses}")
    result = count_models(formula)
    # A chain of 100 implications has 101 models; 100 free variables multiply by 2^100.
    expected = 101 * 2 ** 100
    assert result["count"] == str(expected)
    assert json.loads(json.dumps(result))["count"] == str(expected)


def test_components_multiply():
    # Two independent (x ∨ y) blocks: 3 * 3 models; plus one free variable.
    formula = parse_dimacs("p cnf 5 2\n1 2 0\n3 4 0\n")
    assert count_models(formula)["count"] == str(3 * 3 * 2)


def test_budget_gives_unknown_never_a_count():
    formula = random_3sat(60, 200, seed=4)
    result = count_models(formula, node_budget=3)
    assert result["status"] == UNKNOWN
    assert result["count"] is None and result["satisfiable"] is None


def test_invalid_timeout_is_refused():
    with pytest.raises(ValueError):
        count_models(parse_dimacs("p cnf 1 1\n1 0\n"), timeout_seconds=0)
