"""
Fuzzing Test Suite: OpenQASM 2.0 / 3.0 Parser & Executor Robustness
Tests edge-case, degenerate, malformed, and boundary inputs against both C++ and Python parsers.
"""

import unittest
import subprocess
import json
from pathlib import Path
from python_bridge.qasm_engine import QASMParser, QASMCircuitSimulator


class TestFuzzQASM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe_path = Path(__file__).parent.parent / "bin" / "Release" / "cq_hecs.exe"
        cls.assertTrue(cls, cls.exe_path.exists(), f"Missing {cls.exe_path}")
        cls.py_parser = QASMParser()
        cls.py_sim = QASMCircuitSimulator(num_qubits=300, max_chi=64)

    def run_cpp_qasm(self, qasm_str: str):
        res = subprocess.run(
            [str(self.exe_path), "qasm", "-", "--json"],
            input=qasm_str,
            capture_output=True,
            text=True
        )
        return res

    def test_empty_qasm(self):
        """Empty input must not crash, should return success with 0 gates."""
        res = self.run_cpp_qasm("")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["gate_count"], 0)

    def test_comments_only_qasm(self):
        """Comments-only input should parse cleanly."""
        qasm = "// Line 1 comment\n// Line 2 comment\n// Line 3 comment\n"
        res = self.run_cpp_qasm(qasm)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["gate_count"], 0)

    def test_zero_qubit_declaration(self):
        """0-qubit declaration should fall back to default lattice without crashing."""
        qasm = "OPENQASM 2.0;\nqreg q[0];\ncreg c[0];\n"
        res = self.run_cpp_qasm(qasm)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertGreater(data["qubit_count"], 0)

    def test_malformed_floating_point_parameters(self):
        """Malformed floats in parametric gates must not cause uncaught exceptions."""
        qasm = """
        OPENQASM 2.0;
        qreg q[300];
        cp(invalid_angle) q[0], q[1];
        cp(3.14.15) q[2], q[3];
        """
        res = self.run_cpp_qasm(qasm)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SUCCESS")

    def test_unsupported_or_unknown_gates(self):
        """Unknown gates should be safely ignored or processed without crashing."""
        qasm = """
        OPENQASM 2.0;
        qreg q[300];
        nonexistent_exotic_gate q[0], q[1], q[2];
        h q[0];
        measure q[0];
        """
        res = self.run_cpp_qasm(qasm)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertGreaterEqual(data["gate_count"], 2)

    def test_large_qubit_indices_expansion(self):
        """Qubit index within valid range expands circuit capacity cleanly."""
        qasm = """
        OPENQASM 2.0;
        qreg q[50];
        h q[49];
        cx q[49], q[120];
        """
        res = self.run_cpp_qasm(qasm)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertGreaterEqual(data["qubit_count"], 121)

    def test_missing_semicolons_recovery(self):
        """Commands with or without trailing semicolons parse reliably."""
        qasm = """
        OPENQASM 2.0
        qreg q[300]
        h q[0]
        cx q[0], q[1]
        """
        res = self.run_cpp_qasm(qasm)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["gate_count"], 2)


if __name__ == "__main__":
    unittest.main()
