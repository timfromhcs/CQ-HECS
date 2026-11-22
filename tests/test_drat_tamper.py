"""Tamper matrix for the in-repo DRAT checker on the fixed CaDiCaL pigeonhole vector.

Trust label when accepted: ``DRAT_CHECKED`` (in-repo checker, not formally
verified). ``EXTERNAL_DRAT_CHECKED`` / ``LRAT_CHECKED`` are NOT claimed here; the
in-repo checker has no LRAT reader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cqhecs.drat import check_drat
from cqhecs.sat import load_dimacs

ROOT = Path(__file__).resolve().parents[1]
CNF = ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf"
PROOF = ROOT / "research" / "v6" / "evidence" / "drat" / "pigeonhole_6_5.cadical.drat"


@pytest.fixture(scope="module")
def vector():
    formula = load_dimacs(CNF)
    proof = [line for line in PROOF.read_text("ascii").splitlines() if line.strip()]
    return formula, proof


def test_untampered_vector_is_accepted(vector):
    formula, proof = vector
    assert check_drat(formula.clauses, proof).valid is True


def test_deleting_the_first_lemma_is_rejected(vector):
    formula, proof = vector
    assert not proof[0].startswith("d")
    assert check_drat(formula.clauses, proof[1:]).valid is False


def test_some_single_lemma_deletions_break_the_proof(vector):
    formula, proof = vector
    rejected = [
        i for i in range(len(proof))
        if check_drat(formula.clauses, proof[:i] + proof[i + 1:]).valid is False
    ]
    # Measured 125 of 235 steps are individually required; assert a safe lower bound.
    assert len(rejected) >= 50


@pytest.mark.parametrize("keep", [0, 1, 10, 100, 234])
def test_truncation_is_rejected(vector, keep):
    formula, proof = vector
    assert check_drat(formula.clauses, proof[:keep]).valid is False


def test_dropping_the_final_empty_clause_is_rejected(vector):
    formula, proof = vector
    assert proof[-1].strip() == "0"
    assert check_drat(formula.clauses, proof[:-1]).valid is False


def test_reversed_proof_is_rejected(vector):
    formula, proof = vector
    assert check_drat(formula.clauses, list(reversed(proof))).valid is False


def test_swapping_the_first_and_last_non_final_steps_is_rejected(vector):
    formula, proof = vector
    shuffled = list(proof)
    shuffled[0], shuffled[-2] = shuffled[-2], shuffled[0]
    assert check_drat(formula.clauses, shuffled).valid is False


def test_flipping_a_literal_breaks_most_lemmas(vector):
    formula, proof = vector
    broken = total = 0
    for i, line in enumerate(proof):
        toks = line.split()
        if line.startswith("d") or len(toks) < 3:
            continue
        toks[0] = str(-int(toks[0]))
        total += 1
        if check_drat(formula.clauses, proof[:i] + [" ".join(toks)] + proof[i + 1:]).valid is not True:
            broken += 1
    assert total > 100 and broken / total > 0.8  # measured 113/126


def test_no_tampered_proof_ever_refutes_a_satisfiable_formula(vector):
    """Soundness: dropping an input clause makes the formula SAT; nothing may pass."""
    formula, proof = vector
    sat_clauses = list(formula.clauses)[:-1]
    assert check_drat(sat_clauses, proof).valid is not True
    for i in range(0, len(proof), 7):
        tampered = proof[:i] + proof[i + 1:]
        assert check_drat(sat_clauses, tampered).valid is not True


def test_wrong_formula_is_rejected(vector):
    _, proof = vector
    assert check_drat([(1, 2), (-1, 2)], proof).valid is not True


def test_exhausted_budgets_are_undecided_never_accepted(vector):
    formula, proof = vector
    assert check_drat(formula.clauses, proof, timeout_seconds=1e-9).valid is None
    assert check_drat(formula.clauses, proof, max_propagations=10).valid is None


def test_malformed_line_is_a_rejection_not_an_acceptance(vector):
    formula, proof = vector
    assert check_drat(formula.clauses, proof[:5] + ["1 x 0"] + proof[5:]).valid is False
