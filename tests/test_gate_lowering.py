"""
Exact composite-gate lowering (v2.3.0).

Every rule in ``cqhecs.gate_lowering`` is checked as a unitary identity against
Qiskit's own gate matrices, *including* global phase, and then end to end:
circuits that use the composite gates run on the router and on each path that
can execute the lowered form, and are compared with ``Statevector``.
"""

import math
import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import (
    C3XGate, C4XGate, CCXGate, CCZGate, CHGate, CSGate, CSXGate, CSdgGate,
    CSwapGate, CU3Gate, CUGate, CYGate, DCXGate, ECRGate, RGate, RXXGate,
    RYYGate, RZZGate, SXGate, SXdgGate, U2Gate, U3Gate, UGate, iSwapGate,
)
from qiskit.quantum_info import Operator, Statevector

from cqhecs.backend import CQHecsBackend
from cqhecs.circuit_analyzer import CircuitAnalyzer
from cqhecs.circuit_parsing import UnsupportedCircuitInputError, parse_circuit
from cqhecs.gate_lowering import LOWERING_RULES, is_lowered_gate, lower_instructions
from cqhecs.gate_manifest import MANIFEST, path_gate_names
from cqhecs.router import FourPathRouter

_ANGLES = (0.37, -1.21, 2.5, 0.83)

#: (name, qiskit gate factory, arity, parameter count)
_CASES = (
    ("u", lambda p: UGate(*p), 1, 3),
    ("u3", lambda p: U3Gate(*p), 1, 3),
    ("u2", lambda p: U2Gate(*p), 1, 2),
    ("sx", lambda p: SXGate(), 1, 0),
    ("sxdg", lambda p: SXdgGate(), 1, 0),
    ("cy", lambda p: CYGate(), 2, 0),
    ("ch", lambda p: CHGate(), 2, 0),
    ("cs", lambda p: CSGate(), 2, 0),
    ("csdg", lambda p: CSdgGate(), 2, 0),
    ("rzz", lambda p: RZZGate(*p), 2, 1),
    ("rxx", lambda p: RXXGate(*p), 2, 1),
    ("ryy", lambda p: RYYGate(*p), 2, 1),
    ("ccx", lambda p: CCXGate(), 3, 0),
    ("toffoli", lambda p: CCXGate(), 3, 0),
    ("ccz", lambda p: CCZGate(), 3, 0),
    ("cswap", lambda p: CSwapGate(), 3, 0),
    ("fredkin", lambda p: CSwapGate(), 3, 0),
    ("r", lambda p: RGate(*p), 1, 2),
    ("iswap", lambda p: iSwapGate(), 2, 0),
    ("dcx", lambda p: DCXGate(), 2, 0),
    ("ecr", lambda p: ECRGate(), 2, 0),
    ("cu3", lambda p: CU3Gate(*p), 2, 3),
    ("cu", lambda p: CUGate(*p), 2, 4),
    ("csx", lambda p: CSXGate(), 2, 0),
    ("c3x", lambda p: C3XGate(), 4, 0),
    ("c4x", lambda p: C4XGate(), 5, 0),
)


def _primitive_operator(instructions, width):
    qc = QuantumCircuit(width)
    for name, qubits, params in instructions:
        getattr(qc, name)(*params, *qubits)
    return Operator(qc)


def _probabilities(counts, width):
    total = sum(counts.values())
    probs = np.zeros(2 ** width)
    for key, value in counts.items():
        probs[int(key.replace(" ", ""), 2)] += value / total
    return probs


class LoweringIdentityTests(unittest.TestCase):
    def test_every_composite_manifest_entry_has_a_rule(self):
        composite = {name for name, spec in MANIFEST.items() if spec.lowered}
        self.assertEqual(composite, set(LOWERING_RULES))
        for name in composite:
            self.assertTrue(is_lowered_gate(name))
            self.assertEqual(MANIFEST[name].paths, frozenset())

    def test_rules_are_exact_including_global_phase(self):
        for name, factory, arity, nparams in _CASES:
            params = list(_ANGLES[:nparams])
            # Reversed / non-contiguous operands exercise operand order too.
            for operands in (list(range(arity)), list(reversed(range(arity)))):
                with self.subTest(gate=name, operands=operands):
                    lowered = lower_instructions([(name, operands, params)])
                    for prim, _q, _p in lowered:
                        self.assertFalse(is_lowered_gate(prim), prim)
                        self.assertIn(prim, MANIFEST)
                    expected = QuantumCircuit(arity)
                    expected.append(factory(params), operands)
                    np.testing.assert_allclose(
                        _primitive_operator(lowered, arity).data,
                        Operator(expected).data,
                        atol=1e-12,
                    )

    def test_lowered_gates_only_use_native_gates(self):
        native = set().union(*(path_gate_names(p) for p in "ABCD"))
        for name, _f, arity, nparams in _CASES:
            lowered = lower_instructions([(name, list(range(arity)), list(_ANGLES[:nparams]))])
            self.assertLessEqual({n for n, _q, _p in lowered}, native)

    def test_non_composite_instructions_pass_through_in_order(self):
        insts = [("h", [0], []), ("frobnicate", [1], []), ("measure", [0], [])]
        self.assertEqual(lower_instructions(insts), insts)

    def test_invalid_composite_signatures_are_refused(self):
        for bad in (
            [("ccx", [0, 1], [])],
            [("u3", [0], [0.1])],
            [("rzz", [0, 1], [])],
            [("ccx", [0, 0, 1], [])],
            [("cy", [2, 2], [])],
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(UnsupportedCircuitInputError):
                    parse_circuit(bad)


class LoweredExecutionTests(unittest.TestCase):
    def _assert_router_matches_statevector(self, qc, shots=20000, seed=7):
        ideal = Statevector(qc.remove_final_measurements(inplace=False))
        expected = np.abs(ideal.data) ** 2
        res = FourPathRouter().route_and_execute(qc, shots=shots, seed=seed)
        self.assertFalse(res.is_unresolved, res.metadata)
        probs = _probabilities(res.counts, qc.num_qubits)
        tvd = 0.5 * np.abs(probs - expected).sum()
        self.assertLess(tvd, 0.03, f"path {res.path}: TVD {tvd:.4f}")
        return res

    def test_toffoli_truth_table(self):
        for bits in range(8):
            qc = QuantumCircuit(3)
            for q in range(3):
                if bits >> q & 1:
                    qc.x(q)
            qc.ccx(0, 1, 2)
            qc.measure_all()
            res = FourPathRouter().route_and_execute(qc, shots=64, seed=1)
            out = bits ^ (4 if (bits & 3) == 3 else 0)
            with self.subTest(bits=bits):
                self.assertEqual(res.counts, {format(out, "03b"): 64})

    def test_clifford_composites_route_to_path_a(self):
        qc = QuantumCircuit(3)
        qc.sx(0)
        qc.cy(0, 1)
        qc.rzz(math.pi / 2, 1, 2)
        qc.sxdg(2)
        props = CircuitAnalyzer().analyze(qc)
        self.assertIn("A", props.supported_paths)
        self.assertEqual(props.recommended_path, "A")
        self._assert_router_matches_statevector(qc)

    def test_mixed_composite_circuit_matches_statevector(self):
        qc = QuantumCircuit(4)
        qc.h(range(4))
        qc.u(0.3, 1.1, -0.4, 0)
        qc.ch(0, 1)
        qc.cs(1, 2)
        qc.rxx(0.7, 2, 3)
        qc.ryy(-0.5, 0, 3)
        qc.cswap(3, 0, 1)
        qc.ccz(0, 1, 2)
        qc.csdg(3, 2)
        self._assert_router_matches_statevector(qc)

    def test_qiskit_mcx_is_lowered_by_control_count(self):
        for controls in (3, 4):
            qc = QuantumCircuit(controls + 1)
            qc.x(range(controls))
            qc.mcx(list(range(controls)), controls)
            qc.measure_all()
            res = FourPathRouter().route_and_execute(qc, shots=32, seed=1)
            with self.subTest(controls=controls):
                self.assertEqual(res.counts, {"1" * (controls + 1): 32})

    def test_unsupported_mcx_width_is_refused(self):
        qc = QuantumCircuit(6)
        qc.mcx(list(range(5)), 5)
        with self.assertRaises(Exception):
            FourPathRouter().route_and_execute(qc, shots=8)

    def test_qasm_source_with_composite_gates(self):
        source = (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
            "qreg q[3];\ncreg c[3];\n"
            "u3(0.2,0.4,0.6) q[0];\nu2(0.1,0.3) q[1];\nsx q[2];\n"
            "ccx q[0],q[1],q[2];\nrzz(0.9) q[0],q[2];\ncy q[2],q[1];\n"
        )
        instructions, width = parse_circuit(source)
        self.assertEqual(width, 3)
        self.assertFalse(any(is_lowered_gate(n) for n, _q, _p in instructions))
        res = FourPathRouter().route_and_execute(source, shots=256, seed=3)
        self.assertEqual(sum(res.counts.values()), 256)

    def test_qiskit_backend_runs_composites_transpiled_and_raw(self):
        from qiskit import transpile

        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.sx(1)
        qc.cy(0, 1)
        qc.rzz(0.4, 1, 2)
        qc.ccx(0, 1, 2)
        qc.measure(range(3), range(3))
        backend = CQHecsBackend(num_qubits=3)
        raw = backend.run(qc, shots=4000, seed_simulator=5).result().get_counts()
        transpiled = transpile(qc, backend, optimization_level=0)
        self.assertNotIn("ccx", transpiled.count_ops())
        tr = backend.run(transpiled, shots=4000, seed_simulator=5).result().get_counts()
        expected = np.abs(Statevector(qc.remove_final_measurements(inplace=False)).data) ** 2
        for counts in (raw, tr):
            tvd = 0.5 * np.abs(_probabilities(counts, 3) - expected).sum()
            self.assertLess(tvd, 0.05)


if __name__ == "__main__":
    unittest.main()
