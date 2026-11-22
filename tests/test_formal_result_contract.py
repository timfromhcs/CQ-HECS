"""Pins ``formal/CQHECS/Result.lean`` (L-RESULT-01) to ``cqhecs/result.py``.

The Lean file is a specification model. These tests enumerate the whole flag space of the
Python class and compare it with a transcription of the Lean ``deriveState`` / ``totalBound``
tables, and check that the Lean file still names the lemmas the audit relies on.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path

from cqhecs.result import SimulationResult, SimulationState

LEAN = Path(__file__).resolve().parents[1] / "formal" / "CQHECS" / "Result.lean"


def lean_derive_state(failed, unresolved, exact, err_zero):
    """Transcription of ``CQHECS.ResultContract.deriveState``."""
    if failed:
        return SimulationState.FAILED
    if unresolved:
        return SimulationState.UNRESOLVED
    if exact and err_zero:
        return SimulationState.EXACT
    return SimulationState.CERTIFIED


def lean_total_bound_is_some(state):
    """Transcription of the ``totalBound`` guard: value only for EXACT / CERTIFIED."""
    return state in (SimulationState.EXACT, SimulationState.CERTIFIED)


def test_state_derivation_matches_lean_table_exhaustively():
    for failed, unresolved, exact, err_zero in itertools.product([False, True], repeat=4):
        result = SimulationResult(
            path="A",
            exact=exact,
            error_bound=0.0 if err_zero else 0.25,
            unresolved=unresolved,
            metadata={"failed": True} if failed else {},
        )
        assert result.state == lean_derive_state(failed, unresolved, exact, err_zero), (
            failed, unresolved, exact, err_zero)


def test_unresolved_or_failed_expose_no_total_error_bound():
    for failed, unresolved, exact, err_zero in itertools.product([False, True], repeat=4):
        result = SimulationResult(
            path="A",
            exact=exact,
            error_bound=0.0 if err_zero else 0.25,
            unresolved=unresolved,
            counts={"0": 1},
            metadata={"failed": True} if failed else {},
        )
        if not lean_total_bound_is_some(result.state):
            assert result.total_error_bound is None
        if unresolved:
            assert result.state in (SimulationState.UNRESOLVED, SimulationState.FAILED)
            assert result.total_error_bound is None


def test_lean_file_still_names_the_pinned_lemmas():
    text = LEAN.read_text(encoding="utf-8")
    assert "sorry" not in re.sub(r"/-.*?-/", "", text, flags=re.S), "unfinished proof"
    for name in (
        "unresolved_derives_unresolved",
        "failed_wins",
        "unresolved_never_certified_or_exact",
        "exact_requires",
        "unresolved_has_no_certified_value",
        "unresolved_flags_expose_no_value",
        "value_only_for_exact_or_certified",
    ):
        assert f"theorem {name}" in text, name
    for ctor in ("exact", "certified", "unresolved", "failed"):
        assert f"| {ctor}\n" in text
    assert {s.value.lower() for s in SimulationState} == {"exact", "certified", "unresolved", "failed"}
