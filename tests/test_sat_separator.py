"""Exact variable-elimination #SAT: oracles, refusal semantics and integration."""

from __future__ import annotations

import itertools
import json
import random
import time

import pytest

from cqhecs import sat_separator as sep
from cqhecs.sat import (
    AUTO_SEPARATOR_MAX_WIDTH,
    CNF,
    COUNT_METHODS,
    count_models,
    random_3sat,
)


def brute(num_vars, clauses):
    total = 0
    for bits in itertools.product((False, True), repeat=num_vars):
        if all(
            any(bits[abs(lit) - 1] == (lit > 0) for lit in clause) for clause in clauses
        ):
            total += 1
    return total


def _all_clauses(n):
    """Every non-empty clause over n variables (tautologies included)."""
    out = []
    for signs in itertools.product((0, 1, -1), repeat=n):
        lits = tuple((i + 1) * s for i, s in enumerate(signs) if s)
        if lits:
            out.append(lits)
    return out


def test_exhaustive_all_small_formulas_over_three_variables():
    """Every formula with <= 3 clauses drawn from all 26 clauses over 3 vars."""
    n = 3
    pool = _all_clauses(n)
    checked = 0
    for size in range(4):
        for combo in itertools.combinations(pool, size):
            expected = brute(n, combo)
            got = sep.count_by_elimination(n, combo)
            assert got["status"] == sep.COUNTED
            assert got["count"] == expected, combo
            checked += 1
    assert checked == 1 + 26 + 325 + 2600


@pytest.mark.parametrize("seed", range(300))
def test_random_formulas_match_brute_force_and_dpll(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 11)
    clauses = []
    for _ in range(rng.randint(0, 3 * n)):
        k = rng.randint(1, min(4, n))
        variables = rng.sample(range(1, n + 1), k)
        clauses.append(tuple(v if rng.random() < 0.5 else -v for v in variables))
    formula = CNF(num_vars=n, clauses=tuple(clauses))
    expected = brute(n, clauses)
    for method in COUNT_METHODS:
        result = count_models(formula, method=method)
        assert result["status"] == "COUNTED"
        assert result["count"] == str(expected), (method, clauses)
        assert result["satisfiable"] == (expected > 0)


def test_free_variables_tautologies_duplicates_and_empty_formula():
    # x3, x4 are free; (1 or -1) is a tautology; (1,2) appears twice.
    formula = CNF(num_vars=4, clauses=((1, 2), (1, 2), (3, -3), (1, -1)))
    assert count_models(formula, method="separator")["count"] == str(3 * 4)
    assert count_models(CNF(num_vars=0, clauses=()), method="separator")["count"] == "1"
    assert count_models(CNF(num_vars=7, clauses=()), method="separator")["count"] == "128"
    assert count_models(CNF(num_vars=3, clauses=((),)), method="separator")["count"] == "0"
    # Variable that only occurs in a tautology is free, not constrained.
    only_taut = CNF(num_vars=2, clauses=((1, -1),))
    assert count_models(only_taut, method="separator")["count"] == "4"


def test_unsatisfiable_formula_counts_zero():
    formula = CNF(num_vars=2, clauses=((1,), (-1,), (2, 1)))
    assert count_models(formula, method="separator")["count"] == "0"
    assert count_models(formula, method="separator")["satisfiable"] is False


def test_disconnected_components_multiply_exactly():
    # Two independent XOR-ish pairs plus 3 free variables.
    clauses = ((1, 2), (-1, -2), (3, 4), (-3, -4))
    formula = CNF(num_vars=7, clauses=clauses)
    assert count_models(formula, method="separator")["count"] == str(2 * 2 * 8)


def test_big_count_survives_json_as_decimal_string():
    formula = CNF(num_vars=200, clauses=((1, 2),))
    result = count_models(formula, method="separator")
    assert result["count"] == str(3 * 2 ** 198)
    assert int(result["count"]) > 2 ** 53
    assert json.loads(json.dumps(result))["count"] == result["count"]


def test_chain_is_low_width_and_matches_fibonacci():
    n = 60
    formula = CNF(num_vars=n, clauses=tuple((i, i + 1) for i in range(1, n)))
    result = count_models(formula, method="separator")
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    assert result["count"] == str(b)
    assert result["induced_width"] == 1
    assert result["max_table"] <= 4


def test_table_budget_returns_unknown_never_a_partial_count():
    formula = CNF(num_vars=20, clauses=((1, 2, 3, 4, 5, 6, 7, 8, 9, 10),))
    result = count_models(formula, method="separator", separator_max_table_entries=8)
    assert result["status"] == "UNKNOWN"
    assert result["count"] is None and result["satisfiable"] is None
    assert "no count claimed" in result["note"]
    # The same formula is fine with a sufficient budget and agrees with DPLL.
    ok = count_models(formula, method="separator")
    assert ok["count"] == count_models(formula)["count"]


def test_deadline_returns_unknown():
    formula = random_3sat(60, 120, seed=3)
    result = count_models(formula, timeout_seconds=1e-6, method="separator")
    assert result["status"] == "UNKNOWN" and result["count"] is None


def test_high_width_formula_is_refused_by_auto_then_counted_by_dpll():
    formula = random_3sat(40, 160, seed=1)
    start = time.perf_counter()
    result = count_models(formula, timeout_seconds=60, method="auto")
    assert result["status"] == "COUNTED"
    assert result["backend"] == "dpll"
    refusal = result["auto_separator"]
    assert refusal["attempted"] and refusal["outcome"] == "refused"
    assert refusal["induced_width"] > AUTO_SEPARATOR_MAX_WIDTH
    assert result["count"] == count_models(formula)["count"]
    assert time.perf_counter() - start < 60


def test_auto_uses_separator_for_low_width_and_reports_backend():
    formula = CNF(num_vars=30, clauses=tuple((i, i + 1) for i in range(1, 30)))
    assert count_models(formula, method="auto")["backend"] == "separator"
    assert count_models(formula)["backend"] == "dpll"  # default is unchanged


def test_default_method_is_still_dpll_and_invalid_method_rejected():
    formula = CNF(num_vars=3, clauses=((1, 2),))
    default = count_models(formula)
    assert default["backend"] == "dpll"
    assert default["method"] == "exact (DPLL counting, components, cache)"
    with pytest.raises(ValueError):
        count_models(formula, method="magic")


def test_elimination_plan_is_deterministic_and_allocates_no_tables():
    clauses = [frozenset(c) for c in ((1, 2, 3), (3, 4), (4, 5, -1), (6, 7))]
    first = sep.plan_elimination(8, clauses)
    second = sep.plan_elimination(8, clauses)
    assert first == second
    assert sorted(first.order) == [1, 2, 3, 4, 5, 6, 7]
    assert first.num_free_variables == 1
    assert first.table_entries_upper_bound == 1 << (first.induced_width + 1)


def test_invalid_arguments_are_rejected():
    with pytest.raises(ValueError):
        sep.count_by_elimination(-1, [])
    with pytest.raises(ValueError):
        sep.count_by_elimination(3, [(1, 2)], max_table_entries=0)
    with pytest.raises(ValueError):
        sep.count_by_elimination(2, [(1, 3)])
    with pytest.raises(ValueError):
        sep.count_by_elimination(2, [(0, 1)])


def test_mutated_join_is_detected_by_the_oracle():
    """A wrong shared-variable check must change at least one count."""
    original = sep._join

    def broken(left, right, max_table, deadline):
        lscope, ltable = left
        rscope, rtable = right
        out = {}
        for lm, lw in ltable.items():
            for rm, rw in rtable.items():  # ignores the shared-variable agreement
                out[lm | rm] = out.get(lm | rm, 0) + lw * rw
        return lscope | rscope, out

    sep._join = broken
    try:
        wrong = sep.count_by_elimination(3, [(1, 2), (2, 3), (-1, -3)])["count"]
    finally:
        sep._join = original
    assert wrong != brute(3, [(1, 2), (2, 3), (-1, -3)])


def test_dpll_counter_refuses_deep_recursion_instead_of_crashing():
    """Regression: deep chains raised an uncaught RecursionError in v3.7.0."""
    import inspect
    import sys

    n = 400
    formula = CNF(num_vars=n, clauses=tuple((i, i + 1) for i in range(1, n)))
    old_limit = sys.getrecursionlimit()
    # Lower the limit so the test is fast and independent of the host default.
    sys.setrecursionlimit(len(inspect.stack()) + 150)
    try:
        result = count_models(formula, timeout_seconds=30)  # default dpll backend
    finally:
        sys.setrecursionlimit(old_limit)
    assert result["status"] == "UNKNOWN"
    assert result["count"] is None and result["satisfiable"] is None
    assert "recursion" in result["note"]
    # The elimination backend decides the same formula exactly.
    exact = count_models(formula, timeout_seconds=30, method="separator")
    assert exact["status"] == "COUNTED"
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    assert exact["count"] == str(b)
    auto = count_models(formula, timeout_seconds=30, method="auto")
    assert auto["status"] == "COUNTED" and auto["count"] == exact["count"]


CNF_TEXT = "p cnf 4 3\n1 2 0\n-2 3 0\n3 4 0\n"


def test_cli_mcp_studio_accept_the_method_and_agree_on_the_count():
    import subprocess
    import sys
    from pathlib import Path

    from cqhecs import mcp_server
    from cqhecs.studio import StudioState
    from cqhecs.studio.app import StudioError

    root = Path(__file__).parent.parent
    expected = count_models(
        __import__("cqhecs.sat", fromlist=["parse_dimacs"]).parse_dimacs(CNF_TEXT)
    )["count"]

    cli = subprocess.run(
        [sys.executable, "-m", "cqhecs.cli", "--format", "json", "sat", "count",
         "--cnf", CNF_TEXT, "--method", "separator"],
        capture_output=True, text=True, cwd=root, timeout=120,
    )
    assert cli.returncode == 0, cli.stderr
    cli_result = json.loads(cli.stdout)["result"]
    assert cli_result["backend"] == "separator" and cli_result["count"] == expected

    mcp = mcp_server.handle({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "cqhecs_sat_count",
                   "arguments": {"cnf": CNF_TEXT, "method": "auto"}},
    })
    text = mcp["result"]["content"][0]["text"]
    assert json.loads(text)["result"]["count"] == expected

    state = StudioState(root)
    studio = state.sat_count({"cnf": CNF_TEXT, "method": "separator"})
    assert studio["result"]["count"] == expected
    with pytest.raises(StudioError):
        state.sat_count({"cnf": CNF_TEXT, "method": "nope"})
