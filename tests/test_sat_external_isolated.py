"""W3-11: child-process isolation of the optional CaDiCaL adapter.

A crashing, hanging, or lying child must never become SAT/UNSAT/certified.
"""

from __future__ import annotations

import json
import sys

import pytest

from cqhecs import sat_external
from cqhecs.sat import SAT, UNKNOWN, UNSAT, parse_dimacs

UNSAT_CNF = "p cnf 1 2\n1 0\n-1 0\n"
SAT_CNF = "p cnf 2 2\n1 2 0\n-1 0\n"


# Windows keeps the full 32-bit status (0x40000409 after masking the sign bit); POSIX truncates a
# process exit status to 8 bits, so the same os._exit() argument is observed as 0x9 there. The
# adapter reports whatever the OS returned, so the expectation is derived from the platform.
_ABORT_EXIT = 0x7FFFFFFF & 0xC0000409
_ABORT_HEX = f"{_ABORT_EXIT if sys.platform == 'win32' else _ABORT_EXIT & 0xFF:#x}"


def _worker(code: str):
    return [sys.executable, "-c", code]


def _emit(raw: dict) -> str:
    body = json.dumps({"ok": True, "raw": raw})
    return (
        "import sys;"
        f"sys.stdin.read();sys.stdout.write('\\n{sat_external._RESULT_MARKER}'+{body!r}+'\\n')"
    )


def test_crashing_child_is_unknown_with_exit_code_recorded():
    # 0xC0000409 as the Windows fail-fast abort code (masked to a portable value).
    f = parse_dimacs(UNSAT_CNF)
    r = sat_external.solve_external_isolated(
        f, 5.0, worker_command=_worker("import sys; sys.stdin.read(); sys.exit(3)")
    )
    assert r.status == UNKNOWN and not r.certified and r.assignment is None
    assert "exit code 3" in r.note and "not SAT or UNSAT" in r.note


def test_abort_after_a_complete_result_is_recorded_and_result_is_reverified():
    """Observed python-sat behaviour: abort at interpreter exit after the result."""
    f = parse_dimacs(SAT_CNF)
    raw = {"outcome": True, "model": [-1, 2], "proof": None, "stats": {}, "version": "fake"}
    code = _emit(raw) + ";sys.stdout.flush();import os;os._exit(0x7FFFFFFF & 0xC0000409)"
    r = sat_external.solve_external_isolated(f, 5.0, worker_command=_worker(code))
    assert r.status == SAT and r.model_verified
    assert "exited abnormally" in r.note and _ABORT_HEX in r.note


def test_abort_after_a_lying_result_still_cannot_certify():
    f = parse_dimacs(SAT_CNF)
    raw = {"outcome": True, "model": [1, -2], "proof": None, "stats": {}, "version": "fake"}
    code = _emit(raw) + ";sys.stdout.flush();import os;os._exit(9)"
    r = sat_external.solve_external_isolated(f, 5.0, worker_command=_worker(code))
    assert r.status == UNKNOWN and r.assignment is None


def test_native_abort_like_exit_code_is_reported_not_suppressed():
    f = parse_dimacs(UNSAT_CNF)
    r = sat_external.solve_external_isolated(
        f, 5.0, worker_command=_worker("import os; os._exit(0x7FFFFFFF & 0xC0000409)")
    )
    assert r.status == UNKNOWN
    assert _ABORT_HEX in r.note and "no result" in r.note


def test_hung_child_is_killed_at_the_hard_deadline(monkeypatch):
    monkeypatch.setattr(sat_external, "_WORKER_GRACE_SECONDS", 0.3)
    f = parse_dimacs(UNSAT_CNF)
    r = sat_external.solve_external_isolated(
        f, 0.2, worker_command=_worker("import time; time.sleep(60)")
    )
    assert r.status == UNKNOWN and "hard deadline" in r.note


def test_garbage_output_is_unknown():
    f = parse_dimacs(UNSAT_CNF)
    r = sat_external.solve_external_isolated(
        f, 5.0, worker_command=_worker("import sys; sys.stdin.read(); print('hello')")
    )
    assert r.status == UNKNOWN and not r.certified


def test_unparseable_marker_payload_is_unknown():
    f = parse_dimacs(UNSAT_CNF)
    code = f"import sys; sys.stdin.read(); print('{sat_external._RESULT_MARKER}{{not json')"
    r = sat_external.solve_external_isolated(f, 5.0, worker_command=_worker(code))
    assert r.status == UNKNOWN and "unparseable" in r.note


def test_lying_sat_child_is_refused_by_the_parent():
    f = parse_dimacs(SAT_CNF)  # forces var 1 false, var 2 true
    raw = {"outcome": True, "model": [1, -2], "proof": None, "stats": {}, "version": "fake"}
    r = sat_external.solve_external_isolated(f, 5.0, worker_command=_worker(_emit(raw)))
    assert r.status == UNKNOWN and r.assignment is None and not r.model_verified
    assert "fails the original CNF" in r.note


def test_lying_unsat_child_with_no_proof_is_not_certified():
    f = parse_dimacs(SAT_CNF)  # actually satisfiable
    raw = {"outcome": False, "model": None, "proof": [], "stats": {}, "version": "fake"}
    r = sat_external.solve_external_isolated(f, 5.0, worker_command=_worker(_emit(raw)))
    assert not r.certified and r.proof_system is None
    assert r.proof_status in ("rejected", "undecided")


def test_honest_unsat_child_with_valid_proof_is_drat_checked_by_the_parent():
    f = parse_dimacs(UNSAT_CNF)
    raw = {"outcome": False, "model": None, "proof": ["0"], "stats": {}, "version": "fake"}
    r = sat_external.solve_external_isolated(f, 5.0, worker_command=_worker(_emit(raw)))
    assert r.status == UNSAT and r.certified and r.proof_system == "DRAT"


def test_nonpositive_timeout_refused():
    with pytest.raises(ValueError):
        sat_external.solve_external_isolated(parse_dimacs(UNSAT_CNF), 0)


def test_real_child_round_trip_when_python_sat_is_installed():
    pytest.importorskip("pysat.solvers", reason="python-sat (optional extra) not installed")
    unsat = sat_external.solve_external_isolated(parse_dimacs(UNSAT_CNF), 20.0)
    assert unsat.status == UNSAT and unsat.certified
    sat = sat_external.solve_external_isolated(parse_dimacs(SAT_CNF), 20.0)
    assert sat.status == SAT and sat.model_verified


def test_missing_python_sat_in_child_raises_backend_unavailable():
    if sat_external.available():
        pytest.skip("python-sat installed; unavailable path not reachable")
    with pytest.raises(sat_external.BackendUnavailable):
        sat_external.solve_external_isolated(parse_dimacs(UNSAT_CNF), 20.0)
