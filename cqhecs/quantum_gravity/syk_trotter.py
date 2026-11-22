"""Track B, W8: SYK Trotter circuit compilation, QASM mapping oracle and error-bound table.

A first-order Lie-Trotter step of ``H = sum_k h_k`` (each ``h_k = c_k P_k`` a real multiple of
a Pauli string) is ``prod_k exp(-i c_k P_k dt)``. Each factor is compiled as

    V^dagger  .  CX-ladder . Rz(2 c_k dt) . CX-ladder  .  V

with single-qubit basis changes ``V`` (``H`` for X, ``S^dagger`` then ``H`` for Y). The
compiled OpenQASM 2.0 is checked against the dense product of matrix exponentials by
:func:`qasm_dense_unitary` (an independent route through Qiskit).

Error reporting (kept separate from shot noise)
-----------------------------------------------
* measured: spectral-norm distance between the dense exact ``exp(-iHt)`` and the dense
  Trotter product, plus the state-vector distance for a given input;
* bound: the standard commutator bound for the first-order formula,
  ``||U - S^r|| <= (t^2 / 2r) * sum_{j<k} ||[h_j, h_k]||``, evaluated in closed form for Pauli
  terms (``||[aP, bQ]|| = 2|ab|`` when ``P`` and ``Q`` anticommute, else ``0``).

The bound is a Trotter bound only. It says nothing about device noise or shot error, and a
small value does not certify any physical claim: this is a finite-N model.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from scipy.linalg import expm

from cqhecs.quantum_gravity.errors import QGModelError, QGResourceError
from cqhecs.quantum_gravity.fermions import DENSE_QUBIT_CEILING, majorana_labels, pauli_matrix
from cqhecs.quantum_gravity.hamiltonians import SYKHamiltonian, _pauli_terms_for_indices

TROTTER_SCHEMA = "cqhecs.qg.syk_trotter.v1"

PauliTerm = Tuple[str, float]


def pauli_terms(syk: SYKHamiltonian) -> List[PauliTerm]:
    """Hermitian Pauli terms ``(label, real coefficient)`` in coupling-index order.

    Each Majorana quadruple maps to one Pauli string with a phase of ``+-1`` (never ``+-i``,
    because a product of four distinct Majoranas is Hermitian). The order matches
    :meth:`SYKHamiltonian.hermitian_terms`, so the Trotter product is the same operator
    product the historical reference used.
    """
    labels = majorana_labels(syk.num_qubits)
    norm = float(np.sqrt(syk.total_terms)) if (syk.normalize and syk.total_terms) else 1.0
    out: List[PauliTerm] = []
    for combo, coupling in sorted(syk.couplings.items()):
        phase, label = _pauli_terms_for_indices(labels, combo)
        if abs(phase.imag) > 1e-12 or abs(abs(phase.real) - 1.0) > 1e-12:
            raise QGModelError(f"Majorana quadruple {combo} produced a non-Hermitian phase {phase}")
        out.append((label, float(coupling / norm * phase.real)))
    return out


def anticommute(a: str, b: str) -> bool:
    """True when two equal-length Pauli strings anticommute."""
    if len(a) != len(b):
        raise QGModelError("Pauli strings must have equal length")
    clashes = sum(1 for x, y in zip(a, b) if x != "I" and y != "I" and x != y)
    return clashes % 2 == 1


# -- QASM compilation ---------------------------------------------------------------
def _basis_in(label: str) -> List[str]:
    lines: List[str] = []
    for q, ch in enumerate(label):
        if ch == "X":
            lines.append(f"h q[{q}];")
        elif ch == "Y":
            lines.append(f"sdg q[{q}];")
            lines.append(f"h q[{q}];")
    return lines


def _basis_out(label: str) -> List[str]:
    lines: List[str] = []
    for q, ch in enumerate(label):
        if ch == "X":
            lines.append(f"h q[{q}];")
        elif ch == "Y":
            lines.append(f"h q[{q}];")
            lines.append(f"s q[{q}];")
    return lines


def pauli_rotation_lines(label: str, phi: float) -> List[str]:
    """OpenQASM lines for ``exp(-i phi P)``; an all-identity label is a global phase (no gates)."""
    active = [q for q, ch in enumerate(label) if ch != "I"]
    if not active:
        return []
    target = active[-1]
    ladder = [f"cx q[{q}],q[{target}];" for q in active[:-1]]
    body = list(ladder) + [f"rz({2.0 * phi:.17g}) q[{target}];"] + list(reversed(ladder))
    return _basis_in(label) + body + _basis_out(label)


def _validate_steps(t: float, steps: int) -> None:
    if not math.isfinite(t):
        raise QGModelError("t must be finite")
    if int(steps) != steps or steps < 1:
        raise QGModelError("steps must be an integer >= 1")


def trotter_qasm(
    terms: Sequence[PauliTerm],
    num_qubits: int,
    t: float,
    steps: int = 1,
    *,
    measure: bool = False,
    inverse: bool = False,
) -> str:
    """OpenQASM 2.0 for the first-order Trotter product ``(prod_k exp(-i c_k P_k t/r))^r``.

    With ``inverse=True`` the factors are emitted in reverse order with negated angles, which
    is the exact inverse of the forward product.
    """
    _validate_steps(t, steps)
    dt = float(t) / steps
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{num_qubits}];"]
    if measure:
        lines.append(f"creg c[{num_qubits}];")
    ordered = list(terms)[::-1] if inverse else list(terms)
    sign = -1.0 if inverse else 1.0
    for _ in range(int(steps)):
        for label, coeff in ordered:
            if len(label) != num_qubits:
                raise QGModelError(f"term {label!r} does not match {num_qubits} qubits")
            lines.extend(pauli_rotation_lines(label, sign * coeff * dt))
    if measure:
        lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def syk_trotter_qasm(syk: SYKHamiltonian, t: float, steps: int = 1, *, measure: bool = False) -> str:
    return trotter_qasm(pauli_terms(syk), syk.num_qubits, t, steps, measure=measure)


def syk_mirror_qasm(syk: SYKHamiltonian, t: float, steps: int = 1, *, measure: bool = False) -> str:
    """Forward Trotter evolution followed by its exact inverse (a true return-to-start test)."""
    terms = pauli_terms(syk)
    forward = trotter_qasm(terms, syk.num_qubits, t, steps)
    backward = trotter_qasm(terms, syk.num_qubits, t, steps, inverse=True)
    body = forward.splitlines() + [
        line for line in backward.splitlines() if not line.startswith(("OPENQASM", "include", "qreg"))
    ]
    if measure:
        body.insert(3, f"creg c[{syk.num_qubits}];")
        body.append("measure q -> c;")
    return "\n".join(body) + "\n"


# -- dense oracles ------------------------------------------------------------------
def qasm_dense_unitary(qasm: str) -> np.ndarray:
    """Dense unitary of a measurement-free QASM string in this package's qubit order (q0 most significant)."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator

    circuit = QuantumCircuit.from_qasm_str(qasm)
    return np.asarray(Operator(circuit.reverse_bits()).data, dtype=complex)


def _guard(num_qubits: int) -> None:
    if num_qubits > DENSE_QUBIT_CEILING:
        raise QGResourceError(
            f"dense Trotter oracle limited to {DENSE_QUBIT_CEILING} qubits",
            estimate={"num_qubits": num_qubits, "ceiling": DENSE_QUBIT_CEILING},
        )


def dense_hamiltonian(terms: Sequence[PauliTerm], num_qubits: int) -> np.ndarray:
    _guard(num_qubits)
    dim = 2 ** num_qubits
    ham = np.zeros((dim, dim), dtype=complex)
    for label, coeff in terms:
        ham += coeff * pauli_matrix(label)
    return ham


def dense_trotter_unitary(terms: Sequence[PauliTerm], num_qubits: int, t: float, steps: int) -> np.ndarray:
    """Independent dense route: product of per-term matrix exponentials (no QASM, no CX ladders)."""
    _guard(num_qubits)
    _validate_steps(t, steps)
    dt = float(t) / steps
    dim = 2 ** num_qubits
    step = np.eye(dim, dtype=complex)
    for label, coeff in terms:
        step = expm(-1j * coeff * dt * pauli_matrix(label)) @ step
    return np.linalg.matrix_power(step, int(steps))


def equal_up_to_global_phase(a: np.ndarray, b: np.ndarray, *, atol: float = 1e-9) -> bool:
    if a.shape != b.shape:
        return False
    overlap = np.vdot(b, a)
    if abs(overlap) < 1e-12:
        return False
    phase = overlap / abs(overlap)
    return bool(np.allclose(a, phase * b, atol=atol))


# -- error table --------------------------------------------------------------------
def trotter_error_bound(terms: Sequence[PauliTerm], t: float, steps: int) -> float:
    """``(t^2 / 2r) * sum_{j<k} ||[h_j, h_k]||`` in closed form for Pauli terms."""
    _validate_steps(t, steps)
    total = 0.0
    items = list(terms)
    for j in range(len(items)):
        for k in range(j + 1, len(items)):
            if anticommute(items[j][0], items[k][0]):
                total += 2.0 * abs(items[j][1]) * abs(items[k][1])
    return float(t) ** 2 / (2.0 * steps) * total


def trotter_error_table(
    syk: SYKHamiltonian,
    t: float,
    steps_list: Sequence[int] = (1, 2, 4, 8, 16, 32),
) -> Dict[str, Any]:
    """Dense exact vs Trotter error table with the closed-form bound and exact/Trotter ``P(0..0)``.

    ``measured_spectral_error`` is ``||exp(-iHt) - S^r||_2`` (the quantity the bound controls);
    ``state_error`` and the two ``p_zero`` columns are for the all-zeros input. No sampling is
    involved, so none of these columns contains shot error.
    """
    terms = pauli_terms(syk)
    n = syk.num_qubits
    ham = dense_hamiltonian(terms, n)
    exact = expm(-1j * float(t) * ham)
    psi0 = np.zeros(2 ** n, dtype=complex)
    psi0[0] = 1.0
    exact_state = exact @ psi0
    rows: List[Dict[str, Any]] = []
    for steps in steps_list:
        trot = dense_trotter_unitary(terms, n, t, steps)
        spectral = float(np.linalg.norm(exact - trot, ord=2))
        trot_state = trot @ psi0
        rows.append(
            {
                "steps": int(steps),
                "measured_spectral_error": spectral,
                "state_error": float(np.linalg.norm(exact_state - trot_state)),
                "bound": trotter_error_bound(terms, t, steps),
                "p_zero_exact": float(abs(exact_state[0]) ** 2),
                "p_zero_trotter": float(abs(trot_state[0]) ** 2),
                "bound_holds": bool(spectral <= trotter_error_bound(terms, t, steps) + 1e-12),
            }
        )
    return {
        "schema": TROTTER_SCHEMA,
        "model_id": syk.model_id,
        "model_version": syk.model_version,
        "num_qubits": n,
        "seed": syk.seed,
        "scale": syk.scale,
        "t": float(t),
        "num_terms": len(terms),
        "order": 1,
        "surface": "CLASSICAL_REFERENCE",
        "uncertainty_class": "trotter_error",
        "rows": rows,
        "limitations": [
            "finite-N model; no spacetime, wormhole or gravity claim",
            "the bound is a first-order commutator bound; it excludes device noise and shot error",
            "dense route limited to <= 8 qubits",
        ],
    }
