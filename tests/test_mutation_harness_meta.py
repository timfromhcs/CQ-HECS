"""
Meta-tests for scripts/run_mutation_tests.py.

Verifies the mutation testing harness itself:
- A broken baseline causes main() to exit with code 1 and logs failures.
- A surviving mutant causes main() to exit with code 1.
- A harness error causes main() to exit with code 1.
- The clean baseline and all mutants killed exits with code 0.
"""

from __future__ import annotations
import unittest
from unittest.mock import patch
import io
import sys

from scripts import run_mutation_tests


class TestMutationHarnessMeta(unittest.TestCase):
    def test_clean_baseline_and_all_killed_exits_zero(self):
        """Clean baseline where all 7 mutants are killed returns 0."""
        with patch("sys.stdout", new=io.StringIO()):
            exit_code = run_mutation_tests.main()
        self.assertEqual(exit_code, 0)

    def test_broken_baseline_fails_closed_with_exit_one(self):
        """If any baseline invariant check fails, main() must return exit code 1."""
        broken_check = ("Broken invariant test", lambda: False, "Deliberate baseline failure")
        with patch.object(run_mutation_tests, "BASELINE_CHECKS", [broken_check]):
            out = io.StringIO()
            with patch("sys.stdout", out):
                exit_code = run_mutation_tests.main()
            self.assertEqual(exit_code, 1)
            self.assertIn("[FAIL] Baseline is broken", out.getvalue())

    def test_surviving_mutant_fails_closed_with_exit_one(self):
        """If a mutant survives (undetected defect), main() must return exit code 1."""
        surviving_mutant = ("Undetected defect mutant", lambda: False)
        with patch.object(run_mutation_tests, "MUTANTS", [surviving_mutant]):
            out = io.StringIO()
            with patch("sys.stdout", out):
                exit_code = run_mutation_tests.main()
            self.assertEqual(exit_code, 1)
            self.assertIn("[SURVIVED] Mutant 1: Undetected defect mutant", out.getvalue())
            self.assertIn("[FAIL] Mutation gate not met", out.getvalue())

    def test_harness_error_fails_closed_with_exit_one(self):
        """If a mutant function raises an unexpected error, it is a harness error and returns 1."""
        def buggy_mutant():
            raise ZeroDivisionError("Crash inside mutant test")

        error_mutant = ("Crashing mutant", buggy_mutant)
        with patch.object(run_mutation_tests, "MUTANTS", [error_mutant]):
            out = io.StringIO()
            with patch("sys.stdout", out):
                exit_code = run_mutation_tests.main()
            self.assertEqual(exit_code, 1)
            self.assertIn("[HARNESS ERROR] Mutant 1: Crashing mutant", out.getvalue())
            self.assertIn("[FAIL] Mutation gate not met", out.getvalue())


if __name__ == "__main__":
    unittest.main()
