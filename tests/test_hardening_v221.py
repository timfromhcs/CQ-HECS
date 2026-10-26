"""
Regression tests for the v2.2.1 hardening pass.

Every test here pins a defect that was reproduced before it was fixed:

* the analyzer classified ``cp(pi/2)`` by its first parameter only and routed a
  controlled-phase gate to the stabilizer tableau;
* multi-register QASM sized the circuit with ``max(register_size)`` and lost the
  global qubit offsets;
* the Python QASM path silently skipped unknown gates and malformed lines;
* a mid-circuit measurement was moved to the end of the circuit;
* ``reset`` was advertised as a Path A capability;
* Path D accepted ``Z[0]garbage``, boolean masks, out-of-range masks and kept
  duplicate ``Z[i]`` factors.

These are behavioural contracts, not implementation-detail assertions: each
checks the observable result (routing decision, refusal, parsed offsets, counts)
that a caller actually relies on.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import unittest

from qiskit import QuantumCircuit

from cqhecs.backend import CQHecsBackend
from cqhecs.circuit_analyzer import CircuitAnalyzer, UnsupportedCircuitInput
from cqhecs.circuit_parsing import (
    QASMParseError,
    UnsupportedCircuitInputError,
    parse_angle_expression,
    parse_circuit,
)
from cqhecs.gate_manifest import MANIFEST, get_gate, path_gate_names
from cqhecs.router import (
    FourPathRouter,
    UnsupportedCircuitError,
)
from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend


def _qasm(body: str) -> str:
    return "OPENQASM 2.0;\n" + body


class TestSingleSharedInputError(unittest.TestCase):
    """There must be one rejection hierarchy, not two disjoint ones."""

    def test_alias_is_the_parser_error(self):
        self.assertIs(UnsupportedCircuitInput, UnsupportedCircuitInputError)

    def test_analyzer_and_parser_raise_the_same_type(self):
        for bad in (42, None, [("h", [0])], _qasm("qreg q[1];\nnope q[0];\n")):
            with self.subTest(bad=bad):
                with self.assertRaises(UnsupportedCircuitInputError):
                    CircuitAnalyzer().analyze(bad)

    def test_qasm_parse_error_is_a_circuit_input_error(self):
        self.assertTrue(issubclass(QASMParseError, UnsupportedCircuitInputError))
        with self.assertRaises(UnsupportedCircuitInputError):
            parse_circuit(_qasm("qreg q[1];\nh q[0]\n"))


class TestFullParameterClassification(unittest.TestCase):
    """A gate is classified by all of its parameters and its real capabilities."""

    def test_cp_pi_over_2_is_not_clifford_and_routes_to_c(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cp(math.pi / 2, 0, 1)

        props = CircuitAnalyzer().analyze(qc)
        self.assertFalse(props.is_clifford)
        self.assertNotIn("A", props.supported_paths)
        self.assertEqual(props.recommended_path, "C")
        self.assertEqual(props.supported_paths, ("C",))

    def test_cp_pi_over_2_executes_on_the_selected_path(self):
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.cp(math.pi / 2, 0, 1)
        qc.measure_all()

        result = FourPathRouter().route_and_execute(qc, shots=64, seed=3)
        self.assertEqual(result.path, "C")
        # A controlled phase changes no computational-basis outcome: q0=1,
        # q1=0, so the only key is "01" (qubit 0 rightmost).
        self.assertEqual(set(result.counts), {"01"})

    def test_all_controlled_rotations_are_path_c_only(self):
        for gate, params in (
            ("cp", [0.37]),
            ("cu1", [0.37]),
            ("crx", [0.37]),
            ("cry", [0.37]),
            ("crz", [0.37]),
        ):
            with self.subTest(gate=gate):
                props = CircuitAnalyzer().analyze([(gate, [0, 1], params)])
                self.assertEqual(props.supported_paths, ("C",))
                self.assertEqual(props.recommended_path, "C")

    def test_known_but_unimplemented_gates_are_refused_before_execution(self):
        for gate, qubits, params in (
            ("u", [0], [0.1, 0.2, 0.3]),
            ("u2", [0], [0.1, 0.2]),
            ("u3", [0], [0.1, 0.2, 0.3]),
            ("ccx", [0, 1, 2], []),
            ("toffoli", [0, 1, 2], []),
            ("ch", [0, 1], []),
            ("cs", [0, 1], []),
        ):
            with self.subTest(gate=gate):
                props = CircuitAnalyzer().analyze([(gate, qubits, params)])
                self.assertIn(gate, props.unsupported_gates)
                self.assertEqual(props.recommended_path, "")
                with self.assertRaises(UnsupportedCircuitError):
                    FourPathRouter().route_and_execute(
                        [(gate, qubits, params)], shots=8
                    )

    def test_qiskit_u_gate_is_not_silently_treated_as_identity(self):
        qc = QuantumCircuit(1)
        qc.u(0.1, 0.2, 0.3, 0)
        # Qiskit's ``u`` is in the manifest but no path implements it.
        with self.assertRaises(UnsupportedCircuitError):
            FourPathRouter().route_and_execute(qc, shots=8)

    def test_unknown_gate_is_not_a_supported_path(self):
        props = CircuitAnalyzer().analyze([("not_a_gate", [0], [])])
        self.assertEqual(props.unsupported_gates, ("not_a_gate",))
        self.assertEqual(props.recommended_path, "")


class TestMultiRegisterMapping(unittest.TestCase):
    """Registers map to global offsets; the width is the sum of their sizes."""

    def test_separate_quantum_registers_keep_their_offsets(self):
        qasm = _qasm(
            "qreg a[2];\n"
            "qreg b[3];\n"
            "creg c[5];\n"
            "h b[0];\n"
            "cx a[1], b[2];\n"
        )
        instructions, num_qubits = parse_circuit(qasm)
        self.assertEqual(num_qubits, 5)
        self.assertEqual(instructions[0], ("h", [2], []))
        self.assertEqual(instructions[1], ("cx", [1, 4], []))

    def test_whole_register_operand_expands_in_offset_order(self):
        instructions, num_qubits = parse_circuit(
            _qasm("qreg a[2];\nqreg b[3];\nh b;\n")
        )
        self.assertEqual(num_qubits, 5)
        self.assertEqual([q for _n, q, _p in instructions], [[2], [3], [4]])

    def test_whole_register_two_qubit_operand_expands_in_pairs(self):
        instructions, num_qubits = parse_circuit(_qasm("qreg q[4];\ncx q;\n"))
        self.assertEqual(num_qubits, 4)
        self.assertEqual(
            [qubits for _n, qubits, _p in instructions], [[0, 1], [2, 3]]
        )

    def test_offsets_survive_execution(self):
        # x on the first qubit of the *second* register is global qubit 2.
        result = FourPathRouter().route_and_execute(
            _qasm("qreg a[2];\nqreg b[3];\nx b[0];\n"), shots=32, seed=5
        )
        self.assertEqual(result.path, "A")
        self.assertEqual(set(result.counts), {"00100"})

    def test_qiskit_multiple_registers_use_global_indices(self):
        from qiskit import ClassicalRegister, QuantumRegister

        a = QuantumRegister(2, "a")
        b = QuantumRegister(3, "b")
        qc = QuantumCircuit(a, b)
        qc.x(b[0])
        instructions, num_qubits = parse_circuit(qc)
        self.assertEqual(num_qubits, 5)
        self.assertEqual(instructions, [("x", [2], [])])


class TestStrictQASMContract(unittest.TestCase):
    """Malformed QASM is rejected with a structured, native-compatible category."""

    REJECTIONS = (
        ("unknown gate", "qreg q[1];\nnope q[0];\n", "unsupported_gate"),
        ("missing semicolon", "qreg q[1];\nh q[0]\n", "missing_semicolon"),
        ("undeclared register", "qreg q[2];\nh phantom[0];\n", "undeclared_register"),
        ("out of range index", "qreg q[2];\nh q[2];\n", "index_out_of_range"),
        ("duplicate register", "qreg q[1];\nqreg q[1];\n", "duplicate_register"),
        (
            "measurement width mismatch",
            "qreg q[4];\ncreg c[2];\nmeasure q -> c;\n",
            "width_mismatch",
        ),
        ("wrong parameter count", "qreg q[1];\nrx q[0];\n", "parameter_count_mismatch"),
        ("empty parameter list", "qreg q[1];\nrx() q[0];\n", "parameter_count_mismatch"),
        (
            "operand count mismatch",
            "qreg q[3];\ncx q;\n",
            "operand_count_mismatch",
        ),
        ("bad parameter", "qreg q[1];\nrx(sin(pi)) q[0];\n", "invalid_parameter"),
        ("bare header", "OPENQASM;\nqreg q[1];\n", "unsupported_version"),
        ("bad version", "OPENQASM 4.0;\n", "unsupported_version"),
        ("block comment", "OPENQASM 2.0;\n/* x */\n", "unsupported_syntax"),
        ("condition", "qreg q[1];\nif(c==0) x q[0];\n", "unsupported_syntax"),
        (
            "classical bit remap",
            "qreg q[2];\ncreg c[2];\nmeasure q[0] -> c[1];\n",
            "unsupported_syntax",
        ),
    )

    def test_rejection_categories(self):
        for label, body, expected in self.REJECTIONS:
            source = body if body.startswith("OPENQASM") else _qasm(body)
            with self.subTest(case=label):
                with self.assertRaises(QASMParseError) as ctx:
                    parse_circuit(source)
                self.assertEqual(ctx.exception.category, expected)

    def test_no_statement_is_silently_skipped(self):
        source = _qasm("qreg q[2];\nh q[0];\nnot_a_gate q[1];\n")
        with self.assertRaises(QASMParseError):
            parse_circuit(source)

    def test_empty_and_comment_only_sources_are_empty_circuits(self):
        for source in ("", "// only a comment\n", "\n\n"):
            with self.subTest(source=source):
                instructions, num_qubits = parse_circuit(source)
                self.assertEqual(instructions, [])
                self.assertEqual(num_qubits, 0)

    def test_terminal_measurements_are_sorted_by_qubit(self):
        source = _qasm(
            "qreg q[3];\ncreg c[3];\n"
            "measure q[2] -> c[2];\n"
            "measure q[0] -> c[0];\n"
        )
        instructions, _n = parse_circuit(source)
        self.assertEqual([q for _n2, q, _p in instructions], [[0], [2]])

    def test_mid_circuit_measurement_keeps_its_position(self):
        source = _qasm(
            "qreg q[2];\ncreg c[2];\n"
            "h q[0];\n"
            "measure q[0] -> c[0];\n"
            "x q[1];\n"
        )
        instructions, _n = parse_circuit(source)
        self.assertEqual([name for name, _q, _p in instructions], ["h", "measure", "x"])
        props = CircuitAnalyzer().analyze(source)
        self.assertTrue(props.has_mid_circuit_measurement)
        self.assertEqual(props.recommended_path, "")
        with self.assertRaises(UnsupportedCircuitError):
            FourPathRouter().route_and_execute(source)

    def test_identity_and_barrier_do_not_make_a_measurement_mid_circuit(self):
        source = _qasm(
            "qreg q[1];\ncreg c[1];\n"
            "h q[0];\n"
            "measure q[0] -> c[0];\n"
            "id q[0];\n"
            "barrier q[0];\n"
        )
        props = CircuitAnalyzer().analyze(source)
        self.assertFalse(props.has_mid_circuit_measurement)
        self.assertEqual(props.recommended_path, "A")


class TestAngleExpressionSafety(unittest.TestCase):
    """Angles are parsed by a bounded grammar, never by ``eval``."""

    def test_documented_expressions(self):
        for text, expected in (
            ("pi/2", math.pi / 2),
            ("-pi/4", -math.pi / 4),
            ("2*pi", 2 * math.pi),
            ("1e-3", 1e-3),
            (" (pi/4) + 0.5 ", math.pi / 4 + 0.5),
            ("pi/(2)", math.pi / 2),
            ("+pi", math.pi),
            ("1.5e2", 150.0),
        ):
            with self.subTest(text=text):
                self.assertAlmostEqual(parse_angle_expression(text), expected)

    def test_code_execution_is_not_part_of_the_grammar(self):
        for text in (
            "__import__('os').system('echo pwned')",
            "open('/etc/passwd').read()",
            "eval('1+1')",
            "pi.__class__",
            "1 if True else 2",
            "[1,2][0]",
            "lambda: 1",
        ):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_angle_expression(text)

    def test_invalid_arithmetic_and_non_finite_values_are_rejected(self):
        for text in (
            "1/0",
            "0/0",
            "nan",
            "inf",
            "-inf",
            "1e999",
            "2**3",
            "pi//2",
            "pi 2",
            "pi()",
            "(" * 300 + "pi" + ")" * 300,
            "9" * 600,
        ):
            with self.subTest(text=text[:30]):
                with self.assertRaises(ValueError):
                    parse_angle_expression(text)

    def test_qiskit_non_finite_parameters_are_rejected(self):
        # Qiskit itself accepts float('nan')/inf as gate parameters. The shared
        # parser must reject them exactly like the QASM and tuple input forms,
        # instead of letting a NaN reach the numerical backends.
        for value in (float("nan"), float("inf"), float("-inf")):
            qc = QuantumCircuit(1)
            qc.rx(value, 0)
            with self.subTest(value=value):
                with self.assertRaises(UnsupportedCircuitInputError):
                    parse_circuit(qc)


class TestDynamicCircuitRefusal(unittest.TestCase):
    """Non-unitary dynamics are refused, never reordered or ignored."""

    def test_mid_circuit_measurement_is_refused(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.measure(0, 0)
        qc.x(1)
        with self.assertRaises(UnsupportedCircuitError) as ctx:
            FourPathRouter().route_and_execute(qc, shots=16)
        self.assertIn("mid-circuit", str(ctx.exception).lower())

    def test_reset_is_refused(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.reset(0)
        with self.assertRaises(UnsupportedCircuitError):
            FourPathRouter().route_and_execute(qc, shots=16)

    def test_classical_condition_is_refused(self):
        from qiskit import ClassicalRegister, QuantumRegister

        qr = QuantumRegister(1, "q")
        cr = ClassicalRegister(1, "c")
        qc = QuantumCircuit(qr, cr)
        qc.h(0)
        qc.measure(0, 0)
        with qc.if_test((cr[0], 1)):
            qc.x(0)
        with self.assertRaises(UnsupportedCircuitInputError) as ctx:
            parse_circuit(qc)
        self.assertIn("classically controlled", str(ctx.exception))

    def test_backend_run_refuses_mid_circuit_measurement(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.measure(0, 0)
        qc.x(1)
        with self.assertRaises(UnsupportedCircuitError):
            CQHecsBackend(num_qubits=2).run(qc, shots=16)

    def test_backend_run_refuses_reset(self):
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.reset(0)
        qc.measure(0, 0)
        with self.assertRaises(UnsupportedCircuitError):
            CQHecsBackend(num_qubits=1).run(qc, shots=16)

    def test_no_path_advertises_reset(self):
        for path in ("A", "B", "C", "D"):
            with self.subTest(path=path):
                self.assertNotIn("reset", path_gate_names(path))

    def test_reset_is_in_the_manifest_as_unimplemented(self):
        spec = get_gate("reset")
        self.assertIsNotNone(spec)
        self.assertTrue(spec.reset)
        self.assertEqual(spec.paths, frozenset())


class TestQiskitClassicalBitMapping(unittest.TestCase):
    """The Qiskit result must use the circuit's classical-bit layout."""

    def test_repeated_measurement_into_two_clbits_is_preserved(self):
        qc = QuantumCircuit(2, 4)
        qc.x(0)
        qc.measure(0, 3)
        qc.measure(0, 1)
        counts = (
            CQHecsBackend(num_qubits=2)
            .run(qc, shots=64, seed_simulator=7)
            .result()
            .get_counts()
        )
        self.assertEqual(counts, {"1010": 64})

    def test_non_contiguous_clbits_are_padded(self):
        qc = QuantumCircuit(3, 5)
        qc.x(2)
        qc.measure(2, 4)
        qc.measure(0, 1)
        counts = (
            CQHecsBackend(num_qubits=3)
            .run(qc, shots=32, seed_simulator=11)
            .result()
            .get_counts()
        )
        # clbit 4 = qubit 2 = 1, clbit 1 = qubit 0 = 0, unmeasured bits = 0.
        self.assertEqual(counts, {"10000": 32})

    def test_measure_all_layout_is_preserved(self):
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.measure_all()
        counts = (
            CQHecsBackend(num_qubits=2)
            .run(qc, shots=32, seed_simulator=13)
            .result()
            .get_counts()
        )
        self.assertEqual(counts, {"01": 32})

    def test_multi_qubit_measure_instruction_is_supported(self):
        # Qiskit represents ``measure([0, 1], [0, 1])`` as one instruction with
        # two qubits and two clbits. Its 1:1 pairs must be preserved.
        qc = QuantumCircuit(2, 2)
        qc.x(1)
        qc.measure([0, 1], [0, 1])
        counts = (
            CQHecsBackend(num_qubits=2)
            .run(qc, shots=16, seed_simulator=5)
            .result()
            .get_counts()
        )
        self.assertEqual(counts, {"10": 16})

    def test_noop_after_terminal_measurement_is_not_mid_circuit(self):
        # A barrier or identity after the last measurement has no state effect.
        # It must not be mistaken for a mid-circuit measurement.
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.measure(0, 0)
        qc.barrier()
        qc.id(1)
        counts = (
            CQHecsBackend(num_qubits=2)
            .run(qc, shots=16, seed_simulator=3)
            .result()
            .get_counts()
        )
        self.assertEqual(counts, {"01": 16})


class TestPathCResourceHonesty(unittest.TestCase):
    """Path C distinguishes internal tensor bytes from process RSS and fails closed."""

    def test_ram_budget_is_enforced_before_reporting_success(self):
        # One byte of RAM budget cannot hold even a single 2x2 complex site.
        backend = PathCMPSExactBackend(
            ram_budget_mb=0.000001, max_storage_mb=100.0
        )
        qc = QuantumCircuit(1)
        qc.h(0)
        result = backend.execute(qc, shots=16)
        self.assertTrue(result.unresolved)
        self.assertEqual(result.counts, {})
        self.assertEqual(result.metadata["resource_limit"], "ram")
        self.assertFalse(result.metadata["truncation_applied"])

    def test_internal_tensor_accounting_is_not_labelled_as_rss(self):
        backend = PathCMPSExactBackend(ram_budget_mb=100.0)
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        result = backend.execute(qc, shots=32, seed=1)

        metadata = result.metadata
        for key in (
            "active_ram_mb",
            "active_tensor_mb",
            "internal_allocation_mb",
            "process_rss_mb",
            "process_peak_rss_mb",
            "rss_measurement_available",
            "resource_accounting_note",
        ):
            with self.subTest(key=key):
                self.assertIn(key, metadata)
        self.assertIn("not process RSS", metadata["resource_accounting_note"])

    def test_numerical_bound_is_not_invented(self):
        result = PathCMPSExactBackend().execute(
            [("h", [0], []), ("cx", [0, 1], [])], shots=16
        )
        self.assertTrue(result.exact)
        self.assertIsNone(result.numerical_error_bound)
        self.assertIn("not derived", result.metadata["numerical_error_bound_reason"])


class TestManifestIsTheSingleSourceOfTruth(unittest.TestCase):
    """Target, router and backend sets are all subsets of one validated table."""

    def test_every_manifest_gate_has_a_consistent_signature(self):
        for name, spec in MANIFEST.items():
            with self.subTest(gate=name):
                self.assertEqual(name, name.lower())
                self.assertGreaterEqual(spec.arity, 0)
                self.assertLessEqual(spec.min_params, spec.max_params)
                if spec.barrier:
                    self.assertEqual(spec.arity, 0)
                if spec.measurement:
                    self.assertEqual(spec.paths, frozenset({"A", "C"}))
                if spec.reset:
                    self.assertEqual(spec.paths, frozenset())
                for path in spec.paths:
                    self.assertIn(path, {"A", "B", "C", "D"})

    def test_router_capabilities_are_derived_from_the_manifest(self):
        for path in ("A", "B", "C", "D"):
            with self.subTest(path=path):
                self.assertEqual(
                    FourPathRouter.PATH_CAPABILITIES[path], path_gate_names(path)
                )

    def test_backend_sets_are_subsets_of_their_path(self):
        self.assertLessEqual(
            PathAStabilizerBackend.SUPPORTED_GATES, path_gate_names("A")
        )
        self.assertLessEqual(
            PathAStabilizerBackend._CLIFFORD_ROTATIONS, path_gate_names("A")
        )
        b_gates = (
            PathBStabilizerRankBackend.SUPPORTED_CLIFFORD_GATES
            | PathBStabilizerRankBackend.SUPPORTED_NON_CLIFFORD_GATES
        )
        self.assertLessEqual(b_gates, path_gate_names("B"))
        self.assertLessEqual(PathCMPSExactBackend.SUPPORTED_GATES, path_gate_names("C"))

    def test_qiskit_target_is_a_subset_of_the_manifest(self):
        backend = CQHecsBackend(num_qubits=4)
        for name in backend.target.operation_names:
            with self.subTest(gate=name):
                self.assertIn(name.lower(), MANIFEST)

    def test_qiskit_target_never_advertises_unimplemented_gates(self):
        target = set(CQHecsBackend(num_qubits=4).target.operation_names)
        for name in ("u", "u2", "u3", "ccx", "reset"):
            with self.subTest(gate=name):
                self.assertNotIn(name, target)

    def test_qiskit_target_covers_path_c_gates_for_transpilation(self):
        from qiskit import transpile

        backend = CQHecsBackend(num_qubits=3)
        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.cp(math.pi / 2, 0, 1)
        qc.crz(0.4, 1, 2)
        qc.measure_all()

        transpiled = transpile(qc, backend, optimization_level=0)
        names = set(transpiled.count_ops())
        self.assertIn("cp", names)
        self.assertIn("crz", names)
        result = backend.run(transpiled, shots=32, seed_simulator=1).result()
        self.assertTrue(result.success)
        self.assertEqual(sum(result.get_counts().values()), 32)


class TestPathDObservableGrammar(unittest.TestCase):
    """Observables are parsed as a whole; invalid tails are not ignored."""

    def setUp(self):
        self.backend = PathDSparsePauliBackend()
        self.one = [("h", [0], [])]
        self.two = [("h", [0], []), ("cx", [0, 1], [])]

    def test_trailing_garbage_is_rejected(self):
        for bad in ("Z[0]garbage", "Z[0] Z[1]junk", "Z[0]X[1]", "z[0]", "Z[-1]"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.backend.execute(self.one, observables=[bad], shots=8)

    def test_mask_validation(self):
        for mask in (True, False, -1, 1.0, "1"):
            with self.subTest(mask=mask):
                with self.assertRaises(ValueError):
                    self.backend.execute(
                        self.one, observables={"Z[0]": mask}, shots=8
                    )
        with self.assertRaises(ValueError):
            self.backend.execute(self.one, observables={"Z[0]": 1 << 1}, shots=8)
        with self.assertRaises(TypeError):
            self.backend.execute(self.one, observables={1: 0}, shots=8)

    def test_duplicate_factors_cancel_to_identity(self):
        result = self.backend.execute(
            self.one, observables=["Z[0]Z[0]"], shots=8
        )
        self.assertEqual(set(result.expectation_values), {"I"})
        self.assertAlmostEqual(result.expectation_values["I"], 1.0)

    def test_repeated_factor_in_a_longer_product_cancels(self):
        result = self.backend.execute(
            self.two, observables=["Z[0]Z[1]Z[1]"], shots=8
        )
        self.assertEqual(set(result.expectation_values), {"Z[0]"})

    def test_whitespace_between_factors_is_accepted(self):
        result = self.backend.execute(
            self.two, observables=["Z[0] Z[1]"], shots=8
        )
        self.assertEqual(set(result.expectation_values), {"Z[0]Z[1]"})

    def test_bell_correlation_is_reported(self):
        result = self.backend.execute(
            self.two, observables=["Z[0]Z[1]"], shots=8
        )
        self.assertAlmostEqual(result.expectation_values["Z[0]Z[1]"], 1.0)

    def test_counts_are_not_claimed_as_joint_distribution(self):
        result = self.backend.execute(self.two, shots=16)
        self.assertEqual(result.counts, {})
        self.assertFalse(result.metadata["counts_supported"])
        self.assertFalse(result.metadata["counts_are_joint_distribution"])


class TestPythonNativeQASMDifferential(unittest.TestCase):
    """
    The Python and native parsers must agree on the shared strict contract.

    Both are run on the same source. The assertions compare the *category* of
    the rejection (the normalized IR / typed error), not message wording.
    """

    @classmethod
    def setUpClass(cls):
        from tests.native_artifacts import require_executable

        cls.exe_path = require_executable()
        if os.name != "nt":
            os.chmod(cls.exe_path, 0o755)

    def native_categories(self, source: str) -> set:
        result = subprocess.run(
            [str(self.exe_path), "qasm", "-", "--json"],
            input=source,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        payload = json.loads(result.stdout)
        return {error["category"] for error in payload["errors"]}

    def test_shared_rejections_have_the_same_category(self):
        cases = {
            "unsupported_gate": "qreg q[1];\nnope q[0];\n",
            "missing_semicolon": "qreg q[1];\nh q[0]\n",
            "undeclared_register": "qreg q[2];\nh phantom[0];\n",
            "index_out_of_range": "qreg q[2];\nh q[2];\n",
            "duplicate_register": "qreg q[1];\nqreg q[1];\n",
            "width_mismatch": "qreg q[4];\ncreg c[2];\nmeasure q -> c;\n",
            "parameter_count_mismatch": "qreg q[1];\nrx q[0];\n",
            "operand_count_mismatch": "qreg q[3];\ncx q;\n",
            "invalid_parameter": "qreg q[1];\nrx(sin(pi)) q[0];\n",
            "unsupported_version": "OPENQASM 4.0;\n",
            "unsupported_syntax": "OPENQASM 2.0;\n/* x */\n",
        }
        for expected, body in cases.items():
            source = body if body.startswith("OPENQASM") else _qasm(body)
            with self.subTest(category=expected):
                with self.assertRaises(QASMParseError) as ctx:
                    parse_circuit(source)
                self.assertEqual(ctx.exception.category, expected)
                self.assertIn(expected, self.native_categories(source))

    def test_valid_multi_register_circuit_is_accepted_by_both(self):
        source = _qasm(
            "qreg a[2];\nqreg b[3];\ncreg c[5];\n"
            "h b[0];\ncx a[1], b[2];\n"
        )
        instructions, num_qubits = parse_circuit(source)
        self.assertEqual(num_qubits, 5)
        self.assertEqual(instructions[0], ("h", [2], []))
        self.assertEqual(instructions[1], ("cx", [1, 4], []))

        result = subprocess.run(
            [str(self.exe_path), "qasm", "-", "--json"],
            input=source,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["qubit_count"], 5)
        self.assertEqual(payload["gate_count"], 2)

    def test_python_only_diagnostics_do_not_change_acceptance(self):
        # ``u``/``u2``/``u3`` are known to the Python manifest (for a precise
        # refusal) but unknown to the native legacy executor. Both reject;
        # only the layer differs: parse-time vs capability-time.
        for source in (
            _qasm("qreg q[1];\nu(0.1,0.2,0.3) q[0];\n"),
            _qasm("qreg q[1];\nu2(0.1,0.2) q[0];\n"),
            _qasm("qreg q[1];\nu3(0.1,0.2,0.3) q[0];\n"),
        ):
            with self.subTest(source=source):
                # Python parses it, then refuses execution.
                instructions, _n = parse_circuit(source)
                with self.assertRaises(UnsupportedCircuitError):
                    FourPathRouter().route_and_execute(instructions, shots=8)
                # Native refuses at parse time.
                self.assertIn("unsupported_gate", self.native_categories(source))


if __name__ == "__main__":
    unittest.main()
