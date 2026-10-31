"""Exhaustive oracle tests for the research separator/bucket #SAT prototype."""

from __future__ import annotations

import importlib.util
import itertools
import random
import sys
from pathlib import Path

import pytest

from cqhecs.sat import CNF, count_models as shipped_count

PATH = Path(__file__).resolve().parent.parent / "research" / "v6" / "prototypes" / "separator_count.py"
spec = importlib.util.spec_from_file_location("separator_count", PATH)
separator = importlib.util.module_from_spec(spec)
sys.modules["separator_count"] = separator
spec.loader.exec_module(separator)


def brute(num_vars: int, clauses) -> int:
    total = 0
    for bits in itertools.product((False, True), repeat=num_vars):
        if all(any(bits[abs(lit) - 1] == (lit > 0) for lit in clause) for clause in clauses):
            total += 1
    return total


@pytest.mark.parametrize("seed", range(200))
def test_bucket_elimination_matches_brute_force(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 10)
    clauses = []
    for _ in range(rng.randint(0, 4 * n)):
        variables = rng.sample(range(1, n + 1), min(3, n))
        clauses.append(tuple(var if rng.random() < 0.5 else -var for var in variables))
    result = separator.count_models(n, clauses)
    assert result["status"] == "COUNTED"
    expected = brute(n, clauses)
    assert result["count"] == expected
    assert int(shipped_count(CNF(n, tuple(clauses)))["count"]) == expected


def test_low_width_chain_stays_small_and_exact():
    clauses = [(i, i + 1) for i in range(1, 40)]
    result = separator.count_models(40, clauses, max_table_entries=16)
    assert result["status"] == "COUNTED"
    first, second = 1, 1
    for _ in range(40):
        first, second = second, first + second
    assert result["count"] == second
    assert result["max_table"] <= 16


def test_table_limit_returns_unknown_not_a_partial_count():
    result = separator.count_models(20, [(1, 2, 3)], max_table_entries=1)
    assert result["status"] == "UNKNOWN"
    assert result["count"] is None


def test_empty_formula_counts_every_assignment():
    result = separator.count_models(5, [])
    assert result["status"] == "COUNTED" and result["count"] == 32


def test_empty_clause_is_zero_without_search():
    result = separator.count_models(5, [()])
    assert result["status"] == "COUNTED" and result["count"] == 0
