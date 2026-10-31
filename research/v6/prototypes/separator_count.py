"""
Research prototype: exact #SAT by bucket elimination over CNF factors.

This is a small, readable separator/variable-elimination counter for low-width
formulas. It is **not** wired into `cqhecs.sat.count_models` and does not claim
competition performance. The point is to have an independent exact oracle with a
real width/table budget:

* each clause becomes a factor over its variables;
* factors are multiplied (join) and a variable is summed out at a time;
* the elimination order is a min-fill heuristic on the primal graph;
* a table-size limit returns ``UNKNOWN`` instead of truncating a count.

All arithmetic is Python ``int``; there is no floating point or sampling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

UNKNOWN = "UNKNOWN"
COUNTED = "COUNTED"


@dataclass(frozen=True)
class Factor:
    """A non-negative integer table over ``variables`` (bit i = variable vars[i])."""

    variables: Tuple[int, ...]
    table: Dict[int, int]

    def project(self, keep: Sequence[int]) -> "Factor":
        keep = tuple(sorted(keep))
        index = {var: i for i, var in enumerate(keep)}
        out: Dict[int, int] = {}
        for mask, value in self.table.items():
            mapped = 0
            for i, var in enumerate(self.variables):
                if var in index and mask >> i & 1:
                    mapped |= 1 << index[var]
            out[mapped] = out.get(mapped, 0) + value
        return Factor(keep, out)


def _clause_factor(clause: Sequence[int]) -> Factor:
    variables = tuple(sorted({abs(literal) for literal in clause}))
    table: Dict[int, int] = {}
    for mask in range(1 << len(variables)):
        assignment = {var: bool(mask >> i & 1) for i, var in enumerate(variables)}
        table[mask] = 1 if any(assignment[abs(l)] == (l > 0) for l in clause) else 0
    return Factor(variables, table)


def _join(left: Factor, right: Factor) -> Factor:
    variables = tuple(sorted(set(left.variables) | set(right.variables)))
    left_index = {var: i for i, var in enumerate(left.variables)}
    right_index = {var: i for i, var in enumerate(right.variables)}
    position = {var: i for i, var in enumerate(variables)}
    shared = set(left.variables) & set(right.variables)
    table: Dict[int, int] = {}
    for left_mask, left_value in left.table.items():
        if left_value == 0:
            continue
        for right_mask, right_value in right.table.items():
            if right_value == 0:
                continue
            if any(
                ((left_mask >> left_index[var]) & 1) != ((right_mask >> right_index[var]) & 1)
                for var in shared
            ):
                continue
            merged = 0
            for var, i in left_index.items():
                if left_mask >> i & 1:
                    merged |= 1 << position[var]
            for var, i in right_index.items():
                if right_mask >> i & 1:
                    merged |= 1 << position[var]
            table[merged] = table.get(merged, 0) + left_value * right_value
    return Factor(variables, table)


def _sum_out(factor: Factor, variable: int) -> Factor:
    keep = tuple(var for var in factor.variables if var != variable)
    index = {var: i for i, var in enumerate(keep)}
    table: Dict[int, int] = {}
    for mask, value in factor.table.items():
        mapped = 0
        for i, var in enumerate(factor.variables):
            if var != variable and mask >> i & 1:
                mapped |= 1 << index[var]
        table[mapped] = table.get(mapped, 0) + value
    return Factor(keep, table)


def _primal_graph(clauses: Sequence[Sequence[int]]) -> Dict[int, set]:
    graph: Dict[int, set] = {}
    for clause in clauses:
        variables = sorted({abs(literal) for literal in clause})
        for var in variables:
            graph.setdefault(var, set())
        for i, var in enumerate(variables):
            for other in variables[i + 1:]:
                graph[var].add(other)
                graph[other].add(var)
    return graph


def _min_fill_order(graph: Dict[int, set]) -> List[int]:
    """Greedy min-fill: remove the vertex that adds the fewest edges."""
    graph = {var: set(neighbours) for var, neighbours in graph.items()}
    order: List[int] = []
    while graph:
        best = None
        best_cost = None
        for var, neighbours in graph.items():
            missing = 0
            neighbours = sorted(neighbours)
            for i, first in enumerate(neighbours):
                for second in neighbours[i + 1:]:
                    if second not in graph[first]:
                        missing += 1
            cost = (missing, len(neighbours), var)
            if best_cost is None or cost < best_cost:
                best, best_cost = var, cost
        assert best is not None
        order.append(best)
        neighbours = graph.pop(best)
        for first in neighbours:
            graph[first].discard(best)
        for i, first in enumerate(sorted(neighbours)):
            for second in sorted(neighbours)[i + 1:]:
                graph[first].add(second)
                graph[second].add(first)
    return order


def count_models(
    num_vars: int,
    clauses: Sequence[Sequence[int]],
    *,
    max_table_entries: int = 1_000_000,
) -> Dict[str, object]:
    """
    Exact count by bucket elimination.

    Returns ``COUNTED`` with an integer ``count`` or ``UNKNOWN`` when the
    intermediate table would exceed ``max_table_entries``. The count is over all
    ``2^num_vars`` assignments; variables not occurring in any clause are free.
    """
    if num_vars < 0:
        raise ValueError("num_vars must be >= 0")
    if max_table_entries <= 0:
        raise ValueError("max_table_entries must be > 0")
    if any(not clause for clause in clauses):
        return {"status": COUNTED, "count": 0, "max_table": 0, "order": []}
    used = {abs(literal) for clause in clauses for literal in clause}
    if any(abs(literal) > num_vars for clause in clauses for literal in clause):
        raise ValueError("literal exceeds num_vars")

    factors: List[Factor] = [_clause_factor(clause) for clause in clauses]
    graph = _primal_graph(clauses)
    for var in range(1, num_vars + 1):
        graph.setdefault(var, set())
    order = _min_fill_order(graph)
    max_table = max((len(factor.table) for factor in factors), default=0)

    for variable in order:
        touching = [factor for factor in factors if variable in factor.variables]
        if not touching:
            continue
        factors = [factor for factor in factors if variable not in factor.variables]
        joined = touching[0]
        for factor in touching[1:]:
            joined = _join(joined, factor)
            max_table = max(max_table, len(joined.table))
            if len(joined.table) > max_table_entries:
                return {
                    "status": UNKNOWN,
                    "count": None,
                    "max_table": max_table,
                    "order": order,
                    "reason": "intermediate factor exceeds max_table_entries",
                }
        reduced = _sum_out(joined, variable)
        max_table = max(max_table, len(reduced.table))
        if len(reduced.table) > max_table_entries:
            return {
                "status": UNKNOWN,
                "count": None,
                "max_table": max_table,
                "order": order,
                "reason": "reduced factor exceeds max_table_entries",
            }
        factors.append(reduced)

    total = 1
    for factor in factors:
        if not factor.variables:
            total *= factor.table.get(0, 0)
        else:
            # A remaining factor cannot happen for a complete elimination order;
            # fail closed rather than return a partial product.
            return {
                "status": UNKNOWN,
                "count": None,
                "max_table": max_table,
                "order": order,
                "reason": "uneliminated variables",
            }
    free = num_vars - len(used)
    total *= 1 << free
    return {"status": COUNTED, "count": total, "max_table": max_table, "order": order, "free": free}
