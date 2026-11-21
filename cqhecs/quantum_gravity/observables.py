"""Entanglement and correlation observables (pure NumPy, no Qiskit dependency).

Every function states its convention. The implementations are intentionally simple and
independent of Qiskit so that the tests can cross-check them against Qiskit's
``quantum_info`` as an *independent* oracle rather than a mirror of the same code.

Basis convention: for ``n`` qubits the state index is ``sum_k b_k * 2**(n-1-k)``, i.e.
qubit 0 is the most significant bit. This matches CQ-HECS / Qiskit little-endian display
of bitstrings ``b0 b1 ... b_{n-1}``.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

_PAULI = {
    "I": np.array([[1, 0], [0, 1]], dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
}


def normalize_state(psi) -> np.ndarray:
    """Return ``psi`` as a unit-norm complex column vector."""
    vec = np.asarray(psi, dtype=complex).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("state vector has zero or non-finite norm")
    return vec / norm


def ket_to_density(psi) -> np.ndarray:
    """Return ``|psi><psi|`` for a (possibly unnormalised) state vector."""
    vec = normalize_state(psi)
    return np.outer(vec, vec.conj())


def _as_square(matrix, name: str) -> np.ndarray:
    arr = np.asarray(matrix, dtype=complex)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(f"{name} must be a square matrix")
    return arr


def _hermitian(matrix: np.ndarray) -> np.ndarray:
    return 0.5 * (matrix + matrix.conj().T)


def partial_transpose(rho, dims: Sequence[int], subsystem: int) -> np.ndarray:
    """Partial transpose of ``rho`` on ``subsystem`` (0-based) with the given dims."""
    rho = _as_square(rho, "rho")
    dims = tuple(int(d) for d in dims)
    n = len(dims)
    if int(np.prod(dims)) != rho.shape[0]:
        raise ValueError("dims do not match the matrix dimension")
    if not 0 <= subsystem < n:
        raise ValueError(f"subsystem {subsystem} out of range for {n} subsystems")
    tensor = rho.reshape(dims + dims)
    axes = list(range(2 * n))
    axes[subsystem], axes[subsystem + n] = axes[subsystem + n], axes[subsystem]
    return tensor.transpose(axes).reshape(rho.shape)


def partial_trace(rho, dims: Sequence[int], keep: Sequence[int] = (0,)) -> np.ndarray:
    """Partial trace of ``rho`` keeping the subsystems in ``keep``."""
    rho = _as_square(rho, "rho")
    dims = tuple(int(d) for d in dims)
    n = len(dims)
    keep = tuple(sorted(int(k) for k in keep))
    if int(np.prod(dims)) != rho.shape[0]:
        raise ValueError("dims do not match the matrix dimension")
    rest = tuple(i for i in range(n) if i not in keep)
    perm = tuple(keep) + tuple(rest)
    axes = perm + tuple(p + n for p in perm)
    tensor = rho.reshape(dims + dims).transpose(axes)
    dk = int(np.prod([dims[i] for i in keep])) if keep else 1
    dr = int(np.prod([dims[i] for i in rest])) if rest else 1
    tensor = tensor.reshape(dk, dr, dk, dr)
    return np.einsum("ijkj->ik", tensor)


def negativity_2qubit(rho, dims: Sequence[int] = (2, 2)) -> float:
    """Negativity ``N = (||rho^{T_A}||_1 - 1)/2`` for a 2-qubit state."""
    rho = _as_square(rho, "rho")
    pt = _hermitian(partial_transpose(rho, dims, 0))
    weights = np.linalg.eigvalsh(pt)
    return float((np.sum(np.abs(weights)) - 1.0) / 2.0)


def concurrence_2qubit(rho, *, rel_tol: float = 1e-12) -> float:
    """Wootters concurrence of a two-qubit density matrix (0 for separable states).

    The ``lambda_i`` are the square roots of the eigenvalues ``mu_i`` of
    ``rho (Y(x)Y) rho* (Y(x)Y)``; ``C = max(0, l0 - l1 - l2 - l3)``.

    Numerical-zero policy: an eigenvalue ``mu_i < rel_tol * max(mu)`` is treated as
    exactly zero. This matches the repository's documented numerical-rank floor and
    stops ``sqrt`` of pure roundoff (~1e-17) from adding ~1e-9 to a pure state's
    concurrence. The floor is relative, so it never hides a genuine entanglement signal.
    """
    rho = _as_square(rho, "rho")
    if rho.shape != (4, 4):
        raise ValueError("concurrence_2qubit expects a 4x4 two-qubit density matrix")
    y = _PAULI["Y"]
    yy = np.kron(y, y)
    rho_tilde = yy @ rho.conj() @ yy
    product = rho @ rho_tilde
    mu = np.clip(np.real(np.linalg.eigvals(product)), 0.0, None)
    top = float(mu.max()) if mu.size else 0.0
    if top > 0.0:
        mu = np.where(mu < rel_tol * top, 0.0, mu)
    eigenvalues = np.sort(np.sqrt(mu))[::-1]
    return float(max(0.0, eigenvalues[0] - eigenvalues[1] - eigenvalues[2] - eigenvalues[3]))


def concurrence_pure_2qubit(psi) -> float:
    """Closed-form concurrence ``2|ad - bc|`` for a pure two-qubit state."""
    vec = normalize_state(psi)
    if vec.size != 4:
        raise ValueError("concurrence_pure_2qubit expects a two-qubit state vector")
    a, b, c, d = vec
    return float(2.0 * abs(a * d - b * c))


def entanglement_entropy(rho, dims: Sequence[int], keep: Sequence[int] = (0,)) -> float:
    """Von Neumann entropy (bits) of the reduced state on ``keep``."""
    reduced = _hermitian(partial_trace(rho, dims, keep))
    weights = np.linalg.eigvalsh(reduced)
    weights = weights[weights > 1e-15]
    return float(-np.sum(weights * np.log2(weights)))


def correlation_matrix(psi) -> np.ndarray:
    """Return ``T[i, j] = <psi| sigma_i (x) sigma_j |psi>`` for i, j in {X, Y, Z}."""
    rho = ket_to_density(psi)
    labels = "XYZ"
    out = np.zeros((3, 3), dtype=float)
    for i, li in enumerate(labels):
        for j, lj in enumerate(labels):
            op = np.kron(_PAULI[li], _PAULI[lj])
            out[i, j] = float(np.real(np.trace(rho @ op)))
    return out


def chsh_bound(psi) -> float:
    """Horodecki CHSH maximum ``2*sqrt(u1^2 + u2^2)`` for a two-qubit pure state.

    ``u1, u2`` are the two largest singular values of the correlation matrix. For a pure
    state this equals ``2*sqrt(1 + C^2)`` with concurrence ``C``; the tests check that
    identity, so the CHSH route is an independent oracle for the entanglement measure.
    """
    singular = np.linalg.svd(correlation_matrix(psi), compute_uv=False)
    value = singular[0] ** 2 + singular[1] ** 2
    return float(2.0 * np.sqrt(max(0.0, value)))


def chsh_from_correlators(correlators) -> float:
    """CHSH combination ``E00 + E01 + E10 - E11`` from a 2x2 array of correlators."""
    corr = np.asarray(correlators, dtype=float)
    if corr.shape != (2, 2):
        raise ValueError("correlators must be a 2x2 array of E(a, b)")
    return float(corr[0, 0] + corr[0, 1] + corr[1, 0] - corr[1, 1])


def local_observable(bloch_vector) -> np.ndarray:
    """Return ``a . sigma`` for a 3-vector of Bloch components."""
    vx, vy, vz = (float(x) for x in bloch_vector)
    return vx * _PAULI["X"] + vy * _PAULI["Y"] + vz * _PAULI["Z"]


def correlation_ab(psi, a: Sequence[float], b: Sequence[float]) -> float:
    """Expectation ``<psi| (a . sigma) (x) (b . sigma) |psi>``."""
    rho = ket_to_density(psi)
    op = np.kron(local_observable(a), local_observable(b))
    return float(np.real(np.trace(rho @ op)))


def binary_entropy(probability: float) -> float:
    """Von Neumann entropy of a qubit with eigenvalue ``p`` (bits)."""
    p = float(probability)
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-p * np.log2(p) - (1.0 - p) * np.log2(1.0 - p))
