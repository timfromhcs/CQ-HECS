"""Tests for the metamorphic/property-based installation self-test."""

from __future__ import annotations

import contextlib
import io
import json
import unittest

from cqhecs.cli import EXIT_OK, main
from cqhecs.selftest import SELFTEST_SCHEMA_VERSION, run_selftest


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestSelftest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_selftest(cases=2, seed=11)

    def test_all_checks_pass(self):
        self.assertTrue(self.report.passed)
        self.assertEqual(len(self.report.checks), 11)
        self.assertTrue(all(check.passed for check in self.report.checks))

    def test_expected_check_names(self):
        names = [check.name for check in self.report.checks]
        self.assertEqual(
            names,
            [
                "normalization",
                "inverse_identity",
                "permutation_equivariance",
                "global_phase",
                "mps_dense_parity",
                "sampling",
                "noise_invariants",
                "noise_permutation_equivariance",
                "zero_noise_identity",
                "channel_composition_order",
                "expectation_oracle",
            ],
        )

    def test_json_contract(self):
        payload = self.report.to_dict()
        self.assertEqual(payload["schema_version"], SELFTEST_SCHEMA_VERSION)
        self.assertEqual(payload["seed"], 11)
        self.assertEqual(payload["cases"], 2)
        self.assertTrue(payload["passed"])
        self.assertTrue(all(check["duration_ms"] >= 0.0 for check in payload["checks"]))

    def test_deterministic(self):
        again = run_selftest(cases=2, seed=11)
        self.assertEqual(
            [(c.name, c.passed, c.detail) for c in again.checks],
            [(c.name, c.passed, c.detail) for c in self.report.checks],
        )

    def test_invalid_cases_refused(self):
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    run_selftest(cases=value)


class TestSelftestCli(unittest.TestCase):
    def test_json(self):
        code, out, err = run_cli("--format", "json", "selftest", "--cases", "2")
        self.assertEqual(code, EXIT_OK, err)
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], SELFTEST_SCHEMA_VERSION)
        self.assertIn("checks", payload)
        self.assertTrue(payload["passed"])

    def test_text(self):
        code, out, err = run_cli("selftest", "--cases", "1")
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("Metamorphic self-test", out)
        self.assertIn("Result: PASS", out)

    def test_cli_help_lists_command(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli("--help")
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
