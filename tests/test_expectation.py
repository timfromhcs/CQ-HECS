"""
Pauli expectation values (v2.4.0).

Independent oracles: Qiskit ``Statevector`` / ``SparsePauliOp`` and closed-form
stabilizer states. The dense engine, the stabilizer engine and Path D are
checked against these and against each other.
"""

import itertools
import random
import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector

from cqhecs.backends.dense_reference import (
    DenseReferenceError,
    DenseStatevector,
    simulate,
)
from cqhecs.circuit_parsing import parse_circuit
from cqhecs.expectation import (
    ExpectationError,
    expectation_values,
    parse_pauli,
)


def _random_circuit(rng, n, depth, clifford_only=False, controlled_rotations=True):
    qc = QuantumCircuit(n)
    for _ in range(depth):
        k = rng.random()
        theta = rng.uniform(-3.0, 3.0)
        if clifford_only:
            if k < 0.4:
                getattr(qc, rng.choice(["h", "s", "sdg", "x", "y", "z"]))(rng.randrange(n))
            else:
                a, b = rng.sample(range(n), 2)
                getattr(qc, rng.choice(["cx", "cz", "swap"]))(a, b)
            continue
        if k < 0.25:
            getattr(qc, rng.choice(["h", "s", "t", "tdg", "x", "y", "z"]))(rng.randrange(n))
        elif k < 0.5:
            getattr(qc, rng.choice(["rx", "ry", "rz", "p"]))(theta, rng.randrange(n))
        elif k < 0.75:
            a, b = rng.sample(range(n), 2)
            getattr(qc, rng.choice(["cx", "cz", "swap"]))(a, b)
        elif controlled_rotations:
            a, b = rng.sample(range(n), 2)
            getattr(qc, rng.choice(["cp", "crx", "cry", "crz"]))(theta, a, b)
        else:
            qc.t(rng.randrange(n))
    return qc


class DenseReferenceTests(unittest.TestCase):
    def test_statevector_matches_qiskit_including_phase(self):
        rng = random.Random(11)
        for trial in range(40):
            n = rng.randint(2, 5)
            qc = _random_circuit(rng, n, rng.randint(1, 14))
            instructions, width = parse_circuit(qc)
            state = simulate(instructions, max(width, 1))
            with self.subTest(trial=trial):
                np.testing.assert_allclose(
                    state.statevector(), Statevector(qc).data, atol=1e-12
                )

    def test_pauli_expectation_matches_sparse_pauli_op(self):
        rng = random.Random(5)
        for trial in range(40):
            n = rng.randint(2, 5)
            qc = _random_circuit(rng, n, rng.randint(1, 12))
            instructions, width = parse_circuit(qc)
            state = simulate(instructions, max(width, 1))
            sv = Statevector(qc)
            for _ in range(6):
                label = "".join(rng.choice("IXYZ") for _ in range(n))
                ops = [(n - 1 - i, c) for i, c in enumerate(label) if c != "I"]
                expected = sv.expectation_value(SparsePauliOp(label)).real
                with self.subTest(trial=trial, label=label):
                    self.assertAlmostEqual(state.pauli_expectation(ops), expected, places=11)

    def test_invalid_operands_and_gates_are_refused(self):
        state = DenseStatevector(2)
        with self.assertRaises(DenseReferenceError):
            state.apply("cx", [0, 0])
        with self.assertRaises(DenseReferenceError):
            state.apply("h", [2])
        with self.assertRaises(DenseReferenceError):
            state.apply("frobnicate", [0])
        with self.assertRaises(DenseReferenceError):
            state.apply("measure", [0])
        with self.assertRaises(DenseReferenceError):
            DenseStatevector(0)
        with self.assertRaises(DenseReferenceError):
            DenseStatevector(10_000)


class ParsePauliTests(unittest.TestCase):
    def test_dense_label_has_qubit_zero_rightmost(self):
        self.assertEqual(parse_pauli("IZX", 3).ops, ((0, "X"), (1, "Z")))
        self.assertEqual(parse_pauli("zi", 2).ops, ((1, "Z"),))

    def test_sparse_forms_agree(self):
        expected = ((0, "X"), (2, "Z"))
        for text in ("X0 Z2", "X[0]Z[2]", "x0z2", " X 0  Z 2 "):
            with self.subTest(text=text):
                self.assertEqual(parse_pauli(text, 3).ops, expected)

    def test_identity(self):
        self.assertEqual(parse_pauli("III", 3).ops, ())
        self.assertEqual(parse_pauli("I0", 3).ops, ())
        self.assertEqual(parse_pauli("I0", 3).label, "I")

    def test_rejections(self):
        for text, n in (
            ("", 2), ("XX", 3), ("X5", 3), ("X0 X0", 2), ("X0 Z0", 2),
            ("X0 junk", 2), ("Q1", 2), ("X-1", 2), ("X0.5", 2),
        ):
            with self.subTest(text=text):
                with self.assertRaises(ExpectationError):
                    parse_pauli(text, n)
        with self.assertRaises(ExpectationError):
            parse_pauli(None, 2)  # type: ignore[arg-type]


class StabilizerEngineTests(unittest.TestCase):
    def test_exhaustive_pauli_strings_match_dense_on_random_cliffords(self):
        rng = random.Random(21)
        for trial in range(12):
            n = rng.randint(2, 4)
            qc = _random_circuit(rng, n, rng.randint(2, 16), clifford_only=True)
            labels = ["".join(p) for p in itertools.product("IXYZ", repeat=n)]
            stab = expectation_values(qc, labels, method="stabilizer")
            dense = expectation_values(qc, labels, method="dense")
            self.assertTrue(stab.exact)
            self.assertEqual(stab.error_bound, 0.0)
            for label in labels:
                with self.subTest(trial=trial, label=label):
                    self.assertAlmostEqual(stab.values[label], dense.values[label], places=10)

    def test_bell_and_ghz_closed_forms(self):
        bell = QuantumCircuit(2)
        bell.h(0)
        bell.cx(0, 1)
        res = expectation_values(bell, ["ZZ", "XX", "YY", "ZI", "XI"])
        self.assertEqual(res.method, "stabilizer")
        self.assertEqual(res.values, {"ZZ": 1.0, "XX": 1.0, "YY": -1.0, "ZI": 0.0, "XI": 0.0})

    def test_wide_ghz_is_exact_without_sampling(self):
        n = 300
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)
        res = expectation_values(
            qc,
            {"zz": "Z0 Z299", "z": "Z0", "xall": "".join(f"X{i}" for i in range(n)),
             "yy": "Y0 Y1"},
        )
        self.assertEqual(res.method, "stabilizer")
        self.assertEqual(res.values["zz"], 1.0)
        self.assertEqual(res.values["z"], 0.0)
        self.assertEqual(res.values["xall"], 1.0)
        # Y0 Y1 on GHZ anticommutes with a stabilizer pair product -> 0.
        self.assertEqual(res.values["yy"], 0.0)

    def test_forced_stabilizer_rejects_non_clifford(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.t(0)
        with self.assertRaises(ExpectationError):
            expectation_values(qc, ["ZZ"], method="stabilizer")


class RoutingAndSumsTests(unittest.TestCase):
    def test_auto_selects_engines(self):
        clifford = QuantumCircuit(3)
        clifford.h(0)
        clifford.cx(0, 1)
        self.assertEqual(expectation_values(clifford, ["IZZ"]).method, "stabilizer")

        non_clifford = QuantumCircuit(3)
        non_clifford.ry(0.7, 0)
        non_clifford.cx(0, 1)
        res = expectation_values(non_clifford, ["IZZ"])
        self.assertEqual(res.method, "dense")
        self.assertAlmostEqual(res.values["IZZ"], 1.0, places=12)

        wide = QuantumCircuit(30)
        wide.ry(0.7, 0)
        wide.cx(0, 1)
        res = expectation_values(wide, ["Z0 Z1"])
        self.assertEqual(res.method, "sparse_pauli")
        self.assertFalse(res.exact)

    def test_weighted_sum(self):
        qc = QuantumCircuit(2)
        qc.ry(0.9, 0)
        qc.cx(0, 1)
        sv = Statevector(qc)
        h = SparsePauliOp.from_list([("ZZ", 0.5), ("XX", -1.25), ("IZ", 2.0)])
        res = expectation_values(
            qc, {"H": [(0.5, "ZZ"), (-1.25, "XX"), (2.0, "IZ")]}
        )
        self.assertAlmostEqual(res.values["H"], sv.expectation_value(h).real, places=12)

    def test_measurements_are_ignored_but_mid_circuit_is_refused(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        self.assertEqual(expectation_values(qc, ["ZZ"]).values["ZZ"], 1.0)

        mid = QuantumCircuit(2, 2)
        mid.h(0)
        mid.measure(0, 0)
        mid.cx(0, 1)
        with self.assertRaises(ExpectationError):
            expectation_values(mid, ["ZZ"])

    def test_composite_gates_are_lowered(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.ccx(0, 1, 2)
        qc.sx(1)
        qc.rzz(0.4, 0, 2)
        sv = Statevector(qc)
        res = expectation_values(qc, ["XZY", "ZZZ"])
        for label in ("XZY", "ZZZ"):
            self.assertAlmostEqual(
                res.values[label], sv.expectation_value(SparsePauliOp(label)).real, places=11
            )

    def test_argument_validation(self):
        qc = QuantumCircuit(2)
        for bad in ([], "ZZ", {"": "ZZ"}, ["ZZ", "ZZ"], {"a": []}):
            with self.subTest(bad=bad):
                with self.assertRaises(ExpectationError):
                    expectation_values(qc, bad)  # type: ignore[arg-type]
        with self.assertRaises(ExpectationError):
            expectation_values(qc, ["ZZ"], method="nope")
        with self.assertRaises(ExpectationError):
            expectation_values(qc, ["ZZ"], error_tolerance=0.0)
        with self.assertRaises(ExpectationError):
            expectation_values(qc, {"a": [(float("nan"), "ZZ")]})
        with self.assertRaises(ExpectationError):
            expectation_values(qc, {"a": [(True, "ZZ")]})
        big = QuantumCircuit(24)
        big.ry(0.3, 0)
        with self.assertRaises(ExpectationError):
            expectation_values(big, ["Z0"], method="dense")

    def test_reset_is_refused(self):
        with self.assertRaises(ExpectationError):
            expectation_values([("h", [0], []), ("reset", [0], [])], ["Z0"])


class SparsePauliAgreementTests(unittest.TestCase):
    def test_certified_values_agree_with_dense_within_the_bound(self):
        rng = random.Random(31)
        checked = 0
        for trial in range(10):
            n = rng.randint(3, 6)
            qc = _random_circuit(rng, n, rng.randint(3, 9), controlled_rotations=False)
            labels = list({"".join(rng.choice("IXYZ") for _ in range(n)) for _ in range(5)})
            dense = expectation_values(qc, labels, method="dense")
            sparse = expectation_values(
                qc, labels, method="sparse_pauli", error_tolerance=0.5, max_pauli_terms=4096
            )
            if sparse.unresolved:
                for value in sparse.values.values():
                    self.assertTrue(value is None or isinstance(value, float))
                continue
            for label in labels:
                checked += 1
                with self.subTest(trial=trial, label=label):
                    self.assertLessEqual(
                        abs(sparse.values[label] - dense.values[label]),
                        sparse.error_bound + 1e-9,
                    )
        self.assertGreater(checked, 0)

    def test_path_d_gate_gap_is_a_clear_refusal(self):
        wide = QuantumCircuit(30)
        wide.ry(0.7, 0)
        wide.crx(0.4, 0, 1)
        with self.assertRaises(ExpectationError) as ctx:
            expectation_values(wide, ["Z0"])
        self.assertIn("crx", str(ctx.exception))

    def test_unresolved_values_are_none_never_guessed(self):
        n = 12
        qc = QuantumCircuit(n)
        rng = random.Random(2)
        for _ in range(6):
            for q in range(n):
                qc.ry(rng.uniform(0.3, 2.8), q)
                qc.rz(rng.uniform(0.3, 2.8), q)
            for q in range(n - 1):
                qc.cx(q, q + 1)
        res = expectation_values(
            qc, ["X0 Y5 X11"], method="sparse_pauli",
            error_tolerance=1e-6, max_pauli_terms=4,
        )
        self.assertTrue(res.unresolved)
        self.assertIsNone(res.values["X0 Y5 X11"])
        self.assertIn("reason", res.metadata)


if __name__ == "__main__":
    unittest.main()
