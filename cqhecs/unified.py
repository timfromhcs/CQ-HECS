"""One solving surface over four engines, with one evidence record.

The engines stay what they are - `cqhecs.sat` (scan and watched DPLL with a
tree-resolution certificate), `cqhecs.omniwave` (exhaustive cube search with a DRAT
proof) and `cqhecs.sat_external` (CaDiCaL via ``python-sat``, optional). What was
missing was a layer that knows what each engine can do, spends a budget across them in
a declared order, and returns a single typed result that says which engine decided
what, with which evidence.

CaDiCaL is *not* modified: it is reached through its existing adapter, it is optional,
and forking a third-party solver would buy maintenance cost and no scientific result.
The unification is the contract, not a patch to somebody else's source.

Rules, each covered by a test in ``tests/test_unified_solver.py``:

1. **Capability first.** An engine that cannot answer is reported as ``unavailable``
   and never silently replaced.
2. **Declared order and budget.** Default order ``watched -> omniwave -> cadical ->
   scan`` with fractions ``0.5 / 0.3 / 0.2`` of the remaining time; both are recorded.
3. **Per-engine discipline unchanged.** ``SAT`` is re-verified against the *original*
   CNF here before it is returned; ``UNSAT`` keeps the proof status the engine
   reported and is never upgraded.
4. **One schema.** ``hcs.sat.unified.v1``: status, engine, every attempt, assignment,
   certificate, formula digest.
5. **Deterministic.** Same input, same order, same budgets.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cqhecs import sat
from cqhecs.sat import CNF, SAT, UNKNOWN, UNSAT

SCHEMA = "hcs.sat.unified.v1"

#: Declared order. Changing it is a schema-visible change: the result records it.
DEFAULT_ORDER: Tuple[str, ...] = ("watched", "omniwave", "cadical", "scan")
#: Fraction of the remaining budget each engine gets, in the same order.
DEFAULT_FRACTIONS: Tuple[float, ...] = (0.5, 0.3, 0.2, 0.0)


@dataclass(frozen=True)
class EngineInfo:
    name: str
    proof: str
    requires: Optional[str]
    available: bool

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "proof": self.proof, "requires": self.requires, "available": self.available}


def capabilities() -> Tuple[EngineInfo, ...]:
    """What this installation can actually do, including what is missing."""
    external_available = False
    try:
        from cqhecs import sat_external

        external_available = sat_external.available()
    except Exception:  # noqa: BLE001 - an import failure is "unavailable", not a crash
        external_available = False
    return (
        EngineInfo("watched", "model verified against the original CNF", None, True),
        EngineInfo("omniwave", "DRAT proof checked by cqhecs.drat", None, True),
        EngineInfo("cadical", "DRAT proof checked by cqhecs.drat", "python-sat", external_available),
        EngineInfo("scan", "tree-resolution certificate checked in-repo", None, True),
    )


@dataclass(frozen=True)
class Attempt:
    engine: str
    budget_seconds: float
    elapsed_seconds: float
    status: str
    reason: str
    proof: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "budget_seconds": round(self.budget_seconds, 3),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "status": self.status,
            "reason": self.reason,
            "proof": self.proof,
        }


@dataclass(frozen=True)
class UnifiedResult:
    status: str
    engine: Optional[str]
    attempts: Tuple[Attempt, ...]
    formula_sha256: str
    assignment: Optional[Dict[int, bool]] = None
    certificate: Optional[Sequence[Sequence[Any]]] = None
    order: Tuple[str, ...] = DEFAULT_ORDER
    fractions: Tuple[float, ...] = DEFAULT_FRACTIONS
    detail: Dict[str, Any] = field(default_factory=dict)

    @property
    def schema(self) -> str:
        return SCHEMA

    @property
    def decided(self) -> bool:
        return self.status in (SAT, UNSAT)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": self.status,
            "engine": self.engine,
            "order": list(self.order),
            "fractions": list(self.fractions),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "assignment": {str(k): bool(v) for k, v in self.assignment.items()} if self.assignment else None,
            "certificate_steps": len(self.certificate) if self.certificate else 0,
            "formula_sha256": self.formula_sha256,
            "detail": dict(self.detail),
        }


def budget_split(total: float, count: int, fractions: Sequence[float]) -> Tuple[float, ...]:
    """Split `total` across `count` engines using the declared fractions.

    The fractions are renormalised to `count` entries and the last engine receives the
    remainder, so the parts always add up to `total` (no budget vanishes, none is
    invented). Engines with a zero share are still attempted, with a short floor, because
    a cheap "capability probe" is worth more than skipping an engine silently.
    """
    if total <= 0.0:
        raise ValueError("total budget must be > 0")
    if count < 1:
        raise ValueError("at least one engine is required")
    shares = list(fractions[:count]) + [0.0] * max(0, count - len(fractions))
    # Every engine gets a non-zero slice: a cheap capability probe (and an
    # "unavailable" record for an optional backend) is worth more than silently
    # skipping it. Zero shares receive the floor, and the whole vector is then
    # rescaled so the parts add up to the total exactly.
    floor = 0.02
    shares = [share if share > 0 else floor for share in shares]
    positive = sum(shares)
    if positive <= 0:  # pragma: no cover - defensive
        shares = [1.0] * count
        positive = float(count)
    budgets = [total * (share / positive) for share in shares]
    # Absorb float drift into the largest share so the sum is exact to the last bit.
    drift = total - sum(budgets)
    if budgets:
        largest = max(range(len(budgets)), key=lambda index: budgets[index])
        budgets[largest] += drift
    return tuple(budgets)


def _attempt(engine: str, formula: CNF, budget: float) -> Tuple[Attempt, Optional[Any]]:
    """Run one engine under its own budget; returns the attempt record and its result."""
    started = time.perf_counter()
    try:
        if engine == "watched":
            result = sat.solve(formula, timeout_seconds=budget, certify=False, propagation="watched")
            # The watched engine proves UNSAT by exhaustion but is asked for no
            # certificate here, so the record says exactly that instead of leaving the
            # field empty or pretending a proof exists.
            if result.status == SAT:
                proof = "model verified against the original CNF"
            elif result.status == UNSAT:
                proof = "no certificate produced (exhaustive search; the scan engine produces a tree-resolution proof)"
            else:
                proof = None
            return Attempt(engine, budget, time.perf_counter() - started, result.status, result.note, proof), result
        if engine == "scan":
            result = sat.solve(formula, timeout_seconds=budget, certify=True)
            proof = "tree-resolution certificate checked in-repo" if result.status == UNSAT and result.certificate else None
            return Attempt(engine, budget, time.perf_counter() - started, result.status, result.note, proof), result
        if engine == "omniwave":
            from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine

            omni = OmniwaveEngine(formula, OmniwaveConfig(waves=1, workers=1, timeout_seconds=budget, check_proof=True))
            result = omni.run()
            proof = "DRAT proof checked by cqhecs.drat" if result.status == UNSAT else None
            return Attempt(engine, budget, time.perf_counter() - started, result.status, result.note, proof), result
        if engine == "cadical":
            from cqhecs import sat_external

            if not sat_external.available():
                return Attempt(engine, budget, 0.0, "unavailable", "python-sat is not installed; pip install cqhecs[sat]", None), None
            result = sat_external.solve_external(formula, timeout_seconds=budget, check_proof=True)
            proof = "DRAT proof checked by cqhecs.drat" if result.status == UNSAT else None
            return Attempt(engine, budget, time.perf_counter() - started, result.status, result.note, proof), result
    except Exception as exc:  # noqa: BLE001 - an engine failure is a recorded attempt, not a crash
        return Attempt(engine, budget, time.perf_counter() - started, "error", f"{type(exc).__name__}: {exc}", None), None
    return Attempt(engine, budget, 0.0, "unavailable", "unknown engine", None), None


def solve_unified(
    formula: CNF,
    *,
    engines: Sequence[str] = DEFAULT_ORDER,
    fractions: Sequence[float] = DEFAULT_FRACTIONS,
    timeout_seconds: float = 10.0,
    stop_on_decision: bool = True,
) -> UnifiedResult:
    """Solve with the declared engine order and return one evidence record.

    The first engine that decides wins; ``stop_on_decision=False`` keeps going so a
    caller can compare engines on one formula (used by the measurement script).
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    info = {entry.name: entry for entry in capabilities()}
    unknown = [name for name in engines if name not in info]
    if unknown:
        raise ValueError(f"unknown engine(s): {', '.join(unknown)}")

    budgets = budget_split(timeout_seconds, len(engines), fractions)
    attempts: List[Attempt] = []
    assignment: Optional[Dict[int, bool]] = None
    certificate: Optional[Sequence[Sequence[Any]]] = None
    decided_by: Optional[str] = None
    status = UNKNOWN

    for engine, budget in zip(engines, budgets):
        attempt, result = _attempt(engine, formula, budget)
        attempts.append(attempt)
        if result is None or result.status == UNKNOWN:
            continue
        if result.status == SAT:
            model = result.assignment or {}
            # The portfolio's own re-verification: independent of what the engine claims.
            if not formula.is_satisfied(model):
                attempts[-1] = Attempt(engine, budget, attempt.elapsed_seconds, UNKNOWN,
                                       "engine returned a model that fails verification; refused", None)
                continue
            assignment = dict(model)
            status = SAT
            decided_by = engine
        elif result.status == UNSAT:
            status = UNSAT
            decided_by = engine
            certificate = result.certificate
        else:  # pragma: no cover - defensive
            continue
        if stop_on_decision:
            break

    return UnifiedResult(
        status=status,
        engine=decided_by,
        attempts=tuple(attempts),
        formula_sha256=formula.sha256,
        assignment=assignment,
        certificate=certificate,
        order=tuple(engines),
        fractions=tuple(fractions[: len(engines)]),
        detail={"capabilities": [entry.to_dict() for entry in info.values()]},
    )
