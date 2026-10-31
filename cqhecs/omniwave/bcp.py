"""
Batched Boolean constraint propagation over many partial assignments.

This is the trusted CPU reference for the Vulkan kernel ``omniwave_bcp.comp``.
Both implement one **evaluation pass**:

for every front ``f`` and clause ``c`` the status is

* ``SAT`` (0): some literal is true;
* ``CONFLICT`` (1): every literal is assigned and false;
* ``UNIT`` (2): exactly one literal is unassigned and the others are false
  (the code word also carries that literal);
* ``OPEN`` (3): otherwise.

A front is two bit vectors over the variables, packed into 32-bit words: ``assigned``
and ``value``. :func:`propagate_batch` iterates passes to a fixed point, applying
all units of a pass at once. Two units on the same variable with opposite signs
make a conflict. The GPU path must produce bit-identical status words to
:func:`evaluate_batch`; ``tests/test_omniwave.py`` checks this whenever the native
library is available.

Encoding of a status word: ``status | (literal_code << 2)``, with
``literal_code = 2*(v-1) + (1 if negative else 0)``, the same code the shader uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

SAT_, CONFLICT_, UNIT_, OPEN_ = 0, 1, 2, 3


def lit_code(lit: int) -> int:
    return 2 * (abs(lit) - 1) + (1 if lit < 0 else 0)


def code_lit(code: int) -> int:
    v = code // 2 + 1
    return -v if code & 1 else v


@dataclass
class Fronts:
    """``num_fronts`` partial assignments over ``num_vars`` variables, bit-packed."""

    num_vars: int
    assigned: List[List[int]]  # [front][word]
    value: List[List[int]]

    @property
    def words(self) -> int:
        return (self.num_vars + 31) // 32

    @staticmethod
    def from_cubes(num_vars: int, cubes: Sequence[Sequence[int]]) -> "Fronts":
        words = (num_vars + 31) // 32
        assigned, value = [], []
        for cube in cubes:
            a, v = [0] * words, [0] * words
            for lit in cube:
                i = abs(lit) - 1
                a[i // 32] |= 1 << (i % 32)
                if lit > 0:
                    v[i // 32] |= 1 << (i % 32)
            assigned.append(a)
            value.append(v)
        return Fronts(num_vars, assigned, value)

    def get(self, f: int, var: int) -> Optional[bool]:
        i = var - 1
        if not self.assigned[f][i // 32] >> (i % 32) & 1:
            return None
        return bool(self.value[f][i // 32] >> (i % 32) & 1)

    def set(self, f: int, lit: int) -> None:
        i = abs(lit) - 1
        self.assigned[f][i // 32] |= 1 << (i % 32)
        if lit > 0:
            self.value[f][i // 32] |= 1 << (i % 32)
        else:
            self.value[f][i // 32] &= ~(1 << (i % 32)) & 0xFFFFFFFF


def flatten_clauses(clauses: Sequence[Sequence[int]]) -> Tuple[List[int], List[int]]:
    """CSR clause layout shared with the GPU: offsets (len m+1) and literal codes."""
    offsets, codes = [0], []
    for clause in clauses:
        codes.extend(lit_code(l) for l in clause)
        offsets.append(len(codes))
    return offsets, codes


def evaluate_batch(clauses: Sequence[Sequence[int]], fronts: Fronts) -> List[List[int]]:
    """One evaluation pass: ``status[front][clause]`` as encoded status words."""
    out: List[List[int]] = []
    for f in range(len(fronts.assigned)):
        row = []
        for clause in clauses:
            status, unit_code, open_count = None, 0, 0
            for lit in clause:
                val = fronts.get(f, abs(lit))
                if val is None:
                    open_count += 1
                    unit_code = lit_code(lit)
                elif val == (lit > 0):
                    status = SAT_
                    break
            if status is None:
                if open_count == 0:
                    status = CONFLICT_
                elif open_count == 1:
                    status = UNIT_ | (unit_code << 2)
                else:
                    status = OPEN_
            row.append(status)
        out.append(row)
    return out


def propagate_batch(
    clauses: Sequence[Sequence[int]],
    fronts: Fronts,
    evaluate=evaluate_batch,
    max_passes: int = 10_000,
) -> List[str]:
    """Fixed-point BCP for every front; returns "conflict" | "sat" | "open" per front."""
    alive = list(range(len(fronts.assigned)))
    outcome = ["open"] * len(fronts.assigned)
    for _ in range(max_passes):
        if not alive:
            break
        sub = Fronts(fronts.num_vars, [fronts.assigned[f] for f in alive], [fronts.value[f] for f in alive])
        statuses = evaluate(clauses, sub)
        still = []
        for k, f in enumerate(alive):
            row = statuses[k]
            codes = [s & 3 for s in row]
            if CONFLICT_ in codes:
                outcome[f] = "conflict"
                continue
            if all(c == SAT_ for c in codes):
                outcome[f] = "sat"
                continue
            units = {code_lit(s >> 2) for s in row if s & 3 == UNIT_}
            if not units:
                continue  # fixed point, open
            if any(-u in units for u in units):
                outcome[f] = "conflict"
                continue
            for u in units:
                fronts.set(f, u)
            still.append(f)
        alive = still
    return outcome
