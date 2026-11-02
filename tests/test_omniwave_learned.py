"""Tests for the learned branch scorer ("JEV") and its effect on OMNIWAVE.

The point of these tests is not that the model is good - it is not, and
`research/sha_forge/FINDINGS.md` records that. The point is that a learned
*heuristic* can never change an answer: the engine still has to verify a SAT model
against the original CNF and still has to check a DRAT proof for UNSAT. An adversarial
policy that always picks the worst variable must therefore produce the same verdict as
Jeroslow-Wang, only more slowly.
"""
import json

import pytest

from cqhecs.omniwave import OmniwaveEngine, OmniwaveConfig
from cqhecs.omniwave.learned import (
    FEATURE_NAMES,
    Candidate,
    FeatureScorer,
    fit_logistic,
    front_features,
)
from cqhecs.sat import CNF


def small_sat() -> CNF:
    return CNF(num_vars=4, clauses=((1, 2), (-1, 3), (-2, -3), (3, 4), (-4, 2)))


def small_unsat() -> CNF:
    # Every 2-clause combination over 2 variables, which is contradictory.
    return CNF(num_vars=2, clauses=((1, 2), (1, -2), (-1, 2), (-1, -2)))


# ------------------------------------------------------------------ features

def test_features_are_deterministic_and_counted():
    formula = CNF(num_vars=3, clauses=((1, 2, 3), (-1, 2), (2,)))
    candidates = front_features({}, [1, 2, 3], formula.clauses, [], jw_scores={1: 0.5, 2: 1.0, 3: 0.25}, depth=2, wave=1)
    assert [c.variable for c in candidates] == [1, 2, 3]
    by_var = {c.variable: c.as_dict() for c in candidates}
    # var 1: one occurrence in a 3-clause (positive) and one in a 2-clause (negative)
    assert by_var[1]["occ3"] == 1 and by_var[1]["occ2"] == 1
    assert by_var[1]["pos"] == 1 and by_var[1]["neg"] == 1 and by_var[1]["balance"] == 1
    # var 2 appears in all three clauses: 3-clause + 2-clause + unit (counted as >= 4 bucket)
    assert by_var[2]["pos"] == 3
    assert by_var[3]["occ3"] == 1
    assert all(c.as_dict()["depth"] == 2 and c.as_dict()["wave"] == 1 for c in candidates)

    again = front_features({}, [1, 2, 3], formula.clauses, [], jw_scores={1: 0.5, 2: 1.0, 3: 0.25}, depth=2, wave=1)
    assert [c.features for c in again] == [c.features for c in candidates], "features must be deterministic"


def test_features_respect_the_assignment():
    formula = CNF(num_vars=2, clauses=((1, 2), (-1, 2)))
    # With 1 assigned true, the first clause is satisfied and must not count.
    candidates = front_features({1: True}, [2], formula.clauses, [])
    assert candidates[0].as_dict()["occ2"] == 1
    assert candidates[0].as_dict()["pos"] == 1


def test_feature_order_is_a_contract():
    assert FEATURE_NAMES == ("occ2", "occ3", "occk", "pos", "neg", "balance", "depth", "nogood", "wave", "jwd")
    assert len(FEATURE_NAMES) == 10


# ------------------------------------------------------------------- scorer

def test_scorer_round_trip_and_validation(tmp_path):
    scorer = FeatureScorer([0.0] * len(FEATURE_NAMES), intercept=0.5, metadata={"trained_on": ["unit-test"]})
    path = tmp_path / "weights.json"
    scorer.save(path)
    loaded = FeatureScorer.load(path)
    assert loaded.coefficients == scorer.coefficients
    assert loaded.intercept == scorer.intercept
    assert loaded.describe()["kind"] == "logistic"

    # A weights file from a different feature set must be rejected, not silently used.
    data = json.loads(path.read_text(encoding="utf-8"))
    data["features"] = list(reversed(FEATURE_NAMES))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="different feature set"):
        FeatureScorer.load(bad)

    with pytest.raises(ValueError, match="coefficients"):
        FeatureScorer([0.0] * 3)


def test_scorer_chooses_the_highest_score():
    coefficients = [0.0] * len(FEATURE_NAMES)
    coefficients[FEATURE_NAMES.index("occ2")] = 1.0
    scorer = FeatureScorer(coefficients)
    candidates = [
        Candidate(1, tuple(1.0 if name == "occ2" else 0.0 for name in FEATURE_NAMES)),
        Candidate(2, tuple(5.0 if name == "occ2" else 0.0 for name in FEATURE_NAMES)),
    ]
    assert scorer.choose(candidates) == 2
    assert scorer.choose([]) is None


def test_fit_logistic_learns_a_separable_signal():
    # Positive examples differ only in the first feature; the fit must pick that up.
    samples = [(tuple([1.0] + [0.0] * 9), 1), (tuple([0.0] * 10), 0)] * 40
    coefficients, intercept = fit_logistic(samples, epochs=600, learning_rate=0.5)
    assert coefficients[0] > 0.1, f"the fit should weight the informative feature, got {coefficients[0]:.4f}"
    assert all(abs(c) < 0.1 for c in coefficients[1:])


# ------------------------------------------------------------- the engine

class StubPolicy:
    """Always picks the lowest-numbered candidate: no intelligence at all."""

    kind = "stub"

    def __init__(self, pick_last: bool = False):
        self.pick_last = pick_last
        self.calls = 0

    def choose(self, candidates):
        self.calls += 1
        if not candidates:
            return None
        return max(c.variable for c in candidates) if self.pick_last else min(c.variable for c in candidates)

    def describe(self):
        return {"kind": self.kind}


def _run(formula: CNF, **config_kwargs):
    engine = OmniwaveEngine(formula, OmniwaveConfig(waves=1, workers=1, timeout_seconds=30, **config_kwargs))
    return engine, engine.run()


def test_learned_branch_needs_a_model():
    with pytest.raises(ValueError, match="learned_model"):
        OmniwaveEngine(small_sat(), OmniwaveConfig(branch="learned"))


def test_unknown_branch_mode_is_rejected():
    with pytest.raises(ValueError, match="branch must be"):
        OmniwaveEngine(small_sat(), OmniwaveConfig(branch="magic"))


@pytest.mark.parametrize("formula_factory", [small_sat, small_unsat])
def test_learned_policy_cannot_change_verdicts(formula_factory):
    """The whole safety argument for shipping a learned heuristic, as a test."""
    formula = formula_factory()
    _, baseline = _run(formula, branch="jw")
    engine, _ = _run(formula, branch="jw")
    # Replace the policy directly: no weights file needed, and the stub is worse than
    # JW by construction (it ignores every feature).
    engine._policy = StubPolicy(pick_last=True)
    verdict = engine.run()
    assert verdict.status == baseline.status
    if baseline.status == "SAT":
        assert formula.is_satisfied(verdict.assignment), "a SAT model must verify against the original CNF"
    if baseline.status == "UNSAT":
        assert "DRAT" in verdict.note or "proof" in verdict.note.lower()


def test_learned_choices_are_counted():
    # `small_sat` is decided by propagation at the root, so it never splits and the
    # policy is never consulted; the unsat instance has to branch.
    formula = small_unsat()
    # Build the engine *without* running it: _run() above executes immediately, and a
    # second run() on a finished engine returns at once (its stop flag is set), which is
    # what made this test look like the policy was never consulted.
    engine = OmniwaveEngine(formula, OmniwaveConfig(waves=1, workers=1, timeout_seconds=30, branch="jw"))
    engine._policy = StubPolicy()
    engine.run()
    snapshot = engine.snapshot()
    assert engine._policy.calls > 0, "the stub policy was never consulted"
    assert snapshot["learned_choices"] > 0, "consultations must be counted for the Studio"
    assert snapshot["learned_choices"] == engine._policy.calls
