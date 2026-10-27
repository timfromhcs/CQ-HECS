"""CQ-10: large-register inputs must be refused before huge allocations."""

import unittest

from qiskit import QuantumCircuit

from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import (
    PathBStabilizerRankBackend,
    StabilizerRankError,
)
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend


class TestBackendSizeCeilings(unittest.TestCase):
    def test_every_backend_refuses_oversized_registers(self):
        backends = (
            ("A", PathAStabilizerBackend(), ValueError, PathAStabilizerBackend.MAX_QUBITS),
            ("B", PathBStabilizerRankBackend(), StabilizerRankError, PathBStabilizerRankBackend.MAX_QUBITS),
            ("C", PathCMPSExactBackend(), ValueError, 4096),
            ("D", PathDSparsePauliBackend(), ValueError, PathDSparsePauliBackend.MAX_QUBITS),
        )
        for name, backend, exc_type, ceiling in backends:
            with self.subTest(path=name):
                qc = QuantumCircuit(ceiling + 1)
                with self.assertRaises(exc_type) as ctx:
                    backend.execute(qc, shots=8)
                self.assertIn(str(ceiling), str(ctx.exception))

    def test_oversized_shots_are_refused(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        for name, backend, exc_type in (
            ("A", PathAStabilizerBackend(), ValueError),
            ("B", PathBStabilizerRankBackend(), ValueError),
            ("C", PathCMPSExactBackend(), ValueError),
            ("D", PathDSparsePauliBackend(), ValueError),
        ):
            with self.subTest(path=name):
                with self.assertRaises(exc_type):
                    backend.execute(qc, shots=backend.MAX_SHOTS + 1)

    def test_qasm_register_is_bounded_before_execution(self):
        # A syntactically legal but physically unreasonable register must be
        # refused by execution, not materialised as millions of tensors.
        from cqhecs.circuit_parsing import parse_circuit

        qasm = "OPENQASM 2.0;\nqreg q[1000000];\ncreg c[1];\nmeasure q[0] -> c[0];\n"
        instructions, n_q = parse_circuit(qasm)
        self.assertEqual(n_q, 1_000_000)
        self.assertTrue(instructions)
        with self.assertRaises(ValueError):
            PathCMPSExactBackend().execute(qasm, shots=8)


if __name__ == "__main__":
    unittest.main()
