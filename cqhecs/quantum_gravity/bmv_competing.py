"""Track A, W8: parameterisation, competing predictions and null controls for the BMV toy model.

Scope and boundary
------------------
Everything here is a *finite two-qubit model*. It compares **state-preparation hypotheses**
(an entangling ZZ interaction, a measure-and-feedback classical channel, shared classical
randomness, an interaction followed by decoherence) by their predicted two-qubit state. It
does not measure, simulate or constrain gravity. The literature records (``L-A3``, ``L-A4``,
``L-A5`` in ``research/qg_2026/LITERATURE_MAP.md``) state that a positive entanglement
witness is premise-dependent and that some classical-gravity models can produce
entanglement under fuller field-theoretic assumptions. The separable controls below are
*specific channel constructions* that provably cannot entangle; they are not a statement
about every classical-gravity theory.

Phase convention
----------------
``qg.bmv.zz.v1`` uses ``U = exp(-i (theta/2) Z (x) Z)``. ``QGRAVITY.md`` section 2.1 writes
``exp(-i theta_qg Z (x) Z)``, so ``theta = 2 * theta_qg``. For a four-branch phase table the
local-phase-invariant combination is ``Phi = phi00 + phi11 - phi01 - phi10`` and
``theta = -Phi / 2`` (principal value). A circuit ``theta`` is a model parameter; mapping it to
a physical mass/separation requires a validated dimensional model this repository does not
contain, and :func:`theta_from_physical_parameters` refuses accordingly.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np

from cqhecs.quantum_gravity.errors import QGModelError, QGUnsupported
from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel
from cqhecs.quantum_gravity.observables import (
    concurrence_2qubit,
    ket_to_density,
    negativity_2qubit,
)

COMPETING_SCHEMA = "cqhecs.qg.bmv_competing.v1"

_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_I = np.eye(2, dtype=complex)
_PAULIS = {"I": _I, "X": _X, "Y": _Y, "Z": _Z}
_PLUS = np.array([1.0, 1.0], dtype=complex) / math.sqrt(2.0)

#: Literature premises that every comparison must carry (never dropped by a caller).
CAVEATS: Tuple[str, ...] = (
    "toy two-qubit state-preparation model: no mass, separation, field or graviton is simulated",
    "a positive entanglement witness is premise-dependent (L-A3, L-A4); it does not by itself "
    "separate quantum from every classical-gravity model",
    "the separable controls are specific channel constructions, not all classical-gravity theories",
    "collapse/decoherence models (L-A5) are represented only by a declared dephasing channel",
)


# -- parameterisation ---------------------------------------------------------------
def _wrap(angle: float) -> float:
    """Wrap to ``(-pi, pi]``."""
    wrapped = math.fmod(angle + math.pi, 2.0 * math.pi)
    if wrapped <= 0.0:
        wrapped += 2.0 * math.pi
    return wrapped - math.pi


def invariant_phase_from_branch_phases(
    phi00: float, phi01: float, phi10: float, phi11: float
) -> float:
    """Local-phase-invariant ``Phi = phi00 + phi11 - phi01 - phi10`` wrapped to ``(-pi, pi]``."""
    for value in (phi00, phi01, phi10, phi11):
        if not math.isfinite(value):
            raise QGModelError("branch phases must be finite")
    return _wrap(phi00 + phi11 - phi01 - phi10)


def theta_from_branch_phases(phi00: float, phi01: float, phi10: float, phi11: float) -> float:
    """Model ``theta`` (principal value, ``[-pi/2, pi/2)``) for a four-branch phase table.

    The branch amplitudes ``exp(i phi_ab)/2`` give ``Phi = -2 theta`` for ``qg.bmv.zz.v1``.
    """
    return -invariant_phase_from_branch_phases(phi00, phi01, phi10, phi11) / 2.0


def theta_code_from_qgravity(theta_qg: float) -> float:
    """Convert ``QGRAVITY.md`` ``exp(-i theta_qg ZZ)`` to the code convention ``exp(-i theta/2 ZZ)``."""
    if not math.isfinite(theta_qg):
        raise QGModelError("theta_qg must be finite")
    return 2.0 * float(theta_qg)


def toy_branch_phase_table(kappa: float, d: float, delta: float) -> Dict[str, float]:
    """Dimensionless toy table ``phi_ab = kappa / d_ab`` (``d_00 = d_11 = d``, ``d_01 = d_10 = d + delta``).

    ``kappa`` stands for an unspecified dimensionless coupling-times-time. This is a
    *parameterisation device* for exploring the sign/size of ``Phi``; it is not a physical
    estimate and carries no units.
    """
    if not all(math.isfinite(v) for v in (kappa, d, delta)):
        raise QGModelError("kappa, d and delta must be finite")
    if d <= 0.0 or d + delta <= 0.0:
        raise QGModelError("branch distances must be positive")
    near = kappa / d
    far = kappa / (d + delta)
    return {"phi00": near, "phi11": near, "phi01": far, "phi10": far}


def theta_from_physical_parameters(*_args: Any, **_kwargs: Any) -> float:
    """Typed refusal: there is no validated dimensional model for ``theta``."""
    raise QGUnsupported(
        "mapping a circuit theta to physical masses/separations needs a validated dimensional "
        "model that is not part of CQ-HECS; use theta as a declared model parameter",
        code="QG_NO_DIMENSIONAL_MODEL",
    )


# -- helpers ------------------------------------------------------------------------
def _check_rho(rho: np.ndarray) -> np.ndarray:
    arr = np.asarray(rho, dtype=complex)
    if arr.shape != (4, 4):
        raise QGModelError("expected a 4x4 two-qubit density matrix")
    if not np.isclose(np.trace(arr).real, 1.0, atol=1e-9):
        raise QGModelError("density matrix must have unit trace")
    return arr


def dephase(rho: np.ndarray, qubit: int, p: float) -> np.ndarray:
    """Phase-flip channel ``(1-p) rho + p Z_q rho Z_q`` on one qubit (``p`` in ``[0, 1]``)."""
    if qubit not in (0, 1):
        raise QGModelError("qubit must be 0 or 1")
    if not (0.0 <= p <= 1.0):
        raise QGModelError("dephasing probability must be in [0, 1]")
    z = np.kron(_Z, _I) if qubit == 0 else np.kron(_I, _Z)
    arr = _check_rho(rho)
    return (1.0 - p) * arr + p * (z @ arr @ z.conj().T)


def wootters_concurrence(rho: np.ndarray) -> float:
    """Independent oracle: Wootters spin-flip concurrence ``max(0, l1 - l2 - l3 - l4)``.

    Shares no code with ``observables.concurrence_2qubit`` beyond the matrix inputs.
    """
    arr = _check_rho(rho)
    yy = np.kron(_Y, _Y)
    # lambda_i are the singular values of sqrt(rho) YY conj(sqrt(rho)); this equals the
    # square roots of the eigenvalues of rho * rho_tilde without taking sqrt of rounding noise.
    weights, vectors = np.linalg.eigh((arr + arr.conj().T) / 2.0)
    root = (vectors * np.sqrt(np.clip(weights, 0.0, None))) @ vectors.conj().T
    lam = np.sort(np.linalg.svd(root @ yy @ root.conj(), compute_uv=False))[::-1]
    return float(max(0.0, lam[0] - lam[1] - lam[2] - lam[3]))


def pauli_correlator(rho: np.ndarray, label: str) -> float:
    """``Tr[rho P_a (x) P_b]`` for a two-character Pauli label such as ``"XX"``."""
    if len(label) != 2 or any(ch not in _PAULIS for ch in label):
        raise QGModelError(f"invalid two-qubit Pauli label {label!r}")
    op = np.kron(_PAULIS[label[0]], _PAULIS[label[1]])
    return float(np.real(np.trace(_check_rho(rho) @ op)))


def fidelity_witness(rho: np.ndarray, psi: np.ndarray) -> float:
    """``F - lambda_max^2`` with ``F = <psi|rho|psi>`` and ``lambda_max^2`` the largest Schmidt weight.

    ``F <= lambda_max^2`` for every separable ``rho`` (standard fidelity witness), so a
    positive value certifies entanglement. A negative value certifies nothing.
    """
    vec = np.asarray(psi, dtype=complex).reshape(2, 2)
    norm = np.linalg.norm(vec)
    if norm == 0.0:
        raise QGModelError("witness state has zero norm")
    vec = vec / norm
    schmidt = np.linalg.svd(vec, compute_uv=False)
    lam2 = float(schmidt[0] ** 2)
    ket = vec.reshape(4)
    fidelity = float(np.real(np.vdot(ket, _check_rho(rho) @ ket)))
    return fidelity - lam2


# -- competing state-preparation hypotheses ----------------------------------------
def rho_quantum_zz(theta: float) -> np.ndarray:
    """Entangling model: ``U_ZZ(theta)|+>|+>`` (pure)."""
    return BMVEffectivePhaseModel(theta=theta).density_matrix()


def rho_classical_feedback(theta: float) -> np.ndarray:
    """Measure-and-feedback (LOCC) control: ZZ evolution with qubit A fully dephased in Z.

    Equivalent to measuring ``Z_A`` and rotating B conditionally on the classical outcome:
    a classical-quantum state, separable by construction.
    """
    return dephase(rho_quantum_zz(theta), 0, 0.5)


def rho_shared_randomness(theta: float) -> np.ndarray:
    """Shared-classical-randomness control: a fair mixture of product states ``Rz(s theta)^{(x)2}|+>^{(x)2}``."""
    def rz(phi: float) -> np.ndarray:
        return np.diag([np.exp(-0.5j * phi), np.exp(0.5j * phi)]).astype(complex)

    rho = np.zeros((4, 4), dtype=complex)
    for sign in (1.0, -1.0):
        single = rz(sign * theta) @ _PLUS
        rho += 0.5 * ket_to_density(np.kron(single, single))
    return rho


def rho_decoherence(theta: float, p: float) -> np.ndarray:
    """Interaction followed by symmetric dephasing ``p`` on both probes (collapse/decoherence stand-in)."""
    return dephase(dephase(rho_quantum_zz(theta), 0, p), 1, p)


def rho_null(local_phase_a: float = 0.0, local_phase_b: float = 0.0) -> np.ndarray:
    """``theta = 0`` with local phases only: a pure product state."""
    return BMVEffectivePhaseModel(
        theta=0.0, local_phase_a=local_phase_a, local_phase_b=local_phase_b
    ).density_matrix()


_MODEL_NOTES = {
    "quantum_zz": "coherent ZZ interaction (pure state)",
    "classical_feedback": "Z_A measured, B rotated conditionally (LOCC, separable)",
    "shared_randomness": "shared classical sign selects a local rotation on both probes (separable)",
    "decoherence": "ZZ interaction then symmetric dephasing (declared channel, not a derived collapse model)",
    "null_local_only": "theta = 0 control (separable)",
}


def competing_predictions(theta: float, *, dephasing: float = 0.25) -> Dict[str, Any]:
    """Predicted two-qubit observables for each hypothesis at one ``theta``.

    The models intentionally do **not** all predict the same thing; the returned
    ``distinguishing_correlators`` lists observables where they differ.
    """
    states = {
        "quantum_zz": rho_quantum_zz(theta),
        "classical_feedback": rho_classical_feedback(theta),
        "shared_randomness": rho_shared_randomness(theta),
        "decoherence": rho_decoherence(theta, dephasing),
        "null_local_only": rho_null(),
    }
    witness_target = BMVEffectivePhaseModel(theta=theta).state()
    labels = ("XX", "XY", "YX", "YY", "YZ", "ZY", "ZZ", "XZ", "ZX")
    models: Dict[str, Any] = {}
    for name, rho in states.items():
        c_wootters = wootters_concurrence(rho)
        models[name] = {
            "note": _MODEL_NOTES[name],
            "concurrence": c_wootters,
            "concurrence_cross_check": concurrence_2qubit(rho),
            "negativity": negativity_2qubit(rho),
            "fidelity_witness": fidelity_witness(rho, witness_target),
            "correlators": {lab: pauli_correlator(rho, lab) for lab in labels},
            "entangled": bool(c_wootters > 1e-9),
        }
    base = models["quantum_zz"]["correlators"]
    distinguishing: List[str] = []
    for lab in labels:
        values = [m["correlators"][lab] for m in models.values()]
        if max(values) - min(values) > 1e-9:
            distinguishing.append(lab)
    return {
        "schema": COMPETING_SCHEMA,
        "theta": float(theta),
        "dephasing": float(dephasing),
        "models": models,
        "distinguishing_correlators": distinguishing,
        "quantum_zz_correlators": base,
        "surface": "MODEL_PREDICTION",
        "caveats": list(CAVEATS),
    }


def competing_table(theta_values: Tuple[float, ...], *, dephasing: float = 0.25) -> Dict[str, Any]:
    """Frozen table of :func:`competing_predictions` over declared theta values."""
    return {
        "schema": COMPETING_SCHEMA,
        "rows": [competing_predictions(t, dephasing=dephasing) for t in theta_values],
        "caveats": list(CAVEATS),
    }
