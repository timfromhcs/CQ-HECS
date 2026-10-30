"""CLI contract tests for ``cq-hecs reference``."""

from __future__ import annotations

import contextlib
import io
import json
import unittest

from cqhecs.cli import EXIT_OK, EXIT_USAGE, JSON_SCHEMA_VERSION, main


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestReferenceCli(unittest.TestCase):
    def test_list_json(self):
        code, out, err = run_cli("--format", "json", "reference", "list")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], JSON_SCHEMA_VERSION)
        ids = {item["dataset_id"] for item in payload["datasets"]}
        self.assertIn("r-io-5", ids)
        self.assertIn("r-io-6", ids)

    def test_run_json(self):
        code, out, err = run_cli(
            "--format", "json", "reference", "run",
            "--bootstrap", "50",
            "--data-dir", "tests/data/quantum_noise_transfer",
        )
        self.assertEqual(code, EXIT_OK, err)
        payload = json.loads(out)
        self.assertEqual(payload["dataset_id"], "r-io-5")
        self.assertEqual(payload["aggregate"]["n_circuits"], 14)
        self.assertIn("verdict", payload["aggregate"])
        self.assertEqual(len(payload["circuits"]), 14)

    def test_unknown_dataset_is_usage_error(self):
        code, out, err = run_cli("reference", "run", "--dataset", "nope")
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(out, "")

    def test_missing_data_is_usage_error(self):
        code, out, err = run_cli("reference", "run", "--data-dir", "tests/data/does-not-exist")
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
