"""
Test Suite: DIMACS CNF SAT Engine & J-Space Gamma/Alpha Solver
"""

import unittest
from pathlib import Path
from python_bridge.sat_engine import DIMACSParser, CQSATSolver


class TestSATSolver(unittest.TestCase):
    def setUp(self):
        self.bench_dir = Path(__file__).parent.parent / "benchmarks" / "sat"
        self.solver = CQSATSolver(table_capacity=4096)

    def test_pigeonhole_6_5_unsat(self):
        """Pigeonhole principle with 6 pigeons into 5 holes must prove UNSAT."""
        pigeon_file = self.bench_dir / "pigeonhole_6_5.cnf"
        self.assertTrue(pigeon_file.exists(), f"Missing {pigeon_file}")

        formula = DIMACSParser.parse_file(pigeon_file)
        self.assertEqual(formula.num_vars, 30)
        self.assertEqual(formula.num_clauses, 81)

        result = self.solver.solve(formula, timeout_seconds=5.0)
        self.assertFalse(result.satisfiable, "Pigeonhole 6-into-5 must be UNSAT!")
        self.assertTrue(result.verified, "Proof must be verified!")
        self.assertGreater(result.num_decisions, 0)

    def test_satisfiable_cnf_verification(self):
        """Verify satisfiable formula and certification via isolated oracle."""
        cnf_text = """
        c Satisfiable 4-variable 3-SAT formula
        p cnf 4 3
        1 2 -3 0
        -1 3 4 0
        -2 -4 1 0
        """
        formula = DIMACSParser.parse_string(cnf_text)
        result = self.solver.solve(formula, timeout_seconds=5.0)

        self.assertTrue(result.satisfiable, "Formula should be satisfiable")
        self.assertIsNotNone(result.assignment)
        self.assertTrue(result.verified, "Solution must be certified by forward oracle")

    def test_uf50_hard_solver(self):
        """Test on hard 50-variable 3-SAT instance."""
        uf50_file = self.bench_dir / "uf50_hard.cnf"
        self.assertTrue(uf50_file.exists(), f"Missing {uf50_file}")

        formula = DIMACSParser.parse_file(uf50_file)
        self.assertEqual(formula.num_vars, 50)
        self.assertEqual(formula.num_clauses, 218)

        # Run solver with timeout
        result = self.solver.solve(formula, timeout_seconds=2.0)
        self.assertTrue(result.verified)


if __name__ == "__main__":
    unittest.main()
