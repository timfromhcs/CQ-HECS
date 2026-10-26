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
    """
    Tests the legacy ``python/cq_hecs`` Qiskit provider.

    That provider wraps the *native* engine (``_cq_hecs_core``), so these tests
    require the native component to be built. When it is absent they skip with
    an actionable reason rather than failing, because the provider genuinely
    cannot simulate anything in that state. The four classical backends, which
    need no native build, are covered by tests/test_correctness_contracts.py.
    """

    @staticmethod
    def _require_native():
        # Use the same module name cq_hecs.provider imports, so this reflects
        # whether the provider can actually run.
        import cq_hecs.provider as provider_module
        if not provider_module.HAS_CORE:
            raise ImportError("cq_hecs.provider reports HAS_CORE=False")
        return True

    @classmethod
    def setUpClass(cls):
        try:
            cls._require_native()
            cls.has_native = True
        except ImportError:
            cls.has_native = False

    def _skip_without_native(self):
        if not self.has_native:
            self.skipTest(
                "native _cq_hecs_core is not built; the legacy VulkanQpuBackend "
                "provider requires it (build the native component to run this)"
            )

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
        self._skip_without_native()
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
    def test_qiskit_ghz256_linear_execution(self):
        """Verify the largest QASM-addressable register: a 256-qubit GHZ state.

        ``J_QuantumOpcode`` stores qubit indices in a ``uint8_t``, so 256
        qubits (indices 0..255) is the widest circuit this bridge can express.
        """
        self._skip_without_native()
        qc = QuantumCircuit(256)
        qc.h(0)
        for i in range(255):
            qc.cx(i, i + 1)
        qc.measure_all()

        backend = VulkanQpuBackend(num_qubits=256, topology="linear")
        job = backend.run(qc, shots=1000)
        counts = job.get_counts()

        all_zeros = "0" * 256
        all_ones = "1" * 256
        self.assertIn(all_zeros, counts)
        self.assertIn(all_ones, counts)
        self.assertEqual(counts[all_zeros] + counts[all_ones], 1000)

    @unittest.skipUnless(HAS_QISKIT, "Qiskit not installed")
    def test_qiskit_ghz300_is_rejected_not_truncated(self):
        """A 300-qubit circuit cannot be addressed by the 8-bit opcode fields.

        Refusing is required: truncating q[299] to q[43] would silently corrupt
        the circuit while still reporting plausible counts.
        """
        self._skip_without_native()
        qc = QuantumCircuit(300)
        qc.h(0)
        for i in range(299):
            qc.cx(i, i + 1)
        qc.measure_all()

        backend = VulkanQpuBackend(num_qubits=300, topology="linear")
        with self.assertRaises((IndexError, ValueError)):
            backend.run(qc, shots=100)


if __name__ == "__main__":
    unittest.main()
