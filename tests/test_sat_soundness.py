"""Soundness of the pure-Python SAT engine (GEMINI.md §3.1/§3.2, CQ-V3-01/02).

Before the fix a timeout returned ``satisfiable=False, verified=True`` and the
cycle pruner keyed states by a hash of the first 32 assigned variables, so a
satisfiable formula with 32 forced variables was reported as a verified UNSAT.
"""

from __future__ import annotations

import itertools
import random
import unittest

from python_bridge.sat_engine import (
    SAT_VERIFIED,
    TIMEOUT_UNKNOWN,
    UNSAT_PROVEN,
    CNFFormula,
    CQSATSolver,
)


def _formula(num_vars, clauses):
    return CNFFormula(num_vars=num_vars, num_clauses=len(clauses), clauses=[list(c) for c in clauses])


def _brute_force(num_vars, clauses):
    for bits in itertools.product((False, True), repeat=num_vars):
        if all(any(bits[abs(l) - 1] == (l > 0) for l in c) for c in clauses):
            return True
    return False


class SatSoundnessTests(unittest.TestCase):
    def test_timeout_is_unknown_never_unsat(self):
        clauses = [[1, 2, 3], [-1, -2], [2, -3]]
        result = CQSATSolver().solve(_formula(3, clauses), timeout_seconds=-1.0)
        self.assertEqual(result.status, TIMEOUT_UNKNOWN)
        self.assertIsNone(result.satisfiable)
        self.assertFalse(result.verified)
        self.assertTrue(result.timed_out)

    def test_branches_beyond_the_32nd_variable_are_not_merged(self):
        units = [[v] for v in range(1, 33)]
        rest = [[33, 34, 35], [-33, -34, 36], [-35, -36, 37], [33, -37, 38], [-38, 34, -36]]
        result = CQSATSolver().solve(_formula(38, units + rest))
        self.assertEqual(result.status, SAT_VERIFIED)
        self.assertTrue(result.satisfiable)

    def test_a_refuted_sibling_with_the_same_32_variable_prefix_is_not_merged(self):
        units = [[v] for v in range(1, 33)]
        rest = [
            [35, -34, 36], [33, -36, -35], [-35, 34, -36], [34, -33, -35], [36, -34, 33],
            [-33, 36, -35], [33, 34, 36], [-35, 36, -33], [35, -36, -33], [-34, -36, -35],
            [-33, -34, -35], [-33, -35, -34], [35, -33, -36], [-33, -36, -35], [33, 34, -36],
            [36, -35, 34],
        ]
        result = CQSATSolver().solve(_formula(36, units + rest))
        self.assertTrue(result.satisfiable)
        self.assertEqual(result.status, SAT_VERIFIED)

    def test_a_constant_hash_cannot_change_the_answer(self):
        solver = CQSATSolver()
        solver._compute_state_hash = lambda assignment: 7  # adversarial collisions
        clauses = [[1, 2], [-1, 3], [-2, -3], [2, 3]]
        result = solver.solve(_formula(3, clauses))
        self.assertEqual(result.satisfiable, _brute_force(3, clauses))

    def test_random_cnfs_agree_with_brute_force(self):
        rng = random.Random(20261030)
        for _ in range(300):
            n = rng.randint(1, 9)
            m = rng.randint(1, 4 * n)
            clauses = []
            for _ in range(m):
                width = rng.randint(1, min(3, n))
                variables = rng.sample(range(1, n + 1), width)
                clauses.append([v if rng.random() < 0.5 else -v for v in variables])
            result = CQSATSolver().solve(_formula(n, clauses), timeout_seconds=30.0)
            expected = _brute_force(n, clauses)
            self.assertEqual(result.satisfiable, expected, clauses)
            self.assertEqual(result.status, SAT_VERIFIED if expected else UNSAT_PROVEN)
            self.assertTrue(result.verified)
            if expected:
                self.assertTrue(all(any(result.assignment[abs(l)] == (l > 0) for l in c) for c in clauses))


if __name__ == "__main__":
    unittest.main()
