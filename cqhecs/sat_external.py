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
    try:
        from pysat.solvers import Solver
    except ImportError as exc:
        raise BackendUnavailable("python-sat is not installed; pip install cqhecs[sat]") from exc

    started = time.perf_counter()
    clauses = [list(c) for c in formula.clauses]
    with Solver(name=SOLVER_NAME, bootstrap_with=clauses, with_proof=check_proof) as solver:
        timer = threading.Timer(float(timeout_seconds), solver.interrupt)
        timer.start()
        try:
            outcome = solver.solve_limited(expect_interrupt=True)
        finally:
            timer.cancel()
        model = solver.get_model() if outcome is True else None
        proof = solver.get_proof() if (outcome is False and check_proof) else None
        stats = solver.accum_stats() or {}
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    assignment = None
    certified = False
    if outcome is True:
        assignment = {abs(lit): lit > 0 for lit in model or []}
        for var in range(1, formula.num_vars + 1):
            assignment.setdefault(var, False)
        if formula.is_satisfied(assignment):
            status, note = SAT, f"{backend_version()}; model verified clause by clause"
        else:
            status, assignment = UNKNOWN, None
            note = f"{backend_version()} returned a model that fails the original CNF; refused"
    elif outcome is False:
        status = UNSAT
        if not check_proof:
            note = f"{backend_version()}; proof checking disabled; uncertified"
        else:
            budget = proof_timeout_seconds if proof_timeout_seconds is not None else max(10.0, 2 * timeout_seconds)
            check = check_drat(formula.clauses, proof or [], timeout_seconds=budget)
            certified = check.valid is True
            if check.valid is True:
                note = f"{backend_version()}; DRAT proof checked by cqhecs.drat ({check.lemmas} lemmas)"
            elif check.valid is None:
                note = f"{backend_version()}; DRAT check undecided ({check.reason}); uncertified"
            else:
                note = f"{backend_version()}; DRAT proof rejected ({check.reason}); uncertified"
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
        engine="cadical",
    )
