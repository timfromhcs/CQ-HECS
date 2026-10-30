"""Python/native DIMACS parity (GEMINI.md 3.3, CQ-V3-03).

The Python parser used to split a clause that spans lines and to drop an empty
clause ``0``; the first can turn a satisfiable formula into an unsatisfiable
one, the second an unsatisfiable formula into a "verified" satisfiable one.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest

from python_bridge.sat_engine import CQSATSolver, DIMACSParseError, DIMACSParser

# (label, DIMACS, expected: "SAT" | "UNSAT" | "ERROR")
CASES = [
    ("clause spans lines", "p cnf 3 2\n1 2\n3 0 -1 0\n", "SAT"),
    ("two clauses on one line", "p cnf 2 2\n1 0 -1 0\n", "UNSAT"),
    ("empty clause makes UNSAT", "p cnf 2 2\n0\n1 0\n", "UNSAT"),
    ("unterminated final clause", "p cnf 2 1\n1 2\n", "ERROR"),
    ("literal above declared count", "p cnf 2 1\n1 5 0\n", "ERROR"),
    ("negative header count", "p cnf -3 1\n1 0\n", "ERROR"),
    ("duplicate header", "p cnf 2 1\np cnf 2 1\n1 0\n", "ERROR"),
    ("malformed header", "p dnf 2 1\n1 0\n", "ERROR"),
    ("non-integer literal", "p cnf 2 1\n1 x 0\n", "ERROR"),
    ("no header grows variables", "1 -2 0\n2 0\n", "SAT"),
    ("comments and blanks", "c hello\n\np cnf 1 1\n  1 0\n", "SAT"),
    ("tautology and duplicates", "p cnf 2 1\n1 -1 1 0\n", "SAT"),
    ("empty input", "", "SAT"),
]


def python_verdict(source: str) -> str:
    try:
        formula = DIMACSParser.parse_string(source)
    except DIMACSParseError:
        return "ERROR"
    return "SAT" if CQSATSolver().solve(formula, timeout_seconds=10.0).satisfiable else "UNSAT"


class PythonGrammarTests(unittest.TestCase):
    def test_documented_grammar(self):
        for label, source, expected in CASES:
            with self.subTest(label):
                self.assertEqual(python_verdict(source), expected)

    def test_clause_spanning_lines_is_one_clause(self):
        self.assertEqual(DIMACSParser.parse_string("p cnf 3 1\n1 2\n3 0\n").clauses, [[1, 2, 3]])


class NativeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.native_artifacts import require_executable

        cls.exe = require_executable()
        if os.name != "nt":
            os.chmod(cls.exe, 0o755)

    def native_verdict(self, source: str) -> str:
        result = subprocess.run(
            [str(self.exe), "sat", "-", "--json"], input=source, capture_output=True, text=True, timeout=30
        )
        status = json.loads(result.stdout)["status"]
        return "ERROR" if status == "ERROR" else status

    def test_python_and_native_agree(self):
        for label, source, expected in CASES:
            with self.subTest(label):
                self.assertEqual(self.native_verdict(source), expected)
                self.assertEqual(python_verdict(source), self.native_verdict(source))


if __name__ == "__main__":
    unittest.main()
