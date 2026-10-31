"""
CNF to a sparse quadratic system over GF(2), preserving the model count exactly.

A literal's truth value is ``t = x`` (positive) or ``t = 1 + x`` (negative). A clause
``(l1 ∨ … ∨ lk)`` is false exactly when ``Π (1 + t_i) = 1``. Equations used:

* k = 1:  ``1 + t1 = 0``                          (linear)
* k = 2:  ``(1 + t1)(1 + t2) = 0``                (quadratic)
* k ≥ 3:  auxiliary ``u_2 = (1+t1)(1+t2)``, ``u_j = u_{j-1}(1+t_j)`` for
          j = 3 … k-1, and ``u_{k-1}(1+t_k) = 0``. Every equation has degree ≤ 2.

Each ``u_j`` is defined by an equality, so every assignment of the original
variables has exactly one extension to the auxiliary variables, and the last
equation holds iff the clause is satisfied. Hence

    #solutions(system) = #models(F)

which ``tests/test_omniwave.py`` checks exhaustively. A polynomial is a set of
monomials; a monomial is a ``frozenset`` of variables (the empty set is the
constant 1). Coefficients are in GF(2), so equal monomials cancel, and
``x^2 = x`` holds because a monomial is a set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Tuple

Monomial = FrozenSet[int]
Polynomial = FrozenSet[Monomial]


def _add(*polys: Polynomial) -> Polynomial:
    acc: Dict[Monomial, int] = {}
    for poly in polys:
        for mono in poly:
            acc[mono] = acc.get(mono, 0) ^ 1
    return frozenset(m for m, c in acc.items() if c)


def _mul(a: Polynomial, b: Polynomial) -> Polynomial:
    acc: Dict[Monomial, int] = {}
    for ma in a:
        for mb in b:
            m = ma | mb
            acc[m] = acc.get(m, 0) ^ 1
    return frozenset(m for m, c in acc.items() if c)


ONE: Polynomial = frozenset({frozenset()})


def var(v: int) -> Polynomial:
    return frozenset({frozenset({v})})


def falsity(lit: int) -> Polynomial:
    """``1 + t`` for literal ``lit``: equals 1 exactly when the literal is false."""
    t = var(abs(lit)) if lit > 0 else _add(ONE, var(abs(lit)))
    return _add(ONE, t)


@dataclass(frozen=True)
class QuadraticSystem:
    num_original: int
    num_vars: int  # original + auxiliary
    equations: Tuple[Polynomial, ...]  # each means "polynomial = 0"
    formula_sha256: str

    @property
    def max_degree(self) -> int:
        return max((len(m) for eq in self.equations for m in eq), default=0)

    def evaluate(self, assignment: Sequence[int]) -> bool:
        """``assignment[v]`` in {0,1} for v = 1..num_vars (index 0 unused)."""
        for eq in self.equations:
            value = 0
            for mono in eq:
                value ^= int(all(assignment[v] for v in mono))
            if value:
                return False
        return True


def encode(clauses: Sequence[Sequence[int]], num_vars: int, formula_sha256: str = "") -> QuadraticSystem:
    """Encode a CNF as a degree-≤2 GF(2) system with auxiliary variables."""
    equations: List[Polynomial] = []
    next_var = num_vars
    for clause in clauses:
        lits = list(dict.fromkeys(clause))  # duplicate literals do not change a clause
        if any(-lit in lits for lit in lits):
            continue  # tautology: always satisfied, contributes no equation
        if not lits:
            equations.append(ONE)  # empty clause: "1 = 0", unsatisfiable
            continue
        if len(lits) <= 2:
            poly = ONE
            for lit in lits:
                poly = _mul(poly, falsity(lit))
            equations.append(poly)
            continue
        next_var += 1
        u = next_var
        # u_2 = (1+t1)(1+t2)  ->  u_2 + (1+t1)(1+t2) = 0
        equations.append(_add(var(u), _mul(falsity(lits[0]), falsity(lits[1]))))
        for lit in lits[2:-1]:
            next_var += 1
            u_next = next_var
            equations.append(_add(var(u_next), _mul(var(u), falsity(lit))))
            u = u_next
        equations.append(_mul(var(u), falsity(lits[-1])))
    return QuadraticSystem(num_vars, next_var, tuple(equations), formula_sha256)
