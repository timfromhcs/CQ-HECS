"""Strict parser contracts: Qiskit measurement mapping and index coercion.

CQ-03: the flat instruction triple ``(name, qubits, params)`` cannot carry a
classical destination.  ``parse_circuit()`` therefore accepts only the identity
mapping ``measure q[i] -> c[i]`` (the same rule the QASM reader enforces) and
rejects everything else before simulation.  The Qiskit *provider*
(`CQHecsBackend`) keeps full mapping support because it normalises the pairs and
pads the counts itself.

CQ-04: qubit indices used to be coerced with ``int(q)``, silently turning
``1.7``/``True``/``"2"`` into a different, valid circuit.  Only genuine integral
types are accepted now.
"""

import unittest

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from cqhecs.backend import CQHecsBackend
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.circuit_parsing import UnsupportedCircuitInputError, parse_circuit
from cqhecs.router import UnsupportedCircuitError


class TestQiskitMeasurementMapping(unittest.TestCase):
    def test_non_identity_single_mapping_is_rejected(self):
        qc = QuantumCircuit(2, 3)
        qc.measure(0, 2)
        with self.assertRaises(UnsupportedCircuitInputError) as ctx:
            parse_circuit(qc)
        self.assertIn("remapping", str(ctx.exception))

    def test_swapped_mapping_is_rejected(self):
        qc = QuantumCircuit(2, 2)
        qc.measure(0, 1)
        qc.measure(1, 0)
        with self.assertRaises(UnsupportedCircuitInputError):
            parse_circuit(qc)

    def test_reverse_measurement_order_is_normalised(self):
        qc = QuantumCircuit(2, 2)
        qc.measure(1, 1)
        qc.measure(0, 0)
        instructions, n = parse_circuit(qc)
        self.assertEqual(n, 2)
        self.assertEqual([q for _n, q, _p in instructions], [[0], [1]])

    def test_multi_register_offsets_use_global_indices(self):
        a = QuantumRegister(2, "a")
        b = QuantumRegister(2, "b")
        c = ClassicalRegister(2, "c")
        d = ClassicalRegister(2, "d")
        qc = QuantumCircuit(a, b, c, d)
        qc.measure(a[0], c[0])  # global 0 -> 0
        qc.measure(b[0], d[0])  # global 2 -> 2
        instructions, n = parse_circuit(qc)
        self.assertEqual(n, 4)
        self.assertEqual([q for _n, q, _p in instructions], [[0], [2]])

    def test_multi_register_offset_mismatch_is_rejected(self):
        a = QuantumRegister(2, "a")
        b = QuantumRegister(2, "b")
        c = ClassicalRegister(2, "c")
        qc = QuantumCircuit(a, b, c)
        qc.measure(b[0], c[1])  # qubit 2 -> clbit 1: not representable
        with self.assertRaises(UnsupportedCircuitInputError):
            parse_circuit(qc)

    def test_repeated_measurement_is_deduplicated(self):
        qc = QuantumCircuit(2, 2)
        qc.measure(0, 0)
        qc.measure(0, 0)
        instructions, _n = parse_circuit(qc)
        self.assertEqual([q for _n2, q, _p in instructions], [[0]])

    def test_measure_all_identity_layout_is_accepted(self):
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.measure_all()
        instructions, n = parse_circuit(qc)
        self.assertEqual(n, 2)
        measured = [q for name, q, _p in instructions if name == "measure"]
        self.assertEqual(measured, [[0], [1]])

    def test_direct_backend_renders_lowest_measured_qubit_rightmost(self):
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.measure(1, 1)
        qc.measure(0, 0)
        result = PathCMPSExactBackend(ram_budget_mb=64.0).execute(
            qc, shots=64, seed=3
        )
        self.assertFalse(result.unresolved)
        self.assertEqual(set(result.counts), {"01"})

    def test_provider_preserves_arbitrary_classical_layout(self):
        qc = QuantumCircuit(2, 3)
        qc.x(0)
        qc.measure(0, 2)  # c0/c1 stay unmeasured and must be padded with 0
        counts = CQHecsBackend().run(
            qc, shots=64, seed_simulator=3
        ).result().get_counts()
        self.assertEqual(set(counts), {"100"})

    def test_provider_preserves_swapped_layout(self):
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.measure(0, 1)
        qc.measure(1, 0)
        counts = CQHecsBackend().run(
            qc, shots=64, seed_simulator=3
        ).result().get_counts()
        # c0 <- q0 = 1, c1 <- q1 = 0 -> "10" (c1 c0)
        self.assertEqual(set(counts), {"10"})

    def test_mid_circuit_measurement_is_still_refused(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.measure(0, 0)
        qc.cx(0, 1)
        qc.measure(1, 1)
        with self.assertRaises(ValueError):
            PathCMPSExactBackend(ram_budget_mb=64.0).execute(qc, shots=8)


class TestInstructionIndexStrictness(unittest.TestCase):
    REJECTED_INDICES = (
        1.7,
        2.0,
        True,
        False,
        "1",
        complex(1, 0),
        float("nan"),
        float("inf"),
        -1,
        1 << 21,
    )

    def test_invalid_qubit_indices_are_rejected(self):
        for value in self.REJECTED_INDICES:
            with self.subTest(value=value):
                with self.assertRaises(UnsupportedCircuitInputError):
                    parse_circuit([("h", [value], [])])

    def test_non_iterable_operands_are_rejected(self):
        for item in (
            ("h", 0, []),
            ("h", [0], 0.5),
            ("h", "0", []),
            ("h", [0], "0.5"),
        ):
            with self.subTest(item=item):
                with self.assertRaises(UnsupportedCircuitInputError):
                    parse_circuit([item])

    def test_non_finite_and_non_numeric_parameters_are_rejected(self):
        for params in ([float("nan")], [float("inf")], ["nan"], [object()]):
            with self.subTest(params=params):
                with self.assertRaises(UnsupportedCircuitInputError):
                    parse_circuit([("rz", [0], params)])

    def test_empty_gate_name_is_rejected(self):
        with self.assertRaises(UnsupportedCircuitInputError):
            parse_circuit([("   ", [0], [])])

    def test_integral_types_and_generators_are_accepted(self):
        numpy_index = np.int64(2)
        instructions, n = parse_circuit([
            ("h", (q for q in [numpy_index]), []),
            ("x", [0], (p for p in [])),
        ])
        self.assertEqual(n, 3)
        self.assertEqual(instructions[0], ("h", [2], []))
        self.assertEqual(instructions[1], ("x", [0], []))

    def test_structured_error_is_not_a_plain_python_crash(self):
        with self.assertRaises(UnsupportedCircuitInputError) as ctx:
            parse_circuit([("h", [[0]], [])])
        self.assertIn("non-integer qubit index", str(ctx.exception))


class TestArityStillFailsClosed(unittest.TestCase):
    def test_wrong_arity_is_refused_by_backend(self):
        with self.assertRaises((ValueError, UnsupportedCircuitError)):
            PathCMPSExactBackend(ram_budget_mb=64.0).execute(
                [("cx", [0], [])], shots=8
            )


if __name__ == "__main__":
    unittest.main()
