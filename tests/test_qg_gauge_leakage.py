"""W8: Z2 gauge toy constraint-leakage observable with analytic oracles and null controls."""

from __future__ import annotations

import numpy as np
import pytest

from cqhecs.quantum_gravity.errors import QGModelError
from cqhecs.quantum_gravity.gauge import (
    Z2Lattice,
    apply_link_z_error,
    gauss_law_satisfied,
    gauss_leakage,
    gauss_projector,
    gauss_violation_profile,
    leakage_under_evolution,
    link_rotation,
    uniform_plus_state,
)

LATTICES = [(1, 1), (1, 2)]


@pytest.mark.parametrize("rows,cols", LATTICES)
def test_projector_is_a_projector_and_physical_state_has_zero_leakage(rows, cols):
    lat = Z2Lattice(rows, cols)
    proj = gauss_projector(lat)
    assert np.allclose(proj @ proj, proj, atol=1e-12)
    assert np.allclose(proj, proj.conj().T, atol=1e-12)
    psi = uniform_plus_state(lat)
    assert gauss_law_satisfied(psi, lat)
    assert gauss_leakage(psi, lat) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("rows,cols", LATTICES)
@pytest.mark.parametrize("eps", [0.0, 0.1, 0.5, np.pi / 4, np.pi / 2])
def test_single_link_z_rotation_leakage_equals_sin_squared(rows, cols, eps):
    lat = Z2Lattice(rows, cols)
    psi = uniform_plus_state(lat)
    for link in range(lat.num_links):
        out = link_rotation(lat, link, "Z", eps) @ psi
        assert gauss_leakage(out, lat) == pytest.approx(np.sin(eps) ** 2, abs=1e-10)
        profile = gauss_violation_profile(out, lat)
        hit = {v for v, p in profile.items() if p > 1e-9}
        endpoints = {v for v, _ in lat.gauss_generators() if link in lat.vertex_links(*v)}
        assert hit == (endpoints if eps != 0.0 else set())
        for v in hit:
            assert profile[v] == pytest.approx(np.sin(eps) ** 2, abs=1e-10)


@pytest.mark.parametrize("rows,cols", LATTICES)
def test_gauge_preserving_x_rotation_is_a_null_control(rows, cols):
    lat = Z2Lattice(rows, cols)
    psi = uniform_plus_state(lat)
    for link in range(lat.num_links):
        out = link_rotation(lat, link, "X", 0.7) @ psi
        assert gauss_leakage(out, lat) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("p", [0.0, 0.05, 0.3, 1.0])
def test_incoherent_z_error_leaks_with_probability_p(p):
    lat = Z2Lattice(1, 1)
    rho = apply_link_z_error(uniform_plus_state(lat), lat, 0, p)
    assert gauss_leakage(rho, lat) == pytest.approx(p, abs=1e-12)
    assert np.trace(rho).real == pytest.approx(1.0)


def test_hamiltonian_evolution_never_leaks_and_x_field_control_never_leaks():
    lat = Z2Lattice(1, 2)
    psi = uniform_plus_state(lat)
    for t in (0.3, 1.0, 5.0):
        assert leakage_under_evolution(lat, psi, t)["leakage"] == pytest.approx(0.0, abs=1e-10)
    row = leakage_under_evolution(lat, psi, 2.0, perturbation="x_field", strength=0.4)
    assert row["leakage"] == pytest.approx(0.0, abs=1e-10)


def test_zero_strength_breaking_field_is_a_null_control():
    lat = Z2Lattice(1, 1)
    row = leakage_under_evolution(lat, uniform_plus_state(lat), 1.0, perturbation="z_field", strength=0.0)
    assert row["leakage"] == pytest.approx(0.0, abs=1e-10)


def test_short_time_breaking_field_leakage_matches_second_order_oracle():
    lat = Z2Lattice(1, 2)
    psi = uniform_plus_state(lat)
    strength, t = 0.05, 0.1
    row = leakage_under_evolution(lat, psi, t, perturbation="z_field", strength=strength)
    expected = lat.num_links * (strength * t) ** 2
    assert row["leakage"] == pytest.approx(expected, rel=0.05)
    assert row["leakage"] > 0.0


def test_breaking_field_leakage_grows_with_strength():
    lat = Z2Lattice(1, 1)
    psi = uniform_plus_state(lat)
    vals = [
        leakage_under_evolution(lat, psi, 0.3, perturbation="z_field", strength=s)["leakage"]
        for s in (0.0, 0.1, 0.3)
    ]
    assert vals[0] < vals[1] < vals[2]


def test_density_matrix_input_matches_state_input():
    lat = Z2Lattice(1, 1)
    out = link_rotation(lat, 0, "Z", 0.4) @ uniform_plus_state(lat)
    rho = np.outer(out, out.conj())
    assert gauss_leakage(rho, lat) == pytest.approx(gauss_leakage(out, lat), abs=1e-12)


def test_bad_inputs_are_refused():
    lat = Z2Lattice(1, 1)
    with pytest.raises(QGModelError):
        gauss_leakage(np.ones(3), lat)
    with pytest.raises(QGModelError):
        gauss_leakage(np.zeros(2 ** lat.num_links), lat)
    with pytest.raises(QGModelError):
        link_rotation(lat, 99, "Z", 0.1)
    with pytest.raises(QGModelError):
        link_rotation(lat, 0, "Y", 0.1)
    with pytest.raises(QGModelError):
        apply_link_z_error(uniform_plus_state(lat), lat, 0, 1.5)
    with pytest.raises(QGModelError):
        leakage_under_evolution(lat, uniform_plus_state(lat), 1.0, perturbation="bogus")
    with pytest.raises(QGModelError):
        leakage_under_evolution(lat, uniform_plus_state(lat), float("nan"))


def test_leakage_result_carries_limitations_without_gravity_claim():
    lat = Z2Lattice(1, 1)
    row = leakage_under_evolution(lat, uniform_plus_state(lat), 0.5)
    assert row["surface"] == "CLASSICAL_REFERENCE"
    assert "not a quantum-gravity result" in " ".join(row["limitations"])
