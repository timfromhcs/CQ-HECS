"""
Optional external SAT backend: CaDiCaL via ``python-sat``.

The built-in DPLL in :mod:`cqhecs.sat` stays the reference engine. This adapter adds
coverage for larger instances without widening the trust boundary:

* ``SAT``: the external model is re-checked clause by clause against the
  **original** CNF; a model that fails is refused (``UNKNOWN``).
* ``UNSAT``: CaDiCaL's DRAT proof is checked by :mod:`cqhecs.drat`, which shares no
  code with the solver. ``certified`` is True only if that check accepts it.
* Timeout: ``UNKNOWN``.
* ``python-sat`` not installed: :class:`BackendUnavailable`, never a silent
  fallback to another engine.

Install with ``pip install cqhecs[sat]`` (or ``python-sat``).
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import threading
import time
from typing import Optional

from cqhecs.drat import check_drat
from cqhecs.sat import CNF, SAT, SATResult, UNKNOWN, UNSAT

SOLVER_NAME = "cadical195"


class BackendUnavailable(RuntimeError):
    """``python-sat`` (and with it CaDiCaL) is not installed."""


def available() -> bool:
    try:
        import pysat.solvers  # noqa: F401
    except ImportError:
        return False
    return True


def backend_version() -> str:
    try:
        import pysat
    except ImportError as exc:  # pragma: no cover - exercised via available()
        raise BackendUnavailable("python-sat is not installed; pip install cqhecs[sat]") from exc
    return f"CaDiCaL 1.9.5 via python-sat {pysat.__version__}"


def _proof_budget(
    timeout_seconds: float, elapsed_seconds: float, explicit: Optional[float]
) -> float:
    """Time left within the stated total for the DRAT proof check (W3-10).

    The proof check must fit inside the caller's total deadline, so by default it
    gets only what the search did not use. An explicit positive budget overrides
    that (a documented escape hatch for a caller who allows a longer proof check).
    """
    if explicit is not None:
        return max(0.0, float(explicit))
    return max(0.0, float(timeout_seconds) - float(elapsed_seconds))


def _run_cadical(clauses: list, timeout_seconds: float, with_proof: bool) -> dict:
    """Run CaDiCaL and return raw, unverified output (JSON-serialisable)."""
    try:
        from pysat.solvers import Solver
    except ImportError as exc:
        raise BackendUnavailable("python-sat is not installed; pip install cqhecs[sat]") from exc
    with Solver(name=SOLVER_NAME, bootstrap_with=clauses, with_proof=with_proof) as solver:
        timer = threading.Timer(float(timeout_seconds), solver.interrupt)
        timer.start()
        try:
            outcome = solver.solve_limited(expect_interrupt=True)
        finally:
            timer.cancel()
        model = solver.get_model() if outcome is True else None
        proof = solver.get_proof() if (outcome is False and with_proof) else None
        stats = solver.accum_stats() or {}
    return {
        "outcome": outcome,
        "model": [int(x) for x in model] if model is not None else None,
        "proof": [str(x) for x in proof] if proof is not None else None,
        "stats": {k: int(v) for k, v in stats.items() if isinstance(v, (int, float))},
        "version": backend_version(),
    }


def solve_external(
    formula: CNF,
    timeout_seconds: float = 10.0,
    *,
    check_proof: bool = True,
    proof_timeout_seconds: Optional[float] = None,
) -> SATResult:
    """Solve with CaDiCaL; verify SAT models and DRAT-check UNSAT proofs."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    started = time.perf_counter()
    clauses = [list(c) for c in formula.clauses]
    raw = _run_cadical(clauses, timeout_seconds, check_proof)
    return _finish(formula, raw, started, timeout_seconds, check_proof, proof_timeout_seconds)


def _unknown(formula: CNF, started: float, timeout_seconds: float, note: str) -> SATResult:
    return SATResult(
        status=UNKNOWN,
        assignment=None,
        decisions=0,
        propagations=0,
        conflicts=0,
        nodes=0,
        max_depth=0,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        timeout_seconds=float(timeout_seconds),
        model_verified=False,
        formula_sha256=formula.sha256,
        formula_original_sha256=formula.original_sha256,
        note=note,
        certificate=None,
        certified=False,
        proof_system=None,
        proof_status=None,
        engine="cadical",
    )


def _finish(
    formula: CNF,
    raw: dict,
    started: float,
    timeout_seconds: float,
    check_proof: bool,
    proof_timeout_seconds: Optional[float],
) -> SATResult:
    """Verify the raw solver output against the original CNF (the trust boundary)."""
    outcome = raw.get("outcome")
    model = raw.get("model")
    proof = raw.get("proof")
    stats = raw.get("stats") or {}
    version = raw.get("version") or SOLVER_NAME
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    assignment = None
    certified = False
    proof_status = None
    if outcome is True:
        assignment = {abs(lit): lit > 0 for lit in model or []}
        for var in range(1, formula.num_vars + 1):
            assignment.setdefault(var, False)
        if formula.is_satisfied(assignment):
            status, note = SAT, f"{version}; model verified clause by clause"
        else:
            status, assignment = UNKNOWN, None
            note = f"{version} returned a model that fails the original CNF; refused"
    elif outcome is False:
        status = UNSAT
        if not check_proof:
            proof_status = "disabled"
            note = f"{version}; proof checking disabled; uncertified"
        else:
            budget = _proof_budget(timeout_seconds, elapsed_ms / 1000.0, proof_timeout_seconds)
            if budget <= 0.0:
                proof_status = "undecided"
                note = f"{version}; DRAT check skipped: the solve deadline is exhausted; uncertified"
            else:
                check = check_drat(formula.clauses, proof or [], timeout_seconds=budget)
                certified = check.valid is True
                if check.valid is True:
                    proof_status = "accepted"
                    note = f"{version}; DRAT proof checked by cqhecs.drat ({check.lemmas} lemmas)"
                elif check.valid is None:
                    proof_status = "undecided"
                    note = f"{version}; DRAT check undecided ({check.reason}); uncertified"
                else:
                    proof_status = "rejected"
                    note = f"{version}; DRAT proof rejected ({check.reason}); uncertified"
    else:
        status = UNKNOWN
        note = f"timeout after {float(timeout_seconds):.6g} s; result not decided"

    return SATResult(
        status=status,
        assignment=assignment,
        decisions=int(stats.get("decisions", 0)),
        propagations=int(stats.get("propagations", 0)),
        conflicts=int(stats.get("conflicts", 0)),
        nodes=0,
        max_depth=0,
        elapsed_ms=elapsed_ms,
        timeout_seconds=float(timeout_seconds),
        model_verified=status == SAT,
        formula_sha256=formula.sha256,
        formula_original_sha256=formula.original_sha256,
        note=note,
        certificate=None,
        certified=certified,
        proof_system="DRAT" if status == UNSAT and certified else None,
        proof_status=proof_status if status == UNSAT else None,
        engine="cadical",
    )


# --- W3-11: child-process isolation -------------------------------------------------
#
# A native abort inside python-sat (seen on Windows / Python 3.14 as exit code
# 0xC0000409) kills the whole interpreter. The isolated entry point runs CaDiCaL in
# a child process; the parent treats the child as untrusted: it re-verifies the
# model and DRAT-checks the proof itself. A crash, hard timeout, or unparseable
# output is UNKNOWN with the exit code recorded. It is never reported as SAT/UNSAT
# and never hidden.

_WORKER_GRACE_SECONDS = 5.0
_RESULT_MARKER = "@@CQHECS_SAT_RESULT@@"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _worker_main() -> int:
    payload = json.loads(sys.stdin.read())
    try:
        raw = _run_cadical(payload["clauses"], payload["timeout"], payload["with_proof"])
        out = {"ok": True, "raw": raw}
    except BackendUnavailable as exc:
        out = {"ok": False, "unavailable": str(exc)}
    sys.stdout.write("\n" + _RESULT_MARKER + json.dumps(out) + "\n")
    sys.stdout.flush()
    return 0


def solve_external_isolated(
    formula: CNF,
    timeout_seconds: float = 10.0,
    *,
    check_proof: bool = True,
    proof_timeout_seconds: Optional[float] = None,
    worker_command: Optional[list] = None,
) -> SATResult:
    """Like :func:`solve_external`, but CaDiCaL runs in a child process.

    ``worker_command`` is a test seam (argv of the child); by default the current
    interpreter runs ``cqhecs.sat_external --worker``. A child that crashes (for
    example the Windows 0xC0000409 abort), is killed at the hard deadline, or emits
    unparseable output yields ``UNKNOWN``, never SAT/UNSAT.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    started = time.perf_counter()
    default = worker_command is None
    cmd = worker_command or [sys.executable, "-m", "cqhecs.sat_external", "--worker"]
    payload = json.dumps(
        {
            "clauses": [list(c) for c in formula.clauses],
            "timeout": float(timeout_seconds),
            "with_proof": bool(check_proof),
        }
    )
    try:
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            timeout=float(timeout_seconds) + _WORKER_GRACE_SECONDS,
            cwd=_PROJECT_ROOT if default else None,
        )
    except subprocess.TimeoutExpired:
        return _unknown(
            formula, started, timeout_seconds,
            "isolated CaDiCaL child exceeded the hard deadline and was killed; not decided",
        )
    body = proc.stdout.rsplit(_RESULT_MARKER, 1)[1].strip() if _RESULT_MARKER in proc.stdout else None
    exit_note = ""
    if proc.returncode != 0:
        exit_note = (
            f"; WARNING: isolated child exited abnormally (exit code {proc.returncode} = "
            f"{proc.returncode & 0xFFFFFFFF:#x})"
        )
    if body is None:
        return _unknown(
            formula, started, timeout_seconds,
            f"isolated CaDiCaL child produced no result (exit code {proc.returncode} = "
            f"{proc.returncode & 0xFFFFFFFF:#x}); not decided; this is not SAT or UNSAT",
        )
    try:
        message = json.loads(body)
    except ValueError:
        return _unknown(formula, started, timeout_seconds,
                        "isolated CaDiCaL child produced unparseable output; not decided"
                        + exit_note)
    if not message.get("ok"):
        raise BackendUnavailable(str(message.get("unavailable", "python-sat is not installed")))
    result = _finish(formula, message["raw"], started, timeout_seconds, check_proof,
                     proof_timeout_seconds)
    if exit_note:
        # A complete result was emitted before the abort (observed: python-sat/CaDiCaL
        # aborts at interpreter exit with 0xC0000409 after a with_proof solve). The
        # parent re-verified the model / DRAT proof itself, so soundness does not rest
        # on the child; the abnormal exit is recorded, not hidden.
        result = dataclasses.replace(
            result,
            note=(result.note or "") + exit_note + "; result independently re-verified by the parent",
        )
    return result


if __name__ == "__main__":  # pragma: no cover - child entry point
    if "--worker" in sys.argv:
        raise SystemExit(_worker_main())
