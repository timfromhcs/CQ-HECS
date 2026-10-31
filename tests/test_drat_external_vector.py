"""External DRAT proof vector produced by CaDiCaL.

The proof is a data fixture under ``research/v6/evidence/drat``. The in-repo
checker must accept it; a truncated or altered proof must fail. If
``CQ_DRAT_TRIM`` points at a drat-trim executable, the same vector is also
checked by that independent implementation.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from cqhecs.drat import check_drat
from cqhecs.sat import load_dimacs

ROOT = Path(__file__).resolve().parents[1]
CNF = ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf"
PROOF = ROOT / "research" / "v6" / "evidence" / "drat" / "pigeonhole_6_5.cadical.drat"


def _proof_lines() -> list[str]:
    return [line for line in PROOF.read_text("ascii").splitlines() if line.strip()]


def test_external_cadical_proof_is_accepted():
    formula = load_dimacs(CNF)
    proof = _proof_lines()
    result = check_drat(formula.clauses, proof)
    assert result.valid is True
    assert result.lemmas == 156


def test_external_proof_corruption_is_rejected():
    formula = load_dimacs(CNF)
    proof = _proof_lines()
    assert check_drat(formula.clauses, proof[:-1]).valid is False
    altered = list(proof)
    altered[0] = altered[0].replace("-", "", 1) if altered[0].startswith("-") else "-" + altered[0]
    assert check_drat(formula.clauses, altered).valid is False
    assert check_drat(formula.clauses[:-1], proof).valid is False


@pytest.mark.skipif(not os.environ.get("CQ_DRAT_TRIM"), reason="set CQ_DRAT_TRIM to a drat-trim executable")
def test_external_checker_agrees():
    completed = subprocess.run(
        [os.environ["CQ_DRAT_TRIM"], str(CNF), str(PROOF)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0
    assert "s VERIFIED" in completed.stdout
