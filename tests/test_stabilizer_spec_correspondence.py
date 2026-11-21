"""Path A tableau vs the Lean specification (formal/CQHECS/Stabilizer.lean, Pauli.lean).

Assurance level: these are *tests*, not a refinement proof. Lean proves the specification
statements (symplectic-form invariance of the bit update, single-qubit sign rules); these tests
check, with independent oracles (dense matrices, Stim), that the NumPy tableau implements the same
rules on sampled inputs. A pass here does not formally link the two.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from cqhecs.backends.path_a_stabilizer import StabilizerTableauSimulator as Tab

GATES_1Q = ["h", "s", "sdg", "x", "y", "z"]
GATES_2Q = ["cx", "cz", "swap"]

I2 = np.eye(2, dtype=complex)
PX = np.array([[0, 1], [1, 0]], dtype=complex)
PY = np.array([[0, -1j], [1j, 0]], dtype=complex)
PZ = np.array([[1, 0], [0, -1]], dtype=complex)
HAD = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
SG = np.diag([1, 1j]).astype(complex)
SDG = np.diag([1, -1j]).astype(complex)
P0 = np.diag([1, 0]).astype(complex)
P1 = np.diag([0, 1]).astype(complex)
ONE_Q = {"h": HAD, "s": SG, "sdg": SDG, "x": PX, "y": PY, "z": PZ}


def herm(x: int, z: int) -> np.ndarray:
    """Hermitian letter i^(xz) X^x Z^z (Lean `herm`): I, X, Z, Y."""
    return {(0, 0): I2, (1, 0): PX, (0, 1): PZ, (1, 1): PY}[(x, z)]


def embed1(m: np.ndarray, q: int, n: int) -> np.ndarray:
    out = np.eye(1, dtype=complex)
    for k in range(n):
        out = np.kron(out, m if k == q else I2)
    return out


def full_gate(name: str, qubits: list[int], n: int) -> np.ndarray:
    if name in ONE_Q:
        return embed1(ONE_Q[name], qubits[0], n)
    a, b = qubits
    if name == "cx":
        return embed1(P0, a, n) + embed1(P1, a, n) @ embed1(PX, b, n)
    if name == "cz":
        return embed1(P0, a, n) + embed1(P1, a, n) @ embed1(PZ, b, n)
    if name == "swap":
        return 0.5 * (
            embed1(I2, 0, n)
            + embed1(PX, a, n) @ embed1(PX, b, n)
            + embed1(PY, a, n) @ embed1(PY, b, n)
            + embed1(PZ, a, n) @ embed1(PZ, b, n)
        )
    raise AssertionError(name)


def apply(sim: Tab, name: str, qubits: list[int]) -> None:
    getattr(sim, f"apply_{name}")(*qubits)


def random_circuit(rng: random.Random, n: int, depth: int):
    ops = []
    for _ in range(depth):
        if n >= 2 and rng.random() < 0.45:
            a, b = rng.sample(range(n), 2)
            ops.append((rng.choice(GATES_2Q), [a, b]))
        else:
            ops.append((rng.choice(GATES_1Q), [rng.randrange(n)]))
    return ops


def row_pauli(sim: Tab, row: int) -> np.ndarray:
    """Dense matrix of tableau row: (-1)^r * tensor of Hermitian letters."""
    n = sim.n
    out = np.eye(1, dtype=complex)
    for k in range(n):
        out = np.kron(out, herm(int(sim.tableau[row, k]), int(sim.tableau[row, n + k])))
    return (-1.0) ** int(sim.tableau[row, 2 * n]) * out


def omega(sim: Tab, r1: int, r2: int) -> int:
    n = sim.n
    x1, z1 = sim.tableau[r1, :n].astype(int), sim.tableau[r1, n : 2 * n].astype(int)
    x2, z2 = sim.tableau[r2, :n].astype(int), sim.tableau[r2, n : 2 * n].astype(int)
    return int((x1 @ z2 + z1 @ x2) % 2)


# --- Lean local rules, restated independently (formal/CQHECS/Stabilizer.lean) ----------------

def lean_bits(name: str, qubits: list[int], x: np.ndarray, z: np.ndarray) -> None:
    """In-place bit update per the Lean model (hLoc, sLoc, cxLoc, swap); X/Y/Z leave bits alone."""
    if name == "h":
        q = qubits[0]
        x[:, q], z[:, q] = z[:, q].copy(), x[:, q].copy()
    elif name == "s":
        q = qubits[0]
        z[:, q] ^= x[:, q]
    elif name == "sdg":
        for _ in range(3):
            lean_bits("s", qubits, x, z)
    elif name == "cx":
        c, t = qubits
        xc, zt = x[:, c].copy(), z[:, t].copy()
        x[:, t] ^= xc
        z[:, c] ^= zt
    elif name == "cz":
        c, t = qubits
        lean_bits("h", [t], x, z)
        lean_bits("cx", [c, t], x, z)
        lean_bits("h", [t], x, z)
    elif name == "swap":
        a, b = qubits
        x[:, [a, b]] = x[:, [b, a]]
        z[:, [a, b]] = z[:, [b, a]]


@pytest.mark.parametrize("name,qubits", [(g, [1]) for g in GATES_1Q] + [("cx", [1, 3]), ("cz", [3, 0]), ("swap", [0, 2])])
def test_bit_update_matches_the_lean_local_rule_on_arbitrary_rows(name, qubits):
    """The Lean model is a statement about arbitrary row bits, so test arbitrary (even invalid) rows."""
    n = 4
    rng = np.random.default_rng(7)
    for _ in range(25):
        sim = Tab(n)
        sim.tableau[: 2 * n, : 2 * n] = rng.integers(0, 2, size=(2 * n, 2 * n), dtype=np.uint8)
        x = sim.tableau[: 2 * n, :n].astype(np.uint8).copy()
        z = sim.tableau[: 2 * n, n : 2 * n].astype(np.uint8).copy()
        lean_bits(name, qubits, x, z)
        apply(sim, name, qubits)
        assert np.array_equal(sim.tableau[: 2 * n, :n], x), name
        assert np.array_equal(sim.tableau[: 2 * n, n : 2 * n], z), name


@pytest.mark.parametrize("seed", range(12))
def test_symplectic_form_is_invariant_over_whole_circuits(seed):
    """L-STAB-01 `omega_run` / `tableau_invariant`: D/S relations persist for every row pair."""
    rng = random.Random(seed)
    n = rng.randint(2, 6)
    sim = Tab(n)
    initial = {(a, b): omega(sim, a, b) for a in range(2 * n) for b in range(2 * n)}
    # initial relations are exactly the Lean ones: omega(D_i, S_j) = [i == j], others zero
    for i in range(n):
        for j in range(n):
            assert initial[(i, n + j)] == (1 if i == j else 0)
            assert initial[(n + i, n + j)] == 0 and initial[(i, j)] == 0
    for name, qubits in random_circuit(rng, n, 40):
        apply(sim, name, qubits)
        for a in range(2 * n):
            for b in range(2 * n):
                assert omega(sim, a, b) == initial[(a, b)], (name, qubits)


@pytest.mark.parametrize("seed", range(10))
def test_rows_with_signs_equal_dense_conjugation(seed):
    """Row (x,z,r) = (-1)^r * letters must equal U P0 U^dagger (single-qubit sign rules in Pauli.lean
    plus the CX/CZ/SWAP sign behaviour that Lean does not prove)."""
    rng = random.Random(100 + seed)
    n = rng.randint(1, 3)
    sim = Tab(n)
    u = np.eye(2**n, dtype=complex)
    for name, qubits in random_circuit(rng, n, 25):
        apply(sim, name, qubits)
        u = full_gate(name, qubits, n) @ u
    for k in range(n):
        assert np.allclose(row_pauli(sim, k), u @ embed1(PX, k, n) @ u.conj().T)
        assert np.allclose(row_pauli(sim, n + k), u @ embed1(PZ, k, n) @ u.conj().T)


@pytest.mark.parametrize("gate", GATES_1Q)
@pytest.mark.parametrize("letter", [(0, 0), (1, 0), (0, 1), (1, 1)])
def test_single_qubit_sign_table_matches_dense_and_lean_statements(gate, letter):
    """h_conj/s_conj/x_conj/y_conj/z_conj: U Q(a,b) U^dagger = sign * Q(a',b') on dense matrices."""
    a, b = letter
    u = ONE_Q[gate]
    out = u @ herm(a, b) @ u.conj().T
    sgn = lambda c: -1.0 if c else 1.0  # noqa: E731
    expected = {
        "h": sgn(a & b) * herm(b, a),
        "s": sgn(a & b) * herm(a, a ^ b),
        "x": sgn(b) * herm(a, b),
        "z": sgn(a) * herm(a, b),
        "y": sgn(a ^ b) * herm(a, b),
    }
    if gate == "sdg":
        # inverse of s: sdg Q(a,c) s = (-1)^(a & ~c) Q(a, a^c)
        expected["sdg"] = sgn(a & (1 - b)) * herm(a, a ^ b)
    assert np.allclose(out, expected[gate])


# --- Stim cross-check (independent implementation) ---------------------------------------------

stim = pytest.importorskip("stim")
STIM_NAME = {"h": "H", "s": "S", "sdg": "S_DAG", "x": "X", "y": "Y", "z": "Z", "cx": "CX", "cz": "CZ", "swap": "SWAP"}


@pytest.mark.parametrize("seed", range(10))
def test_all_rows_including_signs_match_stim_tableau(seed):
    rng = random.Random(500 + seed)
    n = rng.randint(2, 7)
    sim = Tab(n)
    circ = stim.Circuit()
    for name, qubits in random_circuit(rng, n, 60):
        apply(sim, name, qubits)
        circ.append(STIM_NAME[name], qubits)
    tab = stim.Tableau.from_circuit(circ)

    def check(row: int, ps: "stim.PauliString") -> None:
        sign = -1 if int(sim.tableau[row, 2 * n]) else 1
        assert sign == ps.sign.real, (row, ps)
        for k in range(n):
            letter = ps[k]  # 0=I 1=X 2=Y 3=Z
            x, z = int(sim.tableau[row, k]), int(sim.tableau[row, n + k])
            assert (x, z) == {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}[letter], (row, k)

    for k in range(n):
        check(k, tab.x_output(k))
        check(n + k, tab.z_output(k))


def test_dropping_a_sign_update_is_caught_by_the_dense_oracle(monkeypatch):
    """Negative control: a tableau with a wrong S sign rule must fail the dense row check."""
    def bad_s(self, q):
        self.tableau[: 2 * self.n, self.n + q] ^= self.tableau[: 2 * self.n, q]  # no r update

    monkeypatch.setattr(Tab, "apply_s", bad_s)
    sim = Tab(1)
    sim.apply_s(0)
    sim.apply_s(0)  # Z-like row: S^2 = Z; destabilizer X -> -X requires the sign update
    u = SG @ SG
    assert not np.allclose(row_pauli(sim, 0), u @ PX @ u.conj().T)
