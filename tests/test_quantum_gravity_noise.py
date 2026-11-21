"""Noise-channel and finite-shot witness tests (QG-BMV-03)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel
from cqhecs.quantum_gravity.noise import (
    NoiseConfig,
    _apply_single,
    apply_noise,
    apply_readout,
    estimate_zz,
    kraus_amplitude_damping,
    kraus_depolarizing,
    kraus_phase_damping,
    sample_counts,
    witness_under_noise,
)


def _assert_valid_state(rho, tol=1e-9):
    assert abs(float(np.real(np.trace(rho))) - 1.0) < tol
    assert np.allclose(rho, rho.conj().T, atol=tol)
    assert float(np.min(np.linalg.eigvalsh((rho + rho.conj().T) / 2))) > -tol


def test_amplitude_damping_full_decay():
    excited = np.array([[0, 0], [0, 1]], dtype=complex)
    out = _apply_single(excited, kraus_amplitude_damping(1.0), 0, 1)
    assert np.allclose(out, [[1, 0], [0, 0]], atol=1e-12)


def test_phase_damping_removes_coherence():
    coherent = np.array([[0.5, 0.5], [0.5, 0.5]], dtype=complex)
    out = _apply_single(coherent, kraus_phase_damping(1.0), 0, 1)
    assert abs(out[0, 1]) < 1e-12 and abs(out[1, 0]) < 1e-12


def test_depolarizing_p1_is_maximally_mixed():
    pure = np.array([[1, 0], [0, 0]], dtype=complex)
    out = _apply_single(pure, kraus_depolarizing(1.0), 0, 1)
    assert np.allclose(out, np.eye(2) / 2, atol=1e-12)


@pytest.mark.parametrize("config", [
    NoiseConfig(dephasing=0.2),
    NoiseConfig(amplitude_damping=0.3),
    NoiseConfig(depolarizing=0.25),
    NoiseConfig(two_qubit_depolarizing=0.4),
    NoiseConfig(dephasing=0.1, amplitude_damping=0.1, depolarizing=0.1, two_qubit_depolarizing=0.1),
])
def test_channels_are_trace_preserving_and_positive(config):
    rng = np.random.default_rng(0)
    psi = rng.normal(size=4) + 1j * rng.normal(size=4)
    psi /= np.linalg.norm(psi)
    rho = np.outer(psi, psi.conj())
    out = apply_noise(rho, config)
    _assert_valid_state(out)


def test_readout_identity_and_shift():
    probs = np.array([1.0, 0.0, 0.0, 0.0])
    assert np.allclose(apply_readout(probs, 0.0, 0.0), probs)
    shifted = apply_readout(probs, 0.1, 0.2)
    assert abs(shifted.sum() - 1.0) < 1e-12
    assert shifted[0] < 1.0 and shifted[1] > 0.0


def test_sample_counts_total():
    counts = sample_counts([0.5, 0.0, 0.0, 0.5], 1000, seed=3)
    assert sum(counts.values()) == 1000
    assert set(counts) == {"00", "01", "10", "11"}


def test_estimate_zz_on_phi_plus_is_plus_one():
    counts = sample_counts([0.5, 0.0, 0.0, 0.5], 4000, seed=7)
    estimate = estimate_zz(counts)
    assert abs(estimate["estimate"] - 1.0) < 0.1
    assert estimate["ci_low"] <= 1.0 <= estimate["ci_high"]


def test_witness_decreases_with_noise():
    ideal = BMVEffectivePhaseModel(theta=math.pi / 2).density_matrix()
    clean = witness_under_noise(ideal, NoiseConfig(), shots=2000, seed=1)
    noisy = witness_under_noise(
        ideal,
        NoiseConfig(dephasing=0.3, amplitude_damping=0.2, depolarizing=0.2),
        shots=2000,
        seed=1,
    )
    assert noisy["noisy_negativity"] < clean["noisy_negativity"]
    assert noisy["negativity_loss"] > 0.0


def test_null_model_stays_separable_under_noise():
    ideal = BMVEffectivePhaseModel(theta=0.0).density_matrix()
    result = witness_under_noise(ideal, NoiseConfig(dephasing=0.2), shots=1000, seed=2)
    assert result["noisy_negativity"] < 1e-9
    assert result["ideal_negativity"] < 1e-9


def test_noise_config_manifest_is_serialisable():
    manifest = NoiseConfig(dephasing=0.1).manifest()
    assert manifest["noise_model_id"] == "qg.noise.uniform.v1"
    assert "not a measured device calibration" in manifest["note"]
