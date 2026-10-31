"""
The unified problem field: one canonical CNF and several exact views of it.

Every view is derived from the same :class:`cqhecs.sat.CNF` and carries its
SHA-256 (``formula_sha256``), so a result can always be traced to the input it
was computed from. Views:

* ``incidence``: CSR occurrence lists, literal → clause ids (positive and
  negative separately), plus the variable interaction graph;
* ``xor_view()``: the XOR constraints that are *exactly* encoded in the CNF
  (all ``2^(k-1)`` clauses of one parity over the same k variables), as a
  :class:`~cqhecs.omniwave.gf2.XorSystem`. Detection is exact; a partial pattern
  is not reported;
* ``quadratic_view()``: the count-preserving degree-≤2 GF(2) encoding;
* ``tensor_count()``: ``Z(F) = Σ_x Π_j T_j(x|scope(C_j))`` computed by exact
  variable elimination (bucket elimination) along an explicit order, with
  integer tables. This is an independent counter, used as a differential check
  of :func:`cqhecs.sat.count_models`; it is exponential in the induced width
  and refuses when a table would exceed ``max_table``.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from cqhecs.omniwave.gf2 import XorSystem
from cqhecs.omniwave.quadratic import QuadraticSystem, encode
from cqhecs.sat import CNF


class TableTooLarge(RuntimeError):
    """Bucket elimination would build a table larger than the budget."""


@dataclass(frozen=True)
class Incidence:
    """CSR occurrence lists. ``pos_ptr[v]..pos_ptr[v+1]`` index ``pos_idx`` for variable v (1-based)."""

    pos_ptr: Tuple[int, ...]
    pos_idx: Tuple[int, ...]
    neg_ptr: Tuple[int, ...]
    neg_idx: Tuple[int, ...]

    def occurrences(self, lit: int) -> Tuple[int, ...]:
        v = abs(lit)
        ptr, idx = (self.pos_ptr, self.pos_idx) if lit > 0 else (self.neg_ptr, self.neg_idx)
        return idx[ptr[v - 1]:ptr[v]]


@dataclass
class ProblemField:
    cnf: CNF
    incidence: Incidence = field(init=False)

    def __post_init__(self) -> None:
        n = self.cnf.num_vars
        pos: List[List[int]] = [[] for _ in range(n)]
        neg: List[List[int]] = [[] for _ in range(n)]
        for cid, clause in enumerate(self.cnf.clauses):
            for lit in clause:
                (pos if lit > 0 else neg)[abs(lit) - 1].append(cid)

        def csr(lists: List[List[int]]) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
            ptr, idx = [0], []
            for occ in lists:
                idx.extend(occ)
                ptr.append(len(idx))
            return tuple(ptr), tuple(idx)

        pp, pi = csr(pos)
        np_, ni = csr(neg)
        self.incidence = Incidence(pp, pi, np_, ni)

    @property
    def formula_sha256(self) -> str:
        return self.cnf.sha256

    def neighbours(self) -> Dict[int, set]:
        """Variable interaction graph: u ~ v if they share a clause."""
        adj: Dict[int, set] = {v: set() for v in range(1, self.cnf.num_vars + 1)}
        for clause in self.cnf.clauses:
            vs = {abs(l) for l in clause}
            for v in vs:
                adj[v] |= vs - {v}
        return adj

    def bfs_order(self, start: int) -> List[int]:
        """Variables ordered by graph distance from ``start``: one wave's direction."""
        adj = self.neighbours()
        order, seen, frontier = [], {start}, [start]
        while frontier:
            order.extend(sorted(frontier))
            nxt = []
            for v in frontier:
                for w in sorted(adj[v]):
                    if w not in seen:
                        seen.add(w)
                        nxt.append(w)
            frontier = nxt
        order.extend(v for v in range(1, self.cnf.num_vars + 1) if v not in seen)
        return order

    # ------------------------------------------------------------------ views

    def xor_view(self) -> XorSystem:
        groups: Dict[Tuple[int, ...], set] = {}
        for clause in self.cnf.clauses:
            vs = tuple(sorted({abs(l) for l in clause}))
            if len(vs) != len(clause) or not 2 <= len(vs) <= 10:
                continue
            signs = tuple(next(l > 0 for l in clause if abs(l) == v) for v in vs)
            groups.setdefault(vs, set()).add(signs)
        rows = []
        for vs, sign_sets in groups.items():
            k = len(vs)
            # Clause with negative-literal set N forbids the assignment x_i = 1 for i in N,
            # x_i = 0 otherwise. All 2^(k-1) clauses forbidding one parity p of
            # "#positive-forbidden ... " encode the XOR Σ x = 1 - p.
            forbidden_parities = {sum(1 for s in signs if not s) % 2 for signs in sign_sets}
            for p in forbidden_parities:
                members = {signs for signs in sign_sets if sum(1 for s in signs if not s) % 2 == p}
                if len(members) == 1 << (k - 1):
                    mask = sum(1 << (v - 1) for v in vs)
                    rows.append((mask, 1 - p))
        return XorSystem(self.cnf.num_vars, tuple(rows))

    def quadratic_view(self) -> QuadraticSystem:
        return encode(self.cnf.clauses, self.cnf.num_vars, self.formula_sha256)

    def tensor_count(self, order: Optional[Sequence[int]] = None, max_table: int = 1 << 20) -> int:
        """Exact ``Z(F)`` by bucket elimination over 0/1 clause tensors."""
        n = self.cnf.num_vars
        order = list(order) if order is not None else list(range(1, n + 1))
        if sorted(order) != list(range(1, n + 1)):
            raise ValueError("order must be a permutation of all variables")
        # A factor is (scope tuple, table dict: assignment tuple -> int count).
        factors: List[Tuple[Tuple[int, ...], Dict[Tuple[int, ...], int]]] = []
        for clause in self.cnf.clauses:
            scope = tuple(sorted({abs(l) for l in clause}))
            table = {}
            for bits in itertools.product((0, 1), repeat=len(scope)):
                val = dict(zip(scope, bits))
                table[bits] = int(any(val[abs(l)] == (l > 0) for l in clause))
            factors.append((scope, table))
        result = 1
        for v in order:
            bucket = [f for f in factors if v in f[0]]
            factors = [f for f in factors if v not in f[0]]
            if not bucket:
                result *= 2  # a free variable doubles the count
                continue
            scope = tuple(sorted({u for s, _ in bucket for u in s} - {v}))
            if 1 << len(scope) > max_table:
                raise TableTooLarge(f"eliminating x{v} needs a table over {len(scope)} variables")
            table = {}
            for bits in itertools.product((0, 1), repeat=len(scope)):
                val = dict(zip(scope, bits))
                total = 0
                for xv in (0, 1):
                    val[v] = xv
                    prod = 1
                    for s, t in bucket:
                        prod *= t[tuple(val[u] for u in s)]
                        if not prod:
                            break
                    total += prod
                table[bits] = total
            factors.append((scope, table))
        for scope, table in factors:
            assert scope == ()
            result *= table[()]
        return result


@dataclass(frozen=True)
class ParityHash:
    """``h(x) = A x + b`` over GF(2), drawn from a recorded seed."""

    num_vars: int
    rows: Tuple[int, ...]   # bit masks of A
    offsets: Tuple[int, ...]  # b
    seed: int

    @staticmethod
    def draw(num_vars: int, r: int, seed: int, density: float = 0.5) -> "ParityHash":
        rng = random.Random(seed)
        rows = []
        for _ in range(r):
            mask = sum(1 << i for i in range(num_vars) if rng.random() < density)
            rows.append(mask or 1 << rng.randrange(num_vars))
        return ParityHash(num_vars, tuple(rows), tuple(rng.randint(0, 1) for _ in range(r)), seed)

    def bucket(self, x: Sequence[bool]) -> Tuple[int, ...]:
        return tuple(
            (sum(x[i] for i in range(self.num_vars) if m >> i & 1) + b) & 1
            for m, b in zip(self.rows, self.offsets)
        )

    def cell_system(self, bucket: Tuple[int, ...]) -> XorSystem:
        """The XOR constraints whose solutions are exactly this bucket's cell."""
        return XorSystem(self.num_vars, tuple((m, s ^ b) for m, s, b in zip(self.rows, bucket, self.offsets)))

    def all_buckets(self) -> List[Tuple[int, ...]]:
        """Every cell. An exact decision must cover all of them; one empty cell proves nothing."""
        return list(itertools.product((0, 1), repeat=len(self.rows)))
