"""Optional CaDiCaL adapter: verified models, DRAT-checked UNSAT, honest fallbacks."""

from __future__ import annotations

from pathlib import Path

import pytest

from cqhecs.sat import CERTIFICATIONS, SAT, UNSAT, parse_dimacs, random_3sat, solve
from cqhecs import sat_external

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("pysat.solvers", reason="python-sat (optional extra) not installed")


def test_sat_model_is_verified_against_the_original_cnf():
    formula = random_3sat(60, 200, seed=1)
    result = sat_external.solve_external(formula)
    assert result.engine == "cadical"
    if result.status == SAT:
        assert result.model_verified and formula.is_satisfied(result.assignment)
        assert result.certification == "MODEL_VERIFIED"


def test_pigeonhole_unsat_is_drat_certified():
    formula = parse_dimacs((ROOT / "benchmarks/sat/pigeonhole_6_5.cnf").read_text("utf-8"))
    result = sat_external.solve_external(formula, timeout_seconds=30)
    assert result.status == UNSAT
    assert result.certified and result.certification == "DRAT_CHECKED"
    assert result.to_dict()["proof_system"] == "DRAT"


def test_unchecked_unsat_is_labelled_uncertified():
    formula = parse_dimacs("p cnf 1 2\n1 0\n-1 0\n")
    result = sat_external.solve_external(formula, check_proof=False)
    assert result.status == UNSAT and not result.certified
    assert result.certification == "UNCERTIFIED"


@pytest.mark.parametrize("seed", range(40))
def test_agrees_with_the_builtin_reference_engine(seed):
    formula = random_3sat(14, 40 + seed % 30, seed=seed)
    ours, theirs = solve(formula), sat_external.solve_external(formula)
    assert ours.status == theirs.status
    if theirs.status == UNSAT:
        assert theirs.certification == "DRAT_CHECKED"
    assert theirs.certification in CERTIFICATIONS


def test_missing_backend_is_reported_not_faked(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("pysat"):
            raise ImportError("simulated missing python-sat")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert sat_external.available() is False
    with pytest.raises(sat_external.BackendUnavailable):
        sat_external.solve_external(parse_dimacs("p cnf 1 1\n1 0\n"))
