import unittest
import sys
import os

# Add python/ directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "python")))

try:
    from qiskit import QuantumCircuit
    from cqhecs.provider import CQHecsBackend
    HAS_QISKIT = True
except ImportError:
    HAS_QISKIT = False


class TestQiskitDropin(unittest.TestCase):
    @unittest.skipUnless(HAS_QISKIT, "Qiskit is not installed")
    def test_100_qubit_ghz_circuit(self):
        """
        Verify end-to-end execution of a 100-qubit GHZ state directly via Qiskit.
        Assert that measurement counts contain ONLY '00...0' and '11...1' (~50% each).
        """
        num_qubits = 100
        shots = 2000

        # Build 100-qubit GHZ circuit in Qiskit
        qc = QuantumCircuit(num_qubits)
        qc.h(0)
        for i in range(num_qubits - 1):
            qc.cx(i, i + 1)
        qc.measure_all()

        # Execute on CQHecsBackend (BackendV2)
        backend = CQHecsBackend(num_qubits=num_qubits)
        job = backend.run(qc, shots=shots)
        result = job.result()
        counts = result.get_counts()

        all_zeros = "0" * num_qubits
        all_ones = "1" * num_qubits

        # Assert only valid GHZ states appear
        self.assertIn(all_zeros, counts)
        self.assertIn(all_ones, counts)
        self.assertEqual(len(counts), 2, f"Expected exactly 2 outcomes, got {len(counts)}")
        self.assertEqual(counts[all_zeros] + counts[all_ones], shots)

        # Assert ~50% distribution (within 6 sigma bounds)
        ratio_zeros = counts[all_zeros] / shots
        ratio_ones = counts[all_ones] / shots
        print(f"\n[Qiskit Drop-In] 100-Qubit GHZ Results:")
        print(f"  |0>^{num_qubits}: {counts[all_zeros]} ({ratio_zeros * 100:.1f}%)")
        print(f"  |1>^{num_qubits}: {counts[all_ones]} ({ratio_ones * 100:.1f}%)")

        self.assertGreater(ratio_zeros, 0.40)
        self.assertLess(ratio_zeros, 0.60)
        self.assertGreater(ratio_ones, 0.40)
        self.assertLess(ratio_ones, 0.60)


if __name__ == "__main__":
    unittest.main()
