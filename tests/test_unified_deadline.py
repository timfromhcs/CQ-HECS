"""W3-10 (D3 second half): the total deadline must cover the DRAT proof check.

Before this change the external adapter used ``max(10, 2*timeout)`` and OMNIWAVE added a
fixed 60 s proof check after the search, so a caller's stated timeout did not bound the
wall time. Now both bound the proof check by the time that remains within the stated
deadline, and a search that refutes the formula but runs out of time for the proof
returns UNKNOWN instead of a false certified UNSAT.
"""
from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine
from cqhecs.sat import CNF, UNSAT, UNKNOWN
from cqhecs.sat_external import _proof_budget


def unsat_formula() -> CNF:
    return CNF(num_vars=2, clauses=((1, 2), (1, -2), (-1, 2), (-1, -2)))


def test_the_proof_budget_is_the_remaining_time():
    assert _proof_budget(10.0, 3.0, None) == 7.0


def test_the_proof_budget_is_zero_when_the_deadline_is_spent():
    assert _proof_budget(10.0, 12.0, None) == 0.0


def test_an_explicit_proof_budget_overrides_the_remaining_time():
    assert _proof_budget(10.0, 3.0, 5.0) == 5.0


def test_a_negative_explicit_budget_is_clamped():
    assert _proof_budget(1.0, 1.0, -2.0) == 0.0


def test_omniwave_with_no_proof_budget_refuses_to_certify():
    # proof_timeout_seconds=0 -> the proof gets no time -> UNKNOWN, never a false UNSAT.
    config = OmniwaveConfig(waves=1, workers=1, timeout_seconds=5.0, check_proof=True, proof_timeout_seconds=0.0)
    result = OmniwaveEngine(unsat_formula(), config).run()
    assert result.status == UNKNOWN
    assert result.certified is False


def test_omniwave_with_a_generous_proof_budget_still_certifies():
    config = OmniwaveConfig(waves=1, workers=1, timeout_seconds=10.0, check_proof=True, proof_timeout_seconds=5.0)
    result = OmniwaveEngine(unsat_formula(), config).run()
    assert result.status == UNSAT
    assert result.certified is True
