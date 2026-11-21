"""Track A tests: BMV effective-phase model against independent oracles.

The oracle for each observable is the analytic closed form in
``cqhecs.quantum_gravity.models``. Independent cross-checks use SciPy's matrix
exponential and (when available) Qiskit's Statevector as a separate simulator.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cqhecs.quantum_gravity import (
    BMVEffectivePhaseModel,
    chsh_from_correlators,
    concurrence_2qubit,
    entanglement_entropy,
    negativity_2qubit,
)
from cqhecs.quantum_gravity.models import null_separable_model, phase_scan

SWEEP = [0.0, math.pi / 8, math.pi / 4, math.pi / 2, 3 * math.pi / 4, math.pi]


def test_interaction_unitary_matches_matrix_exponential():
    scipy = pytest.importorskip("scipy.linalg")
    zz = np.kron(np.diag([1, -1]), np.diag([1, -1])).astype(complex)
    for theta in SWEEP:
        model = BMVEffectivePhaseModel(theta)
        expected = scipy.expm(-1j * (theta / 2.0) * zz)
        assert np.allclose(model.interaction_unitary(), expected, atol=1e-12)


def test_state_matches_analytic_form():
    phi_plus = np.array([1, 0, 0, 1]) / np.sqrt(2)
    psi_plus = np.array([0, 1, 1, 0]) / np.sqrt(2)
    for theta in SWEEP:
        expected = (np.exp(-1j * theta / 2) * phi_plus + np.exp(1j * theta / 2) * psi_plus) / np.sqrt(2)
        model = BMVEffectivePhaseModel(theta)
        assert np.allclose(model.state(), expected, atol=1e-12)


@pytest.mark.parametrize("theta", SWEEP)
def test_concurrence_negativity_entropy_against_oracles(theta):
    model = BMVEffectivePhaseModel(theta)
    assert abs(model.concurrence() - model.analytic_concurrence()) < 1e-9
    assert abs(model.negativity() - model.analytic_negativity()) < 1e-9
    assert abs(model.entropy() - model.analytic_entropy()) < 1e-9
    # concurrence and negativity are consistent: N = C/2 for a pure two-qubit state.
    assert abs(model.negativity() - model.concurrence() / 2.0) < 1e-12
    # Wootters concurrence agrees with the closed form on the pure state.
    assert abs(concurrence_2qubit(model.density_matrix()) - model.analytic_concurrence()) < 1e-9


@pytest.mark.parametrize("theta", SWEEP)
def test_chsh_matches_horodecki_oracle(theta):
    model = BMVEffectivePhaseModel(theta)
    expected = model.analytic_chsh_max()
    assert abs(model.chsh_max() - expected) < 1e-9
    # equivalent identity C = |sin(theta)| => S_max = 2 sqrt(1 + C^2)
    c = abs(math.sin(theta))
    assert abs(model.chsh_max() - 2 * math.sqrt(1 + c ** 2)) < 1e-9


def test_chsh_at_maximal_entanglement_is_two_root_two():
    model = BMVEffectivePhaseModel(math.pi / 2)
    assert abs(model.chsh_max() - 2 * math.sqrt(2)) < 1e-9


def test_entangling_phase_invariant_equals_minus_two_theta():
    for theta in [0.3, 0.7, 1.1, -0.5, 2.0]:
        model = BMVEffectivePhaseModel(theta)
        residual = (model.entangling_phase_invariant() + 2 * theta) % (2 * math.pi)
        residual = min(residual, 2 * math.pi - residual)
        assert residual < 1e-9


def test_local_phase_invariance():
    base = BMVEffectivePhaseModel(theta=0.9)
    shifted = BMVEffectivePhaseModel(theta=0.9, local_phase_a=0.37, local_phase_b=-1.2)
    assert abs(base.concurrence() - shifted.concurrence()) < 1e-12
    assert abs(base.negativity() - shifted.negativity()) < 1e-12
    assert abs(base.entropy() - shifted.entropy()) < 1e-12
    assert abs(base.entangling_phase_invariant() - shifted.entangling_phase_invariant()) < 1e-12


def test_null_control_is_separable():
    model = null_separable_model()
    rho = model.density_matrix()
    assert abs(model.concurrence()) < 1e-12
    assert abs(model.negativity()) < 1e-12
    # product state: partial transpose has no negative eigenvalue
    from cqhecs.quantum_gravity.observables import partial_transpose

    pt = partial_transpose(rho, (2, 2), 0)
    assert np.min(np.linalg.eigvalsh(pt)) > -1e-12


def test_phase_scan_reports_deviation():
    report = phase_scan(tuple(SWEEP))
    assert report["max_concurrence_deviation"] < 1e-9
    assert report["max_negativity_deviation"] < 1e-9
    assert len(report["rows"]) == len(SWEEP)


def test_qiskit_statevector_cross_check():
    """Independent simulator: Qiskit's circuit reproduces the analytic witness."""
    pytest.importorskip("qiskit")
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import DensityMatrix, Statevector

    from cqhecs.quantum_gravity.circuits import bmv_qasm

    for theta in SWEEP:
        model = BMVEffectivePhaseModel(theta)
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cx(0, 1)
        qc.rz(theta, 1)
        qc.cx(0, 1)
        qc.rz(0.0, 0)
        qc.rz(0.0, 1)
        sv = Statevector(qc)
        rho = DensityMatrix(sv).data
        # entanglement measures are ordering-independent for a pure two-qubit state
        assert abs(concurrence_2qubit(rho) - model.analytic_concurrence()) < 1e-9
        assert abs(negativity_2qubit(rho) - model.analytic_negativity()) < 1e-9
        assert abs(entanglement_entropy(rho, (2, 2), (0,)) - model.analytic_entropy()) < 1e-9
        # the emitted QASM must contain the same gate sequence
        assert "rz(" in bmv_qasm(theta)


def test_chsh_from_correlators_helper():
    corr = np.array([[1.0, 0.5], [0.5, -1.0]])
    assert abs(chsh_from_correlators(corr) - 3.0) < 1e-12
