"""The unified solving surface: one contract, four engines, one evidence record.

What these tests protect is not speed - it is that combining engines cannot create a
claim. A SAT model must survive the portfolio's own re-verification against the original
CNF, an UNSAT proof status is copied and never upgraded, a missing optional backend is
reported as unavailable instead of being skipped, and the outcome does not depend on
anything but the declared order and the declared budget.
"""
import json

import pytest

from cqhecs import sat, unified
from cqhecs.sat import CNF, SAT, UNKNOWN, UNSAT


def sat_formula() -> CNF:
    return CNF(num_vars=4, clauses=((1, 2), (-1, 3), (-2, -3), (3, 4), (-4, 2)))


def unsat_formula() -> CNF:
    return CNF(num_vars=2, clauses=((1, 2), (1, -2), (-1, 2), (-1, -2)))


# ------------------------------------------------------------------ capability

def test_capabilities_report_every_engine_and_its_proof_kind():
    caps = {entry.name: entry for entry in unified.capabilities()}
    assert set(caps) == {"watched", "omniwave", "cadical", "scan"}
    assert caps["omniwave"].proof.startswith("DRAT")
    assert caps["scan"].proof.startswith("tree-resolution")
    assert caps["cadical"].requires == "python-sat"
    # CaDiCaL is optional: availability must reflect the installation, not a wish.
    from cqhecs import sat_external

    assert caps["cadical"].available == sat_external.available()


# --------------------------------------------------------------------- budgets

def test_budget_split_sums_to_the_total():
    for total in (1.0, 10.0, 0.5):
        parts = unified.budget_split(total, 4, unified.DEFAULT_FRACTIONS)
        assert len(parts) == 4
        assert pytest.approx(sum(parts), rel=1e-9) == total


def test_budget_split_is_proportional_and_monotone():
    parts = unified.budget_split(100.0, 3, (0.5, 0.3, 0.2))
    assert parts[0] > parts[1] >= parts[2]
    assert pytest.approx(parts[0], rel=1e-6) == 50.0


def test_budget_split_rejects_nonsense():
    with pytest.raises(ValueError):
        unified.budget_split(0.0, 4, unified.DEFAULT_FRACTIONS)
    with pytest.raises(ValueError):
        unified.budget_split(1.0, 0, unified.DEFAULT_FRACTIONS)


# --------------------------------------------------------------------- solving

def test_sat_result_is_verified_and_attributed():
    formula = sat_formula()
    result = unified.solve_unified(formula, timeout_seconds=10.0)
    assert result.status == SAT
    assert result.engine is not None
    assert formula.is_satisfied(result.assignment), "the portfolio must return a verified model"
    assert result.formula_sha256 == formula.sha256
    assert len(result.attempts) >= 1


def test_unsat_result_keeps_the_proof_status_of_the_engine_that_proved_it():
    formula = unsat_formula()
    result = unified.solve_unified(formula, timeout_seconds=10.0, engines=("watched", "omniwave"))
    assert result.status == UNSAT
    winner = [a for a in result.attempts if a.status == UNSAT]
    assert winner, "an UNSAT verdict needs the attempt that produced it"
    assert winner[0].engine == result.engine
    # The proof field must say what evidence exists - including "no certificate" when
    # the engine proves UNSAT by exhaustion without producing one.
    assert winner[0].proof, "an UNSAT attempt must state its proof status"


def test_unknown_lists_every_attempt():
    formula = sat_formula()
    # A budget this small is spent on the first engine; the rest still run with their
    # own (tiny) share, so the record shows what was tried instead of one silence.
    result = unified.solve_unified(formula, timeout_seconds=1e-6)
    assert result.status in (SAT, UNSAT, UNKNOWN)
    assert len(result.attempts) == len(unified.DEFAULT_ORDER) or result.decided
    for attempt in result.attempts:
        assert attempt.status in (SAT, UNSAT, UNKNOWN, "unavailable", "error")


def test_unknown_engine_is_refused():
    with pytest.raises(ValueError, match="unknown engine"):
        unified.solve_unified(sat_formula(), engines=("no-such-engine",))


def test_decision_stops_the_order_unless_asked_otherwise():
    formula = sat_formula()
    first_only = unified.solve_unified(formula, timeout_seconds=10.0)
    assert len(first_only.attempts) == 1, "the first deciding engine ends the search"

    compare = unified.solve_unified(formula, timeout_seconds=10.0, stop_on_decision=False)
    assert len(compare.attempts) == len(unified.DEFAULT_ORDER)


# -------------------------------------------------------------------- contract

def test_result_is_json_serialisable_with_the_declared_schema():
    result = unified.solve_unified(sat_formula(), timeout_seconds=10.0)
    document = result.to_dict()
    assert document["schema"] == "hcs.sat.unified.v1"
    assert document["status"] == SAT
    assert document["engine"] == result.engine
    assert document["order"] == list(result.order)
    assert len(document["fractions"]) == len(result.order)
    assert document["formula_sha256"] == result.formula_sha256
    json.dumps(document)  # must not raise


def test_missing_cadical_is_reported_not_skipped():
    from cqhecs import sat_external

    if sat_external.available():  # pragma: no cover - depends on the environment
        pytest.skip("python-sat is installed here; the unavailable path cannot be observed")
    result = unified.solve_unified(sat_formula(), timeout_seconds=5.0, engines=("cadical", "watched"))
    assert result.attempts[0].engine == "cadical"
    assert result.attempts[0].status == "unavailable"
    assert result.status == SAT, "the portfolio must still answer with another engine"


# ----------------------------------------------------------------- adversarial

class _LyingEngine:
    """A stub result that claims SAT with an invalid model."""

    def __init__(self):
        self.calls = 0

    def run(self):
        self.calls += 1
        return sat.SATResult(
            status=SAT,
            assignment={1: True},
            decisions=0,
            propagations=0,
            conflicts=0,
            nodes=0,
            max_depth=0,
            elapsed_ms=0.0,
            timeout_seconds=1.0,
            model_verified=True,
            formula_sha256="",
            note="stub",
        )


def test_a_model_that_fails_verification_is_refused(monkeypatch):
    """The portfolio's own check must not trust an engine's self-report."""
    lying = _LyingEngine()
    real_attempt = unified._attempt

    def fake_attempt(engine, formula, budget):
        if engine == "watched":
            attempt = unified.Attempt("watched", budget, 0.0, SAT, "stub claims SAT")
            return attempt, lying.run()
        return real_attempt(engine, formula, budget)

    monkeypatch.setattr(unified, "_attempt", fake_attempt)
    result = unified.solve_unified(sat_formula(), timeout_seconds=5.0, engines=("watched", "scan"))
    assert lying.calls == 1
    refused = [a for a in result.attempts if a.engine == "watched"]
    assert refused and refused[0].status == UNKNOWN
    assert "fails verification" in refused[0].reason
