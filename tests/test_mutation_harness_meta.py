"""
Meta-tests for ``scripts/run_mutation_tests.py``.

The harness itself must fail closed. These tests verify:

* every mutation anchor still exists exactly once (drift detection),
* source restoration is byte-exact,
* a broken baseline fails the gate,
* a surviving mutant fails the gate,
* a missing anchor is a harness error, not a silent skip.
"""

from __future__ import annotations

import io
import os
import time
import unittest
from unittest.mock import patch

from scripts import run_mutation_tests as harness
from scripts.run_mutation_tests import SourceMutant


class TestMutationAnchors(unittest.TestCase):
    def test_every_anchor_exists_exactly_once(self):
        for mutant in harness.MUTANTS:
            with self.subTest(mutant=mutant.name):
                path = harness.REPO_ROOT / mutant.target
                self.assertTrue(path.is_file(), msg=f"missing target {mutant.target}")
                text = path.read_text(encoding="utf-8")
                self.assertEqual(
                    text.count(mutant.original),
                    1,
                    msg=f"anchor for {mutant.name!r} is stale or ambiguous",
                )

    def test_every_check_is_registered(self):
        for mutant in harness.MUTANTS:
            with self.subTest(mutant=mutant.name):
                self.assertIn(mutant.check, harness.CHECKS)

    def test_mutant_mechanism_is_described(self):
        for mutant in harness.MUTANTS:
            with self.subTest(mutant=mutant.name):
                self.assertTrue(mutant.mechanism.strip())


class TestApplyRestore(unittest.TestCase):
    def test_apply_and_restore_are_byte_exact(self):
        mutant = harness.MUTANTS[0]
        path, original = harness.apply_mutant(mutant)
        try:
            self.assertNotEqual(path.read_text(encoding="utf-8"), original)
        finally:
            harness.restore_source(path, original)
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_missing_anchor_raises(self):
        broken = SourceMutant(
            name="broken anchor",
            target="cqhecs/cli.py",
            original="THIS ANCHOR DOES NOT EXIST",
            replacement="still not here",
            check="cli_usage_exit_status",
            mechanism="test fixture",
        )
        with self.assertRaises(harness.HarnessError):
            harness.apply_mutant(broken)


class TestFailClosedBehaviour(unittest.TestCase):
    def test_broken_baseline_is_detected(self):
        """A source defect present before mutation must invalidate the baseline."""
        mutant = harness.MUTANTS[0]
        path, original = harness.apply_mutant(mutant)
        try:
            failures = harness.baseline_self_check([mutant])
        finally:
            harness.restore_source(path, original)
        self.assertTrue(failures, msg="broken baseline was not reported")

    def test_surviving_mutant_exits_one(self):
        noop = SourceMutant(
            name="no-op mutant",
            target="cqhecs/cli.py",
            original="EXIT_OK = 0",
            replacement="EXIT_OK = 0  # no behavioural change",
            check="cli_usage_exit_status",
            mechanism="changes nothing; the check must not report a defect",
        )
        out = io.StringIO()
        with patch("sys.stdout", out):
            exit_code = harness.run([noop], verbose=False)
        self.assertEqual(exit_code, harness.EXIT_GATE_FAILED)
        self.assertIn("[SURVIVED]", out.getvalue())

    def test_missing_anchor_is_harness_error(self):
        broken = SourceMutant(
            name="broken anchor",
            target="cqhecs/cli.py",
            original="THIS ANCHOR DOES NOT EXIST",
            replacement="still not here",
            check="cli_usage_exit_status",
            mechanism="test fixture",
        )
        out = io.StringIO()
        with patch("sys.stdout", out):
            exit_code = harness.run([broken], verbose=False)
        self.assertEqual(exit_code, harness.EXIT_GATE_FAILED)
        self.assertIn("[HARNESS ERROR]", out.getvalue())


class TestStaleBytecode(unittest.TestCase):
    def test_same_size_mutant_does_not_leak_via_bytecode_cache(self):
        """A restored source must not be checked through a mutant .pyc.

        CPython validates bytecode with the source mtime truncated to seconds
        and the source size. A same-size mutant written and restored inside one
        second can leave a .pyc that still looks valid, so the mutation
        baseline would execute mutated code and fail spuriously.
        """
        mutant = next(
            item for item in harness.MUTANTS
            if item.check == "t_count_classification"
        )
        path = harness.REPO_ROOT / mutant.target
        original_text = path.read_text(encoding="utf-8")
        original_stat = path.stat()
        fixed = int(time.time()) - 5
        try:
            self.assertFalse(
                harness.run_check_in_subprocess(mutant.check),
                msg="unmutated source must not report the defect",
            )
            mutated_path, _ = harness.apply_mutant(mutant)
            os.utime(mutated_path, (fixed, fixed))
            self.assertTrue(
                harness.run_check_in_subprocess(mutant.check),
                msg="the mutant must be detected",
            )
            harness.restore_source(mutated_path, original_text)
            os.utime(mutated_path, (fixed, fixed))
            self.assertFalse(
                harness.run_check_in_subprocess(mutant.check),
                msg="restored source was checked through stale mutant bytecode",
            )
        finally:
            harness.restore_source(path, original_text)
            os.utime(path, (original_stat.st_atime, original_stat.st_mtime))


class TestFullHarness(unittest.TestCase):
    def test_full_harness_kills_every_mutant(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            exit_code = harness.run(harness.MUTANTS, verbose=False)
        output = out.getvalue()
        self.assertEqual(
            exit_code,
            harness.EXIT_OK,
            msg=f"mutation gate failed:\n{output}",
        )
        self.assertNotIn("[SURVIVED]", output)
        self.assertNotIn("[HARNESS ERROR]", output)


if __name__ == "__main__":
    unittest.main()
