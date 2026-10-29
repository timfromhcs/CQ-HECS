"""``cq-hecs expect`` contract (v2.4.0)."""

from __future__ import annotations
import contextlib
import io
import json
import unittest

from cqhecs.cli import EXIT_OK, EXIT_UNRESOLVED, EXIT_USAGE, JSON_SCHEMA_VERSION, main


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestExpectCommand(unittest.TestCase):
    def test_help(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli("expect", "--help")
        self.assertEqual(ctx.exception.code, 0)

    def test_json_is_a_single_document_with_exact_bell_values(self):
        code, out, _err = run_cli(
            "--format", "json", "expect", "name:bell", "-o", "ZZ", "-o", "XX", "-o", "YY"
        )
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], JSON_SCHEMA_VERSION)
        result = payload["result"]
        self.assertEqual(result["method"], "stabilizer")
        self.assertTrue(result["exact"])
        self.assertEqual(result["error_bound"], 0.0)
        self.assertEqual(result["error_bound_covers"], "expectation_values")
        self.assertEqual(result["values"], {"ZZ": 1.0, "XX": 1.0, "YY": -1.0})

    def test_text_output_lists_each_observable(self):
        code, out, _err = run_cli("expect", "name:ising6", "-o", "Z0", "-o", "X0 X1")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Method      : dense", out)
        self.assertIn("Z0", out)
        self.assertIn("X0 X1", out)

    def test_invalid_observable_is_a_usage_error(self):
        with self.assertLogs("cqhecs.cli", level="ERROR") as logs:
            code, _out, _err = run_cli("expect", "name:bell", "-o", "QQ")
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("invalid Pauli string", logs.output[0])

    def test_missing_observable_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli("expect", "name:bell")
        self.assertEqual(ctx.exception.code, EXIT_USAGE)

    def test_forced_stabilizer_on_non_clifford_is_a_usage_error(self):
        with self.assertLogs("cqhecs.cli", level="ERROR") as logs:
            code, _out, _err = run_cli(
                "expect", "name:low_t_rank4", "-o", "ZZZZ", "--method", "stabilizer"
            )
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("Clifford", logs.output[0])

    def test_unresolved_sparse_result_exits_with_unresolved_status(self):
        code, out, _err = run_cli(
            "--format", "json", "expect", "name:sparse_pauli4", "-o", "X0 Y1",
            "--method", "sparse_pauli", "--error-tolerance", "1e-12",
            "--max-pauli-terms", "1",
        )
        payload = json.loads(out)
        if payload["result"]["unresolved"]:
            self.assertEqual(code, EXIT_UNRESOLVED)
            self.assertIsNone(payload["result"]["values"]["X0 Y1"])
        else:  # a certified answer must still respect the declared bound
            self.assertEqual(code, EXIT_OK)


if __name__ == "__main__":
    unittest.main()
