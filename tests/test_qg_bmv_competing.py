"""W8: BMV parameterisation, competing predictions, null controls, independent oracle.

Model quantities only. Nothing here measures gravity.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.linalg import expm

from cqhecs.quantum_gravity.bmv_competing import (
    CAVEATS,
    competing_predictions,
    competing_table,
    dephase,
    fidelity_witness,
    invariant_phase_from_branch_phases,
    pauli_correlator,
    rho_classical_feedback,
    rho_decoherence,
    rho_null,
    rho_quantum_zz,
    rho_shared_randomness,
    theta_code_from_qgravity,
    theta_from_branch_phases,
    theta_from_physical_parameters,
    toy_branch_phase_table,
    wootters_concurrence,
)
from cqhecs.quantum_gravity.errors import QGModelError, QGUnsupported
from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel
from cqhecs.quantum_gravity.observables import negativity_2qubit

THETAS = [0.0, 0.1, math.pi / 8, math.pi / 4, 1.0, math.pi / 2, 2.0, math.pi - 0.3]
_Z = np.diag([1.0, -1.0]).astype(complex)


@pytest.mark.parametrize("theta", THETAS)
def test_wootters_oracle_matches_analytic_and_code_concurrence(theta):
    rho = rho_quantum_zz(theta)
    assert abs(wootters_concurrence(rho) - abs(math.sin(theta))) < 1e-9
    assert abs(wootters_concurrence(rho) - BMVEffectivePhaseModel(theta=theta).concurrence()) < 1e-9


@pytest.mark.parametrize("theta", THETAS)
def test_branch_phase_table_roundtrip(theta):
    # Build amplitudes from the model, read the invariant back, and also from phi_ab.
    base = 0.37  # arbitrary common/local phase offsets must not matter
    phi = {"phi00": base - theta / 2, "phi11": base - theta / 2, "phi01": base + theta / 2, "phi10": base + theta / 2}
    recovered = theta_from_branch_phases(**phi)
    assert abs(math.sin(recovered) - math.sin(theta)) < 1e-9 or abs(math.sin(recovered) + math.sin(theta)) < 1e-9
    # exact sign/size against the generated unitary phases
    u = BMVEffectivePhaseModel(theta=theta).interaction_unitary()
    arg = np.angle(np.diag(u))
    invariant = invariant_phase_from_branch_phases(arg[0], arg[1], arg[2], arg[3])
    expected = BMVEffectivePhaseModel(theta=theta).entangling_phase_invariant()
    assert abs(math.cos(invariant) - math.cos(expected)) < 1e-9
    assert abs(math.sin(invariant) - math.sin(expected)) < 1e-9


def test_local_branch_phase_offsets_do_not_change_theta():
    a = theta_from_branch_phases(0.1, 0.2, 0.3, 0.4)
    # add a_i + b_j local phases
    la, lb = (0.7, -0.4), (1.9, 0.25)
    shifted = theta_from_branch_phases(
        0.1 + la[0] + lb[0], 0.2 + la[0] + lb[1], 0.3 + la[1] + lb[0], 0.4 + la[1] + lb[1]
    )
    assert abs(a - shifted) < 1e-12


@pytest.mark.parametrize("theta_qg", [0.0, 0.2, 0.5, 0.785])
def test_qgravity_convention_maps_to_code_convention(theta_qg):
    zz = np.kron(_Z, _Z)
    expected = expm(-1j * theta_qg * zz)
    got = BMVEffectivePhaseModel(theta=theta_code_from_qgravity(theta_qg)).interaction_unitary()
    assert np.allclose(got, expected, atol=1e-12)


def test_toy_branch_table_reduces_phi_and_is_dimensionless():
    table = toy_branch_phase_table(kappa=0.8, d=1.0, delta=0.5)
    phi = table["phi00"] + table["phi11"] - table["phi01"] - table["phi10"]
    assert abs(phi - 2 * 0.8 * (1.0 - 1.0 / 1.5)) < 1e-12
    assert theta_from_branch_phases(**{k: table[k] for k in ("phi00", "phi01", "phi10", "phi11")}) == pytest.approx(-phi / 2)
    with pytest.raises(QGModelError):
        toy_branch_phase_table(1.0, 0.0, 1.0)
    with pytest.raises(QGModelError):
        toy_branch_phase_table(float("nan"), 1.0, 1.0)


def test_physical_mapping_is_a_typed_refusal():
    with pytest.raises(QGUnsupported) as excinfo:
        theta_from_physical_parameters(mass_kg=1e-14, separation_m=2e-4, time_s=2.5)
    assert excinfo.value.code == "QG_NO_DIMENSIONAL_MODEL"


@pytest.mark.parametrize("theta", THETAS)
def test_separable_controls_never_entangle(theta):
    for rho in (rho_classical_feedback(theta), rho_shared_randomness(theta), rho_null()):
        assert wootters_concurrence(rho) < 1e-9
        assert negativity_2qubit(rho) < 1e-9
        # valid density matrix
        assert abs(np.trace(rho) - 1) < 1e-12
        assert np.min(np.linalg.eigvalsh(rho)) > -1e-12


def test_locc_does_not_create_entanglement_from_separable_input_random_channels():
    """Property check: LOCC (local unitary + classical-controlled local unitary) keeps PPT."""
    rng = np.random.default_rng(7)
    for _ in range(25):
        theta = rng.uniform(-math.pi, math.pi)
        p = rng.uniform(0.0, 0.5)
        rho = dephase(rho_classical_feedback(theta), 1, p)
        assert wootters_concurrence(rho) < 1e-9


def test_fidelity_witness_certifies_quantum_not_controls():
    for theta in (0.3, 1.0, math.pi / 2):
        psi = BMVEffectivePhaseModel(theta=theta).state()
        assert fidelity_witness(rho_quantum_zz(theta), psi) > 1e-6
        assert fidelity_witness(rho_classical_feedback(theta), psi) <= 1e-9
        assert fidelity_witness(rho_shared_randomness(theta), psi) <= 1e-9
    # theta = 0: product state, no violation possible
    assert fidelity_witness(rho_quantum_zz(0.0), BMVEffectivePhaseModel(theta=0.0).state()) <= 1e-12


def test_witness_bound_holds_for_random_separable_states():
    rng = np.random.default_rng(11)
    psi = BMVEffectivePhaseModel(theta=math.pi / 2).state()
    for _ in range(200):
        rho = np.zeros((4, 4), dtype=complex)
        weights = rng.dirichlet(np.ones(3))
        for w in weights:
            a, b = (rng.normal(size=2) + 1j * rng.normal(size=2) for _ in range(2))
            a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
            ket = np.kron(a, b)
            rho += w * np.outer(ket, ket.conj())
        assert fidelity_witness(rho, psi) <= 1e-9


def test_decoherence_reduces_entanglement_and_full_dephasing_removes_it():
    c0 = wootters_concurrence(rho_decoherence(math.pi / 2, 0.0))
    c1 = wootters_concurrence(rho_decoherence(math.pi / 2, 0.1))
    c2 = wootters_concurrence(rho_decoherence(math.pi / 2, 0.3))
    assert c0 == pytest.approx(1.0, abs=1e-9)
    assert c0 > c1 > c2 >= 0.0
    assert wootters_concurrence(rho_decoherence(math.pi / 2, 0.5)) < 1e-9


def test_competing_models_make_different_predictions():
    pred = competing_predictions(math.pi / 3)
    models = pred["models"]
    assert set(models) == {
        "quantum_zz", "classical_feedback", "shared_randomness", "decoherence", "null_local_only"
    }
    assert models["quantum_zz"]["entangled"]
    assert not models["classical_feedback"]["entangled"]
    assert not models["shared_randomness"]["entangled"]
    assert not models["null_local_only"]["entangled"]
    # the models differ in at least one correlator; they are not identical predictions
    assert pred["distinguishing_correlators"]
    # ZZ commutes with XX, so <XX> = 1 for the coherent model at every theta; the phase is
    # visible in YZ/ZY (= sin theta), which is what the historical QPU analysis measured.
    # Classical feedback fully dephases A in Z, so A-coherence correlators vanish.
    assert abs(models["classical_feedback"]["correlators"]["XX"]) < 1e-12
    assert abs(models["classical_feedback"]["correlators"]["YZ"]) < 1e-12
    assert abs(models["quantum_zz"]["correlators"]["XX"] - 1.0) < 1e-9
    assert abs(models["quantum_zz"]["correlators"]["YZ"] - math.sin(math.pi / 3)) < 1e-9
    assert abs(models["quantum_zz"]["correlators"]["ZY"] - math.sin(math.pi / 3)) < 1e-9
    assert pred["surface"] == "MODEL_PREDICTION"
    assert pred["caveats"] == list(CAVEATS)


def test_caveats_carry_literature_premises_and_no_overclaim():
    text = " ".join(CAVEATS).lower()
    assert "l-a3" in text and "l-a4" in text and "l-a5" in text
    for banned in ("proves gravity", "measures gravity", "demonstrates quantum gravity", "detects gravitons"):
        assert banned not in text


def test_concurrence_cross_check_agrees_with_wootters_on_mixed_states():
    pred = competing_predictions(1.1, dephasing=0.2)
    for name, row in pred["models"].items():
        assert abs(row["concurrence"] - row["concurrence_cross_check"]) < 1e-8, name


def test_table_is_deterministic_and_covers_thetas():
    a = competing_table((0.0, 0.5, 1.0))
    b = competing_table((0.0, 0.5, 1.0))
    assert a == b and len(a["rows"]) == 3


def test_bad_inputs_are_refused():
    with pytest.raises(QGModelError):
        dephase(rho_null(), 2, 0.1)
    with pytest.raises(QGModelError):
        dephase(rho_null(), 0, 1.5)
    with pytest.raises(QGModelError):
        pauli_correlator(rho_null(), "XQ")
    with pytest.raises(QGModelError):
        wootters_concurrence(np.eye(3) / 3)
    with pytest.raises(QGModelError):
        invariant_phase_from_branch_phases(float("inf"), 0, 0, 0)


def _close(a, b, tol=1e-9):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, float):
        return abs(a - b) <= tol
    return a == b


def test_frozen_competing_table_matches_regeneration():
    import json
    from pathlib import Path

    stored = json.loads(
        (Path(__file__).resolve().parent.parent / "research" / "qg_2026" / "models" / "bmv_competing_table.json")
        .read_text(encoding="utf-8")
    )
    fresh = json.loads(json.dumps(competing_table(tuple(k * math.pi / 8 for k in range(5)), dephasing=0.25)))
    assert _close(stored, fresh)
