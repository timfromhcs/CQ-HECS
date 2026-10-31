"""The independent DRAT checker must accept valid proofs and reject every corruption."""

from __future__ import annotations

import pytest

from cqhecs.drat import check_drat, parse_drat, DratFormatError

# (x1 ∨ x2)(¬x1 ∨ x2)(x1 ∨ ¬x2)(¬x1 ∨ ¬x2): UNSAT. Proof: x2 by RUP, then empty clause.
FORMULA = [(1, 2), (-1, 2), (1, -2), (-1, -2)]
PROOF = ["2 0", "0"]


def test_valid_rup_proof_is_accepted():
    result = check_drat(FORMULA, PROOF)
    assert result.valid is True
    assert result.lemmas == 2


def test_proof_for_a_different_formula_is_rejected():
    # Drop one clause: the formula becomes satisfiable, so no refutation may pass.
    assert check_drat(FORMULA[:-1], PROOF).valid is False


def test_lemma_that_does_not_follow_is_rejected():
    assert check_drat(FORMULA, ["1 0", "0"]).valid is True  # 1 is also RUP here
    bogus = [(1, 2, 3), (-1, 2), (1, -2)]
    assert check_drat(bogus, ["-3 0", "0"]).valid is False


def test_truncated_proof_is_rejected():
    assert check_drat(FORMULA, ["2 0"]).valid is False
    assert check_drat(FORMULA, []).valid is False


def test_deleting_an_absent_clause_is_rejected():
    assert check_drat(FORMULA, ["d 5 6 0", "2 0", "0"]).valid is False


def test_deletions_are_honoured():
    # Deleting the clauses the refutation needs must make the proof fail.
    proof = ["d 1 2 0", "d -1 2 0", "2 0", "0"]
    assert check_drat(FORMULA, proof).valid is False


def test_rat_lemma_is_accepted():
    # x3 is fresh: adding (3) is RAT (no clause contains ¬3), then the refutation goes on.
    result = check_drat(FORMULA, ["3 0", "2 0", "0"])
    assert result.valid is True and result.rat_lemmas == 1


def test_malformed_lines_are_errors_not_guesses():
    with pytest.raises(DratFormatError):
        parse_drat(["1 2"])
    with pytest.raises(DratFormatError):
        parse_drat(["1 x 0"])
    assert check_drat(FORMULA, ["1 2"]).valid is False


def test_budget_exhaustion_is_undecided():
    result = check_drat(FORMULA, PROOF, max_propagations=-1)
    assert result.valid is None


def test_empty_clause_in_formula():
    assert check_drat([(1,), ()], []).valid is True
