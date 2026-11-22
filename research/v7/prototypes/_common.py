"""Shared helpers for the W7 research prototypes (Paths E/F/G).

EXPERIMENTAL / RESEARCH_ONLY. Nothing under ``cqhecs`` imports this package.

Conventions (match ``cqhecs.backends.dense_reference``): qubit 0 is the
least-significant bit of a dense basis index; a two-qubit gate is a tensor
``G[o_a, o_b, i_a, i_b]`` with ``a`` the first operand (the control of cx).
"""
from __future__ import annotations

import math
import os
import sys
from typing import List, Sequence, Tuple

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

Instruction = Tuple[str, List[int], List[float]]

_S2 = 1.0 / math.sqrt(2.0)


class ResourceRefusal(RuntimeError):
    """Typed refusal: a declared resource budget would be exceeded."""


class UnsupportedPrototypeInput(ValueError):
    """Typed refusal: input outside the declared scope of the prototype."""


def gate_1q(name: str, params: Sequence[float] = ()) -> np.ndarray:
    fixed = {
        "id": [[1, 0], [0, 1]],
        "h": [[_S2, _S2], [_S2, -_S2]],
        "x": [[0, 1], [1, 0]],
        "y": [[0, -1j], [1j, 0]],
        "z": [[1, 0], [0, -1]],
        "s": [[1, 0], [0, 1j]],
        "t": [[1, 0], [0, np.exp(1j * math.pi / 4)]],
    }
    if name in fixed:
        return np.array(fixed[name], dtype=np.complex128)
    if name not in ("rx", "ry", "rz"):
        raise UnsupportedPrototypeInput(f"unsupported 1q gate {name!r}")
    th = float(params[0])
    c, s = math.cos(th / 2), math.sin(th / 2)
    if name == "rx":
        return np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
    if name == "ry":
        return np.array([[c, -s], [s, c]], dtype=np.complex128)
    return np.array([[np.exp(-0.5j * th), 0], [0, np.exp(0.5j * th)]], dtype=np.complex128)


def gate_2q(name: str) -> np.ndarray:
    """Returns ``G[o_a, o_b, i_a, i_b]`` (first operand is the control of cx)."""
    if name not in ("cx", "cz", "swap"):
        raise UnsupportedPrototypeInput(f"unsupported 2q gate {name!r}")
    g = np.zeros((2, 2, 2, 2), dtype=np.complex128)
    for a in range(2):
        for b in range(2):
            if name == "cx":
                g[a, b ^ a, a, b] = 1.0
            elif name == "cz":
                g[a, b, a, b] = -1.0 if (a and b) else 1.0
            else:
                g[b, a, a, b] = 1.0
    return g


def instruction_tensor(inst) -> np.ndarray:
    name, qubits, params = inst
    if len(qubits) == 1:
        return gate_1q(name, params)
    if len(qubits) == 2:
        return gate_2q(name)
    raise UnsupportedPrototypeInput(f"{len(qubits)}-qubit gate {name!r}")


# -- dense oracles (independent of the prototypes) ---------------------------
def dense_state(instructions, n: int) -> np.ndarray:
    from cqhecs.backends.dense_reference import simulate

    return simulate([(g, list(q), list(p)) for g, q, p in instructions], n).statevector()


def to_qiskit(instructions, n: int, measure: bool = False):
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(n, n if measure else 0)
    for name, qs, ps in instructions:
        getattr(qc, name)(*ps, *qs)
    if measure:
        qc.measure(range(n), range(n))
    return qc


def qiskit_state(instructions, n: int) -> np.ndarray:
    from qiskit.quantum_info import Statevector

    return np.asarray(Statevector.from_instruction(to_qiskit(instructions, n)).data)


# -- circuit families ---------------------------------------------------------
def grid_edges(rows: int, cols: int) -> List[Tuple[int, int]]:
    e = []
    for r in range(rows):
        for c in range(cols):
            q = r * cols + c
            if c + 1 < cols:
                e.append((q, q + 1))
            if r + 1 < rows:
                e.append((q, q + cols))
    return e


def line_edges(n: int) -> List[Tuple[int, int]]:
    return [(i, i + 1) for i in range(n - 1)]


def ring_edges(n: int) -> List[Tuple[int, int]]:
    return line_edges(n) + [(n - 1, 0)]


def star_edges(n: int) -> List[Tuple[int, int]]:
    return [(0, i) for i in range(1, n)]


def all_to_all_edges(n: int) -> List[Tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def random_sparse_edges(n: int, m: int, seed: int) -> List[Tuple[int, int]]:
    rng = np.random.default_rng(seed)
    pool = all_to_all_edges(n)
    idx = rng.permutation(len(pool))[:m]
    return [pool[i] for i in sorted(idx)]


def _matching_layers(edges: Sequence[Tuple[int, int]]) -> List[List[Tuple[int, int]]]:
    """Greedy edge colouring: each layer is a set of disjoint edges."""
    layers: List[List[Tuple[int, int]]] = []
    for e in edges:
        for layer in layers:
            if all(set(e).isdisjoint(f) for f in layer):
                layer.append(e)
                break
        else:
            layers.append([e])
    return layers


def random_graph_circuit(n: int, edges, depth: int, seed: int) -> List[Instruction]:
    """Random non-Clifford circuit on an interaction graph.

    Each of ``depth`` rounds applies random 1q rotations to every qubit and
    then cz on one edge-colour class of the graph (cycled), so the 2q gate
    pattern follows the graph geometry.
    """
    rng = np.random.default_rng(seed)
    layers = _matching_layers(edges)
    out: List[Instruction] = []
    for d in range(depth):
        for q in range(n):
            g = ["rx", "ry", "rz"][int(rng.integers(3))]
            out.append((g, [q], [float(rng.uniform(0.1, 2 * math.pi - 0.1))]))
        for (a, b) in layers[d % len(layers)]:
            out.append(("cz", [a, b], []))
    return out


def grid_circuit(rows: int, cols: int, depth: int, seed: int) -> List[Instruction]:
    return random_graph_circuit(rows * cols, grid_edges(rows, cols), depth, seed)


def tv_distance(p, q) -> float:
    return 0.5 * float(np.sum(np.abs(np.asarray(p) - np.asarray(q))))


def state_infidelity(a, b) -> float:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(max(0.0, 1.0 - abs(np.vdot(a, b)) ** 2))
