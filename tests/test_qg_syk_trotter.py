"""W8: SYK Majorana algebra, seeded reference, Trotter/QASM mapping oracle and error table."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm

from cqhecs.quantum_gravity.errors import QGModelError, QGResourceError
from cqhecs.quantum_gravity.fermions import majorana_labels, majorana_operators, pauli_matrix
from cqhecs.quantum_gravity.hamiltonians import build_syk
from cqhecs.quantum_gravity.references import evolve_state, trotter_first_order
from cqhecs.quantum_gravity.syk_trotter import (
    anticommute,
    dense_hamiltonian,
    dense_trotter_unitary,
    equal_up_to_global_phase,
    pauli_rotation_lines,
    pauli_terms,
    qasm_dense_unitary,
    syk_mirror_qasm,
    syk_trotter_qasm,
    trotter_error_bound,
    trotter_error_table,
    trotter_qasm,
)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "research" / "qg_2026" / "models" / "syk_reference_n3_seed20260101.json"


# -- Majorana algebra (all pairs/quadruples, not just the anticommutator) -------------
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_majorana_pairwise_products_square_and_parity(n):
    ops = majorana_operators(n)
    dim = 2 ** n
    ident = np.eye(dim)
    for g in ops:
        assert np.allclose(g @ g, ident)
    # gamma_i gamma_j (i != j) is anti-Hermitian with square -1
    for i, j in itertools.combinations(range(2 * n), 2):
        prod = ops[i] @ ops[j]
        assert np.allclose(prod.conj().T, -prod)
        assert np.allclose(prod @ prod, -ident)


@pytest.mark.parametrize("n", [2, 3])
def test_distinct_majorana_quadruples_are_hermitian_with_real_pauli_phase(n):
    ops = majorana_operators(n)
    for combo in itertools.combinations(range(2 * n), 4):
        mat = np.eye(2 ** n, dtype=complex)
        for idx in combo:
            mat = mat @ ops[idx]
        assert np.allclose(mat, mat.conj().T)
    syk = build_syk(n, seed=3, scale=0.5)
    for label, coeff in pauli_terms(syk):
        assert isinstance(coeff, float)
        assert len(label) == n


def test_jordan_wigner_total_parity_is_pauli_z_string():
    n = 3
    labels = majorana_labels(n)
    prod = np.eye(2 ** n, dtype=complex)
    for lab in labels:
        prod = prod @ pauli_matrix(lab)
    # i^n * prod gamma = (+-) Z...Z : check it is proportional to a Z-string with unit modulus
    zz = pauli_matrix("Z" * n)
    ratio = prod[0, 0] / zz[0, 0]
    assert abs(abs(ratio) - 1.0) < 1e-12
    assert np.allclose(prod, ratio * zz)


# -- seeded small reference (frozen) ---------------------------------------------------
def _golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_seeded_reference_matches_frozen_golden_values():
    golden = _golden()
    syk = build_syk(golden["num_qubits"], seed=golden["seed"], scale=golden["scale"])
    assert syk.kept_terms == golden["kept_terms"]
    for combo_text, value in golden["couplings"].items():
        combo = tuple(int(x) for x in combo_text.split(","))
        assert syk.couplings[combo] == pytest.approx(value, abs=1e-12)
    assert np.allclose(syk.spectrum(), golden["spectrum"], atol=1e-10)


def test_golden_spectrum_matches_independent_dense_majorana_product():
    """Rebuild H from the *stored* couplings with plain dense Majorana products (no Pauli bookkeeping)."""
    golden = _golden()
    n = golden["num_qubits"]
    ops = majorana_operators(n)
    ham = np.zeros((2 ** n, 2 ** n), dtype=complex)
    for combo_text, value in golden["couplings"].items():
        combo = tuple(int(x) for x in combo_text.split(","))
        mat = np.eye(2 ** n, dtype=complex)
        for idx in combo:
            mat = mat @ ops[idx]
        ham += value * mat
    assert np.allclose(np.linalg.eigvalsh(ham), golden["spectrum"], atol=1e-10)


def test_golden_p000_values_match_documented_historical_ideals():
    golden = _golden()
    syk = build_syk(golden["num_qubits"], seed=golden["seed"], scale=golden["scale"])
    psi = np.zeros(2 ** golden["num_qubits"], dtype=complex)
    psi[0] = 1.0
    exact = evolve_state(syk.matrix(), golden["t"], psi)
    assert abs(exact[0]) ** 2 == pytest.approx(golden["p000_exact"], abs=1e-9)
    assert abs(exact[0]) ** 2 == pytest.approx(0.4280170238029712, abs=1e-9)  # QPU_SYK.md v1 "ideal"
    trot = trotter_first_order(syk.hermitian_terms(), golden["t"], 1, psi)
    assert abs(trot[0]) ** 2 == pytest.approx(0.23258429030050012, abs=1e-9)  # QPU_SYK.md v3 ideal


# -- QASM compilation oracle ------------------------------------------------------------
@pytest.mark.parametrize(
    "label",
    ["Z", "X", "Y", "ZZ", "XX", "YY", "XY", "YZ", "XZY", "IXI", "ZIZ", "YXXY", "XIIY"],
)
def test_pauli_rotation_compiles_to_matrix_exponential(label):
    n = len(label)
    phi = 0.37
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];"] + pauli_rotation_lines(label, phi)
    got = qasm_dense_unitary("\n".join(lines) + "\n")
    want = expm(-1j * phi * pauli_matrix(label))
    assert equal_up_to_global_phase(got, want), label
    assert np.allclose(got, want, atol=1e-9), f"{label}: not exact (global phase changed)"


def test_identity_term_emits_no_gates():
    assert pauli_rotation_lines("III", 1.3) == []


@pytest.mark.parametrize("n,seed,steps", [(2, 5, 1), (3, 20260101, 1), (3, 20260101, 3), (3, 9, 2), (4, 4, 1)])
def test_syk_trotter_qasm_equals_dense_trotter_product(n, seed, steps):
    syk = build_syk(n, seed=seed, scale=0.4)
    t = 0.8
    qasm = syk_trotter_qasm(syk, t, steps)
    got = qasm_dense_unitary(qasm)
    want = dense_trotter_unitary(pauli_terms(syk), n, t, steps)
    assert np.allclose(got, want, atol=1e-8)


def test_trotter_dense_product_matches_references_module():
    syk = build_syk(3, seed=20260101, scale=0.4)
    psi = np.zeros(8, dtype=complex)
    psi[0] = 1.0
    ours = dense_trotter_unitary(pauli_terms(syk), 3, 1.0, 2) @ psi
    theirs = trotter_first_order(syk.hermitian_terms(), 1.0, 2, psi)
    assert np.allclose(ours, theirs, atol=1e-10)


def test_dense_hamiltonian_matches_syk_matrix():
    syk = build_syk(3, seed=11, scale=0.7)
    assert np.allclose(dense_hamiltonian(pauli_terms(syk), 3), syk.matrix(), atol=1e-10)


def test_mirror_circuit_returns_to_start_exactly():
    syk = build_syk(3, seed=20260101, scale=0.4)
    for steps in (1, 2):
        unitary = qasm_dense_unitary(syk_mirror_qasm(syk, 1.0, steps))
        assert np.allclose(unitary, np.eye(8), atol=1e-8)


def test_mirror_is_not_trivially_identity_when_only_forward_is_run():
    syk = build_syk(3, seed=20260101, scale=0.4)
    forward = qasm_dense_unitary(syk_trotter_qasm(syk, 1.0, 1))
    assert not np.allclose(forward, np.eye(8), atol=1e-3)


def test_wrong_term_order_is_detected_by_the_oracle():
    """Mutation check: swapping two non-commuting terms changes the unitary, so the oracle can fail."""
    syk = build_syk(3, seed=20260101, scale=0.4)
    terms = pauli_terms(syk)
    pair = next(
        (i, j)
        for i in range(len(terms))
        for j in range(i + 1, len(terms))
        if anticommute(terms[i][0], terms[j][0])
    )
    swapped = list(terms)
    swapped[pair[0]], swapped[pair[1]] = swapped[pair[1]], swapped[pair[0]]
    a = dense_trotter_unitary(terms, 3, 1.0, 1)
    b = dense_trotter_unitary(swapped, 3, 1.0, 1)
    assert not np.allclose(a, b, atol=1e-6)


def test_measurement_variant_has_terminal_measure_only():
    syk = build_syk(2, seed=1)
    text = syk_trotter_qasm(syk, 0.5, 1, measure=True)
    assert text.strip().endswith("measure q -> c;")
    assert text.count("measure") == 1 and "creg c[2];" in text


# -- Trotter error table ----------------------------------------------------------------
def test_error_table_bound_holds_and_error_decays_with_steps():
    syk = build_syk(3, seed=20260101, scale=0.4)
    table = trotter_error_table(syk, 1.0, (1, 2, 4, 8, 16, 32))
    rows = table["rows"]
    assert all(row["bound_holds"] for row in rows)
    errors = [row["measured_spectral_error"] for row in rows]
    assert all(a > b for a, b in zip(errors, errors[1:]))
    # first-order: doubling steps roughly halves the error in the asymptotic regime
    assert 1.6 < errors[-2] / errors[-1] < 2.4
    bounds = [row["bound"] for row in rows]
    assert bounds[0] == pytest.approx(bounds[1] * 2.0)
    assert table["uncertainty_class"] == "trotter_error"
    assert table["surface"] == "CLASSICAL_REFERENCE"


def test_error_table_exact_and_trotter_p_zero_match_historical_ideals():
    syk = build_syk(3, seed=20260101, scale=0.4)
    rows = {r["steps"]: r for r in trotter_error_table(syk, 1.0, (1, 4))["rows"]}
    assert rows[1]["p_zero_exact"] == pytest.approx(0.4280170238029712, abs=1e-9)
    assert rows[1]["p_zero_trotter"] == pytest.approx(0.23258429030050012, abs=1e-9)
    assert abs(rows[4]["p_zero_trotter"] - rows[1]["p_zero_exact"]) < abs(
        rows[1]["p_zero_trotter"] - rows[1]["p_zero_exact"]
    )


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_bound_holds_across_seeds(seed):
    syk = build_syk(3, seed=seed, scale=0.5)
    for row in trotter_error_table(syk, 0.9, (1, 3, 6))["rows"]:
        assert row["bound_holds"], (seed, row)


def test_bound_is_zero_for_commuting_terms():
    terms = [("ZZI", 0.4), ("IZZ", -0.3), ("ZIZ", 0.2)]
    assert trotter_error_bound(terms, 2.0, 1) == 0.0
    exact = expm(-1j * 2.0 * dense_hamiltonian(terms, 3))
    assert np.allclose(dense_trotter_unitary(terms, 3, 2.0, 1), exact, atol=1e-10)


def test_table_limitations_exclude_gravity_claims():
    table = trotter_error_table(build_syk(2, seed=1), 0.5, (1,))
    text = " ".join(table["limitations"]).lower()
    assert "finite-n" in text and "no spacetime" in text


def test_bad_inputs_are_refused():
    with pytest.raises(QGModelError):
        trotter_qasm([("ZZ", 1.0)], 2, 1.0, 0)
    with pytest.raises(QGModelError):
        trotter_qasm([("ZZ", 1.0)], 2, float("nan"), 1)
    with pytest.raises(QGModelError):
        trotter_qasm([("ZZZ", 1.0)], 2, 1.0, 1)
    with pytest.raises(QGModelError):
        anticommute("XX", "X")
    with pytest.raises(QGResourceError):
        dense_hamiltonian([("Z" * 9, 1.0)], 9)


def test_mutated_basis_change_is_caught_by_the_oracle():
    """Mutation check: using S instead of S-dagger in the Y basis change must fail the oracle."""
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[2];"] + pauli_rotation_lines("YZ", 0.37)
    good = qasm_dense_unitary("\n".join(lines) + "\n")
    bad = qasm_dense_unitary("\n".join(lines).replace("sdg", "s") + "\n")
    want = expm(-1j * 0.37 * pauli_matrix("YZ"))
    assert np.allclose(good, want, atol=1e-9)
    assert not np.allclose(bad, want, atol=1e-6)


def _close(a, b, tol=1e-9):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, float):
        return abs(a - b) <= tol
    return a == b


def test_frozen_error_table_matches_regeneration():
    stored = json.loads(
        (ROOT / "research" / "qg_2026" / "models" / "syk_trotter_error_table_n3_seed20260101.json").read_text(encoding="utf-8")
    )
    fresh = json.loads(json.dumps(trotter_error_table(build_syk(3, seed=20260101, scale=0.4), 1.0, (1, 2, 4, 8, 16, 32))))
    assert _close(stored, fresh)
