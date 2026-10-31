"""
Exact separator merging and boundary-signature compression (research instrument).

Split the variables into ``L``, a separator ``S`` and ``R`` such that no clause
touches both ``L`` and ``R``. Then

    #F = Σ_{s ∈ {0,1}^S} #F_L(s) · #F_R(s)

where ``F_L`` holds the clauses inside ``L ∪ S`` and ``F_R`` the rest. Two left
partial assignments are *exactly interchangeable* for the merge iff they agree
on ``S``. Their boundary signature is the restriction to ``S``. The merge
groups by the exact signature tuple (compared by equality, never by hash) and
multiplies the counts. :func:`separator_count` computes ``#F`` this way, and
:func:`compression_report` measures how many left assignments collapse to how
many signatures. That ratio is the quantity the OMNIWAVE hypotheses ask about.
Everything is exhaustive over its side and meant for small instances.
"""

from __future__ import annotations

import itertools
from typing import Dict, Iterable, List, Sequence, Set, Tuple

Clause = Tuple[int, ...]


def split_clauses(clauses: Sequence[Clause], left: Set[int], sep: Set[int]) -> Tuple[List[Clause], List[Clause]]:
    """Clauses inside L ∪ S go left, the rest right; refuses if a clause touches both L and R."""
    left_side, right_side = [], []
    for c in clauses:
        vs = {abs(l) for l in c}
        if vs <= left | sep:
            left_side.append(c)
        elif vs & left:
            raise ValueError(f"clause {c} touches both sides; {sorted(sep)} is not a separator")
        else:
            right_side.append(c)
    return left_side, right_side


def _side_table(clauses: Sequence[Clause], side: Sequence[int], sep: Sequence[int]) -> Dict[Tuple[int, ...], int]:
    """Exact count per separator signature, by enumerating the side's own variables."""
    table: Dict[Tuple[int, ...], int] = {}
    for sbits in itertools.product((0, 1), repeat=len(sep)):
        val = dict(zip(sep, sbits))
        count = 0
        for bits in itertools.product((0, 1), repeat=len(side)):
            val.update(zip(side, bits))
            if all(any(val[abs(l)] == (l > 0) for l in c) for c in clauses):
                count += 1
        table[sbits] = count
    return table


def separator_count(num_vars: int, clauses: Sequence[Clause], left: Iterable[int], sep: Iterable[int]) -> int:
    left_set, sep_set = set(left), set(sep)
    right = sorted(set(range(1, num_vars + 1)) - left_set - sep_set)
    sep_order = sorted(sep_set)
    lc, rc = split_clauses(clauses, left_set, sep_set)
    tl = _side_table(lc, sorted(left_set), sep_order)
    tr = _side_table(rc, right, sep_order)
    return sum(tl[s] * tr[s] for s in tl)


def compression_report(num_vars: int, clauses: Sequence[Clause], left: Iterable[int], sep: Iterable[int]) -> Dict[str, int]:
    """Left partial assignments that are consistent with F_L, versus their distinct exact signatures."""
    left_order, sep_order = sorted(set(left)), sorted(set(sep))
    lc, _ = split_clauses(clauses, set(left_order), set(sep_order))
    consistent, signatures = 0, set()
    for bits in itertools.product((0, 1), repeat=len(left_order) + len(sep_order)):
        val = dict(zip(left_order + sep_order, bits))
        if all(any(val[abs(l)] == (l > 0) for l in c) for c in lc):
            consistent += 1
            signatures.add(tuple(val[v] for v in sep_order))
    return {
        "left_vars": len(left_order),
        "separator_width": len(sep_order),
        "consistent_left_states": consistent,
        "distinct_signatures": len(signatures),
    }
