"""
Exact #SAT by variable (bucket) elimination - the bounded-width counting backend.

This is the production counterpart of the ``research/v6`` separator prototype.
It computes the same quantity as :func:`cqhecs.sat.count_models`: the number of
satisfying assignments over *all* ``2**num_vars`` assignments, as an arbitrary
precision ``int``. It is exact and involves no sampling or floating point.

Method
------
Every non-tautological clause becomes a factor (a sparse table of the clause's
satisfying assignments, each with weight 1). Variables are eliminated one at a
time in a deterministic min-fill order: all factors mentioning the variable are
joined (hash join on the shared variables) and the variable is summed out. When
no variables remain the factors are scalars whose product is the count. Disjoint
components fall out for free (their scalars simply multiply) and variables that
occur in no clause contribute ``2**free``.

An assignment is stored as an ``int`` bit mask whose bit ``v`` is the value of
variable ``v``; joining two factors on shared variables is then ``a | b`` once
``a & shared == b & shared``.

Cost and refusal
----------------
The largest table is bounded by ``2**(induced_width + 1)`` entries, where
``induced_width`` is the maximum number of neighbours a variable has when it is
eliminated under the chosen order (:func:`plan_elimination`, which allocates no
tables). Nothing here ever returns a partial count: exceeding the table budget
or the deadline returns ``UNKNOWN`` with the reason.

Nothing in this module claims to be faster than :func:`cqhecs.sat.count_models`
in general. High-width formulas (e.g. random 3-SAT near the threshold) are
exactly where it refuses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

COUNTED = "COUNTED"
UNKNOWN = "UNKNOWN"

#: Variables beyond which the quadratic ordering heuristic is not attempted.
MAX_PLANNED_VARIABLES = 4000


@dataclass(frozen=True)
class EliminationPlan:
    """Deterministic elimination order plus its width, computed without tables."""

    order: Tuple[int, ...]
    induced_width: int
    num_used_variables: int
    num_free_variables: int

    @property
    def table_entries_upper_bound(self) -> int:
        """Largest dense table size the order can require."""
        return 1 << (self.induced_width + 1)


class SeparatorBudget(Exception):
    """Raised internally when a table or time budget is exhausted."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def normalise_clauses(
    clauses: Iterable[Sequence[int]],
) -> Tuple[bool, List[frozenset]]:
    """
    Drops tautologies and duplicate clauses.

    Returns ``(has_empty_clause, clauses)``. Tautological clauses are satisfied
    by every assignment, so removing them preserves the count; a variable that
    only occurs in tautologies becomes a free variable.
    """
    seen: Set[frozenset] = set()
    out: List[frozenset] = []
    for clause in clauses:
        literals = frozenset(clause)
        if not literals:
            return True, []
        if any(-lit in literals for lit in literals):
            continue
        if literals not in seen:
            seen.add(literals)
            out.append(literals)
    return False, out


def _fill(graph: Dict[int, Set[int]], v: int) -> int:
    nbrs = sorted(graph[v])
    missing = 0
    for i, a in enumerate(nbrs):
        adj = graph[a]
        for b in nbrs[i + 1:]:
            if b not in adj:
                missing += 1
    return missing


def plan_elimination(
    num_vars: int,
    clauses: Sequence[frozenset],
    *,
    deadline: Optional[float] = None,
) -> EliminationPlan:
    """
    Min-fill elimination order on the primal graph of ``clauses``.

    ``clauses`` must already be normalised (see :func:`normalise_clauses`).
    Ties are broken by (degree, variable index), so the order is deterministic.
    """
    graph: Dict[int, Set[int]] = {}
    for clause in clauses:
        variables = sorted({abs(lit) for lit in clause})
        for v in variables:
            graph.setdefault(v, set())
        for i, a in enumerate(variables):
            for b in variables[i + 1:]:
                graph[a].add(b)
                graph[b].add(a)
    used = len(graph)
    if used > MAX_PLANNED_VARIABLES:
        raise SeparatorBudget(
            f"{used} constrained variables exceed the ordering limit "
            f"({MAX_PLANNED_VARIABLES})"
        )
    cost = {v: (_fill(graph, v), len(graph[v]), v) for v in graph}
    order: List[int] = []
    width = 0
    while graph:
        if deadline is not None and time.perf_counter() > deadline:
            raise SeparatorBudget("time budget exhausted while planning the order")
        best = min(cost.values())
        v = best[2]
        nbrs = graph.pop(v)
        del cost[v]
        order.append(v)
        width = max(width, len(nbrs))
        touched = set(nbrs)
        for a in nbrs:
            graph[a].discard(v)
        ordered = sorted(nbrs)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                graph[a].add(b)
                graph[b].add(a)
        for a in nbrs:
            touched |= graph[a]
        for u in touched:
            if u in graph:
                cost[u] = (_fill(graph, u), len(graph[u]), u)
    return EliminationPlan(
        order=tuple(order),
        induced_width=width,
        num_used_variables=used,
        num_free_variables=num_vars - used,
    )


# A factor is (scope_mask, table): scope_mask has bit v set for each variable v
# in scope, and table maps assignment masks (subsets of scope_mask) to weights.
_Factor = Tuple[int, Dict[int, int]]


def _clause_factor(clause: frozenset, max_table: int) -> _Factor:
    variables = sorted({abs(lit) for lit in clause})
    k = len(variables)
    if (1 << k) - 1 > max_table:
        raise SeparatorBudget(
            f"a clause over {k} variables needs {(1 << k) - 1} table entries "
            f"(budget {max_table})"
        )
    scope = 0
    for v in variables:
        scope |= 1 << v
    # The single falsifying assignment sets exactly the variables whose literal
    # is negative (a positive literal is false when its variable is 0).
    falsifying = 0
    for lit in clause:
        if lit < 0:
            falsifying |= 1 << (-lit)
    bits = [1 << v for v in variables]
    table: Dict[int, int] = {}
    for sub in range(1 << k):
        mask = 0
        s = sub
        i = 0
        while s:
            if s & 1:
                mask |= bits[i]
            s >>= 1
            i += 1
        if mask != falsifying:
            table[mask] = 1
    return scope, table


def _join(
    left: _Factor, right: _Factor, max_table: int, deadline: Optional[float]
) -> _Factor:
    lscope, ltable = left
    rscope, rtable = right
    shared = lscope & rscope
    if not shared and len(ltable) * len(rtable) > max_table:
        raise SeparatorBudget(
            f"cross product of {len(ltable)} x {len(rtable)} entries exceeds "
            f"the table budget {max_table}"
        )
    index: Dict[int, List[Tuple[int, int]]] = {}
    for mask, weight in rtable.items():
        index.setdefault(mask & shared, []).append((mask, weight))
    out: Dict[int, int] = {}
    steps = 0
    for lmask, lweight in ltable.items():
        for rmask, rweight in index.get(lmask & shared, ()):
            merged = lmask | rmask
            out[merged] = out.get(merged, 0) + lweight * rweight
        steps += 1
        if steps & 1023 == 0:
            if len(out) > max_table:
                raise SeparatorBudget(
                    f"joined table exceeds the budget {max_table} entries"
                )
            if deadline is not None and time.perf_counter() > deadline:
                raise SeparatorBudget("time budget exhausted")
    if len(out) > max_table:
        raise SeparatorBudget(f"joined table exceeds the budget {max_table} entries")
    return lscope | rscope, out


def _sum_out(factor: _Factor, variable: int) -> _Factor:
    scope, table = factor
    bit = 1 << variable
    out: Dict[int, int] = {}
    for mask, weight in table.items():
        key = mask & ~bit
        out[key] = out.get(key, 0) + weight
    return scope & ~bit, out


def count_by_elimination(
    num_vars: int,
    clauses: Iterable[Sequence[int]],
    *,
    max_table_entries: int = 500_000,
    deadline: Optional[float] = None,
    plan: Optional[EliminationPlan] = None,
) -> Dict[str, object]:
    """
    Exact model count by variable elimination.

    Returns a dict with ``status`` (``COUNTED``/``UNKNOWN``), ``count`` (``int``
    or ``None``), the plan's ``induced_width`` when computed, ``max_table`` (the
    largest table actually materialised) and, for ``UNKNOWN``, a ``reason``.
    The count is over all ``2**num_vars`` assignments.
    """
    if num_vars < 0:
        raise ValueError("num_vars must be >= 0")
    if max_table_entries <= 0:
        raise ValueError("max_table_entries must be > 0")
    materialised = [tuple(c) for c in clauses]
    for clause in materialised:
        for lit in clause:
            if lit == 0 or abs(lit) > num_vars:
                raise ValueError(f"literal {lit} is outside 1..{num_vars}")
    has_empty, normal = normalise_clauses(materialised)
    if has_empty:
        return {
            "status": COUNTED, "count": 0, "induced_width": 0, "max_table": 0,
            "free_variables": num_vars,
        }
    info: Dict[str, object] = {"induced_width": None, "max_table": 0}
    try:
        if plan is None:
            plan = plan_elimination(num_vars, normal, deadline=deadline)
        info["induced_width"] = plan.induced_width
        info["free_variables"] = plan.num_free_variables
        factors: List[_Factor] = []
        peak = 0
        for clause in normal:
            factor = _clause_factor(clause, max_table_entries)
            peak = max(peak, len(factor[1]))
            factors.append(factor)
        for v in plan.order:
            bit = 1 << v
            touching = [f for f in factors if f[0] & bit]
            if not touching:
                continue
            factors = [f for f in factors if not f[0] & bit]
            touching.sort(key=lambda f: len(f[1]))
            joined = touching[0]
            for other in touching[1:]:
                joined = _join(joined, other, max_table_entries, deadline)
                peak = max(peak, len(joined[1]))
            reduced = _sum_out(joined, v)
            peak = max(peak, len(reduced[1]))
            if not reduced[1]:
                info["max_table"] = peak
                return {"status": COUNTED, "count": 0, **info}
            factors.append(reduced)
        info["max_table"] = peak
        total = 1 << plan.num_free_variables
        for scope, table in factors:
            if scope:
                # Cannot happen for a complete order; fail closed.
                raise SeparatorBudget("variables remained after elimination")
            total *= table.get(0, 0)
        return {"status": COUNTED, "count": total, **info}
    except SeparatorBudget as exc:
        return {"status": UNKNOWN, "count": None, "reason": exc.reason, **info}
