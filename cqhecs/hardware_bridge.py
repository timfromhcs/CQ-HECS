"""
Hardware-Aware Quantum Bridge for CQ-HECS.

Provides:
- Three irreducibly separate execution modes: IDEAL_CLASSICAL, NOISY_CLASSICAL, REAL_HARDWARE.
- Validated, versioned BackendProfile capturing topology, gate errors, readout errors, and T1/T2.
- Mathematically rigorous NoiseModel and Kraus channels with verified completeness (sum K^dag K = I).
- Deterministic offline FakeHardwareProvider and fail-closed RealHardwareProvider boundary.
"""

from __future__ import annotations

import math
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cqhecs.gate_manifest import get_gate
from cqhecs.result import ExecutionMode, SimulationResult


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HardwareBridgeError(Exception):
    """Base exception for Hardware-Aware Quantum Bridge errors."""


class HardwareAuthorizationRequiredError(HardwareBridgeError):
    """Raised when real hardware execution is attempted without explicit authorization."""


class HardwareAuthenticationError(HardwareBridgeError):
    """Raised when real hardware execution is attempted without valid credentials."""


class InvalidProfileError(HardwareBridgeError):
    """Raised when a BackendProfile fails schema or numerical validation."""


class InvalidNoiseModelError(HardwareBridgeError):
    """Raised when a NoiseModel or Kraus channel violates physical or mathematical invariants."""


class InvalidTopologyError(HardwareBridgeError):
    """Raised when a circuit violates backend coupling topology constraints."""


class OutOfModelError(HardwareBridgeError):
    """
    Raised when a circuit uses a qubit or edge whose calibration the profile
    flags as outside the noise model (non-operational, or relaxation data
    missing or physically inconsistent). Such data is never clipped or
    replaced by a guess.
    """


# ---------------------------------------------------------------------------
# Noise Channels & Kraus Representations
# ---------------------------------------------------------------------------


class NoiseChannel(ABC):
    """
    Abstract base class for completely positive trace-preserving (CPTP) quantum noise channels.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the noise channel."""

    @property
    @abstractmethod
    def kraus_operators(self) -> List[np.ndarray]:
        """List of Kraus operators {K_k} representing the channel."""

    def validate_kraus_completeness(self, tol: float = 1e-10) -> bool:
        """
        Verify the completeness relation: sum_k K_k^dagger K_k = I.
        """
        kraus = self.kraus_operators
        if not kraus:
            raise InvalidNoiseModelError(f"Channel {self.name} has no Kraus operators.")
        dim = kraus[0].shape[0]
        identity = np.eye(dim, dtype=complex)
        sum_k = sum(k.conj().T @ k for k in kraus)
        diff = np.max(np.abs(sum_k - identity))
        if diff > tol:
            raise InvalidNoiseModelError(
                f"Channel {self.name} violates Kraus completeness: ||sum K^dag K - I||_max = {diff:.3e} > {tol:.3e}"
            )
        return True

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize channel parameters."""


class DepolarizingChannel(NoiseChannel):
    """
    Single-qubit depolarizing channel:
        E(rho) = (1 - p) rho + p * (I / 2)
               = (1 - 3p/4) rho + (p/4) [X rho X + Y rho Y + Z rho Z]

    Kraus operators:
        K_0 = sqrt(1 - 3p/4) * I
        K_1 = sqrt(p/4) * X
        K_2 = sqrt(p/4) * Y
        K_3 = sqrt(p/4) * Z
    """

    def __init__(self, p: float):
        if not (0.0 <= p <= 1.0) or math.isnan(p):
            raise InvalidNoiseModelError(f"Depolarizing error parameter must be in [0, 1], got {p}")
        self.p = float(p)
        self._kraus = self._build_kraus()
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return "depolarizing_1q"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def _build_kraus(self) -> List[np.ndarray]:
        p = self.p
        I = np.eye(2, dtype=complex)
        X = np.array([[0, 1], [1, 0]], dtype=complex)
        Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
        Z = np.array([[1, 0], [0, -1]], dtype=complex)
        if p == 0.0:
            return [I]
        return [
            np.sqrt(1.0 - 0.75 * p) * I,
            np.sqrt(0.25 * p) * X,
            np.sqrt(0.25 * p) * Y,
            np.sqrt(0.25 * p) * Z,
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "depolarizing_1q", "p": self.p}


class BitFlipChannel(NoiseChannel):
    """
    Single-qubit bit-flip channel:

        E(rho) = (1 - p) rho + p * X rho X

    Kraus operators:
        K_0 = sqrt(1 - p) * I
        K_1 = sqrt(p) * X

    This models a faulty ``x`` gate, not measurement readout. Readout stays in
    :class:`ReadoutErrorChannel`.
    """

    def __init__(self, p: float):
        if not (0.0 <= p <= 1.0) or math.isnan(p):
            raise InvalidNoiseModelError(f"Bit-flip probability must be in [0, 1], got {p}")
        self.p = float(p)
        self._kraus = self._build_kraus()
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return "bit_flip"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def _build_kraus(self) -> List[np.ndarray]:
        p = self.p
        I = np.eye(2, dtype=complex)
        X = np.array([[0, 1], [1, 0]], dtype=complex)
        if p == 0.0:
            return [I]
        if p == 1.0:
            return [X]
        return [math.sqrt(1.0 - p) * I, math.sqrt(p) * X]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "bit_flip", "p": self.p}


class AmplitudeDampingChannel(NoiseChannel):
    """
    Single-qubit amplitude damping (energy relaxation |1> -> |0>):
        K_0 = [[1, 0], [0, sqrt(1 - gamma)]]
        K_1 = [[0, sqrt(gamma)], [0, 0]]
    """

    def __init__(self, gamma: float):
        if not (0.0 <= gamma <= 1.0) or math.isnan(gamma):
            raise InvalidNoiseModelError(f"Amplitude damping parameter gamma must be in [0, 1], got {gamma}")
        self.gamma = float(gamma)
        self._kraus = self._build_kraus()
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return "amplitude_damping"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def _build_kraus(self) -> List[np.ndarray]:
        g = self.gamma
        if g == 0.0:
            return [np.eye(2, dtype=complex)]
        return [
            np.array([[1.0, 0.0], [0.0, np.sqrt(1.0 - g)]], dtype=complex),
            np.array([[0.0, np.sqrt(g)], [0.0, 0.0]], dtype=complex),
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "amplitude_damping", "gamma": self.gamma}


class PhaseDampingChannel(NoiseChannel):
    """
    Single-qubit phase damping (pure dephasing):
        K_0 = [[1, 0], [0, sqrt(1 - lambda)]]
        K_1 = [[0, 0], [0, sqrt(lambda)]]
    """

    def __init__(self, lambd: float):
        if not (0.0 <= lambd <= 1.0) or math.isnan(lambd):
            raise InvalidNoiseModelError(f"Phase damping parameter lambda must be in [0, 1], got {lambd}")
        self.lambd = float(lambd)
        self._kraus = self._build_kraus()
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return "phase_damping"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def _build_kraus(self) -> List[np.ndarray]:
        l = self.lambd
        if l == 0.0:
            return [np.eye(2, dtype=complex)]
        return [
            np.array([[1.0, 0.0], [0.0, np.sqrt(1.0 - l)]], dtype=complex),
            np.array([[0.0, 0.0], [0.0, np.sqrt(l)]], dtype=complex),
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "phase_damping", "lambd": self.lambd}


class TwoQubitDepolarizingChannel(NoiseChannel):
    """
    Two-qubit depolarizing channel:
        E(rho) = (1 - p) rho + p * (I_4 / 4)
               = (1 - 15p/16) rho + (p/16) sum_{P in P_2 \\ {I}} P rho P
    """

    def __init__(self, p: float):
        if not (0.0 <= p <= 1.0) or math.isnan(p):
            raise InvalidNoiseModelError(f"2-qubit depolarizing parameter p must be in [0, 1], got {p}")
        self.p = float(p)
        self._kraus = self._build_kraus()
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return "depolarizing_2q"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def _build_kraus(self) -> List[np.ndarray]:
        p = self.p
        I = np.eye(2, dtype=complex)
        X = np.array([[0, 1], [1, 0]], dtype=complex)
        Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
        Z = np.array([[1, 0], [0, -1]], dtype=complex)
        paulis_1q = [I, X, Y, Z]

        if p == 0.0:
            return [np.eye(4, dtype=complex)]

        kraus = [np.sqrt(1.0 - (15.0 / 16.0) * p) * np.eye(4, dtype=complex)]
        coeff = np.sqrt(p / 16.0)
        for p0 in paulis_1q:
            for p1 in paulis_1q:
                if p0 is I and p1 is I:
                    continue
                kraus.append(coeff * np.kron(p0, p1))
        return kraus

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "depolarizing_2q", "p": self.p}


def average_gate_infidelity(kraus: List[np.ndarray]) -> float:
    """
    ``1 - F_avg`` of the channel with Kraus operators ``kraus`` (compared with
    the identity), using ``F_avg = (sum_k |Tr K_k|^2 + d) / (d (d + 1))``
    (Horodecki et al., Phys. Rev. A 60, 1888 (1999); Nielsen 2002).
    """
    d = kraus[0].shape[0]
    total = sum(abs(np.trace(k)) ** 2 for k in kraus)
    return 1.0 - float((total + d) / (d * (d + 1)))


def _prune(kraus: List[np.ndarray]) -> List[np.ndarray]:
    """Drops exactly-zero Kraus operators (they contribute nothing)."""
    kept = [k for k in kraus if np.any(k != 0)]
    return kept or [np.zeros_like(kraus[0])]


class ThermalRelaxationChannel(NoiseChannel):
    """
    Single-qubit T1/T2 relaxation for a duration ``t`` at zero temperature.

    Amplitude damping with ``gamma = 1 - exp(-t/T1)`` followed by phase
    damping with ``lambda = 1 - exp(-2t/T2) / (1 - gamma)``, so that the
    excited population decays as ``exp(-t/T1)`` and the coherence as
    ``exp(-t/T2)``. This is the channel of Qiskit Aer's
    ``thermal_relaxation_error(T1, T2, t)`` with zero excited-state
    population. It exists only for ``T2 <= 2 T1``; anything else is refused.

    Units: ``t1_us`` and ``t2_us`` in microseconds, ``time_ns`` in nanoseconds.
    """

    def __init__(self, t1_us: float, t2_us: float, time_ns: float):
        for label, value in (("T1", t1_us), ("T2", t2_us)):
            if not _is_real(value) or not math.isfinite(value) or value <= 0.0:
                raise InvalidNoiseModelError(f"{label} must be a finite positive number of us, got {value!r}")
        if not _is_real(time_ns) or not math.isfinite(time_ns) or time_ns < 0.0:
            raise InvalidNoiseModelError(f"duration must be a finite number of ns >= 0, got {time_ns!r}")
        if t2_us > 2.0 * t1_us * (1.0 + 1e-12):
            raise InvalidNoiseModelError(
                f"T2 = {t2_us} us exceeds 2*T1 = {2.0 * t1_us} us; no relaxation channel exists"
            )
        self.t1_us = float(t1_us)
        self.t2_us = float(t2_us)
        self.time_ns = float(time_ns)
        self._kraus = self._build_kraus()
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return "thermal_relaxation"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def _build_kraus(self) -> List[np.ndarray]:
        t = self.time_ns * 1e-3
        if t == 0.0:
            return [np.eye(2, dtype=complex)]
        gamma = 1.0 - math.exp(-t / self.t1_us)
        coherence = math.exp(-t / self.t2_us)
        # T2 = 2 T1 makes lambda zero up to rounding; never let it go negative.
        lambd = min(1.0, max(0.0, 1.0 - coherence ** 2 / (1.0 - gamma)))
        damping = [
            np.array([[1.0, 0.0], [0.0, math.sqrt(1.0 - gamma)]], dtype=complex),
            np.array([[0.0, math.sqrt(gamma)], [0.0, 0.0]], dtype=complex),
        ]
        dephasing = [
            np.array([[1.0, 0.0], [0.0, math.sqrt(1.0 - lambd)]], dtype=complex),
            np.array([[0.0, 0.0], [0.0, math.sqrt(lambd)]], dtype=complex),
        ]
        return _prune([pd @ ad for ad in damping for pd in dephasing])

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "thermal_relaxation", "t1_us": self.t1_us, "t2_us": self.t2_us, "time_ns": self.time_ns}


class TensorChannel(NoiseChannel):
    """
    Two-qubit product ``first (x) second``: ``first`` acts on the gate's first
    operand, ``second`` on its second (the operand order of
    ``NoisyDensityMatrixBackend``'s two-qubit Kraus application).
    """

    def __init__(self, first: NoiseChannel, second: NoiseChannel):
        for ch in (first, second):
            if ch.kraus_operators[0].shape != (2, 2):
                raise InvalidNoiseModelError("TensorChannel combines two single-qubit channels")
        self.first = first
        self.second = second
        self._kraus = _prune([np.kron(a, b) for a in first.kraus_operators for b in second.kraus_operators])
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return f"tensor({self.first.name},{self.second.name})"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "tensor", "first": self.first.to_dict(), "second": self.second.to_dict()}


class ComposedChannel(NoiseChannel):
    """Applies ``first`` and then ``second`` (``E = second o first``)."""

    def __init__(self, first: NoiseChannel, second: NoiseChannel):
        if first.kraus_operators[0].shape != second.kraus_operators[0].shape:
            raise InvalidNoiseModelError("ComposedChannel needs channels of the same dimension")
        self.first = first
        self.second = second
        self._kraus = _prune([b @ a for a in first.kraus_operators for b in second.kraus_operators])
        self.validate_kraus_completeness()

    @property
    def name(self) -> str:
        return f"compose({self.first.name},{self.second.name})"

    @property
    def kraus_operators(self) -> List[np.ndarray]:
        return self._kraus

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "compose", "first": self.first.to_dict(), "second": self.second.to_dict()}


class ReadoutErrorChannel:
    """
    Classical assignment error for single-qubit measurement:
        M = [[1 - p01,  p10    ],
             [p01,      1 - p10]]
    where M_ij = P(measured i | true j). Column sums equal 1.0.
    """

    def __init__(self, p01: float, p10: float):
        if not (0.0 <= p01 <= 1.0) or math.isnan(p01):
            raise InvalidNoiseModelError(f"p01 (P(1|0)) must be in [0, 1], got {p01}")
        if not (0.0 <= p10 <= 1.0) or math.isnan(p10):
            raise InvalidNoiseModelError(f"p10 (P(0|1)) must be in [0, 1], got {p10}")
        self.p01 = float(p01)
        self.p10 = float(p10)
        self.matrix = np.array([
            [1.0 - self.p01, self.p10],
            [self.p01, 1.0 - self.p10],
        ], dtype=float)
        # Verify column stochasticity
        col_sums = np.sum(self.matrix, axis=0)
        if not np.allclose(col_sums, [1.0, 1.0], atol=1e-12):
            raise InvalidNoiseModelError("Readout assignment matrix must be column-stochastic.")

    def to_dict(self) -> Dict[str, Any]:
        return {"p01": self.p01, "p10": self.p10}


# ---------------------------------------------------------------------------
# Noise Model Container
# ---------------------------------------------------------------------------


class NoiseModel:
    """
    Versioned noise model defining error channels for quantum circuits.
    """

    def __init__(self, name: str = "custom_noise_model", schema_version: str = "1.0"):
        self.name = name
        self.schema_version = schema_version
        self.channels_1q: Dict[str, Dict[int, List[NoiseChannel]]] = {}
        self.channels_2q: Dict[str, Dict[Tuple[int, int], List[NoiseChannel]]] = {}
        self.readout_errors: Dict[int, ReadoutErrorChannel] = {}
        #: How the model was derived (conversion conventions, special cases).
        self.metadata: Dict[str, Any] = {}

    def add_1q_channel(self, gate: str, qubit: int, channel: NoiseChannel) -> None:
        gate_l = gate.lower()
        if gate_l not in self.channels_1q:
            self.channels_1q[gate_l] = {}
        if qubit not in self.channels_1q[gate_l]:
            self.channels_1q[gate_l][qubit] = []
        self.channels_1q[gate_l][qubit].append(channel)

    def add_2q_channel(self, gate: str, qubits: Tuple[int, int], channel: NoiseChannel) -> None:
        gate_l = gate.lower()
        if gate_l not in self.channels_2q:
            self.channels_2q[gate_l] = {}
        pair = (int(qubits[0]), int(qubits[1]))
        if pair not in self.channels_2q[gate_l]:
            self.channels_2q[gate_l][pair] = []
        self.channels_2q[gate_l][pair].append(channel)

    def set_readout_error(self, qubit: int, p01: float, p10: float) -> None:
        self.readout_errors[int(qubit)] = ReadoutErrorChannel(p01=p01, p10=p10)

    def validate(self) -> bool:
        for gate, q_dict in self.channels_1q.items():
            for q, ch_list in q_dict.items():
                for ch in ch_list:
                    ch.validate_kraus_completeness()
        for gate, p_dict in self.channels_2q.items():
            for pair, ch_list in p_dict.items():
                for ch in ch_list:
                    ch.validate_kraus_completeness()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema_version": self.schema_version,
            "metadata": dict(self.metadata),
            "readout_errors": {
                str(q): ch.to_dict() for q, ch in self.readout_errors.items()
            },
            "channels_1q": {
                gate: {
                    str(q): [ch.to_dict() for ch in ch_list]
                    for q, ch_list in q_map.items()
                }
                for gate, q_map in self.channels_1q.items()
            },
            "channels_2q": {
                gate: {
                    f"{p[0]}_{p[1]}": [ch.to_dict() for ch in ch_list]
                    for p, ch_list in p_map.items()
                }
                for gate, p_map in self.channels_2q.items()
            },
        }


def _is_real(value: Any) -> bool:
    """True for a non-NaN int/float that is not a bool."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        return False
    return not math.isnan(float(value))


def depolarizing_parameter_from_infidelity(infidelity: float, num_qubits: int) -> float:
    """
    Converts an average gate infidelity into a depolarizing parameter.

    For ``E(rho) = (1 - p) rho + p I/d`` on ``d = 2**num_qubits`` levels the
    average gate fidelity is ``F_avg = 1 - p (d - 1)/d`` (Nielsen, Phys. Lett.
    A 303, 249 (2002)), so ``p = d r / (d - 1)``. This is the same conversion
    Qiskit Aer applies to a backend's reported gate error when relaxation is
    ignored.

    Raises:
        InvalidNoiseModelError: For ``num_qubits`` other than 1 or 2, or an
            infidelity outside ``[0, (d - 1)/d]`` (``p`` would exceed 1, which
            the channel classes do not represent).
    """
    if num_qubits not in (1, 2):
        raise InvalidNoiseModelError(
            f"Only 1- and 2-qubit gate errors can be converted, got {num_qubits} qubits"
        )
    if not _is_real(infidelity) or infidelity < 0.0:
        raise InvalidNoiseModelError(f"Gate infidelity must be a number >= 0, got {infidelity!r}")
    d = 1 << num_qubits
    limit = (d - 1) / d
    if infidelity > limit:
        raise InvalidNoiseModelError(
            f"Gate infidelity {infidelity} exceeds {limit}, the largest value a "
            f"{num_qubits}-qubit depolarizing channel reaches (fully depolarizing)"
        )
    return min(1.0, d * float(infidelity) / (d - 1))


def depolarizing_parameter_with_relaxation(
    infidelity: float, num_qubits: int, relaxation_fidelity: float
) -> Tuple[float, bool]:
    """
    Depolarizing parameter that, followed by a relaxation channel with average
    gate fidelity ``F_r``, gives the reported infidelity ``r`` in total.

    For ``E = R o D_p``, ``F(E) = F_r - p (d F_r - 1)/d``, hence
    ``p = d (F_r - F) / (d F_r - 1)`` with ``F = 1 - r``. This is Qiskit Aer's
    device-model convention. When relaxation alone already reaches the
    reported error (``r <= 1 - F_r``) no depolarizing part is added and the
    second return value is True, so the caller can record it; the total
    infidelity of the model is then ``1 - F_r``, not ``r``.

    Raises:
        InvalidNoiseModelError: For an invalid ``num_qubits``, infidelity or
            fidelity, or when ``p`` would exceed 1.
    """
    if num_qubits not in (1, 2):
        raise InvalidNoiseModelError(
            f"Only 1- and 2-qubit gate errors can be converted, got {num_qubits} qubits"
        )
    if not _is_real(infidelity) or infidelity < 0.0:
        raise InvalidNoiseModelError(f"Gate infidelity must be a number >= 0, got {infidelity!r}")
    if not _is_real(relaxation_fidelity) or not (0.0 < relaxation_fidelity <= 1.0):
        raise InvalidNoiseModelError(f"relaxation fidelity must lie in (0, 1], got {relaxation_fidelity!r}")
    if relaxation_fidelity == 1.0:
        return depolarizing_parameter_from_infidelity(infidelity, num_qubits), False
    if infidelity <= 1.0 - relaxation_fidelity:
        return 0.0, True
    d = 1 << num_qubits
    p = d * (relaxation_fidelity - (1.0 - infidelity)) / (d * relaxation_fidelity - 1.0)
    if p > 1.0:
        raise InvalidNoiseModelError(
            f"Gate infidelity {infidelity} needs a depolarizing parameter {p} > 1 "
            "on top of the relaxation channel"
        )
    return p, False


# ---------------------------------------------------------------------------
# Backend Profile Schema
# ---------------------------------------------------------------------------


@dataclass
class BackendProfile:
    """
    Truthful, validated hardware calibration profile and topology schema.
    """

    name: str
    num_qubits: int
    schema_version: str = "1.0"
    provider_name: str = "CQ-HECS"
    capture_timestamp: Optional[str] = None
    provenance_uri: Optional[str] = None
    is_synthetic: bool = True
    basis_gates: List[str] = field(default_factory=lambda: ["cx", "id", "rz", "sx", "x", "measure"])
    coupling_map: List[Tuple[int, int]] = field(default_factory=list)
    gate_errors: Dict[str, Dict[Tuple[int, ...], float]] = field(default_factory=dict)
    gate_durations_ns: Dict[str, Dict[Tuple[int, ...], float]] = field(default_factory=dict)
    readout_errors: Dict[int, Tuple[float, float]] = field(default_factory=dict)
    t1_us: Dict[int, float] = field(default_factory=dict)
    t2_us: Dict[int, float] = field(default_factory=dict)
    dynamic_circuit_features: Dict[str, bool] = field(default_factory=dict)
    #: Schema 2.0. Calibration data the noise model cannot use, kept instead of
    #: being clipped or dropped. Keys (all optional):
    #: ``non_operational`` - list of ``{"gate", "qubits", "gate_error"}``;
    #: ``relaxation_excluded`` - ``{qubit: reason}`` for missing or
    #: inconsistent T1/T2; ``not_modelled`` - list of ``{"gate", "qubits"}``
    #: for reported operations without a noise channel (e.g. ``reset``).
    calibration_flags: Dict[str, Any] = field(default_factory=dict)
    #: Schema 2.0. SHA-256 of the source file the calibration was read from.
    source_sha256: Optional[str] = None

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        """Validate all numeric ranges, qubit indices, and topology consistency."""
        if (
            not isinstance(self.num_qubits, int)
            or isinstance(self.num_qubits, bool)
            or self.num_qubits < 1
        ):
            raise InvalidProfileError(f"num_qubits must be a positive integer >= 1, got {self.num_qubits}")
        if self.schema_version not in ("1.0", "2.0"):
            raise InvalidProfileError(
                f"Unsupported schema_version: {self.schema_version!r} (expected '1.0' or '2.0')"
            )
        if self.schema_version == "1.0" and (self.calibration_flags or self.source_sha256):
            raise InvalidProfileError("calibration_flags and source_sha256 need schema_version '2.0'")
        self._validate_flags()
        if not self.basis_gates:
            raise InvalidProfileError("basis_gates must not be empty.")
        if not self.is_synthetic and (not self.capture_timestamp or not self.provenance_uri):
            # A profile that claims to be real calibration data must say where
            # and when it was captured; otherwise it is indistinguishable from
            # invented numbers.
            raise InvalidProfileError(
                "A non-synthetic profile requires capture_timestamp and "
                "provenance_uri; mark example or derived values is_synthetic=True."
            )

        # Topology validation
        for edge in self.coupling_map:
            if not isinstance(edge, (tuple, list)) or len(edge) != 2:
                raise InvalidProfileError(f"Coupling map edge must be a (u, v) pair, got {edge}")
            u = self._qubit(edge[0], "coupling map")
            v = self._qubit(edge[1], "coupling map")
            if u == v:
                raise InvalidProfileError(f"Self-loops not allowed in coupling map: ({u}, {v})")

        # Gate errors validation. A key's width must match the gate's arity
        # (for gates the manifest knows), and only 1- and 2-qubit errors can be
        # turned into a noise channel; anything else would be dropped silently.
        for gate, q_dict in self.gate_errors.items():
            for qubits, err in q_dict.items():
                self._gate_key(gate, qubits, "gate error")
                self._probability(err, f"Gate error for {gate} on {qubits}")

        for gate, q_dict in self.gate_durations_ns.items():
            for qubits, dur in q_dict.items():
                self._gate_key(gate, qubits, "gate duration")
                if not _is_real(dur) or not math.isfinite(dur) or dur < 0.0:
                    raise InvalidProfileError(
                        f"Gate duration for {gate} on {qubits} must be a finite "
                        f"non-negative number of ns, got {dur!r}"
                    )

        # Readout errors validation
        for q, errs in self.readout_errors.items():
            self._qubit(q, "readout errors")
            if not isinstance(errs, (tuple, list)) or len(errs) != 2:
                raise InvalidProfileError(f"Readout errors on qubit {q} must be a (p01, p10) pair, got {errs!r}")
            for value in errs:
                self._probability(value, f"Readout errors on qubit {q}")

        # T1 / T2 validation
        for label, table in (("T1", self.t1_us), ("T2", self.t2_us)):
            for q, t in table.items():
                self._qubit(q, f"{label} table")
                if not _is_real(t) or not math.isfinite(t) or t <= 0.0:
                    raise InvalidProfileError(f"{label} on qubit {q} must be a finite positive number, got {t!r}")
        # Physical consistency: 1/T2 = 1/(2 T1) + 1/T_phi with T_phi > 0, so
        # T2 <= 2 T1 for every qubit that reports both.
        for q, t2 in self.t2_us.items():
            t1 = self.t1_us.get(q)
            if t1 is not None and t2 > 2.0 * t1 * (1.0 + 1e-12):
                raise InvalidProfileError(
                    f"T2 = {t2} us on qubit {q} exceeds 2*T1 = {2.0 * t1} us, "
                    "which no physical qubit can satisfy"
                )

    def _validate_flags(self) -> None:
        flags = self.calibration_flags
        if not isinstance(flags, dict):
            raise InvalidProfileError("calibration_flags must be a dict")
        unknown = set(flags) - {"non_operational", "relaxation_excluded", "not_modelled"}
        if unknown:
            raise InvalidProfileError(f"Unknown calibration_flags keys: {sorted(unknown)}")
        for entry in flags.get("non_operational", []) + flags.get("not_modelled", []):
            if not isinstance(entry, dict) or "gate" not in entry or "qubits" not in entry:
                raise InvalidProfileError(f"Flag entries need 'gate' and 'qubits', got {entry!r}")
            for q in entry["qubits"]:
                self._qubit(q, f"calibration flag for {entry['gate']!r}")
        for q in flags.get("relaxation_excluded", {}):
            self._qubit(q, "relaxation_excluded flag")
        if self.source_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", str(self.source_sha256)):
            raise InvalidProfileError(f"source_sha256 must be 64 lowercase hex digits, got {self.source_sha256!r}")

    def out_of_model_reason(self, qubits: List[int], relaxation: bool) -> Optional[str]:
        """
        Why an operation on ``qubits`` would use calibration the model does not
        cover, or None. Circuits are not transpiled to the device's basis
        gates, so any flagged gate on a qubit (or, for two qubits, on that
        pair in either direction) excludes the qubit or pair.
        """
        touched = set(qubits)
        for entry in self.calibration_flags.get("non_operational", []):
            flagged = list(entry["qubits"])
            if (len(flagged) == 1 and flagged[0] in touched) or (
                len(flagged) == 2 and len(qubits) == 2 and set(flagged) == touched
            ):
                return (
                    f"{entry['gate']} on qubits {flagged} is reported non-operational "
                    f"(gate_error={entry.get('gate_error')})"
                )
        if relaxation:
            for q, reason in self.calibration_flags.get("relaxation_excluded", {}).items():
                if int(q) in touched:
                    return f"qubit {int(q)} has no usable T1/T2: {reason}"
        return None

    def _qubit(self, value: Any, where: str) -> int:
        """Returns ``value`` as an in-range qubit index or raises."""
        if not isinstance(value, (int, np.integer)) or isinstance(value, (bool, np.bool_)):
            raise InvalidProfileError(f"Qubit index in {where} must be an int, got {value!r}")
        q = int(value)
        if q < 0 or q >= self.num_qubits:
            raise InvalidProfileError(f"Qubit {q} in {where} out of range [0, {self.num_qubits - 1}]")
        return q

    def _gate_key(self, gate: str, qubits: Any, where: str) -> None:
        if not isinstance(qubits, tuple) or len(qubits) not in (1, 2):
            raise InvalidProfileError(
                f"{where} key for {gate!r} must be a tuple of 1 or 2 qubits, got {qubits!r}"
            )
        indices = [self._qubit(q, f"{where} for {gate!r}") for q in qubits]
        if len(set(indices)) != len(indices):
            raise InvalidProfileError(f"{where} for {gate!r} repeats a qubit: {qubits}")
        spec = get_gate(gate)
        if spec is not None and not spec.barrier and spec.arity and len(qubits) != spec.arity:
            raise InvalidProfileError(
                f"{where} for {gate!r} is keyed by {len(qubits)} qubit(s), "
                f"but {gate!r} acts on {spec.arity}"
            )

    @staticmethod
    def _probability(value: Any, what: str) -> None:
        if not _is_real(value) or not (0.0 <= value <= 1.0):
            raise InvalidProfileError(f"{what} must be in [0, 1], got {value!r}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to JSON-compatible dictionary."""
        return {
            "name": self.name,
            "provider_name": self.provider_name,
            "num_qubits": self.num_qubits,
            "schema_version": self.schema_version,
            "capture_timestamp": self.capture_timestamp,
            "provenance_uri": self.provenance_uri,
            "is_synthetic": self.is_synthetic,
            "basis_gates": list(self.basis_gates),
            "coupling_map": [list(edge) for edge in self.coupling_map],
            "gate_errors": {
                gate: {f"{'_'.join(str(q) for q in qargs)}": err for qargs, err in qmap.items()}
                for gate, qmap in self.gate_errors.items()
            },
            "gate_durations_ns": {
                gate: {f"{'_'.join(str(q) for q in qargs)}": dur for qargs, dur in qmap.items()}
                for gate, qmap in self.gate_durations_ns.items()
            },
            "readout_errors": {str(q): list(errs) for q, errs in self.readout_errors.items()},
            "t1_us": {str(q): val for q, val in self.t1_us.items()},
            "t2_us": {str(q): val for q, val in self.t2_us.items()},
            "dynamic_circuit_features": dict(self.dynamic_circuit_features),
            "calibration_flags": {
                "non_operational": [dict(e) for e in self.calibration_flags.get("non_operational", [])],
                "relaxation_excluded": {
                    str(q): r for q, r in self.calibration_flags.get("relaxation_excluded", {}).items()
                },
                "not_modelled": [dict(e) for e in self.calibration_flags.get("not_modelled", [])],
            } if self.calibration_flags else {},
            "source_sha256": self.source_sha256,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BackendProfile:
        """Construct BackendProfile from serialized dictionary."""
        gate_errors: Dict[str, Dict[Tuple[int, ...], float]] = {}
        for gate, qmap in data.get("gate_errors", {}).items():
            gate_errors[gate] = {
                tuple(int(x) for x in k.split("_")): float(v) for k, v in qmap.items()
            }
        gate_durations_ns: Dict[str, Dict[Tuple[int, ...], float]] = {}
        for gate, qmap in data.get("gate_durations_ns", {}).items():
            gate_durations_ns[gate] = {
                tuple(int(x) for x in k.split("_")): float(v) for k, v in qmap.items()
            }
        readout_errors = {
            int(k): (float(v[0]), float(v[1]))
            for k, v in data.get("readout_errors", {}).items()
        }
        t1_us = {int(k): float(v) for k, v in data.get("t1_us", {}).items()}
        t2_us = {int(k): float(v) for k, v in data.get("t2_us", {}).items()}

        coupling_map = [
            (int(e[0]), int(e[1])) for e in data.get("coupling_map", [])
        ]
        return cls(
            name=data["name"],
            num_qubits=int(data["num_qubits"]),
            schema_version=data.get("schema_version", "1.0"),
            provider_name=data.get("provider_name", "CQ-HECS"),
            capture_timestamp=data.get("capture_timestamp"),
            provenance_uri=data.get("provenance_uri"),
            is_synthetic=data.get("is_synthetic", True),
            basis_gates=data.get("basis_gates", ["cx", "id", "rz", "sx", "x", "measure"]),
            coupling_map=coupling_map,
            gate_errors=gate_errors,
            gate_durations_ns=gate_durations_ns,
            readout_errors=readout_errors,
            t1_us=t1_us,
            t2_us=t2_us,
            dynamic_circuit_features=data.get("dynamic_circuit_features", {}),
            calibration_flags=_flags_from_dict(data.get("calibration_flags") or {}),
            source_sha256=data.get("source_sha256"),
        )

    def migrated_to_v2(self) -> "BackendProfile":
        """
        Return a schema-2.0 copy of a 1.0 profile (V3 W6).

        Schema 2.0 only adds ``calibration_flags`` and ``source_sha256``; a
        1.0 profile has neither, so the physics fields are copied unchanged
        and the new fields stay empty. Nothing is inferred: a 1.0 profile
        never gains flags or a digest it did not record. A 2.0 profile is
        returned as an equal copy; there is no downgrade.
        """
        data = self.to_dict()
        data["schema_version"] = "2.0"
        return BackendProfile.from_dict(data)

    def to_noise_model(self, relaxation: bool = False) -> NoiseModel:
        """
        Derive a NoiseModel from the profile's gate and readout errors.

        ``gate_errors`` holds the average gate infidelity ``r = 1 - F_avg``,
        the quantity Qiskit's ``InstructionProperties.error`` (used by
        :meth:`to_target`) and IBM calibration exports report. It is not the
        depolarizing parameter.

        Without ``relaxation`` each error becomes the depolarizing channel
        with that infidelity, ``p = d r / (d - 1)`` (``d = 2**k`` for a
        k-qubit gate; see :func:`depolarizing_parameter_from_infidelity`).

        With ``relaxation`` every gate with a known duration first gets a
        depolarizing part and then T1/T2 relaxation of each of its qubits for
        that duration, with ``p`` chosen so that the composition has the
        reported infidelity (:func:`depolarizing_parameter_with_relaxation`;
        Qiskit Aer's device-model convention). Gates whose relaxation alone
        exceeds the reported error get no depolarizing part; they are listed
        in ``metadata["relaxation_exceeds_gate_error"]``. Qubits flagged in
        ``calibration_flags["relaxation_excluded"]`` get no channel here; the
        fake backend refuses circuits on them.

        Raises:
            InvalidNoiseModelError: If an infidelity cannot be represented, or
                ``relaxation`` is requested for a gate on a qubit without
                T1/T2 that is not flagged.
        """
        model = NoiseModel(name=f"{self.name}_noise_model")
        model.metadata = {
            "gate_error_convention": "average gate infidelity",
            "relaxation": bool(relaxation),
            "relaxation_exceeds_gate_error": [],
        }
        excluded = {int(q) for q in self.calibration_flags.get("relaxation_excluded", {})}
        for q, (p01, p10) in self.readout_errors.items():
            model.set_readout_error(q, p01, p10)
        for gate, qmap in self.gate_errors.items():
            for qubits, err in qmap.items():
                k = len(qubits)
                duration = self.gate_durations_ns.get(gate, {}).get(qubits)
                relax = None
                if relaxation and duration and not excluded.intersection(qubits):
                    missing = [q for q in qubits if q not in self.t1_us or q not in self.t2_us]
                    if missing:
                        raise InvalidNoiseModelError(
                            f"relaxation requested for {gate} on {qubits}, but qubit(s) "
                            f"{missing} have no T1/T2 and are not flagged"
                        )
                    per_qubit = [ThermalRelaxationChannel(self.t1_us[q], self.t2_us[q], duration) for q in qubits]
                    relax = per_qubit[0] if k == 1 else TensorChannel(per_qubit[0], per_qubit[1])
                if relax is None:
                    p = depolarizing_parameter_from_infidelity(err, k)
                else:
                    fidelity = 1.0 - average_gate_infidelity(relax.kraus_operators)
                    p, zeroed = depolarizing_parameter_with_relaxation(err, k, fidelity)
                    if zeroed:
                        model.metadata["relaxation_exceeds_gate_error"].append([gate, list(qubits)])
                depol: NoiseChannel = DepolarizingChannel(p) if k == 1 else TwoQubitDepolarizingChannel(p)
                channel = depol if relax is None else ComposedChannel(depol, relax)
                if k == 1:
                    model.add_1q_channel(gate, qubits[0], channel)
                else:
                    model.add_2q_channel(gate, (qubits[0], qubits[1]), channel)
        model.validate()
        return model

    def to_target(self) -> Any:
        """Build a Qiskit Target populated with calibration properties if Qiskit is present."""
        try:
            from qiskit.transpiler import Target, InstructionProperties
            from qiskit.circuit.library import (
                CXGate, RZGate, SXGate, XGate, IGate, Measure, Reset
            )
        except ImportError:
            return None

        target = Target(num_qubits=self.num_qubits)
        gate_map = {
            "cx": CXGate(),
            "rz": RZGate(0.0),
            "sx": SXGate(),
            "x": XGate(),
            "id": IGate(),
            "measure": Measure(),
            "reset": Reset(),
        }

        for gate_name in self.basis_gates:
            inst = gate_map.get(gate_name.lower())
            if inst is None:
                continue
            num_q = inst.num_qubits
            props = {}
            if num_q == 1:
                for q in range(self.num_qubits):
                    err = self.gate_errors.get(gate_name, {}).get((q,), None)
                    dur = self.gate_durations_ns.get(gate_name, {}).get((q,), None)
                    dur_s = dur * 1e-9 if dur is not None else None
                    props[(q,)] = InstructionProperties(error=err, duration=dur_s)
                target.add_instruction(inst, props)
            elif num_q == 2:
                for edge in self.coupling_map:
                    err = self.gate_errors.get(gate_name, {}).get(edge, None)
                    dur = self.gate_durations_ns.get(gate_name, {}).get(edge, None)
                    dur_s = dur * 1e-9 if dur is not None else None
                    props[edge] = InstructionProperties(error=err, duration=dur_s)
                target.add_instruction(inst, props)
        return target


def _flags_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inverse of the ``calibration_flags`` part of ``BackendProfile.to_dict``."""
    flags: Dict[str, Any] = {}
    if data.get("non_operational"):
        flags["non_operational"] = [dict(e) for e in data["non_operational"]]
    if data.get("relaxation_excluded"):
        flags["relaxation_excluded"] = {int(q): r for q, r in data["relaxation_excluded"].items()}
    if data.get("not_modelled"):
        flags["not_modelled"] = [dict(e) for e in data["not_modelled"]]
    return flags


# ---------------------------------------------------------------------------
# Standard Built-in Profiles
# ---------------------------------------------------------------------------


def create_fake_manila_profile() -> BackendProfile:
    """
    Synthetic 5-qubit profile on the IBM Manila coupling topology (0-1-2-3-4).

    Only the topology mirrors the Manila device. The error rates, readout
    errors and T1/T2 values are illustrative synthetic numbers; they are not a
    provider calibration export and do not match the ``FakeManila`` snapshot
    shipped by qiskit-ibm-runtime. The profile is therefore marked synthetic
    and carries no capture timestamp or provenance URI.
    """
    coupling = [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2), (3, 4), (4, 3)]
    gate_errors = {
        "cx": {
            (0, 1): 0.0071, (1, 0): 0.0071,
            (1, 2): 0.0068, (2, 1): 0.0068,
            (2, 3): 0.0084, (3, 2): 0.0084,
            (3, 4): 0.0079, (4, 3): 0.0079,
        },
        "sx": {(q,): 0.00025 for q in range(5)},
        "x": {(q,): 0.00025 for q in range(5)},
    }
    durations = {
        "cx": {edge: 320.0 for edge in coupling},
        "sx": {(q,): 35.5 for q in range(5)},
        "x": {(q,): 35.5 for q in range(5)},
    }
    readouts = {
        0: (0.015, 0.025),
        1: (0.020, 0.030),
        2: (0.018, 0.022),
        3: (0.022, 0.028),
        4: (0.019, 0.026),
    }
    t1 = {0: 165.2, 1: 152.0, 2: 174.5, 3: 148.1, 4: 160.0}
    t2 = {0: 55.4, 1: 62.1, 2: 70.3, 3: 49.8, 4: 58.2}
    return BackendProfile(
        name="fake_manila",
        num_qubits=5,
        provider_name="CQ-HECS-Synthetic",
        capture_timestamp=None,
        provenance_uri=None,
        is_synthetic=True,
        basis_gates=["cx", "id", "rz", "sx", "x", "measure"],
        coupling_map=coupling,
        gate_errors=gate_errors,
        gate_durations_ns=durations,
        readout_errors=readouts,
        t1_us=t1,
        t2_us=t2,
        dynamic_circuit_features={"mid_circuit_measurement": False, "reset": False},
    )


def create_linear_profile(
    num_qubits: int = 5,
    gate_error: float = 0.001,
    readout_error: float = 0.01,
    name: str = "generic_linear",
) -> BackendProfile:
    """Parametric linear chain profile with uniform synthetic calibration."""
    coupling = []
    cx_errs = {}
    cx_durs = {}
    for q in range(num_qubits - 1):
        coupling.extend([(q, q + 1), (q + 1, q)])
        cx_errs[(q, q + 1)] = gate_error
        cx_errs[(q + 1, q)] = gate_error
        cx_durs[(q, q + 1)] = 300.0
        cx_durs[(q + 1, q)] = 300.0

    return BackendProfile(
        name=name,
        num_qubits=num_qubits,
        provider_name="CQ-HECS-Synthetic",
        capture_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        is_synthetic=True,
        basis_gates=["cx", "id", "rz", "sx", "x", "measure"],
        coupling_map=coupling,
        gate_errors={
            "cx": cx_errs,
            "sx": {(q,): gate_error * 0.1 for q in range(num_qubits)},
            "x": {(q,): gate_error * 0.1 for q in range(num_qubits)},
        },
        gate_durations_ns={
            "cx": cx_durs,
            "sx": {(q,): 35.0 for q in range(num_qubits)},
            "x": {(q,): 35.0 for q in range(num_qubits)},
        },
        readout_errors={q: (readout_error, readout_error) for q in range(num_qubits)},
        t1_us={q: 150.0 for q in range(num_qubits)},
        t2_us={q: 60.0 for q in range(num_qubits)},
    )


# ---------------------------------------------------------------------------
# Fake and Real Hardware Providers
# ---------------------------------------------------------------------------


class FakeHardwareBackend:
    """
    Offline deterministic simulated hardware backend enforcing profile topology.
    """

    def __init__(
        self,
        profile: BackendProfile,
        noise_model: Optional[NoiseModel] = None,
        relaxation: bool = False,
    ):
        self.profile = profile
        self.relaxation = bool(relaxation)
        self.noise_model = noise_model or profile.to_noise_model(relaxation=self.relaxation)
        self.name = profile.name

    def validate_circuit_topology(self, instructions: List[Tuple[str, List[int], List[float]]]) -> None:
        """Verify that all two-qubit operations respect the backend coupling map."""
        valid_edges = set(self.profile.coupling_map)
        for name, qubits, _ in instructions:
            if len(qubits) == 2:
                pair = (qubits[0], qubits[1])
                if pair not in valid_edges:
                    raise InvalidTopologyError(
                        f"Gate {name!r} on qubits {pair} violates backend topology. "
                        f"Allowed coupling edges: {sorted(valid_edges)}"
                    )

    def _check_in_model(self, instructions: List[Tuple[str, List[int], List[float]]]) -> None:
        for name, qubits, _ in instructions:
            if name in ("barrier", "id") or not qubits:
                continue
            reason = self.profile.out_of_model_reason(list(qubits), self.relaxation)
            if reason is not None:
                raise OutOfModelError(
                    f"Refusing {name} on qubits {list(qubits)}: {reason}. The noise "
                    "model has no calibrated channel for it."
                )

    def expectation_values(self, circuit: Any, observables: Any, **options: Any) -> Any:
        """
        Noisy Pauli expectation values under this backend's noise model.

        Applies the same topology, width and calibration-flag checks as
        :meth:`run`, then delegates to
        :func:`cqhecs.noisy_expectation.noisy_expectation_values` (``options``
        are passed through). Unlike :meth:`run` this is not limited to 10
        qubits: above that the Pauli-propagation engine is used and its
        certified truncation bound is reported.
        """
        from cqhecs.circuit_parsing import parse_circuit
        from cqhecs.noisy_expectation import noisy_expectation_values

        instructions, num_qubits = parse_circuit(circuit)
        if num_qubits > self.profile.num_qubits:
            raise InvalidTopologyError(
                f"Circuit width {num_qubits} exceeds backend qubit count {self.profile.num_qubits}."
            )
        self.validate_circuit_topology(instructions)
        self._check_in_model(instructions)
        result = noisy_expectation_values(circuit, observables, self.noise_model, **options)
        result.metadata.update({
            "backend_profile_id": self.profile.name,
            "profile_is_synthetic": self.profile.is_synthetic,
            "profile_source_sha256": self.profile.source_sha256,
            "calibration_timestamp": self.profile.capture_timestamp,
            "relaxation_modelled": self.relaxation,
            "is_real_hardware": False,
        })
        return result

    def run(
        self,
        circuit: Any,
        shots: int = 1024,
        seed: int = 42,
        execution_mode: ExecutionMode = ExecutionMode.NOISY_CLASSICAL,
    ) -> SimulationResult:
        """
        Execute circuit offline under the hardware profile.
        """
        if execution_mode == ExecutionMode.REAL_HARDWARE:
            raise HardwareBridgeError(
                "FakeHardwareBackend cannot execute in REAL_HARDWARE mode; "
                "it is an offline classical emulation testbed."
            )

        from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
        from cqhecs.circuit_parsing import parse_circuit

        instructions, num_qubits = parse_circuit(circuit)
        if num_qubits > self.profile.num_qubits:
            raise InvalidTopologyError(
                f"Circuit width {num_qubits} exceeds backend qubit count {self.profile.num_qubits}."
            )

        self.validate_circuit_topology(instructions)

        effective_noise = self.noise_model if execution_mode == ExecutionMode.NOISY_CLASSICAL else None
        if effective_noise is not None:
            self._check_in_model(instructions)

        backend = NoisyDensityMatrixBackend()
        res = backend.simulate(
            circuit,
            noise_model=effective_noise,
            shots=shots,
            seed=seed,
        )
        res.execution_mode = execution_mode
        res.backend_profile_id = self.profile.name
        res.noise_model_id = effective_noise.name if effective_noise else None
        res.is_real_hardware = False
        res.calibration_timestamp = self.profile.capture_timestamp
        res.metadata["simulated_hardware"] = True
        res.metadata["provider_name"] = self.profile.provider_name
        res.metadata["profile_is_synthetic"] = self.profile.is_synthetic
        res.metadata["profile_source_sha256"] = self.profile.source_sha256
        res.metadata["relaxation_modelled"] = self.relaxation and effective_noise is not None
        return res


class FakeHardwareProvider:
    """Provider for deterministic fake hardware backends."""

    def __init__(self):
        self._profiles = {
            "fake_manila": create_fake_manila_profile(),
            "linear_5q": create_linear_profile(5, name="linear_5q"),
        }

    def backends(self, name: Optional[str] = None) -> List[FakeHardwareBackend]:
        if name:
            p = self._profiles.get(name)
            return [FakeHardwareBackend(p)] if p else []
        return [FakeHardwareBackend(p) for p in self._profiles.values()]

    def get_backend(self, name: str = "fake_manila") -> FakeHardwareBackend:
        if name not in self._profiles:
            raise KeyError(f"Unknown fake hardware profile: {name!r}. Available: {list(self._profiles.keys())}")
        return FakeHardwareBackend(self._profiles[name])


class RealHardwareBackend:
    """
    Physical QPU execution backend with strict authorization boundaries.
    """

    def __init__(self, name: str, provider_name: str = "RealHardwareProvider"):
        self.name = name
        self.provider_name = provider_name
        self.is_real_hardware = True

    def run(
        self,
        circuit: Any,
        authorized: bool = False,
        api_token: Optional[str] = None,
        shots: int = 1024,
    ) -> SimulationResult:
        """
        Submit a circuit to real physical hardware.
        Fails closed with typed exceptions if unauthorized or unauthenticated.
        NEVER silently falls back to classical simulation.
        """
        if not authorized:
            raise HardwareAuthorizationRequiredError(
                "Real QPU execution is disabled by default. Explicit authorization (authorized=True) "
                "is strictly required before any physical job submission."
            )
        if not api_token:
            raise HardwareAuthenticationError(
                "No valid hardware provider credentials or API token provided. "
                "Real hardware execution is blocked."
            )
        # If authorized and token is provided in a future hardware run, dispatch here.
        raise NotImplementedError("Real hardware submission endpoint is configured as an authorized stub.")


class RealHardwareProvider:
    """Provider interface for real physical QPU devices."""

    def get_backend(self, name: str) -> RealHardwareBackend:
        return RealHardwareBackend(name=name)
