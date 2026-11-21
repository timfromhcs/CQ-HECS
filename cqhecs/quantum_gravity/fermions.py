"""Majorana fermions and the Jordan-Wigner qubit encoding.

Majorana convention: ``n`` qubits carry ``N = 2n`` Majorana modes

    gamma_{2k}   = Z^{x k} (x) X (x) I^{x (n-1-k)}
    gamma_{2k+1} = Z^{x k} (x) Y (x) I^{x (n-1-k)}        (k = 0 .. n-1)

with the qubit-0-is-most-significant index convention used across this package. These
operators are Hermitian and satisfy ``{gamma_i, gamma_j} = 2 delta_ij I``; both facts are
asserted by ``validate_majorana_algebra`` and by the SYK tests.

Pauli labels are strings over ``I X Y Z`` with ``label[0]`` acting on qubit 0.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from cqhecs.quantum_gravity.errors import QGModelError, QGResourceError

_PAULI: Dict[str, np.ndarray] = {
    "I": np.array([[1, 0], [0, 1]], dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
}

#: Single-qubit Pauli products: table[a][b] = (phase, char) with a * b = phase * char.
_MULT_TABLE: Dict[str, Dict[str, Tuple[complex, str]]] = {
    "I": {"I": (1, "I"), "X": (1, "X"), "Y": (1, "Y"), "Z": (1, "Z")},
    "X": {"I": (1, "X"), "X": (1, "I"), "Y": (1j, "Z"), "Z": (-1j, "Y")},
    "Y": {"I": (1, "Y"), "X": (-1j, "Z"), "Y": (1, "I"), "Z": (1j, "X")},
    "Z": {"I": (1, "Z"), "X": (1j, "Y"), "Y": (-1j, "X"), "Z": (1, "I")},
}

#: Dense-matrix inputs are only built for widths at or below this ceiling (dim <= 256).
DENSE_QUBIT_CEILING = 8


def _check_label(label: str, num_qubits: int) -> None:
    if len(label) != num_qubits or any(ch not in _PAULI for ch in label):
        raise QGModelError(f"invalid Pauli label {label!r} for {num_qubits} qubits")


def pauli_multiply(a: str, b: str) -> Tuple[complex, str]:
    """Multiply two Pauli strings of equal length. Returns ``(phase, label)``."""
    if len(a) != len(b):
        raise QGModelError("Pauli strings must have equal length")
    phase: complex = 1.0
    out: List[str] = []
    for ca, cb in zip(a, b):
        p, ch = _MULT_TABLE[ca][cb]
        phase *= p
        out.append(ch)
    return phase, "".join(out)


def majorana_labels(num_qubits: int) -> List[str]:
    """Return the ``2 * num_qubits`` Majorana Pauli labels in order."""
    if num_qubits < 1:
        raise QGModelError("num_qubits must be >= 1")
    labels: List[str] = []
    for k in range(num_qubits):
        prefix = "Z" * k
        suffix = "I" * (num_qubits - 1 - k)
        labels.append(prefix + "X" + suffix)
        labels.append(prefix + "Y" + suffix)
    return labels


def pauli_matrix(label: str) -> np.ndarray:
    """Dense matrix of a Pauli label (qubit 0 most significant)."""
    matrix = np.array([[1.0 + 0j]])
    for ch in label:
        matrix = np.kron(matrix, _PAULI[ch])
    return matrix


def _guard_dense(num_qubits: int) -> None:
    if num_qubits > DENSE_QUBIT_CEILING:
        raise QGResourceError(
            f"dense construction limited to {DENSE_QUBIT_CEILING} qubits "
            f"(2^{DENSE_QUBIT_CEILING} complex amplitudes); got {num_qubits}",
            estimate={"num_qubits": num_qubits, "ceiling": DENSE_QUBIT_CEILING},
        )


def majorana_operators(num_qubits: int) -> List[np.ndarray]:
    """Dense Majorana operators ``[gamma_0 .. gamma_{2n-1}]`` (width <= ceiling)."""
    _guard_dense(num_qubits)
    return [pauli_matrix(label) for label in majorana_labels(num_qubits)]


def validate_majorana_algebra(num_qubits: int, *, tol: float = 1e-10) -> float:
    """Assert ``{gamma_i, gamma_j} = 2 delta_ij I``; return the worst residual."""
    ops = majorana_operators(num_qubits)
    dim = ops[0].shape[0]
    identity = np.eye(dim, dtype=complex)
    worst = 0.0
    for i, gi in enumerate(ops):
        if not np.allclose(gi, gi.conj().T, atol=tol):
            raise QGModelError(f"Majorana gamma_{i} is not Hermitian")
        for j, gj in enumerate(ops):
            residual = gi @ gj + gj @ gi - (2.0 * identity if i == j else 0.0)
            worst = max(worst, float(np.max(np.abs(residual))))
    if worst > tol:
        raise QGModelError(f"Majorana anticommutator residual {worst:.3e} exceeds {tol:.1e}")
    return worst


def parity_operator(num_qubits: int) -> np.ndarray:
    """Return ``prod_i gamma_i`` (a scalar multiple of the fermion-parity operator)."""
    _guard_dense(num_qubits)
    total = np.eye(2 ** num_qubits, dtype=complex)
    for label in majorana_labels(num_qubits):
        total = total @ pauli_matrix(label)
    return total
