"""
Exact lowering of composite gates onto the natively executed gate set.

Several standard OpenQASM/Qiskit operations (``u``/``u3``/``u2``, ``sx``,
``cy``, ``ch``, ``cs``, ``rzz``, ``ccx`` ...) have no dedicated kernel in any
of the four paths. Before v2.3.0 the manifest knew them only to refuse them.
They are now rewritten into gates that at least one path executes natively.

Every rule below is an *exact* identity of unitaries, not an approximation:

* ``u3(theta, phi, lam)  = p(phi) . ry(theta) . p(lam)``   (including phase)
* ``u2(phi, lam)         = u3(pi/2, phi, lam)``
* ``sx  = h . s . h``,  ``sxdg = h . sdg . h``             (including phase)
* ``cy  = s_t . cx . sdg_t``
* ``ch  = ry_t(-pi/4) . cx . ry_t(pi/4)``
* ``cs  = cp(pi/2)``, ``csdg = cp(-pi/2)`` via the phase/CX identity
  ``cp(theta) = p_c(theta/2) p_t(theta/2) cx p_t(-theta/2) cx``
* ``rzz(theta) = cx . rz_t(theta) . cx``; ``rxx``/``ryy`` by local basis change
* ``ccx`` by the standard 7-T Clifford+T circuit; ``ccz = h_t . ccx . h_t``;
  ``cswap = cx(b, a) . ccx(c, a, b) . cx(b, a)``
* ``r(theta, phi) = u3(theta, phi - pi/2, pi/2 - phi)``
* ``iswap = s . s . h_a . cx(a, b) . cx(b, a) . h_b``, ``dcx = cx(a, b) . cx(b, a)``
* ``ecr = rzx(pi/4) . x_a . rzx(-pi/4)`` with ``rzx = h_b . cx . rz_b . cx . h_b``
* ``cu3``/``cu`` by the qelib1 identity (``cu`` adds ``p(gamma)`` on the control);
  ``csx = h_t . cs . h_t``
* ``c3x``/``c4x`` (multi-controlled X): ``h_t . C^kZ . h_t`` where the diagonal
  ``exp(i pi x_1...x_m)`` is the parity expansion
  ``sum_S (-1)^{|S|+1} pi / 2^(m-1) * parity_S`` over non-empty qubit subsets,
  each realised by a CX ladder onto a pivot and one ``p`` rotation

(Products read right to left; the emitted instruction lists read left to
right.) ``tests/test_gate_lowering.py`` checks each rule against Qiskit's
reference matrices. Lowering happens once, inside
:func:`cqhecs.circuit_parsing.parse_circuit`, so the analyzer, the router and
every backend see the same primitive circuit and the non-Clifford resource
count of a composite gate is the count of its decomposition.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence, Tuple

from cqhecs.gate_manifest import get_gate, signature_errors

Instruction = Tuple[str, List[int], List[float]]

_PI = math.pi


def _u3(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    theta, phi, lam = p
    return [("p", [q[0]], [lam]), ("ry", [q[0]], [theta]), ("p", [q[0]], [phi])]


def _u2(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    return [("u3", [q[0]], [_PI / 2.0, p[0], p[1]])]


def _sx(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    return [("h", [q[0]], []), ("s", [q[0]], []), ("h", [q[0]], [])]


def _sxdg(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    return [("h", [q[0]], []), ("sdg", [q[0]], []), ("h", [q[0]], [])]


def _cy(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    c, t = q
    return [("sdg", [t], []), ("cx", [c, t], []), ("s", [t], [])]


def _ch(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    c, t = q
    return [
        ("ry", [t], [_PI / 4.0]),
        ("cx", [c, t], []),
        ("ry", [t], [-_PI / 4.0]),
    ]


def _phase_cp(c: int, t: int, theta: float) -> List[Instruction]:
    half = theta / 2.0
    return [
        ("p", [c], [half]),
        ("p", [t], [half]),
        ("cx", [c, t], []),
        ("p", [t], [-half]),
        ("cx", [c, t], []),
    ]


def _cs(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    return _phase_cp(q[0], q[1], _PI / 2.0)


def _csdg(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    return _phase_cp(q[0], q[1], -_PI / 2.0)


def _rzz(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    a, b = q
    return [("cx", [a, b], []), ("rz", [b], [p[0]]), ("cx", [a, b], [])]


def _rxx(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    a, b = q
    basis = [("h", [a], []), ("h", [b], [])]
    return basis + [("rzz", [a, b], [p[0]])] + basis


def _ryy(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    a, b = q
    into = [("rx", [a], [_PI / 2.0]), ("rx", [b], [_PI / 2.0])]
    out = [("rx", [a], [-_PI / 2.0]), ("rx", [b], [-_PI / 2.0])]
    return into + [("rzz", [a, b], [p[0]])] + out


def _ccx(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    a, b, t = q
    return [
        ("h", [t], []),
        ("cx", [b, t], []),
        ("tdg", [t], []),
        ("cx", [a, t], []),
        ("t", [t], []),
        ("cx", [b, t], []),
        ("tdg", [t], []),
        ("cx", [a, t], []),
        ("t", [b], []),
        ("t", [t], []),
        ("h", [t], []),
        ("cx", [a, b], []),
        ("t", [a], []),
        ("tdg", [b], []),
        ("cx", [a, b], []),
    ]


def _ccz(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    t = q[2]
    return [("h", [t], []), ("ccx", list(q), []), ("h", [t], [])]


def _cswap(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    c, a, b = q
    return [("cx", [b, a], []), ("ccx", [c, a, b], []), ("cx", [b, a], [])]


def _r(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    theta, phi = p
    return [("u3", [q[0]], [theta, phi - _PI / 2.0, _PI / 2.0 - phi])]


def _iswap(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    a, b = q
    return [
        ("s", [a], []),
        ("s", [b], []),
        ("h", [a], []),
        ("cx", [a, b], []),
        ("cx", [b, a], []),
        ("h", [b], []),
    ]


def _dcx(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    a, b = q
    return [("cx", [a, b], []), ("cx", [b, a], [])]


def _rzx(a: int, b: int, theta: float) -> List[Instruction]:
    return [
        ("h", [b], []),
        ("cx", [a, b], []),
        ("rz", [b], [theta]),
        ("cx", [a, b], []),
        ("h", [b], []),
    ]


def _ecr(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    a, b = q
    return _rzx(a, b, _PI / 4.0) + [("x", [a], [])] + _rzx(a, b, -_PI / 4.0)


def _cu3(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    c, t = q
    theta, phi, lam = p
    return [
        ("p", [c], [(lam + phi) / 2.0]),
        ("p", [t], [(lam - phi) / 2.0]),
        ("cx", [c, t], []),
        ("u3", [t], [-theta / 2.0, 0.0, -(phi + lam) / 2.0]),
        ("cx", [c, t], []),
        ("u3", [t], [theta / 2.0, phi, 0.0]),
    ]


def _cu(q: Sequence[int], p: Sequence[float]) -> List[Instruction]:
    return [("p", [q[0]], [p[3]])] + _cu3(q, p[:3])


def _csx(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    c, t = q
    return [("h", [t], [])] + _cs([c, t], []) + [("h", [t], [])]


def _multi_controlled_z(qubits: Sequence[int]) -> List[Instruction]:
    """
    Exact diagonal ``exp(i*pi*x_1*...*x_m)`` over ``m`` qubits.

    ``x_1...x_m = 2^-(m-1) * sum_S (-1)^(|S|+1) * parity_S(x)`` over the
    non-empty subsets ``S`` of the qubits, so each subset contributes one phase
    rotation on a parity computed by a CX ladder.
    """
    m = len(qubits)
    out: List[Instruction] = []
    for mask in range(1, 1 << m):
        subset = [qubits[i] for i in range(m) if mask >> i & 1]
        pivot = subset[-1]
        ladder = [("cx", [other, pivot], []) for other in subset[:-1]]
        angle = (-1.0) ** (len(subset) + 1) * _PI / 2.0 ** (m - 1)
        out += ladder + [("p", [pivot], [angle])] + list(reversed(ladder))
    return out


def _mcx(q: Sequence[int], _p: Sequence[float]) -> List[Instruction]:
    t = q[-1]
    return [("h", [t], [])] + _multi_controlled_z(list(q)) + [("h", [t], [])]


#: Composite gate name -> exact rewrite. Every name here has an empty ``paths``
#: set and ``lowered=True`` in the manifest.
LOWERING_RULES: Dict[str, Callable[[Sequence[int], Sequence[float]], List[Instruction]]] = {
    "u": _u3,
    "u3": _u3,
    "u2": _u2,
    "sx": _sx,
    "sxdg": _sxdg,
    "cy": _cy,
    "ch": _ch,
    "cs": _cs,
    "csdg": _csdg,
    "rzz": _rzz,
    "rxx": _rxx,
    "ryy": _ryy,
    "ccx": _ccx,
    "toffoli": _ccx,
    "ccz": _ccz,
    "cswap": _cswap,
    "fredkin": _cswap,
    "r": _r,
    "iswap": _iswap,
    "dcx": _dcx,
    "ecr": _ecr,
    "cu3": _cu3,
    "cu": _cu,
    "csx": _csx,
    "c3x": _mcx,
    "c4x": _mcx,
}

#: Recursion guard. Rules nest at most three deep (cswap -> ccx -> primitives).
_MAX_DEPTH = 8


class GateLoweringError(ValueError):
    """Raised when a composite gate has an invalid signature or operands."""


def _lower_one(inst: Instruction, depth: int, out: List[Instruction]) -> None:
    name, qubits, params = inst
    rule = LOWERING_RULES.get(name)
    if rule is None:
        out.append(inst)
        return
    if depth > _MAX_DEPTH:  # pragma: no cover - guards future rule edits
        raise GateLoweringError(f"lowering of {name!r} did not terminate")
    errors = signature_errors(name, qubits, params)
    if errors:
        raise GateLoweringError("; ".join(errors))
    if len(set(qubits)) != len(qubits):
        raise GateLoweringError(
            f"gate {name!r} requires distinct qubit operands, got {list(qubits)}"
        )
    for sub in rule(list(qubits), list(params)):
        _lower_one(sub, depth + 1, out)


def lower_instructions(instructions: Sequence[Instruction]) -> List[Instruction]:
    """
    Rewrites every composite gate into natively executed gates.

    Non-composite instructions (including measurements, barriers and unknown
    names, which later stages refuse) pass through unchanged and in order.
    """
    out: List[Instruction] = []
    for inst in instructions:
        _lower_one(inst, 0, out)
    return out


def is_lowered_gate(name: str) -> bool:
    """True when `name` is executed through an exact decomposition."""
    spec = get_gate(name)
    return spec is not None and spec.lowered
