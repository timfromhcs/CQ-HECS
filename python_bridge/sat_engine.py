"""
CQ-HECS DIMACS CNF SAT engine (pure-Python DPLL).

Result semantics (GEMINI.md §3.1/§3.2):

* ``SAT_VERIFIED``: a full assignment that an independent clause check accepts;
* ``UNSAT_PROVEN``: the DPLL search was exhaustive. Branches are skipped only
  when an *identical* partial assignment (exact key, no hash) was already
  refuted, which is sound because the residual formula is a function of the
  assignment;
* ``TIMEOUT_UNKNOWN``: the wall-clock budget ran out; this is never UNSAT.
"""

from __future__ import annotations
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, Union

from python_bridge.cq_hecs import JSpaceAlpha, JSpaceGamma


@dataclass
class CNFFormula:
    num_vars: int
    num_clauses: int
    clauses: List[List[int]]
    source_file: Optional[str] = None


SAT_VERIFIED = "SAT_VERIFIED"
UNSAT_PROVEN = "UNSAT_PROVEN"
TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"


@dataclass
class SATSolverResult:
    """
    ``satisfiable`` is ``True`` (SAT), ``False`` (UNSAT proven) or ``None``
    (unknown, e.g. timeout). ``verified`` is ``True`` only for a checked SAT
    witness or an exhaustive UNSAT search.
    """

    satisfiable: Optional[bool]
    assignment: Optional[Dict[int, bool]]
    num_decisions: int
    num_pruned_cycles: int
    elapsed_ms: float
    verified: bool
    status: str = UNSAT_PROVEN
    timed_out: bool = False


class _SearchTimeout(Exception):
    """Raised inside the search when the budget is exhausted."""


class DIMACSParseError(ValueError):
    """Malformed or out-of-limit DIMACS input (never silently repaired)."""


class DIMACSParser:
    """
    Strict DIMACS CNF parser with the same grammar and limits as the native
    parser in ``src/sat_solver.cpp`` (GEMINI.md 3.3):

    * a clause ends at ``0`` and may span lines; ``0`` alone is an empty clause;
    * an unterminated final clause, a malformed or duplicate header, a negative
      count and a literal above the declared variable count are errors;
    * without a header the variable count is the largest literal seen;
    * the declared clause count is informational, as in the native parser.
    """

    MAX_VARIABLES = 1_000_000
    MAX_CLAUSES = 4_000_000
    MAX_CLAUSE_LITERALS = 1_000_000
    MAX_INPUT_BYTES = 64 * 1024 * 1024

    @staticmethod
    def parse_file(file_path: Union[str, Path]) -> CNFFormula:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        formula = DIMACSParser.parse_string(content)
        formula.source_file = str(file_path)
        return formula

    @staticmethod
    def parse_string(content: str) -> CNFFormula:
        limits = DIMACSParser
        if len(content.encode("utf-8")) > limits.MAX_INPUT_BYTES:
            raise DIMACSParseError(f"DIMACS input exceeds the {limits.MAX_INPUT_BYTES}-byte limit")
        num_vars = 0
        saw_header = False
        clauses: List[List[int]] = []
        current: List[int] = []
        line_number = 0

        def fail(message: str) -> DIMACSParseError:
            return DIMACSParseError(f"line {line_number}: {message}")

        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("p"):
                if saw_header:
                    raise fail("duplicate 'p cnf' header")
                tokens = line.split()
                if len(tokens) != 4 or tokens[0] != "p" or tokens[1] != "cnf":
                    raise fail("malformed DIMACS header; expected 'p cnf <vars> <clauses>'")
                if not (tokens[2].isdigit() and tokens[3].isdigit()):
                    raise fail("DIMACS header counts must be non-negative integers")
                declared_vars, declared_clauses = int(tokens[2]), int(tokens[3])
                if declared_vars > limits.MAX_VARIABLES:
                    raise fail(f"header declares {declared_vars} variables; the ceiling is {limits.MAX_VARIABLES}")
                if declared_clauses > limits.MAX_CLAUSES:
                    raise fail(f"header declares {declared_clauses} clauses; the ceiling is {limits.MAX_CLAUSES}")
                num_vars = declared_vars
                saw_header = True
                continue
            for token in line.split():
                body = token[1:] if token[:1] in "+-" else token
                if not body.isdigit():
                    raise fail(f"invalid DIMACS literal '{token}'")
                literal = int(token)
                if literal == 0:
                    if len(clauses) >= limits.MAX_CLAUSES:
                        raise fail(f"clause count exceeds the ceiling of {limits.MAX_CLAUSES}")
                    clauses.append(current)
                    current = []
                    continue
                magnitude = abs(literal)
                if magnitude > limits.MAX_VARIABLES:
                    raise fail(f"literal {token} exceeds the variable ceiling {limits.MAX_VARIABLES}")
                if saw_header and magnitude > num_vars:
                    raise fail(f"literal {token} exceeds the declared variable count {num_vars}")
                if len(current) >= limits.MAX_CLAUSE_LITERALS:
                    raise fail(f"clause exceeds the literal ceiling of {limits.MAX_CLAUSE_LITERALS}")
                current.append(literal)
                num_vars = max(num_vars, magnitude)
        if current:
            raise fail("final clause is not terminated by 0")
        return CNFFormula(num_vars=num_vars, num_clauses=len(clauses), clauses=clauses)


class CQSATSolver:
    """
    DPLL with unit propagation and an exact memo of refuted partial
    assignments. ``num_pruned_cycles`` counts memo hits (identical states).
    The J-Space Gamma hash table is kept for API compatibility but never
    decides a branch: a hash match is not proof of identical states.
    """
    def __init__(self, table_capacity: int = 4096):
        self.table_capacity = table_capacity
        self.gamma = JSpaceGamma(table_capacity=table_capacity)
        self.alpha = JSpaceAlpha(bit_width=64)
        self.num_decisions = 0
        self.num_pruned_cycles = 0

    def solve(self, formula: CNFFormula, timeout_seconds: float = 10.0) -> SATSolverResult:
        t_start = time.perf_counter()
        self.gamma = JSpaceGamma(table_capacity=self.table_capacity)
        self.num_decisions = 0
        self.num_pruned_cycles = 0
        self._refuted: Set[FrozenSet[Tuple[int, bool]]] = set()

        assignment: Dict[int, bool] = {}
        try:
            sat, final_assignment = self._dpll(
                formula.clauses, assignment, formula.num_vars, t_start, timeout_seconds
            )
        except _SearchTimeout:
            return SATSolverResult(
                satisfiable=None,
                assignment=None,
                num_decisions=self.num_decisions,
                num_pruned_cycles=self.num_pruned_cycles,
                elapsed_ms=(time.perf_counter() - t_start) * 1000.0,
                verified=False,
                status=TIMEOUT_UNKNOWN,
                timed_out=True,
            )
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        if sat and final_assignment is not None:
            # A witness is only reported if an independent check accepts it.
            if not self._verify_solution(formula.clauses, final_assignment):
                raise RuntimeError("internal error: DPLL produced an assignment that fails the clause check")
            return SATSolverResult(
                satisfiable=True,
                assignment=final_assignment,
                num_decisions=self.num_decisions,
                num_pruned_cycles=self.num_pruned_cycles,
                elapsed_ms=elapsed_ms,
                verified=True,
                status=SAT_VERIFIED,
            )
        return SATSolverResult(
            satisfiable=False,
            assignment=None,
            num_decisions=self.num_decisions,
            num_pruned_cycles=self.num_pruned_cycles,
            elapsed_ms=elapsed_ms,
            verified=True,  # exhaustive search, exact-key memo only
            status=UNSAT_PROVEN,
        )

    def _dpll(
        self, clauses: List[List[int]], assignment: Dict[int, bool], 
        total_vars: int, t_start: float, timeout_sec: float
    ) -> Tuple[bool, Optional[Dict[int, bool]]]:
        if time.perf_counter() - t_start > timeout_sec:
            raise _SearchTimeout()

        self.num_decisions += 1

        # 1. Unit Propagation
        simplified_clauses, assignment = self._unit_propagate(clauses, assignment)
        if simplified_clauses is None:
            return False, None # Conflict detected

        # 2. Check if all clauses are satisfied
        if not simplified_clauses:
            # Complete remaining unassigned variables
            for v in range(1, total_vars + 1):
                if v not in assignment:
                    assignment[v] = True
            return True, assignment

        # 3. Check for empty clause (unsatisfiable state)
        if any(len(c) == 0 for c in simplified_clauses):
            return False, None

        # 4. Exact memo: the residual formula is determined by the original
        # clauses and the partial assignment, so an identical assignment that
        # was already refuted is refuted again. The key is the full assignment
        # (no hash), so distinct states can never be merged.
        state_key = frozenset(assignment.items())
        if state_key in self._refuted:
            self.num_pruned_cycles += 1
            return False, None

        # 5. Variable Selection Heuristic (MOM's / Maximum Occurrence in Minimum Clauses)
        chosen_var = self._select_variable(simplified_clauses)
        if chosen_var is None:
            return True, assignment

        # 6. Branching: Try True, then False
        for val in (True, False):
            next_assignment = dict(assignment)
            next_assignment[chosen_var] = val

            # Substitute into clauses
            sub_clauses = self._substitute_var(simplified_clauses, chosen_var, val)
            sat, res_assignment = self._dpll(sub_clauses, next_assignment, total_vars, t_start, timeout_sec)
            if sat:
                return True, res_assignment

        # Both branches were searched to completion (a timeout raises).
        self._refuted.add(state_key)
        return False, None

    def _unit_propagate(
        self, clauses: List[List[int]], assignment: Dict[int, bool]
    ) -> Tuple[Optional[List[List[int]]], Dict[int, bool]]:
        current_clauses = [list(c) for c in clauses]
        current_assignment = dict(assignment)

        changed = True
        while changed:
            changed = False
            # Find unit clause
            unit_lit = None
            for c in current_clauses:
                if len(c) == 1:
                    unit_lit = c[0]
                    break

            if unit_lit is not None:
                changed = True
                var = abs(unit_lit)
                val = (unit_lit > 0)
                if var in current_assignment and current_assignment[var] != val:
                    return None, current_assignment # Direct contradiction!
                current_assignment[var] = val
                current_clauses = self._substitute_var(current_clauses, var, val)
                if any(len(c) == 0 for c in current_clauses):
                    return None, current_assignment

        return current_clauses, current_assignment

    @staticmethod
    def _substitute_var(clauses: List[List[int]], var: int, val: bool) -> List[List[int]]:
        new_clauses = []
        for c in clauses:
            if (var in c and val) or (-var in c and not val):
                # Clause is satisfied by this assignment, drop it
                continue
            # Remove the falsified literal: if val is True, -var is false; if val is False, +var is false
            falsified_lit = -var if val else var
            filtered = [lit for lit in c if lit != falsified_lit]
            new_clauses.append(filtered)
        return new_clauses

    @staticmethod
    def _select_variable(clauses: List[List[int]]) -> Optional[int]:
        # Count literal frequencies in shortest clauses
        min_len = min(len(c) for c in clauses) if clauses else 1
        freq: Dict[int, int] = {}
        for c in clauses:
            if len(c) <= min_len + 1:
                for lit in c:
                    v = abs(lit)
                    freq[v] = freq.get(v, 0) + 1
        if not freq:
            return None
        return max(freq.items(), key=lambda item: item[1])[0]

    @staticmethod
    def _compute_state_hash(assignment: Dict[int, bool]) -> int:
        """Projects partial variable assignment into a 64-bit coordinate key."""
        h = 0x123456789ABCDEF0
        for var in sorted(assignment.keys())[:32]:
            bit = 1 if assignment[var] else 0
            h ^= ((var * 0x9e3779b97f4a7c15) + bit) & 0xFFFFFFFFFFFFFFFF
            h = ((h << 7) | (h >> 57)) & 0xFFFFFFFFFFFFFFFF
        return h

    @staticmethod
    def _verify_solution(clauses: List[List[int]], assignment: Dict[int, bool]) -> bool:
        """Top Non-Master isolated forward verification."""
        for c in clauses:
            satisfied = False
            for lit in c:
                var = abs(lit)
                expected_val = (lit > 0)
                if assignment.get(var, False) == expected_val:
                    satisfied = True
                    break
            if not satisfied:
                return False
        return True
