"""
Exact linear algebra over GF(2) with bit-packed rows (Python ints as bit vectors).

* :class:`XorSystem`: equations ``Hx = b`` (mod 2), deterministic Gaussian
  elimination (lowest free pivot column first), rank, consistency and the exact
  solution count ``2^(n - rank)``.
* :func:`rank` and :func:`rank_factorization`: ``M = U V`` over GF(2), with ``U``
  of shape ``rows x r`` and ``V`` of shape ``r x cols``, ``r = rank_GF2(M)``. The
  rank is the GF(2) rank, never a floating-point one.

Everything is exact integer arithmetic; there is no tolerance anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Matrix = List[int]  # row i is an int whose bit j is M[i][j]


def _bits(row: int, width: int) -> List[int]:
    return [(row >> j) & 1 for j in range(width)]


@dataclass(frozen=True)
class XorSystem:
    """Rows ``(mask, parity)``: bit i of ``mask`` is variable i+1; Σ x_i = parity (mod 2)."""

    num_vars: int
    rows: Tuple[Tuple[int, int], ...]

    def reduced(self) -> Tuple[Optional[List[Tuple[int, int]]], int]:
        """Row-reduce. Returns ``(rows, rank)``; rows is None if the system is inconsistent."""
        rows = [list(r) for r in self.rows]
        rank = 0
        for bit in range(self.num_vars):
            pivot = next((i for i in range(rank, len(rows)) if rows[i][0] >> bit & 1), None)
            if pivot is None:
                continue
            rows[rank], rows[pivot] = rows[pivot], rows[rank]
            for i in range(len(rows)):
                if i != rank and rows[i][0] >> bit & 1:
                    rows[i][0] ^= rows[rank][0]
                    rows[i][1] ^= rows[rank][1]
            rank += 1
        if any(mask == 0 and parity == 1 for mask, parity in rows[rank:]):
            return None, rank
        return [tuple(r) for r in rows[:rank]], rank

    def count_solutions(self) -> int:
        rows, rank = self.reduced()
        return 0 if rows is None else 1 << (self.num_vars - rank)

    def satisfied(self, x: Sequence[bool]) -> bool:
        return all(
            (sum(x[i] for i in range(self.num_vars) if mask >> i & 1) & 1) == parity
            for mask, parity in self.rows
        )


def rank(matrix: Sequence[int], cols: int) -> int:
    """GF(2) rank of a matrix given as row bit masks."""
    rows = list(matrix)
    r = 0
    for bit in range(cols):
        pivot = next((i for i in range(r, len(rows)) if rows[i] >> bit & 1), None)
        if pivot is None:
            continue
        rows[r], rows[pivot] = rows[pivot], rows[r]
        for i in range(len(rows)):
            if i != r and rows[i] >> bit & 1:
                rows[i] ^= rows[r]
        r += 1
    return r


def rank_factorization(matrix: Sequence[int], cols: int) -> Tuple[Matrix, Matrix, int]:
    """
    Exact ``M = U V`` over GF(2) with inner dimension ``r = rank(M)``.

    ``V`` is the nonzero rows of the reduced row-echelon form of ``M`` (an ``r x cols``
    basis of the row space); ``U[i]`` holds the coefficients expressing row ``i`` of
    ``M`` in that basis (read off at the pivot columns). Returns ``(U, V, r)``.
    """
    rows = list(matrix)
    echelon = list(rows)
    pivots: List[int] = []
    r = 0
    for bit in range(cols):
        pivot = next((i for i in range(r, len(echelon)) if echelon[i] >> bit & 1), None)
        if pivot is None:
            continue
        echelon[r], echelon[pivot] = echelon[pivot], echelon[r]
        for i in range(len(echelon)):
            if i != r and echelon[i] >> bit & 1:
                echelon[i] ^= echelon[r]
        pivots.append(bit)
        r += 1
    V = echelon[:r]
    # In RREF each basis row has a 1 at its own pivot and 0 at the others, so the
    # coefficient of basis row k in M[i] is simply M[i]'s bit at pivots[k].
    U = [sum(((row >> p) & 1) << k for k, p in enumerate(pivots)) for row in rows]
    return U, V, r


def multiply(U: Sequence[int], V: Sequence[int], inner: int) -> Matrix:
    """``U V`` over GF(2): row i is the XOR of V[k] for every set bit k of U[i]."""
    out = []
    for row in U:
        acc = 0
        for k in range(inner):
            if row >> k & 1:
                acc ^= V[k]
        out.append(acc)
    return out


def bilinear(left: int, matrix: Sequence[int], right: int) -> int:
    """``x_L^T M x_R`` over GF(2), with ``x_L`` and ``x_R`` as bit masks."""
    acc = 0
    for i, row in enumerate(matrix):
        if left >> i & 1:
            acc ^= bin(row & right).count("1") & 1
    return acc
