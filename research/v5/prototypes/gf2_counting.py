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
from typing import Dict, Optional, Sequence, Tuple

Clause = Tuple[int, ...]


# The XOR solver lives in the package (single source of truth); re-exported here.
from cqhecs.omniwave.gf2 import XorSystem  # noqa: E402,F401


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
