"""Path C tensor-axis / operand-order contract (CQ-01 regression).

The MPS chain stores a two-site block as ``[left, right]`` in chain order
(``left`` is the lower qubit index), while a gate matrix is ordered by the
operation's *operand* order.  When a gate is applied as ``(q1, q2)`` with
``q1 > q2`` those two orders disagree on both inputs and outputs.  The original
implementation swapped only the output axes, silently transposing the
control/target inputs.

Every test here uses an independent Qiskit ``Statevector`` reference.  Qiskit
orders the *operands* of an operator little-endian (first operand is the least
significant matrix index), so the reference matrix is explicitly re-ordered to
the chain's big-endian operand convention before it is handed to the chain.
That conversion is itself pinned by a test.
"""

import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import (
    CPhaseGate,
    CRXGate,
    CRYGate,
    CRZGate,
    CU1Gate,
    CXGate,
    CZGate,
    SwapGate,
)
from qiskit.quantum_info import Operator, Statevector

from cqhecs.backends.path_c_mps_exact import (
    ExactMPSTensorChain,
    PathCMPSExactBackend,
)


def _chain_matrix_from_qiskit(matrix: np.ndarray, num_gate_qubits: int) -> np.ndarray:
    """Re-orders a Qiskit operator matrix into CQ-HECS operand order.

    Qiskit's flat index is ``sum(q_i * 2**i)`` (first operand least
    significant); CQ-HECS's is ``sum(q_i * 2**(n-1-i))`` (first operand most
    significant).  The reshape exposes the axes as
    ``(out_last, ..., out_first, in_last, ..., in_first)`` and the transpose
    reverses each group.
    """
    dim = 1 << num_gate_qubits
    tensor = np.asarray(matrix, dtype=np.complex128).reshape((2,) * (2 * num_gate_qubits))
    out_perm = tuple(reversed(range(num_gate_qubits)))
    in_perm = tuple(reversed(range(num_gate_qubits, 2 * num_gate_qubits)))
    return tensor.transpose(out_perm + in_perm).reshape(dim, dim)


def _mps_vector_in_qiskit_order(mps: ExactMPSTensorChain, n: int) -> np.ndarray:
    """``to_statevector()`` is in chain order (q0 outermost); Qiskit is the reverse."""
    tensor = np.asarray(mps.to_statevector()).reshape((2,) * n)
    return tensor.transpose(tuple(reversed(range(n)))).reshape(-1)


def _run_unitary_circuit_on_chain(qc: QuantumCircuit) -> np.ndarray:
    mps = ExactMPSTensorChain(num_qubits=qc.num_qubits, ram_budget_mb=128.0)
    try:
        for inst in qc.data:
            op = inst.operation
            if op.name in {"barrier", "id"}:
                continue
            qubits = [qc.find_bit(q).index for q in inst.qubits]
            matrix = np.asarray(Operator(op).data, dtype=np.complex128)
            if len(qubits) == 1:
                mps.apply_single_qubit_gate(qubits[0], matrix)
            elif len(qubits) == 2:
                mps.apply_two_qubit_gate(
                    qubits[0],
                    qubits[1],
                    _chain_matrix_from_qiskit(matrix, 2),
                )
            else:
                raise AssertionError(f"unexpected gate arity in test: {op.name}")
            if mps.memory_limit_exceeded:
                raise AssertionError("small reference circuit exceeded the budget")
        return _mps_vector_in_qiskit_order(mps, qc.num_qubits).copy()
    finally:
        mps.cleanup()


def _fidelity_ignoring_global_phase(expected: np.ndarray, actual: np.ndarray) -> float:
    e = np.asarray(expected, dtype=np.complex128)
    a = np.asarray(actual, dtype=np.complex128)
    e = e / np.linalg.norm(e)
    a = a / np.linalg.norm(a)
    return float(abs(np.vdot(e, a)) ** 2)


def _counts_to_probs(counts, num_qubits: int) -> np.ndarray:
    total = sum(counts.values())
    assert total > 0
    out = np.zeros(1 << num_qubits, dtype=float)
    for bitstring, count in counts.items():
        out[int(bitstring, 2)] = count / total
    return out


TWO_QUBIT_GATES = {
    "cx": CXGate(),
    "cz": CZGate(),
    "swap": SwapGate(),
    "cp": CPhaseGate(0.41),
    "crx": CRXGate(0.53),
    "cry": CRYGate(-0.29),
    "crz": CRZGate(0.71),
    "cu1": CU1Gate(0.41),
}


class TestChainMatrixConversion(unittest.TestCase):
    """Pin the test helper's convention so a wrong oracle cannot hide a bug."""

    def test_conversion_preserves_standard_cx_and_swap(self):
        cx_expected = np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
            dtype=np.complex128,
        )
        swap_expected = np.array(
            [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]],
            dtype=np.complex128,
        )
        np.testing.assert_allclose(
            _chain_matrix_from_qiskit(Operator(CXGate()).data, 2), cx_expected
        )
        np.testing.assert_allclose(
            _chain_matrix_from_qiskit(Operator(SwapGate()).data, 2), swap_expected
        )

    def test_conversion_preserves_one_qubit_matrix(self):
        x = np.array([[0, 1], [1, 0]], dtype=np.complex128)
        np.testing.assert_allclose(_chain_matrix_from_qiskit(x, 1), x)


class TestPathCOperandOrder(unittest.TestCase):
    """CQ-01 regression: both operand orders, adjacent and non-adjacent."""

    def test_reversed_cx_basis_state_support_is_exact(self):
        """Deterministic support checks; these were all wrong before the fix."""
        cases = [
            # (name, preparation, gate operands, expected support)
            ("x0_cx_0_1", "x(0)", (0, 1), {"11"}),
            ("x0_cx_1_0", "x(0)", (1, 0), {"01"}),
            ("x1_cx_1_0", "x(1)", (1, 0), {"11"}),
            ("x1_cx_0_1", "x(1)", (0, 1), {"10"}),
        ]
        backend = PathCMPSExactBackend(ram_budget_mb=64.0)
        for name, prep, (a, b), expected_support in cases:
            qc = QuantumCircuit(2)
            if prep == "x(0)":
                qc.x(0)
            else:
                qc.x(1)
            qc.append(CXGate(), [a, b])
            result = backend.execute(qc, shots=256, seed=7)
            self.assertFalse(result.unresolved, name)
            self.assertEqual(sum(result.counts.values()), 256, name)
            self.assertEqual(set(result.counts), expected_support, name)

    def test_all_supported_two_qubit_gates_both_orders(self):
        """Compare the full state up to global phase, not only sampled counts."""
        for gate_name, gate in TWO_QUBIT_GATES.items():
            for operands in ((0, 1), (1, 0)):
                with self.subTest(gate=gate_name, operands=operands):
                    qc = QuantumCircuit(3)
                    qc.h(0)
                    qc.ry(0.37, 1)
                    qc.x(2)
                    qc.append(gate, list(operands))
                    qc.rz(0.23, 2)

                    actual = _run_unitary_circuit_on_chain(qc)
                    expected = np.asarray(Statevector(qc).data, dtype=np.complex128)
                    self.assertGreater(
                        _fidelity_ignoring_global_phase(expected, actual),
                        1.0 - 1e-9,
                        msg=f"{gate_name} on {operands} does not match Statevector",
                    )

    def test_non_adjacent_pairs_both_orders(self):
        for gate_name in ("cx", "swap"):
            gate = TWO_QUBIT_GATES[gate_name]
            for operands in ((0, 2), (2, 0)):
                with self.subTest(gate=gate_name, operands=operands):
                    qc = QuantumCircuit(4)
                    qc.h(0)
                    qc.ry(0.29, 1)
                    qc.x(2)
                    qc.rz(0.4, 3)
                    qc.append(gate, list(operands))
                    qc.ry(0.17, 2)
                    qc.cx(3, 1)

                    actual = _run_unitary_circuit_on_chain(qc)
                    expected = np.asarray(Statevector(qc).data, dtype=np.complex128)
                    self.assertGreater(
                        _fidelity_ignoring_global_phase(expected, actual),
                        1.0 - 1e-9,
                        msg=f"{gate_name} on {operands} does not match Statevector",
                    )

    def test_random_small_circuits_match_statevector(self):
        rng = np.random.default_rng(20261027)
        gate_table = list(TWO_QUBIT_GATES.values())
        for trial in range(12):
            n = 4
            qc = QuantumCircuit(n)
            for q in range(n):
                qc.ry(float(rng.uniform(-np.pi, np.pi)), q)
            for _ in range(10):
                if rng.random() < 0.5:
                    q = int(rng.integers(0, n))
                    qc.rz(float(rng.uniform(-np.pi, np.pi)), q)
                else:
                    a, b = rng.choice(n, size=2, replace=False)
                    gate = gate_table[int(rng.integers(0, len(gate_table)))]
                    qc.append(gate, [int(a), int(b)])
            with self.subTest(trial=trial):
                actual = _run_unitary_circuit_on_chain(qc)
                expected = np.asarray(Statevector(qc).data, dtype=np.complex128)
                self.assertGreater(
                    _fidelity_ignoring_global_phase(expected, actual),
                    1.0 - 1e-9,
                )

    def test_backend_two_qubit_matrices_both_orders(self):
        """
        CQ-01b regression: the backend, not only the chain, must apply each
        canonical gate matrix. The earlier backend hard-coded `crx`/`cry`
        blocks on the wrong basis states and passed raw Qiskit matrices to a
        chain that expects operand-ordered axes; only chain-level tests existed.
        """
        from qiskit.circuit.library import CRXGate, CRYGate, CRZGate
        from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend

        backend = PathCMPSExactBackend(ram_budget_mb=64.0)
        shots = 100_000
        for name, gate in (
            ("crx", CRXGate(0.83)),
            ("cry", CRYGate(-0.57)),
            ("crz", CRZGate(0.71)),
        ):
            for operands in ((0, 1), (1, 0)):
                with self.subTest(gate=name, operands=operands):
                    qc = QuantumCircuit(2)
                    qc.h(0)
                    qc.ry(0.37, 1)
                    qc.append(gate, list(operands))
                    # Phase-sensitive readout: a diagonal-only mistake would not
                    # change the pre-readout probabilities.
                    qc.h(0)
                    qc.ry(0.19, 1)
                    result = backend.execute(qc, shots=shots, seed=11)
                    self.assertFalse(result.unresolved)
                    got = _counts_to_probs(result.counts, 2)
                    expected = Statevector(qc).probabilities()
                    tv = 0.5 * float(np.abs(got - expected).sum())
                    self.assertLess(tv, 0.01, f"{name} {operands}: TVD {tv}")

    def test_sampled_distribution_for_reversed_asymmetric_circuit(self):
        qc = QuantumCircuit(3)
        qc.h(2)
        qc.ry(0.37, 1)
        qc.cx(2, 0)
        qc.cp(0.41, 2, 1)
        qc.swap(1, 0)

        shots = 60000
        result = PathCMPSExactBackend(ram_budget_mb=64.0).execute(
            qc, shots=shots, seed=1234
        )
        self.assertFalse(result.unresolved)
        self.assertEqual(sum(result.counts.values()), shots)
        got = _counts_to_probs(result.counts, qc.num_qubits)
        expected = Statevector(qc).probabilities()
        tv = 0.5 * float(np.abs(got - expected).sum())
        # 8 outcomes, 60k shots -> a 6-sigma TV envelope is far below 0.01.
        self.assertLess(tv, 0.01)


if __name__ == "__main__":
    unittest.main()
