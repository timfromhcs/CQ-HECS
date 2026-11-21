"""Track C tests: bounded Z2 lattice gauge toy model (QG-GAUGE-01)."""

from __future__ import annotations

import numpy as np
import pytest

from cqhecs.quantum_gravity.errors import QGResourceError
from cqhecs.quantum_gravity.gauge import Z2Lattice, gauss_law_satisfied


def test_1x1_lattice_topology():
    lattice = Z2Lattice(1, 1)
    assert lattice.num_links == 4
    assert lattice.num_vertices == 4
    assert sorted(lattice.plaquette_links(0, 0)) == [0, 1, 2, 3]


@pytest.mark.parametrize("rows,cols", [(1, 1), (1, 2), (2, 1)])
def test_hamiltonian_commutes_with_gauss_generators(rows, cols):
    lattice = Z2Lattice(rows, cols)
    assert lattice.commutation_residuals()["max_commutator"] < 1e-9


def test_plaquette_and_gauss_operators_are_involutions():
    lattice = Z2Lattice(1, 1)
    dim = 2 ** lattice.num_links
    identity = np.eye(dim, dtype=complex)
    for _, b in lattice.plaquette_operators():
        assert np.allclose(b @ b, identity, atol=1e-12)
    for _, g in lattice.gauss_generators():
        assert np.allclose(g @ g, identity, atol=1e-12)


def test_gauss_generators_mutually_commute():
    lattice = Z2Lattice(1, 2)
    gens = [g for _, g in lattice.gauss_generators()]
    for a, b in _pairs(gens):
        assert np.allclose(a @ b, b @ a, atol=1e-12)


def test_hamiltonian_spectrum_is_integer():
    lattice = Z2Lattice(1, 2)
    spectrum = np.linalg.eigvalsh(lattice.hamiltonian())
    assert np.allclose(spectrum, np.round(spectrum), atol=1e-9)


def test_gauge_invariant_subspace_is_preserved():
    lattice = Z2Lattice(1, 1)
    dim = 2 ** lattice.num_links
    projector = np.eye(dim, dtype=complex)
    for _, g in lattice.gauss_generators():
        projector = projector @ ((np.eye(dim, dtype=complex) + g) / 2.0)
    rng = np.random.default_rng(0)
    psi = rng.normal(size=dim) + 1j * rng.normal(size=dim)
    invariant = projector @ psi
    invariant /= np.linalg.norm(invariant)
    assert gauss_law_satisfied(invariant, lattice)
    # the Hamiltonian maps the physical subspace to itself
    assert gauss_law_satisfied(lattice.hamiltonian() @ invariant, lattice)


def test_link_ceiling_is_enforced():
    with pytest.raises(QGResourceError):
        Z2Lattice(2, 2)  # 12 links > 8


def test_manifest_lists_limitations():
    manifest = Z2Lattice(1, 1).manifest()
    assert manifest["model_id"] == "qg.gauge.z2.v1"
    assert any("not a quantum-gravity result" in item for item in manifest["limitations"])


def _pairs(items):
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            yield items[i], items[j]
