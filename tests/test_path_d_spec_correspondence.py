"""Path D stored-basis algebra vs the Lean specification (formal/CQHECS/Pauli.lean, Bound.lean).

Assurance level: tests, not a refinement proof. Lean proves `pauli_mul`, `pauli_comm` and the
truncation bounds `truncation_bound` / `expectation_truncation_bound` as specification statements;
this file checks numerically, against dense matrices and Qiskit/Stim where installed, that the
shipped Path D code uses the same conventions and honours the same inequality.
"""

from __future__ import annotations

import itertools
import math
import random

import numpy as np
import pytest

from cqhecs.backends import path_d_sparse_pauli as pd
from cqhecs.backends.path_d_sparse_pauli import (
    PAULI_BASIS,
    PathDSparsePauliBackend,
    conjugation_matrix,
    pauli_observable_from_ops,
)

BASIS = pd._basis_matrices()
INDEX = {xz: i for i, xz in enumerate(PAULI_BASIS)}


def stored(a: int, b: int) -> np.ndarray:
    return BASIS[INDEX[(a, b)]]


@pytest.mark.parametrize("a,b,c,d", list(itertools.product((0, 1), repeat=4)))
def test_pauli_mul_rule(a, b, c, d):
    """Lean `pauli_mul`: (X^a Z^b)(X^c Z^d) = (-1)^(bc) X^(a+c) Z^(b+d)."""
    lhs = stored(a, b) @ stored(c, d)
    rhs = (-1.0) ** (b & c) * stored(a ^ c, b ^ d)
    assert np.allclose(lhs, rhs)


@pytest.mark.parametrize("a,b,c,d", list(itertools.product((0, 1), repeat=4)))
def test_pauli_comm_rule(a, b, c, d):
    """Lean `pauli_comm`: P(a,b)P(c,d) = (-1)^(ad+bc) P(c,d)P(a,b)."""
    lhs = stored(a, b) @ stored(c, d)
    rhs = (-1.0) ** ((a & d) ^ (b & c)) * (stored(c, d) @ stored(a, b))
    assert np.allclose(lhs, rhs)


def test_hermitian_letter_convention_matches_observable_coeff():
    """Lean `herm a b = i^(ab) X^a Z^b`: Path D's observable coeff must be i^(#Y)."""
    pauli = {"X": np.array([[0, 1], [1, 0]]), "Z": np.diag([1, -1]),
             "Y": np.array([[0, -1j], [1j, 0]])}
    for letter in "XYZ":
        obs = pauli_observable_from_ops("o", [(0, letter)])
        mat = obs.coeff * stored(obs.x_mask & 1, obs.z_mask & 1)
        assert np.allclose(mat, pauli[letter]), letter
        assert abs(obs.coeff) == pytest.approx(1.0)


def _herm(x, z):
    return {(0, 0): np.eye(2), (1, 0): BASIS[1], (0, 1): BASIS[3],
            (1, 1): np.array([[0, -1j], [1j, 0]])}[(x, z)]


GATE_UNITARY = pd._single_qubit_gate_matrices()


@pytest.mark.parametrize("gate", ["h", "s", "sdg", "x", "y", "z", "t", "tdg"])
def test_conjugation_matrix_is_the_heisenberg_update_on_every_stored_basis_element(gate):
    """Path D's `conjugation_matrix(U)` gives U^dag P U in the stored basis (no Lean statement
    for T; checked against dense algebra for every supported fixed gate)."""
    u = GATE_UNITARY[gate]
    m = conjugation_matrix(u)
    for j, pj in enumerate(BASIS):
        expect = u.conj().T @ pj @ u
        got = sum(m[k, j] * BASIS[k] for k in range(4))
        assert np.allclose(got, expect), (gate, j)


@pytest.mark.parametrize("gate", ["h", "x", "y", "z"])
@pytest.mark.parametrize("a,b", list(itertools.product((0, 1), repeat=2)))
def test_clifford_sign_rules_match_lean_statements_through_path_d(gate, a, b):
    """For self-inverse Cliffords, U^dag Q U = U Q U^dag, so Path D's matrix must reproduce the
    Lean rules h_conj/x_conj/y_conj/z_conj on Hermitian letters."""
    sgn = lambda c: -1.0 if c else 1.0  # noqa: E731
    expected = {
        "h": sgn(a & b) * _herm(b, a),
        "x": sgn(b) * _herm(a, b),
        "y": sgn(a ^ b) * _herm(a, b),
        "z": sgn(a) * _herm(a, b),
    }[gate]
    # Express the Hermitian letter in the stored basis (Y = i X Z), conjugate, convert back.
    coeff = 1j if (a & b) else 1.0
    vec = np.zeros(4, dtype=complex)
    vec[INDEX[(a, b)]] = coeff
    out = conjugation_matrix(GATE_UNITARY[gate]) @ vec
    got = sum(out[k] * BASIS[k] for k in range(4))
    assert np.allclose(got, expected)


# --- Bound spec (Lean `expectation_truncation_bound`, `truncation_bound`) ----------------------

def test_lean_truncation_inequality_holds_for_random_coefficients():
    rng = np.random.default_rng(3)
    for _ in range(200):
        k = int(rng.integers(1, 20))
        c = rng.normal(size=k)
        e = rng.uniform(-1, 1, size=k)  # |<P>| <= 1 is the only physics input
        assert abs(np.sum(c * e)) <= np.sum(np.abs(c)) + 1e-12
        assert abs(np.sum(c)) <= np.sum(np.abs(c)) + 1e-12


def _dense_expectation(instructions, n, ops):
    qiskit = pytest.importorskip("qiskit")
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Pauli, Statevector

    qc = QuantumCircuit(n)
    for name, qubits, params in instructions:
        getattr(qc, name)(*params, *qubits)
    letters = ["I"] * n
    for q, letter in ops:
        letters[q] = letter
    del qiskit
    return float(Statevector(qc).expectation_value(Pauli("".join(reversed(letters)))).real)


@pytest.mark.parametrize("seed", range(8))
def test_certified_bound_covers_true_error_under_truncation(seed):
    """The shipped per-observable bound is the discarded coefficient mass; true error must be
    inside it (the property Lean proves in real arithmetic)."""
    rng = random.Random(900 + seed)
    n = 4
    instr = []
    for _ in range(14):
        if rng.random() < 0.3:
            a, b = rng.sample(range(n), 2)
            instr.append((rng.choice(["cx", "cz"]), [a, b], []))
        else:
            instr.append((rng.choice(["rx", "ry", "rz"]), [rng.randrange(n)],
                          [rng.uniform(-math.pi, math.pi)]))
    ops = tuple((q, rng.choice("XYZ")) for q in sorted(rng.sample(range(n), 3)))
    exact = _dense_expectation(instr, n, ops)
    backend = PathDSparsePauliBackend(max_pauli_terms=12, prune_threshold=0.0, error_tolerance=10.0)
    obs = pauli_observable_from_ops("o", ops)
    res = backend.evaluate_paulis(instr, n, [obs])["o"]
    assert res.resolved
    assert abs(res.value - exact) <= res.error_bound + 1e-9
