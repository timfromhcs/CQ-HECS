"""
OpenQASM subset parser contract tests (native ``cq_hecs`` executable).

Documented contract (see ``docs/QASM_CONTRACT.md`` and ``src/qasm_parser.cpp``):

* Supported grammar: OpenQASM 2.0 statements with 2.0 ``qreg``/``creg`` or 3.0
  ``qubit[N]``/``bit[N]`` declarations.
* Every statement must end with ``;``. Missing punctuation is a hard error;
  there is no lenient recovery.
* Unknown or unsupported gates are rejected. They are never executed as an
  identity and never counted as applied gates.
* Numeric gate parameters must be constant expressions over decimal literals,
  ``pi``, parentheses and ``+ - * /``. ``NaN``/``inf`` and malformed tokens are
  rejected.
* Operands must reference declared registers and stay inside their declared
  bounds. There is no silent register expansion.
* Empty or comment-only input is a valid empty circuit (``gate_count == 0``,
  ``qubit_count == 0``).
* Exit codes: ``0`` success, ``2`` invalid circuit/input, ``1`` runtime error.
* In ``--json`` mode stdout contains exactly one JSON document; human-readable
  diagnostics go to stderr.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest

DEFAULT_TIMEOUT_SECONDS = 60


class TestFuzzQASM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.native_artifacts import require_executable

        cls.exe_path = require_executable()
        if os.name != "nt":
            os.chmod(cls.exe_path, 0o755)

    # ------------------------------------------------------------------ helpers
    def run_cpp_qasm(self, qasm_str: str, extra_args=()):
        """Runs the native parser with a bounded timeout and captured output."""
        self.assertLess(
            len(qasm_str.encode("utf-8")),
            1_000_000,
            "test input must stay well below the parser's input limit",
        )
        try:
            return subprocess.run(
                [str(self.exe_path), "qasm", "-", "--json", *extra_args],
                input=qasm_str,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - failure path
            self.fail(f"native QASM parser timed out after {DEFAULT_TIMEOUT_SECONDS}s: {exc}")

    def parse_json(self, result):
        self.assertEqual(
            result.returncode,
            0,
            msg=f"expected success, got {result.returncode}\nstderr={result.stderr}",
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"stdout was not one JSON document: {exc}\n{result.stdout!r}")

    def assert_rejected(self, qasm_str, category, extra_args=()):
        result = self.run_cpp_qasm(qasm_str, extra_args)
        self.assertEqual(
            result.returncode,
            2,
            msg=f"expected exit code 2 for invalid input, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}",
        )
        # stdout must still be one valid JSON document in --json mode.
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"error output was not valid JSON: {exc}\n{result.stdout!r}")

        self.assertEqual(payload["status"], "ERROR")
        self.assertEqual(payload["error_category"], "qasm_parse_error")
        self.assertGreater(payload["error_count"], 0)
        categories = {error["category"] for error in payload["errors"]}
        self.assertIn(category, categories, msg=f"categories={categories}")
        self.assertNotIn("gate_count", payload)
        # Diagnostics must not leak into the JSON stream.
        self.assertNotIn("[QASM]", result.stdout)
        return payload

    # -------------------------------------------------------------------- tests
    def test_empty_qasm_is_documented_noop(self):
        payload = self.parse_json(self.run_cpp_qasm(""))
        self.assertEqual(payload["status"], "SUCCESS")
        self.assertEqual(payload["gate_count"], 0)
        self.assertEqual(payload["qubit_count"], 0)
        self.assertFalse(payload["statevector_simulation"])

    def test_comments_only_qasm_is_noop(self):
        qasm = "// Line 1 comment\n// Line 2 comment\n"
        payload = self.parse_json(self.run_cpp_qasm(qasm))
        self.assertEqual(payload["gate_count"], 0)
        self.assertEqual(payload["qubit_count"], 0)

    def test_valid_circuit_records_gates(self):
        qasm = """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[4];
        creg c[2];
        h q[0];
        cx q[0], q[1];
        measure q[0] -> c[0];
        """
        payload = self.parse_json(self.run_cpp_qasm(qasm))
        self.assertEqual(payload["status"], "SUCCESS")
        self.assertEqual(payload["qubit_count"], 4)
        self.assertEqual(payload["gate_count"], 3)

    def test_whole_register_operand_expands(self):
        qasm = "OPENQASM 2.0;\nqreg q[4];\nh q;\n"
        payload = self.parse_json(self.run_cpp_qasm(qasm))
        self.assertEqual(payload["gate_count"], 4)
        self.assertEqual(payload["qubit_count"], 4)

    def test_zero_qubit_declaration_is_rejected(self):
        qasm = "OPENQASM 2.0;\nqreg q[0];\ncreg c[0];\n"
        self.assert_rejected(qasm, "invalid_register_size")

    def test_malformed_floating_point_parameters_are_rejected(self):
        qasm = """
        OPENQASM 2.0;
        qreg q[4];
        cp(invalid_angle) q[0], q[1];
        cp(3.14.15) q[2], q[3];
        """
        payload = self.assert_rejected(qasm, "invalid_parameter")
        lines = {error["line"] for error in payload["errors"]}
        self.assertIn(4, lines)
        self.assertIn(5, lines)

    def test_nan_and_infinity_are_rejected(self):
        for parameter in ("nan", "inf", "1e999", "pi/"):
            with self.subTest(parameter=parameter):
                self.assert_rejected(
                    f"OPENQASM 2.0;\nqreg q[1];\nrx({parameter}) q[0];\n",
                    "invalid_parameter",
                )

    def test_unknown_gate_is_rejected_not_identity(self):
        qasm = """
        OPENQASM 2.0;
        qreg q[3];
        nonexistent_exotic_gate q[0], q[1], q[2];
        h q[0];
        """
        self.assert_rejected(qasm, "unsupported_gate")

    def test_undeclared_register_is_rejected(self):
        qasm = "OPENQASM 2.0;\nqreg q[2];\nh phantom[0];\n"
        self.assert_rejected(qasm, "undeclared_register")

    def test_out_of_range_index_is_rejected(self):
        qasm = "OPENQASM 2.0;\nqreg q[50];\ncx q[49], q[120];\n"
        self.assert_rejected(qasm, "index_out_of_range")

    def test_missing_semicolons_are_rejected(self):
        qasm = "OPENQASM 2.0\nqreg q[4]\nh q[0]\ncx q[0], q[1]\n"
        payload = self.assert_rejected(qasm, "missing_semicolon")
        self.assertEqual(payload["error_count"], 4)

    def test_duplicate_register_is_rejected(self):
        qasm = "OPENQASM 2.0;\nqreg q[2];\nqreg q[2];\n"
        self.assert_rejected(qasm, "duplicate_register")

    def test_measure_width_mismatch_is_rejected(self):
        qasm = "OPENQASM 2.0;\nqreg q[4];\ncreg c[2];\nmeasure q -> c;\n"
        self.assert_rejected(qasm, "width_mismatch")

    def test_wrong_parameter_count_is_rejected(self):
        qasm = "OPENQASM 2.0;\nqreg q[1];\nrx q[0];\n"
        self.assert_rejected(qasm, "parameter_count_mismatch")

    def test_qubit_budget_is_enforced(self):
        qasm = "OPENQASM 2.0;\nqreg q[8];\nh q[0];\n"
        payload = self.assert_rejected(qasm, "qubit_budget_exceeded", ("--qubits", "4"))
        self.assertIn("--qubits", payload["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
