"""Declared noise channels and a finite-shot witness estimator for Track A.

Everything here is an explicit, documented *model* of a device. It is
``NOISY_CLASSICAL`` emulation, never a physical measurement. Each channel is a
completely-positive trace-preserving map given by Kraus operators, and each has a
`trace/positivity` test.

Channels
--------
* amplitude damping (relaxation), parameter ``gamma`` in [0, 1];
* phase damping (dephasing), parameter ``lambda`` in [0, 1];
* single-qubit depolarizing, parameter ``p`` in [0, 1];
* two-qubit depolarizing (uniform), parameter ``p`` in [0, 1];
* asymmetric readout assignment error ``p01`` / ``p10``.

Estimator
---------
The parity observable ``Z(x)Z`` is bounded in [-1, 1], so a *rigorous* Hoeffding
interval ``|mean_hat - mean| <= sqrt(2 ln(2/delta) / n)`` is reported with the estimate.
Sampling error is kept separate from the model (channel) quantities and never folded into
them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from cqhecs.quantum_gravity.errors import QGModelError
from cqhecs.quantum_gravity.observables import negativity_2qubit


# --------------------------------------------------------------------------------------
# operators / embedding
# --------------------------------------------------------------------------------------
def _embed(op: np.ndarray, qubit: int, num_qubits: int = 2) -> np.ndarray:
    left = np.eye(2 ** qubit, dtype=complex)
    right = np.eye(2 ** (num_qubits - qubit - 1), dtype=complex)
    return np.kron(np.kron(left, op), right)


def _apply_single(rho: np.ndarray, kraus: Sequence[np.ndarray], qubit: int, num_qubits: int = 2) -> np.ndarray:
    acc = np.zeros_like(rho)
    for k in kraus:
        e = _embed(k, qubit, num_qubits)
        acc += e @ rho @ e.conj().T
    return acc


def _check_probability(value: float, name: str) -> float:
    value = float(value)
    if not (0.0 <= value <= 1.0):
        raise QGModelError(f"{name}={value} must lie in [0, 1]")
    return value


# --------------------------------------------------------------------------------------
# Kraus sets
# --------------------------------------------------------------------------------------
def kraus_amplitude_damping(gamma: float) -> List[np.ndarray]:
    gamma = _check_probability(gamma, "gamma")
    return [
        np.array([[1.0, 0.0], [0.0, np.sqrt(1.0 - gamma)]], dtype=complex),
        np.array([[0.0, np.sqrt(gamma)], [0.0, 0.0]], dtype=complex),
    ]


def kraus_phase_damping(lam: float) -> List[np.ndarray]:
    lam = _check_probability(lam, "lambda")
    return [
        np.array([[1.0, 0.0], [0.0, np.sqrt(1.0 - lam)]], dtype=complex),
        np.array([[0.0, 0.0], [0.0, np.sqrt(lam)]], dtype=complex),
    ]


def kraus_depolarizing(p: float) -> List[np.ndarray]:
    p = _check_probability(p, "p")
    x = np.array([[0, 1], [1, 0]], dtype=complex)
    y = np.array([[0, -1j], [1j, 0]], dtype=complex)
    z = np.array([[1, 0], [0, -1]], dtype=complex)
    return [
        np.sqrt(1.0 - 3.0 * p / 4.0) * np.eye(2, dtype=complex),
        np.sqrt(p / 4.0) * x,
        np.sqrt(p / 4.0) * y,
        np.sqrt(p / 4.0) * z,
    ]


def apply_two_qubit_depolarizing(rho: np.ndarray, p: float) -> np.ndarray:
    """``rho -> (1 - p) rho + p I/4`` (uniform two-qubit depolarizing)."""
    p = _check_probability(p, "p")
    return (1.0 - p) * rho + p * np.eye(4, dtype=complex) / 4.0


# --------------------------------------------------------------------------------------
# noise configuration
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class NoiseConfig:
    """A declared, reproducible device-noise model for the two-probe experiment."""

    dephasing: float = 0.0
    amplitude_damping: float = 0.0
    depolarizing: float = 0.0
    two_qubit_depolarizing: float = 0.0
    readout_p01: float = 0.0
    readout_p10: float = 0.0
    noise_model_id: str = "qg.noise.uniform.v1"

    def manifest(self) -> Dict[str, object]:
        return {
            "noise_model_id": self.noise_model_id,
            "dephasing": self.dephasing,
            "amplitude_damping": self.amplitude_damping,
            "depolarizing": self.depolarizing,
            "two_qubit_depolarizing": self.two_qubit_depolarizing,
            "readout_p01": self.readout_p01,
            "readout_p10": self.readout_p10,
            "note": "declared model, not a measured device calibration",
        }


def apply_noise(rho: np.ndarray, config: NoiseConfig) -> np.ndarray:
    """Apply the declared channels to a two-qubit density matrix (both qubits)."""
    out = np.asarray(rho, dtype=complex)
    for qubit in (0, 1):
        if config.dephasing:
            out = _apply_single(out, kraus_phase_damping(config.dephasing), qubit)
        if config.amplitude_damping:
            out = _apply_single(out, kraus_amplitude_damping(config.amplitude_damping), qubit)
        if config.depolarizing:
            out = _apply_single(out, kraus_depolarizing(config.depolarizing), qubit)
    if config.two_qubit_depolarizing:
        out = apply_two_qubit_depolarizing(out, config.two_qubit_depolarizing)
    return out


# --------------------------------------------------------------------------------------
# readout and sampling
# --------------------------------------------------------------------------------------
def apply_readout(probabilities: Sequence[float], p01: float, p10: float) -> np.ndarray:
    """Apply asymmetric single-qubit readout assignment error to a 4-outcome distribution.

    Index convention ``b0*2 + b1`` (qubit 0 most significant). ``p01`` is
    ``P(measure 1 | prepared 0)`` and ``p10`` is ``P(measure 0 | prepared 1)``.
    """
    p01 = _check_probability(p01, "p01")
    p10 = _check_probability(p10, "p10")
    a = np.array([[1.0 - p01, p10], [p01, 1.0 - p10]], dtype=float)  # a[measured, true]
    matrix = np.kron(a, a)
    probs = np.asarray(probabilities, dtype=float).reshape(4)
    return matrix @ probs


def sample_counts(probabilities: Sequence[float], shots: int, seed: int) -> Dict[str, int]:
    """Sample ``shots`` bitstrings from a 4-outcome distribution with a fixed seed."""
    if shots <= 0:
        raise QGModelError("shots must be positive")
    rng = np.random.default_rng(int(seed))
    probs = np.clip(np.asarray(probabilities, dtype=float).reshape(4), 0.0, None)
    total = probs.sum()
    if total <= 0:
        raise QGModelError("probability vector has zero mass")
    probs = probs / total
    draws = rng.multinomial(shots, probs)
    return {format(index, "02b"): int(count) for index, count in enumerate(draws)}


def _zz_value(bitstring: str) -> float:
    bits = [int(bit) for bit in bitstring]
    return float((-1) ** (sum(bits)))


def hoeffding_interval(samples: Sequence[float], shots: int, delta: float = 0.05) -> Tuple[float, float]:
    """Rigorous two-sided Hoeffding interval for a mean of variables in [-1, 1]."""
    if shots <= 0:
        raise QGModelError("shots must be positive")
    if not (0.0 < delta < 1.0):
        raise QGModelError("delta must lie in (0, 1)")
    mean = float(np.mean(np.asarray(samples, dtype=float))) if len(samples) else 0.0
    radius = float(np.sqrt(2.0 * np.log(2.0 / delta) / shots))
    return mean - radius, mean + radius


def estimate_zz(counts: Dict[str, int], delta: float = 0.05) -> Dict[str, float]:
    """Estimate ``<Z(x)Z>`` from counts with a rigorous Hoeffding interval."""
    shots = int(sum(counts.values()))
    if shots <= 0:
        raise QGModelError("counts are empty")
    values = [_zz_value(bitstring) for bitstring, count in counts.items() for _ in range(count)]
    mean = float(np.mean(values))
    low, high = hoeffding_interval(values, shots, delta)
    return {"shots": shots, "estimate": mean, "ci_low": low, "ci_high": high, "delta": delta}


# --------------------------------------------------------------------------------------
# witness under noise
# --------------------------------------------------------------------------------------
def witness_under_noise(
    ideal_density: np.ndarray,
    config: NoiseConfig,
    *,
    shots: int = 2000,
    seed: int = 20260101,
    readout: bool = True,
) -> Dict[str, object]:
    """Return the exact noisy negativity plus a finite-shot ZZ estimate for one point."""
    noisy = apply_noise(ideal_density, config)
    ideal_neg = negativity_2qubit(ideal_density)
    noisy_neg = negativity_2qubit(noisy)
    probabilities = np.real(np.diag(noisy)).astype(float)
    probabilities = np.clip(probabilities, 0.0, None)
    probabilities = probabilities / probabilities.sum()
    if readout and (config.readout_p01 or config.readout_p10):
        probabilities = apply_readout(probabilities, config.readout_p01, config.readout_p10)
    counts = sample_counts(probabilities, shots, seed)
    return {
        "noise_model_id": config.noise_model_id,
        "ideal_negativity": ideal_neg,
        "noisy_negativity": noisy_neg,
        "negativity_loss": ideal_neg - noisy_neg,
        "zz": estimate_zz(counts),
        "counts": counts,
    }
