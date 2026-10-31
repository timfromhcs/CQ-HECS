"""
Sound DIMACS CNF solving for CQ-HECS.

This module is deliberately separate from ``python_bridge.sat_engine``, a
demonstrator (its earlier hash/timeout defects, CQ-V3-02, are fixed there). The
engine here is the supported surface:

* ``SAT`` means a model was found **and verified clause by clause**;
* ``UNSAT`` means the search space was exhausted; by default it also carries a
  **tree-resolution refutation** (``SATResult.certificate``) that a separate
  checker, :func:`check_refutation`, replays: unit propagation at every leaf,
  one resolution per inner node. ``certified`` is True only after that check;
* ``UNKNOWN`` means a timeout or node budget stopped the search, or that the
  two search procedures disagreed (fail closed).

The default engine scans every clause during propagation. ``solve(...,
propagation="watched")`` selects a second engine with two watched literals per
non-unit clause and a propagation queue. It deliberately keeps the same decision
variable, polarity and pure-literal rule so a comparison isolates the propagation
data structure. The tree-resolution certificate is always produced by the
independent scan-based certifying search described below.

The certificate comes from a second search that uses unit propagation only
(pure-literal elimination preserves satisfiability but is not a resolution
step). If that search finds a model where the main search found none, the
procedures contradict each other and the result is ``UNKNOWN``. A certificate
that is too large or too slow to produce leaves ``UNSAT`` exhaustive but
``certified=False``, and the note says why.

The public model predicate treats an unassigned variable as unassigned, not as
``False``. A partial assignment can therefore never satisfy a negative literal by
accident; only a genuine full model verifies.

The random-3-SAT sweep is an empirical runtime measurement. A curve that looks
exponential is not a proof of the Exponential Time Hypothesis, and no finite
sweep can decide ``P = NP``.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SAT = "SAT"
UNSAT = "UNSAT"
UNKNOWN = "UNKNOWN"

#: Version of the SAT result dictionary. 1.2 adds the original-input digest and
#: the watched propagation label; 1.1 added ``certification``, ``proof_system``,
#: ``engine`` and this field. Nothing was removed.
RESULT_CONTRACT_VERSION = "1.2"

#: Values of ``SATResult.certification``.
CERTIFICATIONS = ("MODEL_VERIFIED", "TREE_RESOLUTION_CHECKED", "DRAT_CHECKED", "UNCERTIFIED", "NONE")

_CLAUSE_SEPARATORS = {"0"}


class CNFFormatError(ValueError):
    """Raised when DIMACS input is malformed instead of guessing a repair."""


@dataclass(frozen=True)
class CNF:
    """A CNF formula in DIMACS numbering (variables are ``1..num_vars``)."""

    num_vars: int
    clauses: Tuple[Tuple[int, ...], ...]
    source: Optional[str] = None
    #: SHA-256 of the input text as supplied. ``sha256`` is the canonical form;
    #: this field binds the result to the original bytes/text when available.
    original_sha256: Optional[str] = field(default=None, compare=False)

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

    @staticmethod
    def _clause_satisfied(clause: Sequence[int], assignment: Dict[int, bool]) -> bool:
        """
        True if a literal of ``clause`` is true under ``assignment``.

        An unassigned variable is *not* treated as ``False``: otherwise every
        negative literal would count as satisfied on a partial assignment.
        Model verification therefore only accepts a genuine full model.
        """
        for literal in clause:
            value = assignment.get(abs(literal))
            if value is not None and value == (literal > 0):
                return True
        return False

    def is_satisfied(self, assignment: Dict[int, bool]) -> bool:
        """True only if every clause has at least one true literal."""
        return all(self._clause_satisfied(clause, assignment) for clause in self.clauses)

    def first_unsatisfied(self, assignment: Dict[int, bool]) -> Optional[int]:
        for index, clause in enumerate(self.clauses):
            if not self._clause_satisfied(clause, assignment):
                return index
        return None


def parse_dimacs(text: str, source: Optional[str] = None) -> CNF:
    """
    Parse DIMACS CNF.

    Comments (``c``) and the optional ``%`` terminator are ignored. Clauses may
    span lines. A missing ``p cnf`` header is an error; silently inferring the
    variable count would hide a truncated file. Repeated literals inside one
    clause are removed (``1 1 0`` is the unit clause ``1``): DIMACS permits them
    and the native parser accepts them too. A clause with both signs
    (``1 -1 0``) is kept as a tautology. Construct :class:`CNF` directly if
    strict rejection is required.
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
                clauses.append(tuple(dict.fromkeys(pending)))
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
    return CNF(
        num_vars=num_vars,
        clauses=tuple(clauses),
        source=source,
        original_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


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
    #: SHA-256 of the original DIMACS text, when the formula came from the parser.
    formula_original_sha256: Optional[str] = None
    #: Tree-resolution refutation (see :func:`check_refutation`); only for UNSAT.
    certificate: Optional[Tuple[Tuple[Any, ...], ...]] = None
    #: True only if ``certificate`` passed :func:`check_refutation`, or an
    #: external DRAT proof passed :func:`cqhecs.drat.check_drat`.
    certified: bool = False
    #: Proof system of a certified UNSAT: ``"tree-resolution"``, ``"DRAT"`` or None.
    proof_system: Optional[str] = None
    #: ``"dpll"`` (built-in) or ``"cadical"`` (:mod:`cqhecs.sat_external`).
    engine: str = "dpll"

    @property
    def certification(self) -> str:
        """How the verdict is backed: one of :data:`CERTIFICATIONS`."""
        if self.status == SAT:
            return "MODEL_VERIFIED" if self.model_verified else "NONE"
        if self.status == UNSAT:
            if not self.certified:
                return "UNCERTIFIED"
            return "DRAT_CHECKED" if self.proof_system == "DRAT" else "TREE_RESOLUTION_CHECKED"
        return "NONE"

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
            "formula_original_sha256": self.formula_original_sha256,
            "note": self.note,
            "certified": self.certified,
            "certificate_steps": len(self.certificate) if self.certificate else 0,
            "certification": self.certification,
            "proof_system": self.proof_system if self.certified else None,
            "engine": self.engine,
            "contract_version": RESULT_CONTRACT_VERSION,
        }

    def certificate_to_jsonable(self) -> Optional[List[List[Any]]]:
        """The certificate as plain lists (``["leaf", [lits]]``, ``["resolve", var]``)."""
        if self.certificate is None:
            return None
        return [[kind, list(arg) if kind == "leaf" else arg] for kind, arg in self.certificate]


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


class _WatchedDPLL(_DPLL):
    """
    DPLL with two-watched-literal unit propagation.

    The search order (decision variable, polarity and pure-literal
    elimination) is deliberately identical to :class:`_DPLL`. The first
    comparison therefore isolates the propagation data structure instead of
    mixing in a second heuristic change.

    Watch positions are not undone on backtracking: they remain valid because
    a watch only moves to a literal that was not false at the time. Assignments
    are undone through the trail, and ``qhead`` is reset to the trail length.
    """

    def __init__(self, formula: CNF, timeout_seconds: float, deadline: float, node_budget: Optional[int] = None):
        super().__init__(formula, timeout_seconds, deadline, node_budget)
        #: literal -> clause indices that watch it
        self._watches: Dict[int, List[int]] = {}
        #: clause index -> two literal positions, or None for unit/empty clauses
        self._watch_pos: List[Optional[List[int]]] = [None] * formula.num_clauses
        self._qhead = 0
        self._initial_conflict = False
        self._initialize_watches()

    def _initialize_watches(self) -> None:
        for index, clause in enumerate(self.formula.clauses):
            if len(clause) == 0:
                self._initial_conflict = True
            elif len(clause) == 1:
                if not self._assign_literal(clause[0]):
                    self._initial_conflict = True
                else:
                    self.propagations += 1
            else:
                positions = [0, 1]
                self._watch_pos[index] = positions
                for literal in (clause[0], clause[1]):
                    self._watches.setdefault(literal, []).append(index)

    def _undo(self, mark: int) -> None:
        super()._undo(mark)
        if self._qhead > len(self.trail):
            self._qhead = len(self.trail)

    def _bcp(self) -> bool:
        """Propagate all enqueued literals; False on conflict."""
        while self._qhead < len(self.trail):
            true_literal = self.trail[self._qhead]
            self._qhead += 1
            false_literal = -true_literal
            watch_list = self._watches.get(false_literal)
            if not watch_list:
                continue
            position = 0
            while position < len(watch_list):
                clause_index = watch_list[position]
                clause = self.formula.clauses[clause_index]
                watches = self._watch_pos[clause_index]
                if watches is None:  # pragma: no cover - invariant guard
                    watch_list[position] = watch_list[-1]
                    watch_list.pop()
                    continue
                if clause[watches[0]] == false_literal:
                    false_watch, other_watch = 0, 1
                elif clause[watches[1]] == false_literal:
                    false_watch, other_watch = 1, 0
                else:  # pragma: no cover - would mean a stale watch entry
                    watch_list[position] = watch_list[-1]
                    watch_list.pop()
                    continue
                other_literal = clause[watches[other_watch]]
                other_value = self._value(other_literal)
                if other_value == 1:
                    position += 1
                    continue
                replacement = -1
                for candidate, literal in enumerate(clause):
                    if candidate == watches[0] or candidate == watches[1]:
                        continue
                    if self._value(literal) != -1:
                        replacement = candidate
                        break
                if replacement >= 0:
                    watches[false_watch] = replacement
                    watch_list[position] = watch_list[-1]
                    watch_list.pop()
                    self._watches.setdefault(clause[replacement], []).append(clause_index)
                    continue
                if other_value == -1:
                    self.conflicts += 1
                    return False
                if not self._assign_literal(other_literal):
                    self.conflicts += 1
                    return False
                self.propagations += 1
                position += 1
        return True

    def _assign_pure_literals(self) -> bool:
        """Assign literals whose variable now occurs with one polarity only."""
        polarities: Dict[int, int] = {}
        for clause in self.formula.clauses:
            if any(self._value(literal) == 1 for literal in clause):
                continue
            open_literals = [literal for literal in clause if self._value(literal) == 0]
            if len(open_literals) < 2:
                continue
            for literal in open_literals:
                variable = abs(literal)
                polarities[variable] = polarities.get(variable, 0) | (1 if literal > 0 else 2)
        changed = False
        for variable, mask in polarities.items():
            if mask not in (1, 2) or self.assignment[variable] != 0:
                continue
            literal = variable if mask == 1 else -variable
            if not self._assign_literal(literal):
                self.conflicts += 1
                return False
            self.propagations += 1
            changed = True
        return changed

    def _propagate(self) -> bool:
        if self._initial_conflict:
            self.conflicts += 1
            return False
        while True:
            if not self._bcp():
                return False
            if not self._assign_pure_literals():
                return True

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
            self._qhead = len(self.trail)
        self._undo(mark)
        self._qhead = len(self.trail)
        return False


#: Largest refutation produced (steps). A larger one is not kept.
MAX_CERTIFICATE_STEPS = 200_000


class _CertificateTooLarge(Exception):
    pass


def _unit_propagation_conflicts(clauses: Sequence[Sequence[int]], decisions: Sequence[int]) -> bool:
    """True if unit propagation on ``clauses`` under the literals ``decisions`` reaches a conflict."""
    value: Dict[int, bool] = {}
    for literal in decisions:
        var, want = abs(literal), literal > 0
        if var == 0 or value.get(var, want) != want:
            return var != 0
        value[var] = want
    changed = True
    while changed:
        changed = False
        for clause in clauses:
            open_literal = 0
            open_count = 0
            satisfied = False
            for literal in clause:
                known = value.get(abs(literal))
                if known is None:
                    open_count += 1
                    open_literal = literal
                elif known == (literal > 0):
                    satisfied = True
                    break
            if satisfied:
                continue
            if open_count == 0:
                return True
            if open_count == 1:
                value[abs(open_literal)] = open_literal > 0
                changed = True
    return False


def check_refutation(clauses: Sequence[Sequence[int]], certificate: Optional[Sequence[Sequence[Any]]]) -> bool:
    """
    Check a tree-resolution refutation of ``clauses``. Independent of the search.

    ``certificate`` is a post-order list of steps:

    * ``("leaf", decisions)``: unit propagation on ``clauses`` under the decision
      literals must reach a conflict; this derives the clause of the negated
      decisions;
    * ``("resolve", x)``: the entry below the top was derived under the decision
      ``x`` (it contains ``-x``), the top under ``-x`` (it contains ``x``); their
      resolvent replaces both.

    True iff every step holds and exactly one clause is left, the empty one. A
    valid certificate proves that ``clauses`` is unsatisfiable.
    """
    if not certificate:
        return False
    stack: List[frozenset] = []
    for step in certificate:
        if len(step) != 2:
            return False
        kind, argument = step
        if kind == "leaf":
            decisions = tuple(argument)
            if not all(isinstance(lit, int) and not isinstance(lit, bool) for lit in decisions):
                return False
            if not _unit_propagation_conflicts(clauses, decisions):
                return False
            stack.append(frozenset(-lit for lit in decisions))
        elif kind == "resolve":
            if not isinstance(argument, int) or isinstance(argument, bool) or argument == 0 or len(stack) < 2:
                return False
            false_branch = stack.pop()
            true_branch = stack.pop()
            if -argument not in true_branch or argument not in false_branch:
                return False
            stack.append((true_branch - {-argument}) | (false_branch - {argument}))
        else:
            return False
    return len(stack) == 1 and not stack[0]


class _CertifyingDPLL(_DPLL):
    """Plain DPLL (unit propagation only) that records a tree-resolution refutation."""

    def __init__(self, formula: CNF, deadline: float, step_cap: int):
        super().__init__(formula, 0.0, deadline, None)
        self.proof: List[Tuple[Any, ...]] = []
        self.step_cap = step_cap
        self._decisions: List[int] = []

    def _log(self, step: Tuple[Any, ...]) -> None:
        if len(self.proof) >= self.step_cap:
            raise _CertificateTooLarge
        self.proof.append(step)

    def _propagate(self) -> bool:
        while True:
            changed = False
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
                    return False
                if unassigned == 1:
                    self._assign_literal(last)
                    changed = True
            if not changed:
                return True

    def search(self, depth: int = 0) -> bool:
        self.nodes += 1
        self.max_depth = max(self.max_depth, depth)
        self._ticks += 1
        if (self._ticks & 1023) == 0 and time.perf_counter() > self.deadline:
            raise _Timeout
        mark = len(self.trail)
        if not self._propagate():
            self._log(("leaf", tuple(self._decisions)))
            self._undo(mark)
            return False
        if self._all_satisfied():
            return True
        variable = self._choose_variable()
        if variable is None:
            return True
        for value in (1, -1):  # True branch first: the checker relies on this order
            literal = variable if value == 1 else -variable
            branch_mark = len(self.trail)
            self._decisions.append(literal)
            found = self._assign_literal(literal) and self.search(depth + 1)
            self._decisions.pop()
            if found:
                return True
            self._undo(branch_mark)
        self._log(("resolve", variable))
        self._undo(mark)
        return False


def _certify(formula: CNF, timeout_seconds: float) -> Tuple[Optional[Tuple[Tuple[Any, ...], ...]], str, str]:
    """
    Produce and check a refutation. Returns ``(certificate, outcome, note)`` with
    outcome ``CERTIFIED``, ``NOT_PRODUCED`` or ``DISAGREEMENT``.
    """
    import sys

    if any(len(clause) == 0 for clause in formula.clauses):
        certificate = (("leaf", ()),)
        if check_refutation(formula.clauses, certificate):
            return certificate, "CERTIFIED", "empty clause; trivial certificate checked"
        return None, "DISAGREEMENT", "empty clause present but the trivial certificate failed its check"
    engine = _CertifyingDPLL(formula, time.perf_counter() + float(timeout_seconds), MAX_CERTIFICATE_STEPS)
    old_limit = sys.getrecursionlimit()
    needed = max(2000, 4 * formula.num_vars + 1000)
    try:
        if old_limit < needed:
            sys.setrecursionlimit(needed)
        found = engine.search()
    except _Timeout:
        return None, "NOT_PRODUCED", f"certificate not produced: {float(timeout_seconds):.6g} s budget exhausted"
    except _CertificateTooLarge:
        return None, "NOT_PRODUCED", f"certificate not produced: more than {MAX_CERTIFICATE_STEPS} steps"
    finally:
        if sys.getrecursionlimit() != old_limit:
            sys.setrecursionlimit(old_limit)
    if found:
        return None, "DISAGREEMENT", "the certifying search found a model where the main search found none"
    certificate = tuple(engine.proof)
    if not check_refutation(formula.clauses, certificate):
        return None, "DISAGREEMENT", "the recorded refutation failed the independent checker"
    return certificate, "CERTIFIED", f"tree-resolution certificate checked ({len(certificate)} steps)"


def solve(
    formula: CNF,
    timeout_seconds: float = 10.0,
    node_budget: Optional[int] = None,
    certify: bool = True,
    certificate_timeout_seconds: Optional[float] = None,
    propagation: str = "scan",
) -> SATResult:
    """
    Solve ``formula`` soundly. Timeout or node budget yields ``UNKNOWN``.

    With ``certify`` (default) an UNSAT verdict is followed by a certifying
    search. ``certificate_timeout_seconds`` is its own budget, additionally
    capped by the remaining wall-clock budget of the solve call: the certificate
    never extends the advertised deadline. If no time remains, the verdict stays
    ``UNSAT`` but ``certified=False`` and the note says why.

    ``propagation="watched"`` selects the two-watched-literal engine. It uses
    the same decision order and pure-literal rule as the default ``"scan"``
    engine, so a comparison isolates the propagation data structure. The
    tree-resolution certificate is always produced by the independent
    scan-based certifying search.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    if node_budget is not None and node_budget <= 0:
        raise ValueError("node_budget must be > 0 when provided")
    if propagation not in ("scan", "watched"):
        raise ValueError("propagation must be 'scan' or 'watched'")
    started = time.perf_counter()
    deadline = started + float(timeout_seconds)
    engine: _DPLL
    if propagation == "watched":
        engine = _WatchedDPLL(formula, float(timeout_seconds), deadline, node_budget)
    else:
        engine = _DPLL(formula, float(timeout_seconds), deadline, node_budget)
    status: str
    assignment: Optional[Dict[int, bool]] = None
    note: str
    certificate: Optional[Tuple[Tuple[Any, ...], ...]] = None
    certified = False

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
                note = "exhaustive DPLL search; no certificate requested"
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

    if status == UNSAT and certify:
        configured = float(timeout_seconds if certificate_timeout_seconds is None else certificate_timeout_seconds)
        remaining = deadline - time.perf_counter()
        budget = min(configured, max(0.0, remaining))
        if budget <= 0.0:
            certificate, outcome, certificate_note = (
                None,
                "NOT_PRODUCED",
                "certificate not produced: the solve deadline is exhausted",
            )
        else:
            certificate, outcome, certificate_note = _certify(formula, budget)
        if outcome == "DISAGREEMENT":
            status = UNKNOWN
            note = f"UNSAT withheld: {certificate_note}; refusing to report either verdict"
        else:
            certified = outcome == "CERTIFIED"
            note = f"exhaustive DPLL search; {certificate_note}"

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
        formula_original_sha256=formula.original_sha256,
        note=note,
        certificate=certificate if status == UNSAT else None,
        certified=bool(certified and status == UNSAT),
        proof_system="tree-resolution" if (certified and status == UNSAT) else None,
        engine="dpll-watched" if propagation == "watched" else "dpll",
    )


def enumerate_models(
    formula: CNF,
    limit: int = 10,
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """
    Enumerate up to ``limit`` models by adding a blocking clause after each.

    ``complete`` is true only when the solver proved that no further model
    exists. Hitting the limit or the shared timeout is reported explicitly.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")
    started = time.perf_counter()
    deadline = started + float(timeout_seconds)
    clauses = list(formula.clauses)
    models: List[Dict[int, bool]] = []
    status = "UNKNOWN"
    complete_certified = False
    while len(models) < limit:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            status = "TIMEOUT"
            break
        current = CNF(num_vars=formula.num_vars, clauses=tuple(clauses), source=formula.source)
        result = solve(current, timeout_seconds=remaining)
        if result.status == UNSAT:
            status = "COMPLETE"
            complete_certified = result.certified
            break
        if result.status != SAT or result.assignment is None:
            status = "UNKNOWN"
            break
        models.append(dict(result.assignment))
        # Block exactly this assignment.
        clauses.append(tuple(-var if value else var for var, value in sorted(result.assignment.items())))
    else:
        status = "LIMIT"
    return {
        "status": status,
        "complete": status == "COMPLETE",
        "complete_certified": complete_certified,
        "count": len(models),
        "limit": limit,
        "models": models,
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
        "formula_sha256": formula.sha256,
        "formula_original_sha256": formula.original_sha256,
    }


COUNTED = "COUNTED"


class _CountBudget(Exception):
    pass


def count_models(
    formula: CNF,
    timeout_seconds: float = 10.0,
    node_budget: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Exact model count ``#F`` over all ``2^num_vars`` assignments.

    #SAT is its own problem, not SAT with a counter: the result is ``COUNTED`` with
    an exact integer (serialized as a decimal string, so counts beyond 2^53
    survive JSON) or ``UNKNOWN`` when the time or node budget runs out. The
    method is exact DPLL counting: unit propagation, splitting into
    variable-disjoint components whose counts multiply, a cache keyed by the
    component's clause set, and ``2^k`` for the ``k`` unconstrained variables.
    No sampling or approximation is involved.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    started = time.perf_counter()
    deadline = started + float(timeout_seconds)
    stats = {"nodes": 0, "cache_hits": 0}
    cache: Dict[frozenset, int] = {}

    def simplify(clauses: List[frozenset], lit: int) -> Optional[List[frozenset]]:
        out = []
        for clause in clauses:
            if lit in clause:
                continue
            if -lit in clause:
                reduced = clause - {-lit}
                if not reduced:
                    return None
                out.append(reduced)
            else:
                out.append(clause)
        return out

    def count(clauses: List[frozenset], variables: frozenset) -> int:
        stats["nodes"] += 1
        if (node_budget is not None and stats["nodes"] > node_budget) or (
            stats["nodes"] % 256 == 0 and time.perf_counter() > deadline
        ):
            raise _CountBudget()
        # Unit propagation: fixed variables leave the count unchanged.
        while True:
            unit = next((next(iter(c)) for c in clauses if len(c) == 1), None)
            if unit is None:
                break
            reduced = simplify(clauses, unit)
            if reduced is None:
                return 0
            clauses = reduced
            variables = variables - {abs(unit)}
        if not clauses:
            return 1 << len(variables)
        key = frozenset(clauses)
        constrained = frozenset(abs(lit) for c in clauses for lit in c)
        free = len(variables - constrained)
        if key in cache:
            stats["cache_hits"] += 1
            return cache[key] << free
        # Split into variable-disjoint components; their counts multiply.
        components: List[Tuple[List[frozenset], set]] = []
        for clause in clauses:
            vars_ = {abs(lit) for lit in clause}
            merged = [comp for comp in components if comp[1] & vars_]
            for comp in merged:
                components.remove(comp)
            new_clauses = [clause] + [c for comp in merged for c in comp[0]]
            new_vars = set(vars_).union(*(comp[1] for comp in merged)) if merged else set(vars_)
            components.append((new_clauses, new_vars))
        if len(components) > 1:
            total = 1
            for comp_clauses, comp_vars in components:
                part = count(comp_clauses, frozenset(comp_vars))
                if part == 0:
                    total = 0
                    break
                total *= part
            cache[key] = total
            return total << free
        # Branch on the most frequent variable.
        occurrences: Dict[int, int] = {}
        for clause in clauses:
            for lit in clause:
                occurrences[abs(lit)] = occurrences.get(abs(lit), 0) + 1
        var = max(occurrences, key=lambda v: (occurrences[v], -v))
        rest = constrained - {var}
        total = 0
        for lit in (var, -var):
            branch = simplify(clauses, lit)
            if branch is not None:
                total += count(branch, rest)
        cache[key] = total
        return total << free

    status = COUNTED
    value: Optional[int] = None
    note = "exact DPLL counting with component decomposition and caching"
    if any(len(c) == 0 for c in formula.clauses):
        value, note = 0, "empty clause present; count is 0 without search"
    else:
        try:
            value = count(
                [frozenset(c) for c in formula.clauses],
                frozenset(range(1, formula.num_vars + 1)),
            )
        except _CountBudget:
            status, value = UNKNOWN, None
            note = "time or node budget exhausted; no count claimed"
    return {
        "status": status,
        "count": str(value) if value is not None else None,
        "satisfiable": None if value is None else value > 0,
        "num_vars": formula.num_vars,
        "num_clauses": formula.num_clauses,
        "nodes": stats["nodes"],
        "cache_hits": stats["cache_hits"],
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
        "method": "exact (DPLL counting, components, cache)",
        "note": note,
        "formula_sha256": formula.sha256,
        "formula_original_sha256": formula.original_sha256,
        "contract_version": RESULT_CONTRACT_VERSION,
    }


def max_sat(
    formula: CNF,
    clause_weights: Optional[Sequence[float]] = None,
    *,
    max_vars: int = 20,
) -> Dict[str, Any]:
    """
    Exact weighted MaxSAT by exhaustive enumeration for small formulas.

    This is deliberately bounded: exact MaxSAT is NP-hard, and this function
    refuses above ``max_vars`` instead of pretending to scale. A larger
    instance needs a real MaxSAT solver, not this function.
    """
    if formula.num_vars > max_vars:
        raise ValueError(
            f"exact max_sat is limited to {max_vars} variables; got {formula.num_vars}"
        )
    if clause_weights is None:
        weights = [1.0] * formula.num_clauses
    else:
        weights = [float(w) for w in clause_weights]
        if len(weights) != formula.num_clauses:
            raise ValueError("clause_weights must have one entry per clause")
        if any(w < 0 for w in weights):
            raise ValueError("clause_weights must be non-negative")
    best_assignment: Dict[int, bool] = {}
    best_score = -1.0
    best_satisfied: List[int] = []
    best_unsatisfied: List[int] = []
    for bits in range(1 << formula.num_vars):
        assignment = {
            var: bool((bits >> (var - 1)) & 1) for var in range(1, formula.num_vars + 1)
        }
        satisfied = [
            index
            for index, clause in enumerate(formula.clauses)
            if any(assignment[abs(lit)] == (lit > 0) for lit in clause)
        ]
        satisfied_set = set(satisfied)
        score = sum(weights[index] for index in satisfied)
        if score > best_score:
            best_score = score
            best_assignment = assignment
            best_satisfied = satisfied
            best_unsatisfied = [i for i in range(formula.num_clauses) if i not in satisfied_set]
    return {
        "status": "OPTIMAL",
        "satisfied_weight": best_score,
        "total_weight": sum(weights),
        "assignment": best_assignment,
        "satisfied_clauses": best_satisfied,
        "unsatisfied_clauses": best_unsatisfied,
        "num_vars": formula.num_vars,
        "num_clauses": formula.num_clauses,
        "method": f"exhaustive over 2^{formula.num_vars} assignments",
        "formula_sha256": formula.sha256,
        "formula_original_sha256": formula.original_sha256,
    }


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
                result = solve(formula, timeout_seconds=timeout_seconds, certify=False)
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
        proof = (
            f"certificate checked ({len(result.certificate)} steps)"
            if result.certified
            else "not certified"
        )
        return f"UNSAT in {result.elapsed_ms:.1f} ms after {result.decisions} decisions ({proof})"
    return f"UNKNOWN: {result.note}"


def result_to_json(result: SATResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)
