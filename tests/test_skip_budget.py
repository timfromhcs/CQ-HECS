"""W4-20: the skip-budget gate parses JUnit XML and fails on new or grown skips."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import skip_budget  # noqa: E402


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "report.xml"
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>', encoding="utf-8")
    return path


def test_skips_are_grouped_by_reason(tmp_path):
    xml = _write(
        tmp_path,
        '<testcase name="a"><skipped message="optional dep missing">x</skipped></testcase>'
        '<testcase name="b"><skipped message="optional dep missing">x</skipped></testcase>'
        '<testcase name="c"><skipped type="env"/></testcase>'
        '<testcase name="d"/>',
    )
    counts = skip_budget.parse_junit(xml)
    assert counts == {"optional dep missing": 2, "env": 1}


def test_an_unbudgeted_reason_fails():
    problems = skip_budget.compare({}, {"new reason": 1})
    assert problems and "unbudgeted" in problems[0]


def test_a_grown_count_fails():
    problems = skip_budget.compare({"flaky": 1}, {"flaky": 2})
    assert problems and "grew" in problems[0]


def test_fewer_or_equal_skips_pass():
    assert skip_budget.compare({"a": 3, "b": 1}, {"a": 2, "b": 1}) == []


def test_record_then_check_round_trips(tmp_path):
    xml = _write(tmp_path, '<testcase name="a"><skipped message="why"/></testcase>')
    budget = tmp_path / "budget.json"
    assert skip_budget.main(["--junitxml", str(xml), "--budget", str(budget), "--record"]) == 0
    assert skip_budget.main(["--junitxml", str(xml), "--budget", str(budget), "--check"]) == 0
    # One more skip of the same reason exceeds the recorded budget.
    xml2 = _write(tmp_path, '<testcase name="a"><skipped message="why"/></testcase>'
                           '<testcase name="b"><skipped message="why"/></testcase>')
    assert skip_budget.main(["--junitxml", str(xml2), "--budget", str(budget), "--check"]) == 1
