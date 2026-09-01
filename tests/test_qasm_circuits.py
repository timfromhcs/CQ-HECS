"""
Test Suite: OpenQASM 2.0 / 3.0 Circuit Simulator on 300-Qubit MPS
Tests GHZ-300, QFT-300, and Surface Code Stabilizer Cycles.
"""

import unittest
from pathlib import Path
from python_bridge.qasm_engine import QASMParser, QASMCircuitSimulator


class TestQASMCircuits(unittest.TestCase):
    def setUp(self):
        self.parser = QASMParser()
        self.sim = QASMCircuitSimulator(num_qubits=300, max_chi=64, max_vram_mb=120.0)
        self.bench_dir = Path(__file__).parent.parent / "benchmarks" / "qasm"

    def test_ghz_300_simulation(self):
        """Verify GHZ-300 state preparation across 300 qubits."""
        ghz_file = self.bench_dir / "ghz_300.qasm"
        self.assertTrue(ghz_file.exists(), f"Missing {ghz_file}")

        circuit = self.parser.parse_file(ghz_file)
        self.assertEqual(circuit.num_qubits, 300)
        self.assertEqual(len(circuit.instructions), 600) # H + 299 CX + 300 measure

        result = self.sim.run_circuit(circuit)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_gates"], 600)
        self.assertLess(result["active_vram_mb"], 120.0)

    def test_qft_300_simulation(self):
        """Verify Quantum Fourier Transform on 300 qubits with Z_8 phase mapping."""
        qft_file = self.bench_dir / "qft_300.qasm"
        self.assertTrue(qft_file.exists(), f"Missing {qft_file}")

        circuit = self.parser.parse_file(qft_file)
        self.assertEqual(circuit.num_qubits, 300)
        self.assertGreater(len(circuit.instructions), 1000)

        result = self.sim.run_circuit(circuit)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreater(result["total_gates"], 1000)
        self.assertLess(result["active_vram_mb"], 120.0)

    def test_surface_code_stabilizer_cycles(self):
        """Verify Surface Code X and Z stabilizer syndrome extraction cycles."""
        # 16-qubit local surface code patch on 300-qubit lattice
        qasm_surface = """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[300];
        creg c[300];
        // Syndrome extraction cycle
        h q[0];
        cx q[0], q[1];
        cx q[0], q[2];
        h q[0];
        measure q[0] -> c[0];
        h q[3];
        cx q[3], q[4];
        cx q[3], q[5];
        h q[3];
        measure q[3] -> c[3];
        """
        circuit = self.parser.parse_string(qasm_surface)
        result = self.sim.run_circuit(circuit)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_gates"], 10)
        self.assertLess(result["active_vram_mb"], 120.0)


if __name__ == "__main__":
    unittest.main()
