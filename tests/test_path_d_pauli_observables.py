"""Path D native X/Y/Z observables: independent oracles, phases and per-observable bounds."""

from __future__ import annotations

import itertools
import math
import random

import numpy as np
import pytest

qiskit = pytest.importorskip("qiskit")
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.quantum_info import Pauli, Statevector  # noqa: E402

from cqhecs.backends import path_d_sparse_pauli as pd  # noqa: E402
from cqhecs.backends.path_d_sparse_pauli import (  # noqa: E402
    PathDSparsePauliBackend,
    PauliObservable,
    SparsePauliDynamicsSimulator,
    pauli_observable_from_ops,
)
from cqhecs.expectation import ExpectationError, expectation_values  # noqa: E402

ONE_Q = ["h", "s", "sdg", "t", "tdg", "x", "y", "z"]
ROT = ["rx", "ry", "rz", "p"]
TWO_Q = ["cx", "cz", "swap"]


def to_qiskit(instructions, n):
    qc = QuantumCircuit(n)
    for name, qubits, params in instructions:
        getattr(qc, name)(*params, *qubits)
    return qc


def qiskit_expectation(instructions, n, ops):
    """<psi|P|psi> from Qiskit; its labels put qubit 0 on the right."""
    letters = ["I"] * n
    for q, letter in ops:
        letters[q] = letter
    label = "".join(reversed(letters))
    return float(Statevector(to_qiskit(instructions, n)).expectation_value(Pauli(label)).real)


def random_circuit(rng, n, depth):
    ops = []
    for _ in range(depth):
        kind = rng.random()
        if kind < 0.35 and n >= 2:
            a, b = rng.sample(range(n), 2)
            ops.append((rng.choice(TWO_Q), [a, b], []))
        elif kind < 0.65:
            ops.append((rng.choice(ROT), [rng.randrange(n)], [rng.uniform(-math.pi, math.pi)]))
        else:
            ops.append((rng.choice(ONE_Q), [rng.randrange(n)], []))
    return ops


def random_ops(rng, n):
    k = rng.randint(1, min(4, n))
    qubits = sorted(rng.sample(range(n), k))
    return tuple((q, rng.choice("XYZ")) for q in qubits)


def exact_backend(**kw):
    return PathDSparsePauliBackend(
        max_pauli_terms=kw.pop("max_pauli_terms", 10**6),
        prune_threshold=kw.pop("prune_threshold", 0.0),
        error_tolerance=kw.pop("error_tolerance", 10.0),
    )


def native(instructions, n, ops_list, backend=None):
    backend = backend or exact_backend()
    obs = [pauli_observable_from_ops(f"o{i}", ops) for i, ops in enumerate(ops_list)]
    out = backend.evaluate_paulis(instructions, n, obs)
    return [out[f"o{i}"] for i in range(len(ops_list))]


# --- phase and conjugation tables -----------------------------------------

def test_y_is_i_times_xz_in_the_stored_basis():
    obs = pauli_observable_from_ops("Y", [(0, "Y")])
    assert (obs.x_mask, obs.z_mask, obs.coeff) == (1, 1, 1j)
    two_y = pauli_observable_from_ops("YY", [(0, "Y"), (3, "Y")])
    assert two_y.coeff == -1  # i * i
    xz = np.array([[0, 1], [1, 0]]) @ np.array([[1, 0], [0, -1]])
    assert np.allclose(1j * xz, np.array([[0, -1j], [1j, 0]]))


@pytest.mark.parametrize("gate", ONE_Q)
@pytest.mark.parametrize("letter", "XYZ")
@pytest.mark.parametrize("prep", [(), (("h", [0], []),), (("ry", [0], [0.7]), ("s", [0], []))])
def test_single_qubit_gate_and_letter_table(gate, letter, prep):
    instructions = list(prep) + [(gate, [0], [])]
    got = native(instructions, 1, [((0, letter),)])[0]
    assert got.resolved and got.error_bound == 0.0
    assert got.value == pytest.approx(qiskit_expectation(instructions, 1, ((0, letter),)), abs=1e-12)


@pytest.mark.parametrize("gate", TWO_Q)
def test_every_two_qubit_pauli_string_through_every_two_qubit_gate(gate):
    prep = [("ry", [0], [0.9]), ("rx", [1], [1.3]), ("h", [1], []), ("t", [0], [])]
    instructions = prep + [(gate, [0, 1], [])]
    strings = [
        tuple((q, letter) for q, letter in enumerate(pair) if letter != "I")
        for pair in itertools.product("IXYZ", repeat=2)
    ]
    strings = [s for s in strings if s]
    results = native(instructions, 2, strings)
    for ops, got in zip(strings, results):
        assert got.value == pytest.approx(qiskit_expectation(instructions, 2, ops), abs=1e-12), ops


# --- exactness without truncation ------------------------------------------

@pytest.mark.parametrize("seed", range(120))
def test_random_circuits_match_qiskit_statevector_without_truncation(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 6)
    instructions = random_circuit(rng, n, rng.randint(4, 14))
    ops_list = [random_ops(rng, n) for _ in range(5)]
    for ops, got in zip(ops_list, native(instructions, n, ops_list)):
        assert got.resolved and got.error_bound == 0.0
        assert got.value == pytest.approx(qiskit_expectation(instructions, n, ops), abs=1e-9), (seed, ops)


# --- the certified bound ----------------------------------------------------

def test_truncated_bound_covers_the_true_error():
    truncated_cases = 0
    for seed in range(150):
        rng = random.Random(1000 + seed)
        n = rng.randint(3, 6)
        instructions = random_circuit(rng, n, rng.randint(8, 18))
        ops_list = [random_ops(rng, n) for _ in range(4)]
        backend = exact_backend(max_pauli_terms=rng.choice([2, 3, 5, 8]),
                                prune_threshold=rng.choice([0.0, 1e-3]))
        for ops, got in zip(ops_list, native(instructions, n, ops_list, backend)):
            assert got.resolved
            truth = qiskit_expectation(instructions, n, ops)
            assert abs(got.value - truth) <= got.error_bound + 1e-9, (seed, ops)
            truncated_cases += got.error_bound > 0
    # The bound must actually have been exercised, not trivially zero.
    assert truncated_cases > 50


def test_per_observable_bound_is_tighter_than_the_shared_total():
    """The Z-only API reports the *sum* of all observables' bounds for each value."""
    tighter = 0
    for seed in range(60):
        rng = random.Random(5000 + seed)
        n = rng.randint(3, 6)
        instructions = random_circuit(rng, n, 14)
        masks = {f"m{i}": sum(1 << q for q in rng.sample(range(n), rng.randint(1, n)))
                 for i in range(4)}
        sim = SparsePauliDynamicsSimulator(n, max_pauli_terms=3, prune_threshold=0.0,
                                           error_tolerance=100.0)
        per = sim.evaluate_pauli_observables(
            instructions, [PauliObservable(k, 0, m, 1) for k, m in masks.items()]
        )
        shared_total = sum(o.error_bound for o in per.values())
        for outcome in per.values():
            assert outcome.error_bound <= shared_total + 1e-12
        tighter += max(o.error_bound for o in per.values()) < shared_total - 1e-12
    assert tighter > 10


def test_unresolved_observable_does_not_poison_the_others():
    rng = random.Random(7)
    n = 6
    instructions = random_circuit(rng, n, 30)
    # Qubit n-1 stays idle in this circuit so Z there is exactly +1.
    instructions = [g for g in instructions if (n - 1) not in g[1]]
    heavy = tuple((q, "X") for q in range(n - 1))
    backend = exact_backend(max_pauli_terms=2, error_tolerance=1e-3)
    out = native(instructions, n, [heavy, ((n - 1, "Z"),)], backend)
    assert out[0].resolved is False and out[0].value is None and out[0].error_bound > 1e-3
    # Float64 noise terms can be dropped by the budget, so allow ~1e-12 rather
    # than demanding bit-exact 1.0 / 0.0.
    assert out[1].resolved is True
    assert out[1].value == pytest.approx(1.0, abs=1e-12)
    assert out[1].error_bound < 1e-12


def test_execute_with_xy_strings_keeps_the_all_or_nothing_result_contract():
    circuit = [("h", [0], []), ("t", [0], []), ("cx", [0, 1], []), ("ry", [1], [0.4])]
    ok = PathDSparsePauliBackend(prune_threshold=0.0).execute(
        circuit, observables=["X[0]Y[1]", "Z[0]", "Y[0]"]
    )
    assert not ok.unresolved and set(ok.expectation_values) == {"X[0]Y[1]", "Z[0]", "Y[0]"}
    assert ok.metadata["per_observable_error_bounds"]["Z[0]"] == 0.0
    assert ok.error_bound == max(ok.metadata["per_observable_error_bounds"].values())
    truth = qiskit_expectation(circuit, 2, ((0, "X"), (1, "Y")))
    assert ok.expectation_values["X[0]Y[1]"] == pytest.approx(truth, abs=1e-12)
    assert ok.counts == {}  # no joint distribution is ever implied

    bad = PathDSparsePauliBackend(max_pauli_terms=1, prune_threshold=0.0,
                                  error_tolerance=1e-12).execute(
        [("ry", [0], [0.3]), ("rx", [1], [0.4]), ("cx", [0, 1], []), ("ry", [1], [0.9])],
        observables=["X[0]X[1]"],
    )
    assert bad.unresolved and bad.expectation_values is None


def test_invalid_observables_are_rejected_not_guessed():
    with pytest.raises(ValueError):
        pauli_observable_from_ops("dup", [(0, "X"), (0, "Z")])
    with pytest.raises(ValueError):
        pauli_observable_from_ops("neg", [(-1, "X")])
    with pytest.raises(ValueError):
        pauli_observable_from_ops("bad", [(0, "Q")])
    backend = exact_backend()
    obs = pauli_observable_from_ops("o", [(3, "X")])
    with pytest.raises(ValueError):
        backend.evaluate_paulis([("h", [0], [])], 2, [obs])
    with pytest.raises(ValueError):
        backend.evaluate_paulis([("h", [0], [])], 2, [obs, obs])
    with pytest.raises(ExpectationError):
        PathDSparsePauliBackend().execute([("h", [0], [])], observables=["X[0]Z[0]"])
    with pytest.raises(pd.UnsupportedPathDOperation):
        native([("ccx", [0, 1, 2], [])], 3, [((0, "X"),)])


# --- the public expectation API now uses one native pass -------------------

def test_expectation_sparse_engine_matches_dense_in_one_run():
    circuit = [("h", [0], []), ("t", [0], []), ("cx", [0, 1], []), ("ry", [2], [0.8]),
               ("cx", [1, 2], []), ("s", [2], [])]
    names = ["X0 Y1", "Z2", "Y0 Z1 X2", "X0", "Z0 Z1"]
    dense = expectation_values(circuit, names, method="dense")
    sparse = expectation_values(circuit, names, method="sparse_pauli", max_pauli_terms=10**6)
    assert sparse.metadata["sparse_pauli_runs"] == 1
    assert sparse.metadata["per_observable_bounds"] is True
    for key in dense.values:
        assert sparse.values[key] == pytest.approx(dense.values[key], abs=1e-9)


def test_wrong_y_phase_is_caught_by_the_oracle(monkeypatch):
    """Mutation check: dropping the factor i of Y must change the answer."""
    def broken(name, ops):
        x = z = 0
        for q, letter in ops:
            if letter in "XY":
                x |= 1 << q
            if letter in "ZY":
                z |= 1 << q
        return PauliObservable(name, x, z, complex(1.0, 0.0))  # forgot i for Y

    circuit = [("h", [0], []), ("s", [0], [])]  # |+i>: <Y> = +1
    good = native(circuit, 1, [((0, "Y"),)])[0].value
    assert good == pytest.approx(1.0)
    monkeypatch.setattr(pd, "pauli_observable_from_ops", broken)
    wrong = exact_backend().evaluate_paulis(circuit, 1, [broken("Y", ((0, "Y"),))])["Y"].value
    assert abs(wrong - good) > 0.5
