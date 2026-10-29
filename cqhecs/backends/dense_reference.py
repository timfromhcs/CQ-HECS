"""
Dense float64 statevector reference.

A deliberately small, self-contained simulator used for exact Pauli expectation
values and probabilities on moderately sized registers, and as an oracle that
shares no code with the four production paths. It implements exactly the
natively executed gate set of :mod:`cqhecs.gate_manifest`; composite gates must
be lowered first (``parse_circuit`` does this).

Conventions
-----------
* Qubit ``q`` is axis ``q`` of the internal ``(2,) * n`` tensor.
* :meth:`statevector` and :meth:`probabilities` use Qiskit's little-endian
  order: bit ``q`` of the basis index is qubit ``q``.
* Rotation gates follow Qiskit (``rz(t) = diag(exp(-it/2), exp(it/2))``).
* Two-qubit gates take the first operand as the control.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np

Instruction = Tuple[str, List[int], List[float]]

#: 2**26 complex128 amplitudes are 1 GiB; refuse before allocating more.
MAX_DENSE_QUBITS = 26

_SQRT1_2 = 1.0 / math.sqrt(2.0)


class DenseReferenceError(ValueError):
    """Raised for unsupported gates, bad operands or oversized registers."""


def _single_qubit_matrix(name: str, params: Sequence[float]) -> np.ndarray:
    if name in ("id",):
        return np.eye(2, dtype=np.complex128)
    fixed = {
        "h": [[_SQRT1_2, _SQRT1_2], [_SQRT1_2, -_SQRT1_2]],
        "x": [[0, 1], [1, 0]],
        "y": [[0, -1j], [1j, 0]],
        "z": [[1, 0], [0, -1]],
        "s": [[1, 0], [0, 1j]],
        "sdg": [[1, 0], [0, -1j]],
        "t": [[1, 0], [0, np.exp(1j * math.pi / 4)]],
        "tdg": [[1, 0], [0, np.exp(-1j * math.pi / 4)]],
    }
    if name in fixed:
        return np.array(fixed[name], dtype=np.complex128)
    if len(params) != 1:
        raise DenseReferenceError(f"gate {name!r} needs exactly one parameter")
    theta = float(params[0])
    if name == "rz":
        return np.array(
            [[np.exp(-0.5j * theta), 0], [0, np.exp(0.5j * theta)]],
            dtype=np.complex128,
        )
    if name == "rx":
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
    if name == "ry":
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return np.array([[c, -s], [s, c]], dtype=np.complex128)
    if name in ("p", "u1"):
        return np.array([[1, 0], [0, np.exp(1j * theta)]], dtype=np.complex128)
    raise DenseReferenceError(f"unsupported single-qubit gate {name!r}")


def _two_qubit_tensor(name: str, params: Sequence[float]) -> np.ndarray:
    """Returns ``G[o_a, o_b, i_a, i_b]`` with ``a`` the first operand."""
    g = np.zeros((2, 2, 2, 2), dtype=np.complex128)
    if name in ("cx", "cnot"):
        for a in range(2):
            for b in range(2):
                g[a, b ^ a, a, b] = 1.0
        return g
    if name == "cz":
        for a in range(2):
            for b in range(2):
                g[a, b, a, b] = -1.0 if a and b else 1.0
        return g
    if name == "swap":
        for a in range(2):
            for b in range(2):
                g[b, a, a, b] = 1.0
        return g
    if len(params) != 1:
        raise DenseReferenceError(f"gate {name!r} needs exactly one parameter")
    theta = float(params[0])
    if name in ("cp", "cu1"):
        for a in range(2):
            for b in range(2):
                g[a, b, a, b] = np.exp(1j * theta) if a and b else 1.0
        return g
    if name in ("crx", "cry", "crz"):
        u = _single_qubit_matrix(name[1:], [theta])
        for b in range(2):
            g[0, b, 0, b] = 1.0
        for ob in range(2):
            for ib in range(2):
                g[1, ob, 1, ib] = u[ob, ib]
        return g
    raise DenseReferenceError(f"unsupported two-qubit gate {name!r}")


_PAULI = {
    "X": _single_qubit_matrix("x", ()),
    "Y": _single_qubit_matrix("y", ()),
    "Z": _single_qubit_matrix("z", ()),
}


class DenseStatevector:
    """Exact dense simulation of the natively executed gate set."""

    def __init__(self, num_qubits: int):
        if not isinstance(num_qubits, int) or num_qubits < 1:
            raise DenseReferenceError(f"num_qubits must be >= 1, got {num_qubits!r}")
        if num_qubits > MAX_DENSE_QUBITS:
            raise DenseReferenceError(
                f"dense statevector of {num_qubits} qubits exceeds the "
                f"{MAX_DENSE_QUBITS}-qubit ceiling (2^{num_qubits} amplitudes)"
            )
        self.n = num_qubits
        self.psi = np.zeros((2,) * num_qubits, dtype=np.complex128)
        self.psi[(0,) * num_qubits] = 1.0

    # -- gate application ---------------------------------------------
    def _check(self, qubits: Sequence[int], arity: int, name: str) -> None:
        if len(qubits) != arity:
            raise DenseReferenceError(
                f"gate {name!r} expects {arity} qubit(s), got {len(qubits)}"
            )
        if len(set(qubits)) != len(qubits):
            raise DenseReferenceError(f"gate {name!r} has repeated operands {list(qubits)}")
        for q in qubits:
            if not 0 <= q < self.n:
                raise DenseReferenceError(
                    f"qubit {q} out of range for {self.n} qubits (gate {name!r})"
                )

    def _apply_1q(self, psi: np.ndarray, matrix: np.ndarray, q: int) -> np.ndarray:
        out = np.tensordot(matrix, psi, axes=([1], [q]))
        return np.moveaxis(out, 0, q)

    def apply(self, name: str, qubits: Sequence[int], params: Sequence[float] = ()) -> None:
        name = name.lower()
        if name in ("barrier",):
            return
        if name == "measure":
            raise DenseReferenceError("measurements are not part of a dense evolution")
        if name in ("cx", "cnot", "cz", "swap", "cp", "cu1", "crx", "cry", "crz"):
            self._check(qubits, 2, name)
            a, b = qubits
            g = _two_qubit_tensor(name, params)
            out = np.tensordot(g, self.psi, axes=([2, 3], [a, b]))
            self.psi = np.moveaxis(out, [0, 1], [a, b])
            return
        self._check(qubits, 1, name)
        self.psi = self._apply_1q(self.psi, _single_qubit_matrix(name, params), qubits[0])

    def run(self, instructions: Sequence[Instruction]) -> "DenseStatevector":
        for name, qubits, params in instructions:
            self.apply(name, qubits, params)
        return self

    # -- read-out ------------------------------------------------------
    def statevector(self) -> np.ndarray:
        """Amplitudes in Qiskit little-endian order."""
        return self.psi.transpose(tuple(reversed(range(self.n)))).reshape(-1).copy()

    def probabilities(self) -> np.ndarray:
        return np.abs(self.statevector()) ** 2

    def pauli_expectation(self, ops: Sequence[Tuple[int, str]]) -> float:
        """``<psi| P |psi>`` for a Pauli string ``P`` given as ``(qubit, letter)``."""
        phi = self.psi
        seen = set()
        for q, letter in ops:
            if q in seen:
                raise DenseReferenceError(f"Pauli string repeats qubit {q}")
            seen.add(q)
            if not 0 <= q < self.n:
                raise DenseReferenceError(f"qubit {q} out of range for {self.n} qubits")
            if letter == "I":
                continue
            if letter not in _PAULI:
                raise DenseReferenceError(f"unknown Pauli letter {letter!r}")
            phi = self._apply_1q(phi, _PAULI[letter], q)
        value = np.vdot(self.psi, phi)
        return float(value.real)


def simulate(instructions: Sequence[Instruction], num_qubits: int) -> DenseStatevector:
    """Runs `instructions` on ``|0...0>`` and returns the final state."""
    return DenseStatevector(num_qubits).run(instructions)


def probabilities_dict(state: DenseStatevector, cutoff: float = 0.0) -> Dict[str, float]:
    """Bitstring -> probability, qubit 0 rightmost, dropping values <= cutoff."""
    probs = state.probabilities()
    return {
        format(i, f"0{state.n}b"): float(p)
        for i, p in enumerate(probs)
        if p > cutoff
    }
