"""
Tests for the unified ``cq-hecs`` command-line interface.

These invoke ``main()`` in-process and capture stdout/stderr so they run
identically on every platform and do not depend on the console script being on
PATH.
"""

from __future__ import annotations
import contextlib
import io
import json
import unittest

from cqhecs.cli import (
    EXIT_OK,
    EXIT_USAGE,
    JSON_SCHEMA_VERSION,
    main,
)


def run_cli(*argv):
    """Runs the CLI and returns (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestCliBasics(unittest.TestCase):
    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli("--help")
        self.assertEqual(ctx.exception.code, 0)

    def test_every_command_has_help(self):
        for command in ("version", "doctor", "profile", "analyze", "run", "verify", "expect", "benchmark"):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as ctx:
                    run_cli(command, "--help")
                self.assertEqual(ctx.exception.code, 0)

    def test_version_text(self):
        code, out, err = run_cli("version")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("cq-hecs", out)

    def test_missing_command_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli()
        self.assertEqual(ctx.exception.code, EXIT_USAGE)

    def test_unknown_command_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli("teleport")
        self.assertEqual(ctx.exception.code, EXIT_USAGE)


class TestJsonOutputContract(unittest.TestCase):
    """--format json must emit exactly one JSON document on stdout."""

    def _assert_pure_json(self, *argv):
        code, out, err = run_cli("--format", "json", *argv)
        self.assertEqual(code, EXIT_OK, msg=f"argv={argv} stderr={err}")
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            self.fail(f"stdout was not valid JSON for argv={argv}: {exc}\n{out!r}")
        self.assertEqual(payload["schema_version"], JSON_SCHEMA_VERSION)
        return payload

    def test_version(self):
        self._assert_pure_json("version")

    def test_doctor(self):
        payload = self._assert_pure_json("doctor")
        self.assertIn("components", payload)
        self.assertIn("os", payload)

    def test_backend_list(self):
        payload = self._assert_pure_json("backend", "list")
        paths = [entry["path"] for entry in payload["backends"]]
        self.assertEqual(paths, ["A", "B", "C", "D"])
        for entry in payload["backends"]:
            self.assertTrue(entry["supported_gates"])

    def test_analyze(self):
        payload = self._assert_pure_json("analyze", "name:ghz8")
        self.assertEqual(payload["analysis"]["num_qubits"], 8)
        self.assertTrue(payload["analysis"]["is_clifford"])
        self.assertEqual(payload["analysis"]["recommended_path"], "A")

    def test_run(self):
        payload = self._assert_pure_json("run", "name:ghz8", "--shots", "100")
        self.assertEqual(payload["result"]["path"], "A")
        self.assertEqual(sum(payload["result"]["counts"].values()), 100)

    def test_run_reports_sampling_error(self):
        """A finite-shot result must not claim zero total error."""
        payload = self._assert_pure_json("run", "name:ghz8", "--shots", "100")
        result = payload["result"]
        self.assertEqual(result["error_bound"], 0.0)
        self.assertGreater(result["sampling_error_bound"], 0.0)
        self.assertAlmostEqual(
            result["total_error_bound"], result["sampling_error_bound"], places=12
        )

    def test_benchmark(self):
        payload = self._assert_pure_json("benchmark", "smoke")
        self.assertTrue(payload["cases"])

    def test_verify(self):
        payload = self._assert_pure_json("verify", "name:bell", "--reference", "aer")
        self.assertIn("verified", payload)

    def test_stdout_is_uncontaminated_by_logging(self):
        """Diagnostics must go to stderr, never stdout."""
        code, out, err = run_cli("--format", "json", "-vv", "run", "name:ghz8", "--shots", "50")
        self.assertEqual(code, EXIT_OK)
        json.loads(out)  # must still parse
        # Verbose logging may write to stderr; it must not reach stdout.
        self.assertNotIn("INFO", out)
        self.assertNotIn("DEBUG", out)

    def test_quiet_suppresses_stderr(self):
        code, out, err = run_cli("--format", "json", "--quiet", "run", "name:ghz8")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err.strip(), "")


class TestExitCodes(unittest.TestCase):
    def test_missing_file_is_usage_error(self):
        code, out, err = run_cli("--format", "json", "run", "does_not_exist.qasm")
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("error", json.loads(out))

    def test_unknown_builtin_is_usage_error(self):
        code, out, err = run_cli("--format", "json", "analyze", "name:not_a_circuit")
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("error", json.loads(out))

    def test_invalid_shots_is_usage_error(self):
        code, out, err = run_cli("--format", "json", "run", "name:ghz8", "--shots", "0")
        self.assertEqual(code, EXIT_USAGE)

    def test_forced_unsupported_backend_is_usage_error(self):
        # Path A cannot run a T-gate circuit, and must say so rather than reroute.
        code, out, err = run_cli(
            "--format", "json", "run", "name:low_t_rank4", "--backend", "A"
        )
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("error", json.loads(out))

    def test_invalid_backend_name_is_usage_error(self):
        code, out, err = run_cli(
            "--format", "json", "run", "name:ghz8", "--backend", "Z"
        )
        self.assertEqual(code, EXIT_USAGE)


class TestDeterminism(unittest.TestCase):
    def test_same_seed_gives_same_counts(self):
        _, first, _ = run_cli(
            "--format", "json", "run", "name:ghz8", "--shots", "200", "--seed", "7"
        )
        _, second, _ = run_cli(
            "--format", "json", "run", "name:ghz8", "--shots", "200", "--seed", "7"
        )
        self.assertEqual(
            json.loads(first)["result"]["counts"],
            json.loads(second)["result"]["counts"],
        )

    def test_path_c_is_reachable_and_deterministic(self):
        _, first, _ = run_cli(
            "--format", "json", "run", "name:mps6", "--backend", "C",
            "--shots", "200", "--seed", "3",
        )
        _, second, _ = run_cli(
            "--format", "json", "run", "name:mps6", "--backend", "C",
            "--shots", "200", "--seed", "3",
        )
        self.assertEqual(
            json.loads(first)["result"]["counts"],
            json.loads(second)["result"]["counts"],
        )


class TestBackendDispatch(unittest.TestCase):
    """Each forced backend must actually execute, or refuse clearly."""

    def test_path_a_executes(self):
        _, out, _ = run_cli("--format", "json", "run", "name:ghz8", "--backend", "A")
        self.assertEqual(json.loads(out)["result"]["path"], "A")

    def test_path_c_executes(self):
        _, out, _ = run_cli("--format", "json", "run", "name:mps6", "--backend", "C")
        self.assertEqual(json.loads(out)["result"]["path"], "C")

    def test_path_d_reports_expectations_not_counts(self):
        _, out, _ = run_cli(
            "--format", "json", "run", "name:sparse_pauli4", "--backend", "D"
        )
        result = json.loads(out)["result"]
        self.assertEqual(result["path"], "D")
        self.assertEqual(result["counts"], {})
        self.assertTrue(result["expectation_values"])
        self.assertFalse(result["metadata"]["counts_are_joint_distribution"])



class TestCliProfileAndBridge(unittest.TestCase):
    """Tests for 'cq-hecs profile' and hardware bridge execution flags."""

    def test_profile_list_text(self):
        code, out, _ = run_cli("profile", "list")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("fake_manila", out)
        self.assertIn("linear_5q", out)

    def test_profile_list_json(self):
        code, out, _ = run_cli("--format", "json", "profile", "list")
        self.assertEqual(code, EXIT_OK)
        doc = json.loads(out)
        self.assertEqual(doc["schema_version"], JSON_SCHEMA_VERSION)
        names = [p["name"] for p in doc["profiles"]]
        self.assertIn("fake_manila", names)

    def test_profile_show_manila(self):
        code, out, _ = run_cli("profile", "show", "fake_manila")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Name         : fake_manila", out)
        self.assertIn("Qubits       : 5", out)

    def test_run_with_profile_fake_manila(self):
        code, out, _ = run_cli(
            "--format", "json", "run", "name:bell", "--profile", "fake_manila", "--shots", "500"
        )
        self.assertEqual(code, EXIT_OK)
        res = json.loads(out)["result"]
        self.assertEqual(res["path"], "NOISY_DM")
        self.assertEqual(res["execution_mode"], "NOISY_CLASSICAL")
        self.assertEqual(res["backend_profile_id"], "fake_manila")
        self.assertFalse(res["is_real_hardware"])
        self.assertEqual(sum(res["counts"].values()), 500)

    def test_run_with_profile_noiseless(self):
        code, out, _ = run_cli(
            "--format", "json", "run", "name:bell", "--profile", "fake_manila", "--no-noisy", "--shots", "200"
        )
        self.assertEqual(code, EXIT_OK)
        res = json.loads(out)["result"]
        self.assertEqual(res["execution_mode"], "IDEAL_CLASSICAL")
        self.assertEqual(res["path"], "NOISY_DM")


if __name__ == "__main__":
    unittest.main()