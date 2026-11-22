"""Path E research prototype: geometry-aware tensor-network contraction.

EXPERIMENTAL / RESEARCH_ONLY. Not imported by the router or any stable module.

Scope (declared, small):
  * circuit -> closed tensor network (amplitude <x|C|0...0>, or the doubled
    network <0|C^dag Z_S C|0> for a Z-string observable with exact light-cone
    pruning);
  * pairwise contraction orders: ``sequential`` (time order, the Schroedinger
    baseline), ``greedy`` (smallest-result-first), ``geometry_sweep`` (sweep
    the qubit coordinates, boundary-MPS-like frontier, no truncation);
  * a symbolic cost planner (largest tensor, FLOPs) run BEFORE any allocation,
    with a typed refusal when a declared element budget would be exceeded.

NOT implemented: Rudolph-Tindall generalised boundary-MPS with truncation,
sampling, GPU, slicing. This is a contraction-order study on exact networks.
All contractions here are exact (no truncation); results agree with the dense
oracle to floating-point precision.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from _common import (
    Instruction,
    ResourceRefusal,
    UnsupportedPrototypeInput,
    instruction_tensor,
)

STRATEGIES = ("sequential", "greedy", "geometry_sweep")


@dataclass
class _T:
    data: Optional[np.ndarray]
    legs: List[int]            # leg labels, each of dimension 2
    key: Tuple = ()            # ordering key for the geometry sweep


@dataclass
class Network:
    tensors: List[_T]
    scalar: complex = 1.0 + 0j
    num_qubits: int = 0
    gates_kept: int = 0
    gates_total: int = 0


@dataclass
class ContractionPlan:
    strategy: str
    path: List[Tuple[int, int]]
    largest_log2: int
    total_flops: float
    steps: int
    sweep_axis: Optional[str] = None


@dataclass
class Report:
    value: complex
    plan: ContractionPlan
    wall_s: float
    network_tensors: int
    gates_kept: int
    gates_total: int
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# network construction
# ---------------------------------------------------------------------------
def _coords(n: int, grid_cols: Optional[int], axis: str):
    """Sweep coordinate (primary, secondary) of each qubit."""
    out = []
    for q in range(n):
        if grid_cols:
            r, c = divmod(q, grid_cols)
            out.append((c, r) if axis == "col" else (r, c))
        else:
            out.append((q, 0))
    return out


class _Builder:
    def __init__(self, n: int):
        self.n = n
        self.next_leg = 0
        self.tensors: List[_T] = []

    def leg(self) -> int:
        self.next_leg += 1
        return self.next_leg - 1


def build_amplitude_network(
    instructions: Sequence[Instruction],
    n: int,
    bitstring: int,
    grid_cols: Optional[int] = None,
    axis: str = "row",
) -> Network:
    """<x|C|0..0> as a closed network; input legs sliced to |0>, outputs to <x|."""
    b = _Builder(n)
    coords = _coords(n, grid_cols, axis)
    cur: Dict[int, Optional[int]] = {q: None for q in range(n)}  # None = still |0>
    scalar = 1.0 + 0j
    for t, inst in enumerate(instructions):
        U = instruction_tensor(inst)
        qs = inst[1]
        k = len(qs)
        outs = [b.leg() for _ in qs]
        data = U
        legs = outs + [None] * k
        # slice fresh input legs to |0>
        sl: List = [slice(None)] * (2 * k)
        for i, q in enumerate(qs):
            if cur[q] is None:
                sl[k + i] = 0
            else:
                legs[k + i] = cur[q]
        data = data[tuple(sl)]
        legs = [l for l, s in zip(legs, sl) if not isinstance(s, int)]
        key = (min(coords[q][0] for q in qs), min(coords[q][1] for q in qs), t, 0)
        b.tensors.append(_T(data, legs, key))
        for o, q in zip(outs, qs):
            cur[q] = o
    # close outputs with <x|
    for q in range(n):
        bit = (bitstring >> q) & 1
        if cur[q] is None:
            scalar *= 1.0 if bit == 0 else 0.0
        else:
            # find the tensor owning leg cur[q] and slice it
            for T in reversed(b.tensors):
                if cur[q] in T.legs:
                    ax = T.legs.index(cur[q])
                    T.data = np.take(T.data, bit, axis=ax)
                    T.legs = [l for l in T.legs if l != cur[q]]
                    break
    return Network(b.tensors, scalar, n, len(instructions), len(instructions))


def lightcone(instructions: Sequence[Instruction], support: Sequence[int]) -> List[Instruction]:
    """Gates that can influence <Z_support>; others cancel exactly (U U^dag = I)."""
    active = set(support)
    keep: List[Instruction] = []
    for inst in reversed(instructions):
        if active.intersection(inst[1]):
            keep.append(inst)
            active.update(inst[1])
    keep.reverse()
    return keep


def build_zstring_network(
    instructions: Sequence[Instruction],
    n: int,
    support: Sequence[int],
    grid_cols: Optional[int] = None,
    axis: str = "row",
) -> Network:
    """<0|C^dag (prod_{q in S} Z_q) C|0> as a doubled closed network (light-cone pruned)."""
    kept = lightcone(instructions, support)
    b = _Builder(n)
    coords = _coords(n, grid_cols, axis)
    cur_k: Dict[int, Optional[int]] = {q: None for q in range(n)}
    cur_b: Dict[int, Optional[int]] = {q: None for q in range(n)}
    for t, inst in enumerate(kept):
        U = instruction_tensor(inst)
        qs = inst[1]
        k = len(qs)
        for copy, cur in ((0, cur_k), (1, cur_b)):
            outs = [b.leg() for _ in qs]
            data = U if copy == 0 else U.conj()
            legs = outs + [None] * k
            sl: List = [slice(None)] * (2 * k)
            for i, q in enumerate(qs):
                if cur[q] is None:
                    sl[k + i] = 0
                else:
                    legs[k + i] = cur[q]
            data = data[tuple(sl)]
            legs = [l for l, s in zip(legs, sl) if not isinstance(s, int)]
            key = (min(coords[q][0] for q in qs), min(coords[q][1] for q in qs), t, copy)
            b.tensors.append(_T(data, legs, key))
            for o, q in zip(outs, qs):
                cur[q] = o
    scalar = 1.0 + 0j
    for q in range(n):
        if cur_k[q] is None:
            if q in support:
                pass  # <0|Z|0> = 1
            continue
        ds = np.diag([1.0, -1.0 if q in support else 1.0]).astype(np.complex128)
        b.tensors.append(
            _T(ds, [cur_k[q], cur_b[q]], (coords[q][0], coords[q][1], 10**9, 2))
        )
    return Network(b.tensors, scalar, n, len(kept), len(instructions))


# ---------------------------------------------------------------------------
# symbolic planning
# ---------------------------------------------------------------------------
def _simulate_path(legsets: List[set], path: List[Tuple[int, int]]):
    pool = {i: set(l) for i, l in enumerate(legsets)}
    nxt = len(legsets)
    largest = max((len(l) for l in pool.values()), default=0)
    flops = 0.0
    for (i, j) in path:
        a, b = pool.pop(i), pool.pop(j)
        union = a | b
        shared = a & b
        out = union - shared
        flops += 2.0 ** len(union)
        largest = max(largest, len(out), len(a), len(b))
        pool[nxt] = out
        nxt += 1
    return largest, flops


def _order_path(legsets: List[set], order: List[int]) -> List[Tuple[int, int]]:
    """Left-fold the tensors in ``order`` into one accumulator."""
    path: List[Tuple[int, int]] = []
    if not order:
        return path
    acc = order[0]
    nxt = len(legsets)
    for idx in order[1:]:
        path.append((acc, idx))
        acc = nxt
        nxt += 1
    return path


def _greedy_path(legsets: List[set]) -> List[Tuple[int, int]]:
    pool = {i: set(l) for i, l in enumerate(legsets)}
    nxt = len(legsets)
    path: List[Tuple[int, int]] = []
    while len(pool) > 1:
        ids = sorted(pool)
        best = None
        for ai, i in enumerate(ids):
            for j in ids[ai + 1:]:
                if not (pool[i] & pool[j]):
                    continue
                out = (pool[i] | pool[j]) - (pool[i] & pool[j])
                score = (len(out) - max(len(pool[i]), len(pool[j])), len(out), i, j)
                if best is None or score < best[0]:
                    best = (score, i, j)
        if best is None:  # disconnected components: outer-product the two smallest
            ids.sort(key=lambda k: len(pool[k]))
            i, j = ids[0], ids[1]
        else:
            _, i, j = best
        out = (pool[i] | pool[j]) - (pool[i] & pool[j])
        path.append((i, j))
        pool.pop(i), pool.pop(j)
        pool[nxt] = out
        nxt += 1
    return path


def plan_contraction(net: Network, strategy: str) -> ContractionPlan:
    if strategy not in STRATEGIES:
        raise UnsupportedPrototypeInput(f"unknown strategy {strategy!r}")
    legsets = [set(t.legs) for t in net.tensors]
    if len(legsets) <= 1:
        return ContractionPlan(strategy, [], max((len(l) for l in legsets), default=0), 0.0, 0)
    if strategy == "sequential":
        # time order = construction order, interleaved by copy for the doubled network
        order = sorted(range(len(legsets)), key=lambda i: (net.tensors[i].key[2], net.tensors[i].key[3]))
        path = _order_path(legsets, order)
    elif strategy == "greedy":
        path = _greedy_path(legsets)
    else:
        order = sorted(range(len(legsets)), key=lambda i: net.tensors[i].key)
        path = _order_path(legsets, order)
    largest, flops = _simulate_path(legsets, path)
    return ContractionPlan(strategy, path, largest, flops, len(path))


def best_plan(builder, strategies: Sequence[str] = STRATEGIES, axes=("row", "col")):
    """Plan every (strategy, sweep axis) combination symbolically, return the best.

    ``builder(axis)`` -> Network. Ranking: (largest tensor, FLOPs). Baseline
    ``sequential`` is always among the candidates, so best_plan is never worse
    than the Schroedinger-style order in largest tensor.
    """
    cands = []
    for ax in axes:
        net = builder(ax)
        for s in strategies:
            p = plan_contraction(net, s)
            p.sweep_axis = ax
            cands.append((p.largest_log2, p.total_flops, s, ax, net, p))
    cands.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
    return cands[0][4], cands[0][5], [c[5] for c in cands]


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def _contract_pair(a: _T, b: _T) -> _T:
    shared = [l for l in a.legs if l in b.legs]
    ax_a = [a.legs.index(l) for l in shared]
    ax_b = [b.legs.index(l) for l in shared]
    data = np.tensordot(a.data, b.data, axes=(ax_a, ax_b))
    legs = [l for l in a.legs if l not in shared] + [l for l in b.legs if l not in shared]
    return _T(data, legs, a.key)


def contract(net: Network, plan: ContractionPlan, max_elements: int = 1 << 24) -> complex:
    """Executes ``plan``. Refuses BEFORE allocation if the plan exceeds ``max_elements``."""
    if (1 << plan.largest_log2) > max_elements:
        raise ResourceRefusal(
            f"largest intermediate 2^{plan.largest_log2} elements exceeds budget {max_elements}"
        )
    pool = {i: t for i, t in enumerate(net.tensors)}
    nxt = len(net.tensors)
    for (i, j) in plan.path:
        pool[nxt] = _contract_pair(pool.pop(i), pool.pop(j))
        nxt += 1
    (last,) = pool.values() if len(pool) == 1 else (None,)
    if last is None:
        raise RuntimeError("plan did not reduce the network to one tensor")
    if last.legs:
        raise RuntimeError(f"open legs remain: {last.legs}")
    return complex(net.scalar * last.data)


def amplitude(
    instructions: Sequence[Instruction],
    n: int,
    bitstring: int,
    strategy: str = "best",
    grid_cols: Optional[int] = None,
    max_elements: int = 1 << 24,
) -> Report:
    t0 = time.perf_counter()
    build = lambda ax: build_amplitude_network(instructions, n, bitstring, grid_cols, ax)  # noqa: E731
    if strategy == "best":
        net, plan, _ = best_plan(build)
    else:
        net = build("row")
        plan = plan_contraction(net, strategy)
        plan.sweep_axis = "row"
    if net.scalar == 0:
        return Report(0j, plan, time.perf_counter() - t0, len(net.tensors), net.gates_kept, net.gates_total, ["idle-qubit mismatch: amplitude exactly 0"])
    if not net.tensors:
        return Report(complex(net.scalar), plan, time.perf_counter() - t0, 0, 0, 0)
    v = contract(net, plan, max_elements)
    return Report(v, plan, time.perf_counter() - t0, len(net.tensors), net.gates_kept, net.gates_total)


def z_expectation(
    instructions: Sequence[Instruction],
    n: int,
    support: Sequence[int],
    strategy: str = "best",
    grid_cols: Optional[int] = None,
    max_elements: int = 1 << 24,
) -> Report:
    t0 = time.perf_counter()
    build = lambda ax: build_zstring_network(instructions, n, support, grid_cols, ax)  # noqa: E731
    if strategy == "best":
        net, plan, _ = best_plan(build)
    else:
        net = build("row")
        plan = plan_contraction(net, strategy)
        plan.sweep_axis = "row"
    if not net.tensors:
        return Report(1.0 + 0j, plan, time.perf_counter() - t0, 0, 0, len(instructions))
    v = contract(net, plan, max_elements)
    return Report(v, plan, time.perf_counter() - t0, len(net.tensors), net.gates_kept, net.gates_total)
