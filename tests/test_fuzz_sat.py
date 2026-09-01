"""
Fuzzing Test Suite: DIMACS CNF SAT Engine Robustness
Tests edge-case, degenerate, malformed, and contradictory formulas against the C++ SAT solver.
"""

import unittest
import subprocess
import json
from pathlib import Path


class TestFuzzSAT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe_path = Path(__file__).parent.parent / "bin" / "Release" / "cq_hecs.exe"
        cls.assertTrue(cls, cls.exe_path.exists(), f"Missing {cls.exe_path}")

    def run_cpp_sat(self, cnf_str: str):
        res = subprocess.run(
            [str(self.exe_path), "sat", "-", "--json"],
            input=cnf_str,
            capture_output=True,
            text=True
        )
        return res

    def test_empty_cnf(self):
        """Empty CNF formula is trivially satisfiable."""
        res = self.run_cpp_sat("")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SAT")

    def test_zero_vars_zero_clauses(self):
        """p cnf 0 0 header with no clauses is trivially SAT."""
        res = self.run_cpp_sat("p cnf 0 0\n")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SAT")

    def test_empty_clause_unsat(self):
        """A clause with 0 literals is immediately UNSAT (Exit code 10)."""
        # Literal 0 alone defines an empty clause
        res = self.run_cpp_sat("p cnf 2 1\n0\n")
        self.assertEqual(res.returncode, 10)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "UNSAT")
        self.assertTrue(data["verified"])

    def test_contradictory_unit_clauses_unsat(self):
        """Direct contradiction (1 and -1) must return UNSAT with exit code 10."""
        cnf = "p cnf 1 2\n1 0\n-1 0\n"
        res = self.run_cpp_sat(cnf)
        self.assertEqual(res.returncode, 10)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "UNSAT")
        self.assertTrue(data["verified"])

    def test_excessive_whitespace_and_blank_lines(self):
        """Heavy trailing spaces, tabs, and interspersed blank lines."""
        cnf = """
        c Comments with lots of spacing
        p    cnf    3   2   

        1    2    0   
        -1       3   0   
        """
        res = self.run_cpp_sat(cnf)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SAT")
        self.assertTrue(data["verified"])

    def test_huge_variable_indices_safe_bound(self):
        """Variables within safe range (e.g. 500) parse and solve safely."""
        cnf = "p cnf 500 2\n500 -250 0\n-500 250 0\n"
        res = self.run_cpp_sat(cnf)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "SAT")


if __name__ == "__main__":
    unittest.main()
