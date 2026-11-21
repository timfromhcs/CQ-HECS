"""Track A: gravity-mediated entanglement, BMV-type effective two-probe model.

Model ``qg.bmv.zz.v1``
----------------------
Two probe degrees of freedom are reduced to one qubit each. Local phase operations are
factored out, so only the entangling invariant matters. The interaction is

    U_ZZ(theta) = exp(-i * (theta/2) * Z (x) Z)

applied to the separable input ``|+>|+>``. Optional local phases ``Rz(alpha) (x) Rz(beta)``
are applied around the interaction to make the local-phase invariance explicit and
testable.

Phase convention (derived, then unit-tested)
--------------------------------------------
Write the final amplitudes as ``c_ab`` in the computational basis. Define the
local-phase-invariant entangling phase

    Phi = arg( c00 * c11 * conj(c01) * conj(c10) )        (= phi00 + phi11 - phi01 - phi10)

For the interaction above, ``Phi = -2 * theta`` (mod 2*pi), hence ``|theta| = |Phi| / 2``.
The factor ``2`` is *derived* from the two eigenvalues (+1, -1) of ``Z (x) Z``; it is not
hard-coded as a bare four. The entanglement measures follow:

    concurrence      C(theta) = |sin(theta)|
    negativity       N(theta) = C(theta) / 2
    entanglement S   S(theta) = H2( (1 + sqrt(1 - C^2)) / 2 )
    CHSH maximum     S_max    = 2 * sqrt(1 + C^2)   (Horodecki, pure state)

These are the independent oracles used by ``tests/test_quantum_gravity_bmv.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

from cqhecs.quantum_gravity.catalog import ExecutionSurface
from cqhecs.quantum_gravity.errors import QGModelError
from cqhecs.quantum_gravity.observables import (
    binary_entropy,
    chsh_bound,
    concurrence_2qubit,
    entanglement_entropy,
    ket_to_density,
    negativity_2qubit,
)

MODEL_ID = "qg.bmv.zz.v1"
MODEL_VERSION = "1.0.0"

_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_ZZ = np.kron(_Z, _Z)
_PLUS = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)


def _rz(phi: float) -> np.ndarray:
    return np.diag([np.exp(-1j * phi / 2.0), np.exp(1j * phi / 2.0)]).astype(complex)


@dataclass(frozen=True)
class BMVEffectivePhaseModel:
    """A declared, finite two-probe effective-interaction model.

    ``theta`` is a *model parameter*. It is not a physical mass, separation, or phase
    accumulation; mapping a circuit value of ``theta`` to a physical claim requires a
    validated dimensional model that this repository does not yet contain.
    """

    theta: float
    local_phase_a: float = 0.0
    local_phase_b: float = 0.0
    model_id: str = MODEL_ID
    model_version: str = MODEL_VERSION

    def __post_init__(self) -> None:
        if not np.isfinite(self.theta):
            raise QGModelError("theta must be finite")
        if not (
            np.isfinite(self.local_phase_a) and np.isfinite(self.local_phase_b)
        ):
            raise QGModelError("local phases must be finite")

    # -- unitaries -----------------------------------------------------------------
    def interaction_unitary(self) -> np.ndarray:
        """``exp(-i (theta/2) Z (x) Z)`` as an exact diagonal 4x4 matrix."""
        # Z(x)Z has eigenvalues (+1, -1, -1, +1) on (00, 01, 10, 11).
        eigen = np.array([1.0, -1.0, -1.0, 1.0])
        phases = np.exp(-1j * (self.theta / 2.0) * eigen)
        return np.diag(phases).astype(complex)

    def local_unitary(self) -> np.ndarray:
        """``Rz(alpha) (x) Rz(beta)`` around the interaction."""
        return np.kron(_rz(self.local_phase_a), _rz(self.local_phase_b))

    def unitary(self) -> np.ndarray:
        """Full two-qubit unitary including the local phases."""
        return self.local_unitary() @ self.interaction_unitary()

    # -- states --------------------------------------------------------------------
    def input_state(self) -> np.ndarray:
        return np.kron(_PLUS, _PLUS)

    def state(self) -> np.ndarray:
        """The evolved two-qubit state vector (unit norm)."""
        return self.unitary() @ self.input_state()

    def density_matrix(self) -> np.ndarray:
        return ket_to_density(self.state())

    # -- derived observables -------------------------------------------------------
    def analytic_concurrence(self) -> float:
        return float(abs(np.sin(self.theta)))

    def analytic_negativity(self) -> float:
        return self.analytic_concurrence() / 2.0

    def analytic_entropy(self) -> float:
        c2 = self.analytic_concurrence() ** 2
        return binary_entropy((1.0 + np.sqrt(max(0.0, 1.0 - c2))) / 2.0)

    def analytic_chsh_max(self) -> float:
        c = self.analytic_concurrence()
        return float(2.0 * np.sqrt(1.0 + c ** 2))

    # -- measured (computed from the actual state) ---------------------------------
    def concurrence(self) -> float:
        return concurrence_2qubit(self.density_matrix())

    def negativity(self) -> float:
        return negativity_2qubit(self.density_matrix())

    def entropy(self) -> float:
        return entanglement_entropy(self.density_matrix(), (2, 2), (0,))

    def chsh_max(self) -> float:
        return chsh_bound(self.state())

    def entangling_phase_invariant(self) -> float:
        """``arg(c00 c11 conj(c01) conj(c10))`` of the evolved state, in radians.

        Equals ``-2*theta`` for this model (mod ``2*pi``) and is unchanged by the local
        phases, which is exactly what ``test_local_phase_invariance`` checks.
        """
        c00, c01, c10, c11 = self.state()
        product = c00 * c11 * np.conj(c01) * np.conj(c10)
        if abs(product) < 1e-30:
            raise QGModelError(
                "entangling phase is undefined: a probability amplitude vanished"
            )
        return float(np.angle(product))

    # -- manifests -----------------------------------------------------------------
    def manifest(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "kind": "effective_two_probe_interaction",
            "surface": ExecutionSurface.MODEL_PREDICTION.value,
            "parameters": {
                "theta": float(self.theta),
                "local_phase_a": float(self.local_phase_a),
                "local_phase_b": float(self.local_phase_b),
            },
            "input_state": "|+>|+>",
            "interaction": "exp(-i (theta/2) Z(x)Z)",
            "entangling_phase_invariant": "arg(c00 c11 conj(c01) conj(c10)) = -2*theta",
            "analytic_oracles": {
                "concurrence": "|sin(theta)|",
                "negativity": "|sin(theta)|/2",
                "chsh_max": "2*sqrt(1 + concurrence^2)",
            },
            "limitations": [
                "theta is a model parameter, not a physical mass/separation",
                "a positive witness is premise-dependent (see literature L-A3, L-A4)",
                "no gravitational field or graviton is measured",
            ],
        }


def null_separable_model(theta: float = 0.0) -> BMVEffectivePhaseModel:
    """The ``theta=0`` control: the interaction reduces to the identity (separable)."""
    return BMVEffectivePhaseModel(theta=theta)


def phase_scan(
    theta_values: Tuple[float, ...],
    *,
    local_phase_a: float = 0.0,
    local_phase_b: float = 0.0,
) -> Dict[str, Any]:
    """Evaluate the model over a declared (frozen) set of theta values.

    Returns plain data plus the maximum absolute deviation of each measured observable
    from its analytic oracle, so a caller can assert the oracle is respected.
    """
    rows = []
    max_concurrence_dev = 0.0
    max_negativity_dev = 0.0
    for theta in theta_values:
        model = BMVEffectivePhaseModel(
            theta=theta, local_phase_a=local_phase_a, local_phase_b=local_phase_b
        )
        c_meas, c_ref = model.concurrence(), model.analytic_concurrence()
        n_meas, n_ref = model.negativity(), model.analytic_negativity()
        max_concurrence_dev = max(max_concurrence_dev, abs(c_meas - c_ref))
        max_negativity_dev = max(max_negativity_dev, abs(n_meas - n_ref))
        rows.append(
            {
                "theta": float(theta),
                "concurrence": c_meas,
                "concurrence_oracle": c_ref,
                "negativity": n_meas,
                "negativity_oracle": n_ref,
                "chsh_max": model.chsh_max(),
                "chsh_max_oracle": model.analytic_chsh_max(),
                "entangling_phase": model.entangling_phase_invariant(),
            }
        )
    return {
        "model_id": MODEL_ID,
        "rows": rows,
        "max_concurrence_deviation": max_concurrence_dev,
        "max_negativity_deviation": max_negativity_dev,
    }
