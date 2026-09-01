import unittest
import sys
import os

# Add python/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

try:
    from qiskit import QuantumCircuit
    from cq_hecs.provider import VulkanQpuBackend
    HAS_QISKIT = True
except ImportError:
    HAS_QISKIT = False


class TestQiskitAndTranspiler(unittest.TestCase):
    @unittest.skipUnless(HAS_QISKIT, "Qiskit not installed")
    def test_vulkan_backend_initialization(self):
        """Verify VulkanQpuBackend initializes with Linear and Heavy-Hex topologies."""
        backend_linear = VulkanQpuBackend(num_qubits=300, topology="linear")
        self.assertEqual(backend_linear.name, "cq_hecs_vulkan_linear_300q")
        self.assertEqual(backend_linear.target.num_qubits, 300)

        backend_heavy_hex = VulkanQpuBackend(num_qubits=64, topology="heavy_hex")
        self.assertEqual(backend_heavy_hex.name, "cq_hecs_vulkan_heavy_hex_64q")
        self.assertEqual(backend_heavy_hex.target.num_qubits, 64)

    @unittest.skipUnless(HAS_QISKIT, "Qiskit not installed")
    def test_qiskit_bell_circuit_execution(self):
        """Execute Bell State on VulkanQpuBackend and verify deterministic counts."""
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()

        backend = VulkanQpuBackend(num_qubits=2, topology="linear")
        job = backend.run(qc, shots=1024)
        counts = job.get_counts()

        self.assertIn("00", counts)
        self.assertIn("11", counts)
        self.assertEqual(counts["00"] + counts["11"], 1024)
        self.assertNotIn("01", counts)
        self.assertNotIn("10", counts)

    @unittest.skipUnless(HAS_QISKIT, "Qiskit not installed")
    def test_qiskit_ghz300_linear_execution(self):
        """Verify 300-qubit GHZ state execution via Qiskit BackendV2."""
        qc = QuantumCircuit(300)
        qc.h(0)
        for i in range(299):
            qc.cx(i, i + 1)
        qc.measure_all()

        backend = VulkanQpuBackend(num_qubits=300, topology="linear")
        job = backend.run(qc, shots=1000)
        counts = job.get_counts()

        all_zeros = "0" * 300
        all_ones = "1" * 300
        self.assertIn(all_zeros, counts)
        self.assertIn(all_ones, counts)
        self.assertEqual(counts[all_zeros] + counts[all_ones], 1000)


if __name__ == "__main__":
    unittest.main()
