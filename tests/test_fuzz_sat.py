"""
Fuzzing Test Suite: DIMACS CNF SAT Engine Robustness
Tests edge-case, degenerate, malformed, and contradictory formulas against the C++ SAT solver.
"""

import unittest
import subprocess
import json
import os
from pathlib import Path

#: Conservative wall-clock bound for a *fuzz* input. The solver itself has a
#: 15 s budget; the subprocess ceiling also catches a parser that never returns.
SAT_FUZZ_TIMEOUT_SECONDS = 30


class TestFuzzSAT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.native_artifacts import require_executable

        cls.exe_path = require_executable()
        if os.name != 'nt':
            os.chmod(cls.exe_path, 0o755)

    def run_cpp_sat(self, cnf_str: str, label: str = ""):
        try:
            res = subprocess.run(
                [str(self.exe_path), "sat", "-", "--json"],
                input=cnf_str,
                capture_output=True,
                text=True,
                timeout=SAT_FUZZ_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            # Sanitized: report only the input size and test label, never the
            # arbitrary hostile payload.
            self.fail(
                f"SAT subprocess exceeded {SAT_FUZZ_TIMEOUT_SECONDS}s for "
                f"{len(cnf_str)} bytes of DIMACS input{(' (' + label + ')') if label else ''}"
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

    def test_huge_declared_variable_count_is_rejected_without_allocating(self):
        # 100 million declared variables must be refused by the parser ceiling,
        # not turned into a 100M-element allocation.
        res = self.run_cpp_sat("p cnf 100000000 0\n", label="huge-vars")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["status"], "ERROR")

    def test_huge_declared_clause_count_is_rejected_without_allocating(self):
        res = self.run_cpp_sat("p cnf 1 100000000\n", label="huge-clauses")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["status"], "ERROR")

    def test_unterminated_clause_is_rejected(self):
        res = self.run_cpp_sat("p cnf 2 1\n1 2\n", label="unterminated")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["status"], "ERROR")

    def test_literal_beyond_declared_variable_count_is_rejected(self):
        res = self.run_cpp_sat("p cnf 2 1\n3 0\n", label="literal-out-of-range")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["status"], "ERROR")

    def test_non_numeric_literal_is_rejected(self):
        res = self.run_cpp_sat("p cnf 2 1\nx 0\n", label="non-numeric")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["status"], "ERROR")

    def test_duplicate_header_is_rejected(self):
        res = self.run_cpp_sat("p cnf 2 1\np cnf 2 1\n1 0\n", label="dup-header")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["status"], "ERROR")

    def test_duplicate_literals_are_accepted(self):
        res = self.run_cpp_sat("p cnf 2 1\n1 1 0\n")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(json.loads(res.stdout)["status"], "SAT")

    def test_tautological_clause_is_accepted(self):
        res = self.run_cpp_sat("p cnf 2 1\n1 -1 0\n")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(json.loads(res.stdout)["status"], "SAT")


if __name__ == "__main__":
    unittest.main()
