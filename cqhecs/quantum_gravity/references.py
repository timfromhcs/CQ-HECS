"""Exact small-system references and independent oracles.

Everything here is for *tiny* dense systems (num_qubits <= 8). It provides two
independent routes to the same physics so a test can compare them:

* matrix exponential (``scipy.linalg.expm``) — the primary route;
* eigen-decomposition of the Hermitian Hamiltonian — an independent route.

Trotter / product-formula evolution is provided so its error can be measured and reported
*separately* from shot noise, exactly as the mission requires.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np
from scipy.linalg import expm

from cqhecs.quantum_gravity.errors import QGModelError


def _check_hermitian(matrix: np.ndarray, tol: float = 1e-10) -> None:
    if not np.allclose(matrix, matrix.conj().T, atol=tol):
        raise QGModelError("operator must be Hermitian for a physical Hamiltonian")


def exact_evolution_operator(hamiltonian: np.ndarray, t: float) -> np.ndarray:
    """Return ``exp(-i H t)`` via the matrix exponential."""
    ham = np.asarray(hamiltonian, dtype=complex)
    _check_hermitian(ham)
    return expm(-1j * float(t) * ham)


def evolve_state(hamiltonian: np.ndarray, t: float, psi0) -> np.ndarray:
    """Evolve ``psi0`` by the exact matrix exponential; returns a unit-norm vector."""
    vec = np.asarray(psi0, dtype=complex).reshape(-1)
    return exact_evolution_operator(hamiltonian, t) @ vec


def evolve_state_eigendecomposition(hamiltonian: np.ndarray, t: float, psi0) -> np.ndarray:
    """Independent oracle: ``V exp(-i Lambda t) V^dagger psi0`` from ``eigh``."""
    ham = np.asarray(hamiltonian, dtype=complex)
    _check_hermitian(ham)
    weights, vectors = np.linalg.eigh(ham)
    vec = np.asarray(psi0, dtype=complex).reshape(-1)
    return vectors @ (np.exp(-1j * weights * float(t)) * (vectors.conj().T @ vec))


def loschmidt_amplitude(hamiltonian: np.ndarray, t: float, psi0) -> complex:
    """``<psi0| exp(-i H t) |psi0>`` for a normalised reference state."""
    vec = np.asarray(psi0, dtype=complex).reshape(-1)
    norm = np.linalg.norm(vec)
    if norm == 0.0:
        raise QGModelError("reference state has zero norm")
    vec = vec / norm
    evolved = evolve_state(hamiltonian, t, vec)
    return complex(np.vdot(vec, evolved))


def trotter_first_order(
    terms: Sequence[np.ndarray], t: float, steps: int, psi0
) -> np.ndarray:
    """First-order product formula using Hermitian term matrices ``H = sum terms``.

    ``U(t) ~= prod_k exp(-i h_k dt)`` repeated ``steps`` times. Each ``h_k`` must be
    Hermitian; the caller is responsible for the decomposition.
    """
    if steps < 1:
        raise QGModelError("steps must be >= 1")
    dt = float(t) / steps
    vec = np.asarray(psi0, dtype=complex).reshape(-1).copy()
    propagators = [expm(-1j * dt * np.asarray(term, dtype=complex)) for term in terms]
    for _ in range(steps):
        for propagator in propagators:
            vec = propagator @ vec
    return vec


def trotter_error_scan(
    hamiltonian: np.ndarray,
    terms: Sequence[np.ndarray],
    t: float,
    psi0,
    steps_list: Sequence[int],
) -> List[dict]:
    """Return ``||psi_trotter - psi_exact||_2`` for each step count (independent of shots)."""
    exact = evolve_state(hamiltonian, t, psi0)
    rows: List[dict] = []
    for steps in steps_list:
        approx = trotter_first_order(terms, t, steps, psi0)
        rows.append(
            {
                "steps": int(steps),
                "l2_error": float(np.linalg.norm(approx - exact)),
            }
        )
    return rows


def infinite_temperature_otoc(
    hamiltonian: np.ndarray,
    w: np.ndarray,
    v: np.ndarray,
    t: float,
    *,
    reference: np.ndarray | None = None,
) -> complex:
    """Infinite-temperature OTOC ``F(t) = <W(t)^dag V^dag W(t) V>``.

    With no ``reference`` the trace ``Tr[W(t)^dag V^dag W(t) V] / d`` is used (maximally
    mixed / infinite temperature). Provide a pure ``reference`` vector for a non-thermal
    average ``<psi|...|psi>``.
    """
    ham = np.asarray(hamiltonian, dtype=complex)
    _check_hermitian(ham)
    evolved = exact_evolution_operator(ham, t)
    wt = evolved.conj().T @ np.asarray(w, dtype=complex) @ evolved
    inner = wt.conj().T @ np.asarray(v, dtype=complex).conj().T @ wt @ np.asarray(v, dtype=complex)
    if reference is None:
        dim = ham.shape[0]
        return complex(np.trace(inner) / dim)
    vec = np.asarray(reference, dtype=complex).reshape(-1)
    vec = vec / np.linalg.norm(vec)
    return complex(np.vdot(vec, inner @ vec))
