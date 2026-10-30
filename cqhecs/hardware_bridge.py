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
        if self.schema_version != "1.0":
            raise InvalidProfileError(f"Unsupported schema_version: {self.schema_version!r} (expected '1.0')")
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
        )

    def to_noise_model(self) -> NoiseModel:
        """
        Derive a NoiseModel from the profile's gate and readout errors.

        ``gate_errors`` holds the average gate infidelity ``r = 1 - F_avg``,
        the quantity Qiskit's ``InstructionProperties.error`` (used by
        :meth:`to_target`) and IBM calibration exports report. It is not the
        depolarizing parameter. Each error becomes the depolarizing channel
        with that infidelity, ``p = d r / (d - 1)`` (``d = 2**k`` for a
        k-qubit gate; see :func:`depolarizing_parameter_from_infidelity`).
        Relaxation (T1/T2) is not modelled.

        Raises:
            InvalidNoiseModelError: If an infidelity exceeds the range a
                depolarizing channel can represent, ``(d - 1) / d``.
        """
        model = NoiseModel(name=f"{self.name}_noise_model")
        # Readout errors
        for q, (p01, p10) in self.readout_errors.items():
            model.set_readout_error(q, p01, p10)
        for gate, qmap in self.gate_errors.items():
            for qubits, err in qmap.items():
                p = depolarizing_parameter_from_infidelity(err, len(qubits))
                if len(qubits) == 1:
                    model.add_1q_channel(gate, qubits[0], DepolarizingChannel(p))
                else:
                    model.add_2q_channel(gate, (qubits[0], qubits[1]), TwoQubitDepolarizingChannel(p))
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
    ):
        self.profile = profile
        self.noise_model = noise_model or profile.to_noise_model()
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

        backend = NoisyDensityMatrixBackend()
        effective_noise = self.noise_model if execution_mode == ExecutionMode.NOISY_CLASSICAL else None
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
