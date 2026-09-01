"""
Test Suite: End-to-End CLI, PowerShell Interop, and Exit Code Verification
Tests binary bin/Release/cq_hecs.exe across all CLI subcommands.
"""

import unittest
import subprocess
import json
import os
from pathlib import Path


class TestCLIPowerShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = Path(__file__).parent.parent
        if os.name == 'nt':
            candidates = [
                base_dir / "bin" / "Release" / "cq_hecs.exe",
                base_dir / "bin" / "cq_hecs.exe",
            ]
        else:
            candidates = [
                base_dir / "bin" / "cq_hecs",
                base_dir / "bin" / "Release" / "cq_hecs",
                base_dir / "build" / "cq_hecs",
            ]
        cls.exe_path = next((p for p in candidates if p.exists()), candidates[0])
        cls.assertTrue(cls, cls.exe_path.exists(), f"Missing binary: {cls.exe_path}")
        if os.name != 'nt':
            os.chmod(cls.exe_path, 0o755)
        cls.bench_dir = Path(__file__).parent.parent / "benchmarks"

    def run_cmd(self, args, input_data=None):
        cmd = [str(self.exe_path)] + args
        res = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True
        )
        return res

    def test_cli_help(self):
        res = self.run_cmd(["--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("CQ-HECS", res.stdout)
        self.assertIn("Commands:", res.stdout)

    def test_cli_self_test(self):
        res = self.run_cmd(["test"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("ALL 7 TESTS PASSED", res.stdout)

    def test_cli_self_test_json(self):
        res = self.run_cmd(["test", "--json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["total_tests"], 7)
        self.assertEqual(data["passed"], 7)
        self.assertEqual(data["failed"], 0)

    def test_cli_qasm_file_and_json(self):
        ghz_path = self.bench_dir / "qasm" / "ghz_300.qasm"
        res = self.run_cmd(["qasm", str(ghz_path), "--json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["qubit_count"], 300)
        self.assertEqual(data["gate_count"], 600)
        self.assertTrue(data["vram_satisfied"])
        self.assertLess(data["active_vram_mb"], 120.0)

    def test_cli_qasm_stdin_piping(self):
        qasm_content = """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[300];
        h q[0];
        cx q[0], q[1];
        measure q[0];
        """
        res = self.run_cmd(["qasm", "-", "--json"], input_data=qasm_content)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["gate_count"], 3)

    def test_cli_sat_unsat_exit_code_10(self):
        pigeon_path = self.bench_dir / "sat" / "pigeonhole_6_5.cnf"
        res = self.run_cmd(["sat", str(pigeon_path), "--json"])
        # Contract: Exit code must be 10 for UNSAT
        self.assertEqual(res.returncode, 10)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "UNSAT")
        self.assertTrue(data["verified"])

    def test_cli_sat_satisfiable_exit_code_0(self):
        sat_cnf = "p cnf 4 3\n1 2 -3 0\n-1 3 4 0\n-2 -4 1 0\n"
        res = self.run_cmd(["sat", "-", "--json"], input_data=sat_cnf)
        # Contract: Exit code must be 0 for SAT
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SAT")
        self.assertTrue(data["verified"])
        self.assertIn("assignment", data)

    def test_cli_arx_ciphers(self):
        for cipher in ["blake2b", "chacha20", "sha256"]:
            res = self.run_cmd(["arx", cipher, "--rounds", "500", "--json"])
            self.assertEqual(res.returncode, 0, f"Failed on {cipher}: {res.stderr}")
            data = json.loads(res.stdout)
            self.assertEqual(data["status"], "SUCCESS")
            self.assertTrue(data["inverse_verified"])
            self.assertTrue(data["carry_shadow_exact"])

    def test_cli_stress_100k(self):
        res = self.run_cmd(["stress", "--cycles", "100000", "--json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["cycles"], 100000)
        self.assertTrue(data["vram_satisfied"])
        self.assertFalse(data["memory_leaks_detected"])

    def test_cli_dashboard_bounded(self):
        res = self.run_cmd(["dashboard", "--cycles", "2"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("CQ-HECS", res.stdout)
        self.assertIn("Exited cleanly after 2 cycles", res.stdout)


if __name__ == "__main__":
    unittest.main()
