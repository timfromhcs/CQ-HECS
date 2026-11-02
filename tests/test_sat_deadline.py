"""The solve budget has to be a real budget, not a marker between search nodes.

`_DPLL.search()` checks the deadline every 1024 nodes. That is fine for a search
that branches, and useless for an instance that never decides: one call to
``_propagate()`` scans the whole formula, repeatedly, and on a large reduced-SHA
instance that single call ran for minutes inside a 45 s budget (measured; see
``research/sha_forge/SAT_SHA.md`` §4). These tests pin the fix: the deadline is
also checked inside propagation and in the branching heuristic, so the overshoot
is bounded by one pass over the formula.

The instances here are deliberately boring — random 3-SAT with no units at all —
because that is the shape that defeated the node-level check: no decisions, lots
of clauses, one long pass.
"""
import random
import time

import pytest

from cqhecs import sat

TIMEOUT_S = 0.2
# Generous: the fix needs about one clause pass plus one heuristic pass. The
# pre-fix behaviour was two orders of magnitude larger (a full 1024-node window,
# each node scanning every clause), so this bound separates the two cleanly
# without being timing-flaky on a loaded machine.
MAX_OVERSHOOT_S = 2.0


def wide_formula(num_vars: int = 60_000, clauses: int = 90_000, seed: int = 20261102) -> sat.CNF:
    rng = random.Random(seed)
    built = []
    for _ in range(clauses):
        a, b, c = rng.sample(range(1, num_vars + 1), 3)
        built.append((a, -b, c))
    return sat.CNF(num_vars=num_vars, clauses=tuple(built))


@pytest.mark.parametrize("propagation", ["scan", "watched"])
def test_timeout_is_enforced_inside_propagation(propagation):
    formula = wide_formula()
    started = time.perf_counter()
    result = sat.solve(formula, timeout_seconds=TIMEOUT_S, certify=False, propagation=propagation)
    elapsed = time.perf_counter() - started

    assert result.status == sat.UNKNOWN, f"{propagation}: expected UNKNOWN, got {result.status}"
    assert "timeout" in result.note.lower(), f"{propagation}: note does not name the timeout: {result.note!r}"
    assert elapsed < MAX_OVERSHOOT_S, (
        f"{propagation}: a {TIMEOUT_S}s budget took {elapsed:.2f}s; the deadline is not enforced inside propagation"
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
