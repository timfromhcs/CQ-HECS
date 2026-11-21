"""Track B tests: Majorana algebra, seeded SYK spectrum and evolution oracles.

Independent oracles: (1) a dense Majorana-matrix product built directly from the couplings,
which shares no code with the Pauli-string construction in ``hamiltonians.py``;
(2) Qiskit ``SparsePauliOp`` when available; (3) SciPy ``expm`` vs an eigen-decomposition
evolution.
"""

from __future__ import annotations

import numpy as np
import pytest

from cqhecs.quantum_gravity.errors import QGModelError, QGResourceError
from cqhecs.quantum_gravity.fermions import (
    majorana_labels,
    majorana_operators,
    pauli_multiply,
    validate_majorana_algebra,
)
from cqhecs.quantum_gravity.hamiltonians import build_syk
from cqhecs.quantum_gravity.references import (
    evolve_state,
    evolve_state_eigendecomposition,
    exact_evolution_operator,
    loschmidt_amplitude,
    trotter_error_scan,
)


def test_pauli_multiplication_rules():
    phase, label = pauli_multiply("X", "Y")
    assert label == "Z" and abs(phase - 1j) < 1e-12
    phase, label = pauli_multiply("Y", "X")
    assert label == "Z" and abs(phase + 1j) < 1e-12
    phase, label = pauli_multiply("Z", "Z")
    assert label == "I" and abs(phase - 1.0) < 1e-12


def test_majorana_labels_shape():
    labels = majorana_labels(3)
    assert labels == ["XII", "YII", "ZXI", "ZYI", "ZZX", "ZZY"]


@pytest.mark.parametrize("num_qubits", [1, 2, 3, 4])
def test_majorana_algebra(num_qubits):
    residual = validate_majorana_algebra(num_qubits)
    assert residual < 1e-10


def test_majorana_operators_hermitian():
    for op in majorana_operators(3):
        assert np.allclose(op, op.conj().T, atol=1e-12)


def _independent_hamiltonian(syk):
    ops = majorana_operators(syk.num_qubits)
    dim = 2 ** syk.num_qubits
    norm = float(np.sqrt(syk.total_terms)) if (syk.normalize and syk.total_terms) else 1.0
    ham = np.zeros((dim, dim), dtype=complex)
    for combo, coupling in syk.couplings.items():
        mat = np.eye(dim, dtype=complex)
        for idx in combo:
            mat = mat @ ops[idx]
        ham += (coupling / norm) * mat
    return ham


@pytest.mark.parametrize("num_qubits", [2, 3, 4])
def test_hamiltonian_matches_independent_majorana_product(num_qubits):
    syk = build_syk(num_qubits, seed=7, scale=0.6)
    ham = syk.matrix()
    assert np.allclose(ham, _independent_hamiltonian(syk), atol=1e-10)
    assert np.allclose(ham, ham.conj().T, atol=1e-10)


@pytest.mark.parametrize("num_qubits", [2, 3, 4])
def test_spectrum_matches_independent_spectrum(num_qubits):
    syk = build_syk(num_qubits, seed=11, scale=0.8)
    ours = np.sort(syk.spectrum())
    theirs = np.sort(np.linalg.eigvalsh(_independent_hamiltonian(syk)))
    assert np.allclose(ours, theirs, atol=1e-9)


def test_spectrum_matches_qiskit_oracle():
    pytest.importorskip("qiskit")
    from qiskit.quantum_info import SparsePauliOp

    syk = build_syk(3, seed=5, scale=0.7)
    # Qiskit labels are little-endian: rightmost char = qubit 0, so reverse our label.
    op = SparsePauliOp.from_list([(label[::-1], coeff) for label, coeff in syk._pauli.items()])
    theirs = np.sort(np.linalg.eigvalsh(op.to_matrix()))
    assert np.allclose(np.sort(syk.spectrum()), theirs, atol=1e-9)


@pytest.mark.parametrize("num_qubits", [2, 3, 4])
def test_parity_commutes_with_hamiltonian(num_qubits):
    syk = build_syk(num_qubits, seed=3, scale=0.9)
    assert syk.parity_commutation_residual() < 1e-10


def test_seed_is_reproducible():
    a = build_syk(4, seed=42, scale=0.5)
    b = build_syk(4, seed=42, scale=0.5)
    c = build_syk(4, seed=43, scale=0.5)
    assert a.manifest()["couplings_sha256"] == b.manifest()["couplings_sha256"]
    assert a.manifest()["couplings_sha256"] != c.manifest()["couplings_sha256"]


def test_sparsification_reports_fraction_and_changes_model():
    full = build_syk(4, seed=1, scale=0.5)
    sparse = build_syk(4, seed=1, scale=0.5, num_terms=10)
    assert full.kept_weight_fraction == 1.0
    assert sparse.kept_weight_fraction < 1.0
    assert sparse.kept_terms == 10
    # sparsification is a different model, not a bounded approximation
    assert not np.allclose(np.sort(full.spectrum()), np.sort(sparse.spectrum()))


def test_dense_ceiling_is_enforced():
    syk = build_syk(9, seed=1, scale=0.5)
    with pytest.raises(QGResourceError):
        syk.matrix()


def test_invalid_order_rejected():
    with pytest.raises(QGModelError):
        build_syk(3, seed=1, q=3)


def test_evolution_routes_agree_and_preserve_norm():
    syk = build_syk(3, seed=9, scale=0.5)
    ham = syk.matrix()
    dim = ham.shape[0]
    rng = np.random.default_rng(0)
    psi0 = rng.normal(size=dim) + 1j * rng.normal(size=dim)
    psi0 /= np.linalg.norm(psi0)
    t = 1.3
    a = evolve_state(ham, t, psi0)
    b = evolve_state_eigendecomposition(ham, t, psi0)
    assert np.allclose(a, b, atol=1e-10)
    assert abs(np.linalg.norm(a) - 1.0) < 1e-10
    # evolution operator is unitary
    u = exact_evolution_operator(ham, t)
    assert np.allclose(u @ u.conj().T, np.eye(dim), atol=1e-10)


def test_loschmidt_amplitude_bounded():
    syk = build_syk(3, seed=2, scale=0.6)
    ham = syk.matrix()
    dim = ham.shape[0]
    psi0 = np.zeros(dim, dtype=complex)
    psi0[-1] = 1.0
    for t in [0.0, 0.5, 1.0, 2.0]:
        amp = loschmidt_amplitude(ham, t, psi0)
        assert abs(amp) <= 1.0 + 1e-9


def test_trotter_error_decreases_with_steps():
    syk = build_syk(3, seed=4, scale=0.4)
    ham = syk.matrix()
    terms = syk.hermitian_terms()
    assert np.allclose(sum(terms), ham, atol=1e-10)
    dim = ham.shape[0]
    psi0 = np.zeros(dim, dtype=complex)
    psi0[0] = 1.0
    scan = trotter_error_scan(ham, terms, t=1.0, psi0=psi0, steps_list=[1, 2, 4, 8])
    errors = [row["l2_error"] for row in scan]
    assert errors[0] > errors[-1]
    assert errors[-1] < errors[0]
