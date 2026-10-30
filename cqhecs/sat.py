"""
Sound DIMACS CNF solving for CQ-HECS.

This module is deliberately separate from ``python_bridge.sat_engine``. The
bridge engine is a demonstrator whose branch-pruning hash covers only the first
32 assigned variables and whose timeout is reported as ``UNSAT``; both are
unsound for real DIMACS input. The engine here is the supported surface:

* ``SAT`` means a model was found **and verified clause by clause**;
* ``UNSAT`` means the search space was exhausted;
* ``UNKNOWN`` means a timeout or node budget stopped the search.

No proof object is produced for ``UNSAT``. The result says so instead of
pretending that "the loop ended" is a certificate.

The random-3-SAT sweep is an empirical runtime measurement. A curve that looks
exponential is not a proof of the Exponential Time Hypothesis, and no finite
sweep can decide ``P = NP``.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SAT = "SAT"
UNSAT = "UNSAT"
UNKNOWN = "UNKNOWN"

_CLAUSE_SEPARATORS = {"0"}


class CNFFormatError(ValueError):
    """Raised when DIMACS input is malformed instead of guessing a repair."""


@dataclass(frozen=True)
class CNF:
    """A CNF formula in DIMACS numbering (variables are ``1..num_vars``)."""

    num_vars: int
    clauses: Tuple[Tuple[int, ...], ...]
    source: Optional[str] = None

    def __post_init__(self) -> None:
        if self.num_vars < 0:
            raise CNFFormatError(f"num_vars must be >= 0, got {self.num_vars}")
        for index, clause in enumerate(self.clauses):
            if not clause:
                # An empty clause is legal DIMACS and immediately UNSAT.
                continue
            for literal in clause:
                if not isinstance(literal, int) or isinstance(literal, bool):
                    raise CNFFormatError(f"clause {index}: literal {literal!r} is not an int")
                if literal == 0:
                    raise CNFFormatError(f"clause {index}: 0 is a terminator, not a literal")
                if abs(literal) > self.num_vars:
                    raise CNFFormatError(
                        f"clause {index}: literal {literal} exceeds num_vars={self.num_vars}"
                    )
            if len(set(clause)) != len(clause):
                raise CNFFormatError(f"clause {index}: duplicated literal {clause}")

    @property
    def num_clauses(self) -> int:
        return len(self.clauses)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_dimacs().encode("ascii")).hexdigest()

    def to_dimacs(self) -> str:
        lines = [f"p cnf {self.num_vars} {self.num_clauses}"]
        for clause in self.clauses:
            lines.append(" ".join(str(lit) for lit in clause) + " 0")
        return "\n".join(lines) + "\n"

    def is_satisfied(self, assignment: Dict[int, bool]) -> bool:
        """True only if every clause has at least one true literal."""
        for clause in self.clauses:
            if not any(assignment.get(abs(lit), False) == (lit > 0) for lit in clause):
                return False
        return True

    def first_unsatisfied(self, assignment: Dict[int, bool]) -> Optional[int]:
        for index, clause in enumerate(self.clauses):
            if not any(assignment.get(abs(lit), False) == (lit > 0) for lit in clause):
                return index
        return None


def parse_dimacs(text: str, source: Optional[str] = None) -> CNF:
    """
    Parse DIMACS CNF.

    Comments (``c``) and the optional ``%`` terminator are ignored. Clauses may
    span lines. A missing ``p cnf`` header is an error; silently inferring the
    variable count would hide a truncated file.
    """
    if not isinstance(text, str):
        raise CNFFormatError("DIMACS input must be text")
    num_vars: Optional[int] = None
    declared_clauses: Optional[int] = None
    clauses: List[Tuple[int, ...]] = []
    pending: List[int] = []

    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("c"):
            continue
        if line.startswith("%"):
            break
        if line.startswith("p"):
            if num_vars is not None:
                raise CNFFormatError(f"line {line_number}: duplicate problem header")
            parts = line.split()
            if len(parts) != 4 or parts[1].lower() != "cnf":
                raise CNFFormatError(f"line {line_number}: expected 'p cnf <vars> <clauses>'")
            try:
                num_vars = int(parts[2])
                declared_clauses = int(parts[3])
            except ValueError as exc:
                raise CNFFormatError(f"line {line_number}: header counts are not integers") from exc
            if num_vars < 0 or declared_clauses < 0:
                raise CNFFormatError(f"line {line_number}: header counts must be non-negative")
            continue
        if num_vars is None:
            raise CNFFormatError(f"line {line_number}: clause before the 'p cnf' header")
        for token in line.split():
            try:
                literal = int(token)
            except ValueError as exc:
                raise CNFFormatError(f"line {line_number}: {token!r} is not an integer") from exc
            if literal == 0:
                clauses.append(tuple(pending))
                pending = []
            else:
                pending.append(literal)

    if num_vars is None:
        raise CNFFormatError("missing 'p cnf' header")
    if pending:
        raise CNFFormatError("last clause is not terminated by 0")
    if declared_clauses is not None and declared_clauses != len(clauses):
        raise CNFFormatError(
            f"header declares {declared_clauses} clauses, parsed {len(clauses)}"
        )
    return CNF(num_vars=num_vars, clauses=tuple(clauses), source=source)


def load_dimacs(path: Path | str) -> CNF:
    path = Path(path)
    return parse_dimacs(path.read_text("utf-8"), source=str(path))


def random_3sat(num_vars: int, num_clauses: int, seed: int = 0) -> CNF:
    """Uniform random 3-CNF with three distinct variables per clause."""
    if num_vars < 3:
        raise ValueError("random_3sat needs at least 3 variables")
    if num_clauses < 0:
        raise ValueError("num_clauses must be >= 0")
    import random

    rng = random.Random(seed)
    clauses: List[Tuple[int, ...]] = []
    for _ in range(num_clauses):
        variables = rng.sample(range(1, num_vars + 1), 3)
        clause = tuple(var if rng.random() < 0.5 else -var for var in variables)
        clauses.append(clause)
    return CNF(num_vars=num_vars, clauses=tuple(clauses), source=f"random:3sat:n={num_vars}:m={num_clauses}:seed={seed}")


@dataclass(frozen=True)
class SATResult:
    status: str
    assignment: Optional[Dict[int, bool]]
    decisions: int
    propagations: int
    conflicts: int
    nodes: int
    max_depth: int
    elapsed_ms: float
    timeout_seconds: float
    model_verified: bool
    formula_sha256: str
    note: str

    @property
    def satisfiable(self) -> Optional[bool]:
        """``True``/``False`` for decided formulas, ``None`` for UNKNOWN."""
        return {SAT: True, UNSAT: False}.get(self.status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "satisfiable": self.satisfiable,
            "assignment": (
                {str(k): bool(v) for k, v in sorted(self.assignment.items())}
                if self.assignment is not None
                else None
            ),
            "decisions": self.decisions,
            "propagations": self.propagations,
            "conflicts": self.conflicts,
            "nodes": self.nodes,
            "max_depth": self.max_depth,
            "elapsed_ms": self.elapsed_ms,
            "timeout_seconds": self.timeout_seconds,
            "model_verified": self.model_verified,
            "formula_sha256": self.formula_sha256,
            "note": self.note,
        }


class _Timeout(Exception):
    pass


class _NodeLimit(Exception):
    pass


class _DPLL:
    def __init__(self, formula: CNF, timeout_seconds: float, deadline: float, node_budget: Optional[int] = None):
        self.formula = formula
        self.timeout_seconds = timeout_seconds
        self.deadline = deadline
        self.node_budget = node_budget
        self.assignment: List[int] = [0] * (formula.num_vars + 1)
        self.trail: List[int] = []
        self.decisions = 0
        self.propagations = 0
        self.conflicts = 0
        self.nodes = 0
        self.max_depth = 0
        self._ticks = 0

    # -- assignment -----------------------------------------------------
    def _value(self, literal: int) -> int:
        value = self.assignment[abs(literal)]
        return value if literal > 0 else -value

    def _assign_literal(self, literal: int) -> bool:
        """Assign; return False on a direct contradiction."""
        var = abs(literal)
        value = 1 if literal > 0 else -1
        current = self.assignment[var]
        if current == 0:
            self.assignment[var] = value
            self.trail.append(literal)
            return True
        return current == value

    def _undo(self, mark: int) -> None:
        while len(self.trail) > mark:
            literal = self.trail.pop()
            self.assignment[abs(literal)] = 0

    # -- propagation ----------------------------------------------------
    def _propagate(self) -> bool:
        """
        Unit propagation followed by pure-literal elimination.

        Both rules are sound: they only assign literals forced by the current
        formula. Returns False on conflict.
        """
        while True:
            changed = False
            polarities: Dict[int, int] = {}
            for clause in self.formula.clauses:
                unassigned = 0
                last = 0
                satisfied = False
                for literal in clause:
                    value = self._value(literal)
                    if value == 1:
                        satisfied = True
                        break
                    if value == 0:
                        unassigned += 1
                        last = literal
                if satisfied:
                    continue
                if unassigned == 0:
                    self.conflicts += 1
                    return False
                if unassigned == 1:
                    if not self._assign_literal(last):
                        self.conflicts += 1
                        return False
                    self.propagations += 1
                    changed = True
                else:
                    for literal in clause:
                        if self._value(literal) == 0:
                            var = abs(literal)
                            polarities[var] = polarities.get(var, 0) | (1 if literal > 0 else 2)
            if not changed:
                # Pure literals: a variable that only occurs with one sign can
                # be fixed to that sign without losing satisfiability.
                for var, mask in polarities.items():
                    if self.assignment[var] == 0 and mask in (1, 2):
                        if not self._assign_literal(var if mask == 1 else -var):
                            self.conflicts += 1
                            return False
                        self.propagations += 1
                        changed = True
                if not changed:
                    return True

    def _all_satisfied(self) -> bool:
        for clause in self.formula.clauses:
            if not any(self._value(literal) == 1 for literal in clause):
                return False
        return True

    def _choose_variable(self) -> Optional[int]:
        """Jeroslow-Wang: weight variables in short unsatisfied clauses."""
        scores: Dict[int, float] = {}
        for clause in self.formula.clauses:
            if any(self._value(literal) == 1 for literal in clause):
                continue
            weight = 2.0 ** (-len(clause))
            for literal in clause:
                if self._value(literal) == 0:
                    scores[abs(literal)] = scores.get(abs(literal), 0.0) + weight
        if not scores:
            return None
        return max(scores.items(), key=lambda item: (item[1], -item[0]))[0]

    # -- search ---------------------------------------------------------
    def search(self, depth: int = 0) -> bool:
        self.nodes += 1
        if self.node_budget is not None and self.nodes > self.node_budget:
            raise _NodeLimit
        self.max_depth = max(self.max_depth, depth)
        self._ticks += 1
        if (self._ticks & 1023) == 0 and time.perf_counter() > self.deadline:
            raise _Timeout

        mark = len(self.trail)
        if not self._propagate():
            self._undo(mark)
            return False
        if self._all_satisfied():
            return True
        variable = self._choose_variable()
        if variable is None:
            return True

        for value in (1, -1):
            self.decisions += 1
            branch_mark = len(self.trail)
            if self._assign_literal(variable if value == 1 else -variable):
                if self.search(depth + 1):
                    return True
            self._undo(branch_mark)
        self._undo(mark)
        return False

    def model(self) -> Dict[int, bool]:
        return {
            var: self.assignment[var] == 1
            for var in range(1, self.formula.num_vars + 1)
        }


def solve(
    formula: CNF,
    timeout_seconds: float = 10.0,
    node_budget: Optional[int] = None,
) -> SATResult:
    """Solve ``formula`` soundly. Timeout or node budget yields ``UNKNOWN``."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    if node_budget is not None and node_budget <= 0:
        raise ValueError("node_budget must be > 0 when provided")
    started = time.perf_counter()
    deadline = started + float(timeout_seconds)
    engine = _DPLL(formula, float(timeout_seconds), deadline, node_budget)
    status: str
    assignment: Optional[Dict[int, bool]] = None
    note: str

    # An empty clause makes the formula UNSAT without any search.
    if any(len(clause) == 0 for clause in formula.clauses):
        status = UNSAT
        note = "empty clause present; UNSAT without search"
    else:
        old_limit = None
        try:
            import sys

            needed = max(2000, 4 * formula.num_vars + 1000)
            if sys.getrecursionlimit() < needed:
                old_limit = sys.getrecursionlimit()
                sys.setrecursionlimit(needed)
            found = engine.search()
            if found:
                candidate = engine.model()
                if formula.is_satisfied(candidate):
                    status = SAT
                    assignment = candidate
                    note = "model verified clause by clause"
                else:  # pragma: no cover - defensive; would be an engine bug
                    status = UNKNOWN
                    note = "engine produced a model that failed verification; refusing it"
            else:
                status = UNSAT
                note = "exhaustive DPLL search; no independently checkable proof object"
        except _Timeout:
            status = UNKNOWN
            note = f"timeout after {float(timeout_seconds):.6g} s; result not decided"
        except _NodeLimit:
            status = UNKNOWN
            note = f"node budget {node_budget} exhausted; result not decided"
        finally:
            if old_limit is not None:
                import sys

                sys.setrecursionlimit(old_limit)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return SATResult(
        status=status,
        assignment=assignment,
        decisions=engine.decisions,
        propagations=engine.propagations,
        conflicts=engine.conflicts,
        nodes=engine.nodes,
        max_depth=engine.max_depth,
        elapsed_ms=elapsed_ms,
        timeout_seconds=float(timeout_seconds),
        model_verified=bool(status == SAT and assignment is not None and formula.is_satisfied(assignment)),
        formula_sha256=formula.sha256,
        note=note,
    )


def sweep(
    sizes: Sequence[int] = (10, 15, 20, 25, 30),
    ratios: Sequence[float] = (3.0, 3.5, 4.0, 4.26, 4.5, 5.0),
    trials: int = 5,
    timeout_seconds: float = 2.0,
    seed: int = 20261030,
) -> Dict[str, Any]:
    """
    Empirical random-3-SAT sweep around the phase transition.

    The result is a measurement of *this* solver on *these* instances. It is not
    a proof of ETH and says nothing about ``P`` versus ``NP``.
    """
    if trials <= 0:
        raise ValueError("trials must be > 0")
    rows: List[Dict[str, Any]] = []
    for num_vars in sizes:
        if num_vars < 3:
            raise ValueError("sizes must be >= 3")
        for ratio in ratios:
            if ratio < 0:
                raise ValueError("ratios must be >= 0")
            num_clauses = int(round(ratio * num_vars))
            counts = {SAT: 0, UNSAT: 0, UNKNOWN: 0}
            decisions: List[int] = []
            times: List[float] = []
            for trial in range(trials):
                instance_seed = seed + 1_000_003 * num_vars + 9_176 * trial + int(ratio * 1000)
                formula = random_3sat(num_vars, num_clauses, seed=instance_seed)
                result = solve(formula, timeout_seconds=timeout_seconds)
                counts[result.status] += 1
                decisions.append(result.decisions)
                times.append(result.elapsed_ms)
            decided = counts[SAT] + counts[UNSAT]
            rows.append(
                {
                    "num_vars": num_vars,
                    "ratio": float(ratio),
                    "num_clauses": num_clauses,
                    "trials": trials,
                    "sat": counts[SAT],
                    "unsat": counts[UNSAT],
                    "unknown": counts[UNKNOWN],
                    "sat_fraction_decided": (counts[SAT] / decided) if decided else None,
                    "median_decisions": _median(decisions),
                    "max_decisions": max(decisions) if decisions else 0,
                    "median_ms": _median(times),
                    "timeout_seconds": float(timeout_seconds),
                }
            )
    return {
        "schema_version": "1.0",
        "generator": "uniform random 3-SAT, three distinct variables per clause",
        "seed": seed,
        "rows": rows,
        "non_claim": (
            "Empirical runtime curve for one DPLL implementation. An exponential-looking "
            "curve is not a proof of the Exponential Time Hypothesis, and no finite sweep "
            "decides P versus NP."
        ),
    }


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2.0)


def summarize(result: SATResult) -> str:
    if result.status == SAT:
        return f"SAT in {result.elapsed_ms:.1f} ms, {result.decisions} decisions, model verified"
    if result.status == UNSAT:
        return f"UNSAT in {result.elapsed_ms:.1f} ms after {result.decisions} decisions (no proof object)"
    return f"UNKNOWN: {result.note}"


def result_to_json(result: SATResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)
