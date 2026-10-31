"""
Independent forward DRAT proof checker.

Used to certify ``UNSAT`` answers of an external solver. The checker shares no code
with any solver: it re-reads the original clauses, replays the proof line by
line, and accepts only if

* every added lemma is **RUP** (unit propagation on the current clause database
  plus the negated lemma reaches a conflict) or **RAT** on its first literal;
* deletions (``d ...``) remove one copy of an existing clause; deleting a clause
  that is not present is an error;
* the empty clause is added and verified.

Deleting clauses can only weaken the database, so honouring deletions never
makes an invalid refutation valid. A step or time budget that runs out gives
``valid=None`` (undecided), never ``True``.

This checker is independent of the solver, but it is not formally verified
the way ``cake_lpr`` is. The documentation states this limit.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Clause = Tuple[int, ...]


class DratFormatError(ValueError):
    """Raised for a syntactically malformed proof line."""


@dataclass(frozen=True)
class DratResult:
    """Outcome of a proof check. ``valid`` is True, False, or None (budget exhausted)."""

    valid: Optional[bool]
    lemmas: int
    rat_lemmas: int
    deletions: int
    propagations: int
    elapsed_ms: float
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "valid": self.valid,
            "lemmas": self.lemmas,
            "rat_lemmas": self.rat_lemmas,
            "deletions": self.deletions,
            "propagations": self.propagations,
            "elapsed_ms": self.elapsed_ms,
            "reason": self.reason,
            "checker": "cqhecs.drat (forward RUP/RAT, not formally verified)",
        }


class _Budget(Exception):
    pass


def parse_drat(lines: Iterable[str]) -> List[Tuple[bool, Clause]]:
    """Parse textual DRAT lines into ``(is_deletion, clause)``; comments are skipped."""
    steps: List[Tuple[bool, Clause]] = []
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        deletion = line.startswith("d")
        body = line[1:].split() if deletion else line.split()
        try:
            literals = [int(token) for token in body]
        except ValueError as exc:
            raise DratFormatError(f"line {number}: non-integer token in {raw!r}") from exc
        if not literals or literals[-1] != 0 or 0 in literals[:-1]:
            raise DratFormatError(f"line {number}: a clause must end with exactly one 0: {raw!r}")
        steps.append((deletion, _normalise(literals[:-1])))
    return steps


def _normalise(literals: Sequence[int]) -> Clause:
    # Keep the first literal first (it is the RAT pivot); drop later duplicates.
    seen: List[int] = []
    for lit in literals:
        if lit not in seen:
            seen.append(lit)
    return tuple(seen)


def _key(clause: Clause) -> Clause:
    return tuple(sorted(set(clause)))


class _Checker:
    def __init__(self, clauses: Iterable[Sequence[int]], deadline: float, max_propagations: int):
        self.db: Counter = Counter(_key(tuple(c)) for c in clauses)
        self.deadline = deadline
        self.max_propagations = max_propagations
        self.propagations = 0

    def _propagates_to_conflict(self, assumptions: Iterable[int]) -> bool:
        """Unit propagation over the database under ``assumptions``; True on conflict."""
        value: Dict[int, bool] = {}
        for lit in assumptions:
            var, val = abs(lit), lit > 0
            if value.get(var, val) != val:
                return True
            value[var] = val
        clauses = [c for c in self.db.elements()]
        changed = True
        while changed:
            changed = False
            if time.perf_counter() > self.deadline or self.propagations > self.max_propagations:
                raise _Budget()
            for clause in clauses:
                unassigned = None
                count = 0
                satisfied = False
                for lit in clause:
                    v = value.get(abs(lit))
                    if v is None:
                        count += 1
                        unassigned = lit
                    elif v == (lit > 0):
                        satisfied = True
                        break
                if satisfied:
                    continue
                if count == 0:
                    return True
                if count == 1:
                    value[abs(unassigned)] = unassigned > 0
                    self.propagations += 1
                    changed = True
        return False

    def rup(self, lemma: Clause) -> bool:
        return self._propagates_to_conflict(-lit for lit in lemma)

    def rat(self, lemma: Clause) -> bool:
        if not lemma:
            return False
        pivot = lemma[0]
        for clause in list(self.db):
            if -pivot not in clause:
                continue
            resolvent = set(lemma) | (set(clause) - {-pivot})
            if any(-lit in resolvent for lit in resolvent):
                continue  # tautology
            if not self._propagates_to_conflict(-lit for lit in resolvent):
                return False
        return True


def check_drat(
    clauses: Iterable[Sequence[int]],
    proof: Iterable[str],
    *,
    timeout_seconds: float = 30.0,
    max_propagations: int = 50_000_000,
) -> DratResult:
    """Check a textual DRAT proof against the original clauses."""
    started = time.perf_counter()
    try:
        steps = parse_drat(proof)
    except DratFormatError as exc:
        return DratResult(False, 0, 0, 0, 0, 0.0, f"malformed proof: {exc}")
    checker = _Checker(clauses, started + float(timeout_seconds), max_propagations)
    lemmas = rat_lemmas = deletions = 0

    def done(valid: Optional[bool], reason: str) -> DratResult:
        return DratResult(valid, lemmas, rat_lemmas, deletions, checker.propagations,
                          (time.perf_counter() - started) * 1000.0, reason)

    try:
        if checker.db[()] > 0:
            return done(True, "the formula contains the empty clause")
        for deletion, clause in steps:
            key = _key(clause)
            if deletion:
                if checker.db[key] == 0:
                    return done(False, f"deletion of a clause that is not present: {list(clause)}")
                checker.db[key] -= 1
                if checker.db[key] == 0:
                    del checker.db[key]
                deletions += 1
                continue
            lemmas += 1
            if not checker.rup(clause):
                if not checker.rat(clause):
                    return done(False, f"lemma {lemmas} is neither RUP nor RAT: {list(clause)}")
                rat_lemmas += 1
            if not clause:
                return done(True, f"empty clause derived after {lemmas} lemmas")
            checker.db[key] += 1
        return done(False, "the proof never derives the empty clause")
    except _Budget:
        return done(None, "check budget exhausted; proof neither accepted nor rejected")
