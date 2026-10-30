"""
Meta-tests for ``scripts/run_mutation_tests.py``.

The harness itself must fail closed. These tests verify, in six focused cases
instead of ten scattered ones:

* every mutation anchor still exists exactly once and is registered,
* source restoration is byte-exact,
* a broken baseline, a surviving mutant and a missing anchor all fail the gate,
* a restored source is never checked through stale mutant bytecode,
* the full 35-mutant gate still runs, opt-in as ``-m slow``.

The full sweep used to run unconditionally and cost ~95 s, two thirds of the
whole suite's wall time. It cannot be made cheaper by shrinking the mutant
list: the harness spawns one fresh interpreter per check just to establish the
baseline, so five mutants cost the same as thirty-five. CI runs the same sweep
via ``python scripts/run_mutation_tests.py``, so the default suite now checks
the harness's structure and its fail-closed edges instead of re-running it.
"""

from __future__ import annotations

import io
import os
import time
import unittest
from unittest.mock import patch

import pytest

from scripts import run_mutation_tests as harness
from scripts.run_mutation_tests import SourceMutant


def one_mutant_per_check():
    """A representative mutant for every distinct check the harness owns.

    Kept because it documents the check families the table is expected to
    cover; the live gate runs all mutants, not just these.
    """
    picked = {}
    for mutant in harness.MUTANTS:
        picked.setdefault(mutant.check, mutant)
    return list(picked.values())


class TestMutationAnchors(unittest.TestCase):
    def test_anchors_are_unique_and_registered(self):
        """One pass over the mutant table: target exists, anchor unique, check known."""
        self.assertGreaterEqual(len(harness.MUTANTS), 3, msg="mutant table collapsed")
        self.assertGreaterEqual(len({m.check for m in harness.MUTANTS}), 3,
                                msg="mutant table collapsed onto one check")
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
                self.assertIn(mutant.check, harness.CHECKS)
                self.assertTrue(mutant.mechanism.strip(),
                                msg=f"{mutant.name!r} has no stated mechanism")


class TestApplyRestore(unittest.TestCase):
    def test_apply_and_restore_are_byte_exact(self):
        mutant = harness.MUTANTS[0]
        path, original = harness.apply_mutant(mutant)
        try:
            self.assertNotEqual(path.read_text(encoding="utf-8"), original)
        finally:
            harness.restore_source(path, original)
        self.assertEqual(path.read_text(encoding="utf-8"), original)


class TestFailClosedBehaviour(unittest.TestCase):
    def test_gate_fails_closed_on_every_broken_input(self):
        """Broken baseline, surviving mutant and missing anchor each exit non-zero."""
        mutant = harness.MUTANTS[0]
        path, original = harness.apply_mutant(mutant)
        try:
            self.assertTrue(harness.baseline_self_check([mutant]),
                            msg="broken baseline was not reported")
        finally:
            harness.restore_source(path, original)

        noop = SourceMutant(
            name="no-op mutant",
            target="cqhecs/cli.py",
            original="EXIT_OK = 0",
            replacement="EXIT_OK = 0  # no behavioural change",
            check="cli_usage_exit_status",
            mechanism="changes nothing; the check must not report a defect",
        )
        broken = SourceMutant(
            name="broken anchor",
            target="cqhecs/cli.py",
            original="THIS ANCHOR DOES NOT EXIST",
            replacement="still not here",
            check="cli_usage_exit_status",
            mechanism="test fixture",
        )
        for case, marker in ((noop, "[SURVIVED]"), (broken, "[HARNESS ERROR]")):
            out = io.StringIO()
            with patch("sys.stdout", out):
                exit_code = harness.run([case], verbose=False)
            self.assertEqual(exit_code, harness.EXIT_GATE_FAILED, msg=case.name)
            self.assertIn(marker, out.getvalue(), msg=case.name)
        with self.assertRaises(harness.HarnessError):
            harness.apply_mutant(broken)


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


class TestEveryMutantIsKilled(unittest.TestCase):
    # The harness spawns one fresh interpreter per distinct check just for the
    # baseline, so a 5-mutant subset costs the same 94 s as all 35. A cheaper
    # subset would buy nothing; the live gate therefore runs only under
    # ``-m slow``, and CI runs the same sweep via scripts/run_mutation_tests.py.
    @pytest.mark.slow
    def test_full_harness_kills_every_mutant(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            exit_code = harness.run(harness.MUTANTS, verbose=False)
        output = out.getvalue()
        self.assertEqual(exit_code, harness.EXIT_OK,
                         msg=f"mutation gate failed:\n{output}")
        self.assertNotIn("[SURVIVED]", output)
        self.assertNotIn("[HARNESS ERROR]", output)


if __name__ == "__main__":
    unittest.main()
