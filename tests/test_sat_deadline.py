"""The solve budget has to be a real budget, not a marker between search nodes.

`_DPLL.search()` checks the deadline every 1024 nodes. That is fine for a search
that branches, and useless for an instance that never decides: one call to
``_propagate()`` scans the whole formula, repeatedly, and on a large reduced-SHA
instance that single call ran for minutes inside a 45 s budget (measured; see
``research/sha_forge/SAT_SHA.md`` section 4). These tests pin the fix: the deadline
is also checked inside propagation and in the branching heuristic.

The first version of this file asserted that a large formula "cannot be decided in
0.2 s". That is a statement about machine speed, not about the code, and a faster
CI runner solved the instance as SAT - the test failed for the wrong reason. The
regression test below therefore uses an **already expired budget**: no engine can
return anything but UNKNOWN, and the only question is whether it returns after one
clause pass or after the whole 1024-node window.
"""
import random
import time

import pytest

from cqhecs import sat

# Generous: one pass over ~90k clauses is milliseconds to tens of milliseconds.
# The pre-fix behaviour was a full 1024-node window, each node scanning every
# clause, which is minutes. The gap is three orders of magnitude, so this bound
# does not depend on the runner.
MAX_OVERSHOOT_S = 2.0

# ``solve()`` rejects a budget of exactly zero ("timeout_seconds must be > 0"), so
# the expired-budget case uses one microsecond: the deadline is in the past long
# before the first propagation pass can look at it.
EXPIRED_BUDGET_S = 1e-6


def wide_formula(num_vars: int = 60_000, clauses: int = 90_000, seed: int = 20261102) -> sat.CNF:
    """No unit clauses at all: the instance is decided by search or not at all."""
    rng = random.Random(seed)
    built = []
    for _ in range(clauses):
        a, b, c = rng.sample(range(1, num_vars + 1), 3)
        built.append((a, -b, c))
    return sat.CNF(num_vars=num_vars, clauses=tuple(built))


@pytest.mark.parametrize("propagation", ["scan", "watched"])
def test_an_expired_budget_stops_the_first_propagation(propagation):
    """The bug: with a budget of zero the old code still propagated, then searched
    up to 1024 nodes. Nothing may be decided once the budget is gone."""
    formula = wide_formula()
    started = time.perf_counter()
    result = sat.solve(formula, timeout_seconds=EXPIRED_BUDGET_S, certify=False, propagation=propagation)
    elapsed = time.perf_counter() - started

    assert result.status == sat.UNKNOWN, f"{propagation}: a spent budget must not decide anything"
    assert "timeout" in result.note.lower(), f"{propagation}: note does not name the timeout: {result.note!r}"
    assert elapsed < MAX_OVERSHOOT_S, (
        f"{propagation}: a zero budget took {elapsed:.2f}s; the deadline is not checked inside propagation"
    )


def _pigeonhole(pigeons: int, holes: int):
    """PHP(pigeons, holes) with pigeons > holes: UNSAT, and it needs decisions."""

    def var(p: int, h: int) -> int:
        return p * holes + h + 1

    clauses = [tuple(var(p, h) for h in range(holes)) for p in range(pigeons)]
    for h in range(holes):
        for p1 in range(pigeons):
            for p2 in range(p1 + 1, pigeons):
                clauses.append((-var(p1, h), -var(p2, h)))
    return sat.CNF(num_vars=pigeons * holes, clauses=tuple(clauses))


@pytest.mark.parametrize("propagation", ["scan", "watched"])
def test_a_small_budget_is_respected_on_a_hard_instance(propagation):
    """A real (non-zero) budget on an instance that genuinely needs search."""
    formula = _pigeonhole(9, 8)
    started = time.perf_counter()
    result = sat.solve(formula, timeout_seconds=0.3, certify=False, propagation=propagation)
    elapsed = time.perf_counter() - started
    assert result.status == sat.UNKNOWN
    assert elapsed < 4 * 0.3 + MAX_OVERSHOOT_S


def test_node_budget_still_wins_over_the_clock():
    """A node budget must still stop the search without waiting for the clock."""
    formula = _pigeonhole(6, 5)
    started = time.perf_counter()
    result = sat.solve(formula, timeout_seconds=60.0, node_budget=2, certify=False)
    elapsed = time.perf_counter() - started
    assert result.status == sat.UNKNOWN
    assert "node budget" in result.note.lower()
    assert elapsed < 10.0


def test_small_formulas_still_get_decided():
    """The added checks must not change verdicts on instances that do finish."""
    cnf = sat.CNF(num_vars=3, clauses=((1, 2), (-1, 3)))
    result = sat.solve(cnf, timeout_seconds=5.0, certify=False)
    assert result.status == sat.SAT
    assert result.assignment is not None

    contradiction = sat.CNF(num_vars=1, clauses=((1,), (-1,)))
    result = sat.solve(contradiction, timeout_seconds=5.0, certify=False)
    assert result.status == sat.UNSAT

    # A zero budget must not break the trivial answers either: an empty formula is
    # settled before the first clock check matters, and a contradiction is a leaf.
    assert sat.solve(sat.CNF(num_vars=1, clauses=((1,), (-1,))), timeout_seconds=EXPIRED_BUDGET_S, certify=False).status in (
        sat.UNSAT,
        sat.UNKNOWN,
    )
