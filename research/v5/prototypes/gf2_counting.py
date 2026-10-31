"""
RESEARCH ONLY — GF(2) parity constraints and count-preserving partitions.

Not imported by ``cqhecs``. Transfer class: ``RESEARCH_ONLY``
(see ``research/v5/COMPLEXITY_CLAIM_AUDIT.md`` §4).

Parity-based counting arguments, including the sparse parity tests in the OpenAI
ETH manuscript, rely on one elementary fact that is checked here
exhaustively, not on anything specific to that paper:

    For any r×n matrix A over GF(2), the sets {x : F(x) ∧ Ax = b} for b ∈ {0,1}^r
    partition the models of F, so  Σ_b #(F ∧ Ax=b) = #F.

The module provides a Gaussian-elimination solver for XOR systems (rank,
consistency, exact solution count 2^(n−rank)) and the partition, plus an
exhaustive checker. It makes no performance claim and is not a solver.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

Clause = Tuple[int, ...]


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


def satisfies_cnf(clauses: Sequence[Clause], x: Sequence[bool]) -> bool:
    return all(any(x[abs(l) - 1] == (l > 0) for l in c) for c in clauses)


def brute_count(num_vars: int, clauses: Sequence[Clause], xor: Optional[XorSystem] = None) -> int:
    total = 0
    for bits in itertools.product((False, True), repeat=num_vars):
        if satisfies_cnf(clauses, bits) and (xor is None or xor.satisfied(bits)):
            total += 1
    return total


def parity_partition(num_vars: int, clauses: Sequence[Clause], masks: Sequence[int]) -> Dict[Tuple[int, ...], int]:
    """#(F ∧ Ax=b) for every syndrome b, by exhaustive enumeration (oracle only)."""
    parts: Dict[Tuple[int, ...], int] = {}
    for bits in itertools.product((False, True), repeat=num_vars):
        if not satisfies_cnf(clauses, bits):
            continue
        syndrome = tuple(sum(bits[i] for i in range(num_vars) if m >> i & 1) & 1 for m in masks)
        parts[syndrome] = parts.get(syndrome, 0) + 1
    return parts
