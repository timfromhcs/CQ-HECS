"""
Pauli expectation values of noisy circuits (``NOISY_CLASSICAL``).

Two engines share one noise semantics (the one of
:class:`~cqhecs.backends.noisy_density_matrix.NoisyDensityMatrixBackend`: each
source instruction is lowered on its own and the channels the model attaches
to that gate act after it):

``density_matrix``
    Exact float64 density matrix, at most ``dm_max_qubits`` qubits.

``pauli_propagation``
    Heisenberg-picture Pauli propagation (Path D) with the adjoint of every
    noise channel applied in the Pauli basis. Pauli terms are truncated by
    coefficient magnitude and term budget, and the discarded 1-norm is
    reported as the error bound.

Why the bound stays a worst-case bound with noise
-------------------------------------------------
The Heisenberg-picture map of a CPTP channel, ``N^dag``, is unital and
positive, hence contractive in operator norm (Russo-Dye). A term ``delta``
discarded at some step therefore changes the final value by at most
``||delta||_op <= sum |c_P|`` for *any* input state, exactly as for unitary
gates. Noise only makes truncation cheaper: it damps high-weight Pauli terms,
which is the mechanism behind the polynomial-time results of Aharonov et al.
(STOC 2023), Schuster et al. (PRX 15, 041018, 2025) and Angrisani et al.
(arXiv:2501.13101). Those results bound the *average* error over input
states or random circuits; CQ-HECS does not claim them. Its bound covers the
truncation of this circuit and this input only, and says nothing about the
distance between the noise model and real hardware.

Readout
-------
With ``readout=True`` the assignment errors of the model act on every
measured (non-identity) factor: ``P_q -> (1 - p01 - p10) P_q + (p10 - p01) I``,
which is ``E[(-1)^m]`` for an outcome ``m`` read through the assignment
matrix. Non-Z factors assume that their basis change is part of the circuit
and noiseless.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.backends.path_d_sparse_pauli import (
    PAULI_BASIS,
    SparsePauliDynamicsSimulator,
    UnsupportedPathDOperation,
    _basis_matrices,
    _PAULI_INDEX_FLAT,
)
from cqhecs.circuit_parsing import parse_source_circuit
from cqhecs.expectation import ExpectationError, ExpectationResult, PauliString, _normalize_observables
from cqhecs.gate_lowering import GateLoweringError, lower_instructions
from cqhecs.hardware_bridge import NoiseModel
from cqhecs.result import ExecutionMode

NOISY_METHODS = ("auto", "density_matrix", "pauli_propagation")

Terms = Dict[Tuple[int, int], complex]


# --------------------------------------------------------------------------
# Heisenberg-picture transfer matrices in the stored basis X^x Z^z
# --------------------------------------------------------------------------
def heisenberg_matrix_1q(kraus: Sequence[np.ndarray]) -> np.ndarray:
    """M with ``N^dag(B_j) = sum_k M[k, j] B_k`` for ``B = (I, X, XZ, Z)``."""
    basis = _basis_matrices()
    m = np.zeros((4, 4), dtype=np.complex128)
    for j, bj in enumerate(basis):
        image = sum(k.conj().T @ bj @ k for k in kraus)
        for k_idx, bk in enumerate(basis):
            m[k_idx, j] = 0.5 * np.trace(bk.conj().T @ image)
    return m


def heisenberg_matrix_2q(kraus: Sequence[np.ndarray]) -> np.ndarray:
    """
    Two-qubit version; index ``4 * a + b`` for ``B_a (x) B_b``, where the first
    factor is the gate's first operand (the operand order of the 4x4 Kraus
    operators in :mod:`cqhecs.hardware_bridge`).
    """
    single = _basis_matrices()
    basis = [np.kron(a, b) for a in single for b in single]
    m = np.zeros((16, 16), dtype=np.complex128)
    for j, bj in enumerate(basis):
        image = sum(k.conj().T @ bj @ k for k in kraus)
        for k_idx, bk in enumerate(basis):
            m[k_idx, j] = 0.25 * np.trace(bk.conj().T @ image)
    return m


def _apply_2q_map(terms: Terms, a: int, b: int, m: np.ndarray) -> Terms:
    columns = []
    for j in range(16):
        entries = []
        for k in range(16):
            c = m[k, j]
            if c.real == 0.0 and c.imag == 0.0:
                continue
            ax, az = PAULI_BASIS[k // 4]
            bx, bz = PAULI_BASIS[k % 4]
            entries.append((ax, az, bx, bz, c))
        columns.append(entries)
    clear = ~((1 << a) | (1 << b))
    out: Terms = {}
    for (x_mask, z_mask), coeff in terms.items():
        ja = _PAULI_INDEX_FLAT[(((x_mask >> a) & 1) << 1) | ((z_mask >> a) & 1)]
        jb = _PAULI_INDEX_FLAT[(((x_mask >> b) & 1) << 1) | ((z_mask >> b) & 1)]
        for ax, az, bx, bz, c in columns[4 * ja + jb]:
            nx = (x_mask & clear) | (ax << a) | (bx << b)
            nz = (z_mask & clear) | (az << a) | (bz << b)
            out[(nx, nz)] = out.get((nx, nz), 0.0) + coeff * c
    return out


# --------------------------------------------------------------------------
# Observables and readout
# --------------------------------------------------------------------------
def _pauli_terms(pauli: PauliString) -> Terms:
    """``pauli`` as a single stored term; ``Y = i X Z``."""
    x_mask = z_mask = 0
    phase = complex(1.0, 0.0)
    for q, letter in pauli.ops:
        if letter in ("X", "Y"):
            x_mask |= 1 << q
        if letter in ("Z", "Y"):
            z_mask |= 1 << q
        if letter == "Y":
            phase *= 1j
    return {(x_mask, z_mask): phase}


def _apply_readout(terms: Terms, noise_model: NoiseModel) -> Terms:
    for q, channel in sorted(noise_model.readout_errors.items()):
        scale = 1.0 - channel.p01 - channel.p10
        shift = channel.p10 - channel.p01
        bit = 1 << q
        out: Terms = {}
        for (x_mask, z_mask), coeff in terms.items():
            if not ((x_mask | z_mask) & bit):
                out[(x_mask, z_mask)] = out.get((x_mask, z_mask), 0.0) + coeff
                continue
            out[(x_mask, z_mask)] = out.get((x_mask, z_mask), 0.0) + scale * coeff
            reduced = (x_mask & ~bit, z_mask & ~bit)
            # The assignment acts on the measured Pauli factor P in
            # {X, Y, Z}: P -> scale P + shift I. The stored factor XZ equals
            # -iY, so its identity part carries the phase -i.
            factor_phase = -1j if ((x_mask & bit) and (z_mask & bit)) else 1.0
            out[reduced] = out.get(reduced, 0.0) + shift * coeff * factor_phase
        terms = out
    return terms


# --------------------------------------------------------------------------
# Circuit preparation
# --------------------------------------------------------------------------
def _blocks(circuit: Any) -> Tuple[List[Tuple[str, List[int], List[Any]]], int]:
    try:
        source, num_qubits = parse_source_circuit(circuit)
    except Exception as exc:  # parser errors are typed but varied
        raise ExpectationError(str(exc)) from exc
    blocks = []
    seen_measure = False
    for name, qubits, params in source:
        lname = name.lower()
        if lname == "measure":
            seen_measure = True
            continue
        if lname == "reset":
            raise ExpectationError("reset is not supported for noisy expectation values")
        if seen_measure and lname not in ("barrier", "id"):
            raise ExpectationError("mid-circuit measurement is not supported for expectation values")
        try:
            ops = lower_instructions([(name, qubits, params)])
        except GateLoweringError as exc:
            raise ExpectationError(str(exc)) from exc
        blocks.append((lname, list(qubits), ops))
    if num_qubits < 1:
        raise ExpectationError("circuit has no qubits")
    return blocks, num_qubits


def _channels(noise_model: NoiseModel, gate: str, qubits: List[int]):
    if len(qubits) == 1:
        return noise_model.channels_1q.get(gate, {}).get(qubits[0], ())
    if len(qubits) == 2:
        return noise_model.channels_2q.get(gate, {}).get((qubits[0], qubits[1]), ())
    return ()


# --------------------------------------------------------------------------
# Engines
# --------------------------------------------------------------------------
def _propagate(
    blocks, noise_model: NoiseModel, start: Terms, sim: SparsePauliDynamicsSimulator, cache: Dict[int, np.ndarray],
) -> Tuple[Terms, float]:
    terms = dict(start)
    bound = 0.0
    for gate, qubits, ops in reversed(blocks):
        for channel in reversed(list(_channels(noise_model, gate, qubits))):
            key = id(channel)
            if key not in cache:
                kraus = channel.kraus_operators
                cache[key] = heisenberg_matrix_1q(kraus) if kraus[0].shape == (2, 2) else heisenberg_matrix_2q(kraus)
            m = cache[key]
            if m.shape == (4, 4):
                terms = sim._apply_single_qubit_backward(terms, qubits[0], m)
            else:
                terms = _apply_2q_map(terms, qubits[0], qubits[1], m)
            terms, dropped = sim._truncate_terms(terms)
            bound += dropped
        for name, op_qubits, params in reversed(ops):
            if name in ("barrier", "id"):
                continue
            terms = sim._apply_gate_backward(terms, name, list(op_qubits), list(params))
            terms, dropped = sim._truncate_terms(terms)
            bound += dropped
    return terms, bound


def _value_on_zero_state(terms: Terms) -> float:
    return float(sum(c.real for (x_mask, _z), c in terms.items() if x_mask == 0))


def _dense_operator(x_mask: int, z_mask: int, n: int) -> np.ndarray:
    xm = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    zm = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    op = np.array([[1.0]], dtype=np.complex128)
    for q in range(n - 1, -1, -1):  # qubit 0 is the least-significant factor
        factor = np.eye(2, dtype=np.complex128)
        if (x_mask >> q) & 1:
            factor = factor @ xm
        if (z_mask >> q) & 1:
            factor = factor @ zm
        op = np.kron(op, factor)
    return op


def noisy_expectation_values(
    circuit: Any,
    observables: Union[Sequence[str], Mapping[str, Any]],
    noise_model: NoiseModel,
    *,
    method: str = "auto",
    readout: bool = True,
    max_pauli_terms: int = 4096,
    prune_threshold: float = 1e-9,
    error_tolerance: float = 0.01,
    dm_max_qubits: int = 10,
) -> ExpectationResult:
    """
    Pauli expectation values of ``circuit`` under ``noise_model``.

    Args:
        circuit: Qiskit circuit, OpenQASM string or instruction list; terminal
            measurements are ignored.
        observables: Pauli strings or a mapping ``name -> string`` /
            ``name -> [(coefficient, string), ...]`` (as
            :func:`cqhecs.expectation.expectation_values`).
        noise_model: the model; an empty :class:`NoiseModel` gives ideal values.
        method: one of :data:`NOISY_METHODS`. ``auto`` uses the exact density
            matrix up to ``dm_max_qubits`` and Pauli propagation above.
        readout: apply the model's assignment errors to measured factors.
        max_pauli_terms, prune_threshold: Pauli-propagation truncation.
        error_tolerance: largest certified bound accepted; values whose bound
            exceeds it are reported as ``None`` and ``unresolved`` is True.

    Raises:
        ExpectationError: invalid arguments, unsupported operations, or a
            register too wide for ``density_matrix``.
    """
    t0 = time.perf_counter()
    if method not in NOISY_METHODS:
        raise ExpectationError(f"method must be one of {NOISY_METHODS}, got {method!r}")
    if not isinstance(noise_model, NoiseModel):
        raise ExpectationError("noise_model must be a cqhecs NoiseModel (use NoiseModel() for none)")
    if not (isinstance(error_tolerance, (int, float)) and not isinstance(error_tolerance, bool)
            and 0.0 < error_tolerance <= 1.0):
        raise ExpectationError(f"error_tolerance must lie in (0, 1], got {error_tolerance!r}")
    if not (isinstance(max_pauli_terms, int) and not isinstance(max_pauli_terms, bool) and max_pauli_terms > 0):
        raise ExpectationError(f"max_pauli_terms must be a positive int, got {max_pauli_terms!r}")
    if not (isinstance(prune_threshold, (int, float)) and not isinstance(prune_threshold, bool)
            and math.isfinite(prune_threshold) and prune_threshold >= 0.0):
        raise ExpectationError(f"prune_threshold must be a finite number >= 0, got {prune_threshold!r}")

    blocks, num_qubits = _blocks(circuit)
    parsed = _normalize_observables(observables, num_qubits)

    chosen = method
    if method == "auto":
        chosen = "density_matrix" if num_qubits <= dm_max_qubits else "pauli_propagation"
    if chosen == "density_matrix" and num_qubits > dm_max_qubits:
        raise ExpectationError(
            f"density_matrix needs 4^{num_qubits} entries; limit is {dm_max_qubits} qubits"
        )

    unique: Dict[Tuple[Tuple[int, str], ...], PauliString] = {}
    for terms in parsed.values():
        for _c, pauli in terms:
            unique[pauli.ops] = pauli

    values_by_term: Dict[Any, Optional[float]] = {}
    bounds: Dict[Any, float] = {}
    meta: Dict[str, Any] = {
        "execution_mode": ExecutionMode.NOISY_CLASSICAL.value,
        "noise_model": noise_model.name,
        "readout_applied": bool(readout),
        "requested_method": method,
        "hardware_access": False,
        "error_bound_covers": "truncation of this circuit for the |0...0> input; not model-vs-hardware error",
    }

    if chosen == "density_matrix":
        backend = NoisyDensityMatrixBackend(max_qubits=dm_max_qubits)
        try:
            # The source circuit, not the lowered blocks: noise attaches to
            # gates as written (CQ-V251-04).
            rho = backend.density_matrix(circuit, noise_model)
        except ValueError as exc:
            raise ExpectationError(str(exc)) from exc
        for key, pauli in unique.items():
            start = _pauli_terms(pauli)
            if readout:
                start = _apply_readout(start, noise_model)
            total = 0.0
            for (x_mask, z_mask), coeff in start.items():
                total += (coeff * np.trace(rho @ _dense_operator(x_mask, z_mask, num_qubits))).real
            values_by_term[key] = float(total)
            bounds[key] = 0.0
        meta["numerical_mode"] = "float64-density-matrix"
    else:
        sim = SparsePauliDynamicsSimulator(
            num_qubits, max_pauli_terms=max_pauli_terms, prune_threshold=prune_threshold,
            error_tolerance=error_tolerance,
        )
        cache: Dict[int, np.ndarray] = {}
        for key, pauli in unique.items():
            start = _pauli_terms(pauli)
            if readout:
                start = _apply_readout(start, noise_model)
            try:
                final, bound = _propagate(blocks, noise_model, start, sim, cache)
            except UnsupportedPathDOperation as exc:
                raise ExpectationError(
                    f"pauli_propagation cannot evolve this circuit ({exc}); use "
                    "method='density_matrix' up to its width limit"
                ) from exc
            values_by_term[key] = _value_on_zero_state(final)
            bounds[key] = bound
        meta["numerical_mode"] = "float64-heisenberg-noisy-certified"
        meta["max_pauli_terms"] = max_pauli_terms
        meta["prune_threshold"] = prune_threshold

    results: Dict[str, Optional[float]] = {}
    total_bound = 0.0
    unresolved = False
    for name, terms in parsed.items():
        bound = sum(abs(c) * bounds[pauli.ops] for c, pauli in terms)
        total_bound = max(total_bound, bound)
        if bound > error_tolerance:
            results[name] = None
            unresolved = True
        else:
            results[name] = float(sum(c * values_by_term[pauli.ops] for c, pauli in terms))

    return ExpectationResult(
        values=results,
        method=f"noisy_{chosen}",
        exact=chosen == "density_matrix",
        error_bound=float(total_bound),
        unresolved=unresolved,
        num_qubits=num_qubits,
        execution_time_ms=(time.perf_counter() - t0) * 1000.0,
        metadata=meta,
    )

