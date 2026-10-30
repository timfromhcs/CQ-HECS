"""UNSAT certificates: tree-resolution refutations replayed by an independent checker."""

from __future__ import annotations

import os

import pytest

from cqhecs.sat import (
    CNF,
    UNKNOWN,
    UNSAT,
    check_refutation,
    enumerate_models,
    random_3sat,
    solve,
    summarize,
)

if os.environ.get("CQ_HECS_REQUIRE_PYSAT") == "1":
    import pysat.solvers as pysat_solvers  # CI must not silently skip the oracle
else:
    pysat_solvers = pytest.importorskip("pysat.solvers")

SQUARE = ((1, 2), (-1, 2), (1, -2), (-1, -2))


def _cadical_sat(clauses):
    with pysat_solvers.Cadical153(bootstrap_with=[list(c) for c in clauses]) as solver:
        return solver.solve()


def test_random_unsat_formulas_get_checked_certificates_matching_cadical():
    unsat_seen = 0
    for seed in range(60):
        n = 5 + seed % 9
        formula = random_3sat(n, int(n * 5.5), seed)
        result = solve(formula, timeout_seconds=10.0)
        reference = _cadical_sat(formula.clauses)
        if result.status == UNSAT:
            unsat_seen += 1
            assert reference is False
            assert result.certified and result.certificate
            assert check_refutation(formula.clauses, result.certificate)
        else:
            assert reference is True and result.satisfiable is True
            assert result.certificate is None and result.certified is False
    assert unsat_seen >= 10


def test_certify_false_leaves_unsat_uncertified():
    result = solve(CNF(2, SQUARE), certify=False)
    assert result.status == UNSAT and not result.certified and result.certificate is None


def test_empty_clause_has_trivial_certificate():
    result = solve(CNF(2, ((1, 2), ())))
    assert result.status == UNSAT and result.certified


def test_checker_rejects_tampered_certificates():
    result = solve(CNF(2, SQUARE))
    steps = list(result.certificate)
    assert check_refutation(SQUARE, steps)
    assert not check_refutation(SQUARE, steps[:-1])  # truncated
    assert not check_refutation(SQUARE, steps + [("leaf", ())])  # extra
    assert not check_refutation(SQUARE, [("leaf", (1,)), ("leaf", (-1,)), ("resolve", 2)])  # wrong pivot
    assert not check_refutation(((1, 2),), [("leaf", ())])  # satisfiable: no conflict at the leaf
    assert not check_refutation(((1,), (-1,)), [("leaf", ()), ("leaf", ()), ("resolve", 1)])
    assert not check_refutation(SQUARE, [("bogus", 1)])
    assert not check_refutation(SQUARE, [])
    assert not check_refutation(SQUARE, None)
    assert not check_refutation(SQUARE, [("resolve", 1)])


def test_checker_rejects_certificate_for_a_different_formula():
    result = solve(CNF(2, SQUARE))
    assert not check_refutation(((1, 2), (-1, 2), (1, -2)), result.certificate)


def test_certificate_json_and_summary():
    result = solve(CNF(2, SQUARE))
    assert result.certificate_to_jsonable()[0][0] == "leaf"
    assert result.to_dict()["certified"] is True
    assert "certificate checked" in summarize(result)
    assert solve(CNF(1, ((1,),))).certificate_to_jsonable() is None


def test_certificate_budget_leaves_unsat_exhaustive_but_uncertified():
    formula = random_3sat(14, 77, 3)
    base = solve(formula, certify=False)
    if base.status != UNSAT:
        pytest.skip("seed no longer UNSAT")
    result = solve(formula, certificate_timeout_seconds=1e-9)
    assert result.status in (UNSAT, UNKNOWN)
    if result.status == UNSAT:
        assert not result.certified or check_refutation(formula.clauses, result.certificate)


def test_models_completeness_is_certified():
    payload = enumerate_models(CNF(2, ((1, 2),)), limit=10)
    assert payload["complete"] and payload["count"] == 3 and payload["complete_certified"]
