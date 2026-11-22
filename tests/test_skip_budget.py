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


# ---------------------------------------------------------------------------
# Per-environment budgets (research/v7/SKIP_BUDGET.json, --environment NAME)
# ---------------------------------------------------------------------------
import json  # noqa: E402

import pytest  # noqa: E402


def _budget_file(tmp_path: Path) -> Path:
    doc = {
        "schema": skip_budget.SCHEMA,
        "reasons": {"native missing": 3, "extra": 1},
        "environments": {
            "default": {"reasons": {"native missing": 3, "extra": 1}},
            "with_native": {"reasons": {"extra": 1}},
        },
    }
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _skips(tmp_path: Path, **reasons: int) -> Path:
    body = ""
    for reason, count in reasons.items():
        for index in range(count):
            body += f'<testcase name="{reason}{index}"><skipped message="{reason.replace("_", " ")}"/></testcase>'
    return _write(tmp_path, body)


def test_environment_selects_its_own_ceilings(tmp_path):
    budget = _budget_file(tmp_path)
    xml = _skips(tmp_path, native_missing=3, extra=1)
    argv = ["--junitxml", str(xml), "--budget", str(budget), "--check"]
    assert skip_budget.main(argv) == 0
    assert skip_budget.main(argv + ["--environment", "default"]) == 0
    # The same skips are unbudgeted in the strict with_native environment.
    assert skip_budget.main(argv + ["--environment", "with_native"]) == 1


def test_a_reason_absent_from_an_environment_has_budget_zero(tmp_path):
    doc = json.loads(_budget_file(tmp_path).read_text(encoding="utf-8"))
    budget = skip_budget.select_budget(doc, "with_native")
    assert "native missing" not in budget
    assert skip_budget.compare(budget, {"native missing": 1})[0].startswith("unbudgeted")


def test_environment_with_only_budgeted_skips_passes(tmp_path):
    budget = _budget_file(tmp_path)
    xml = _skips(tmp_path, extra=1)
    assert skip_budget.main(["--junitxml", str(xml), "--budget", str(budget), "--check",
                             "--environment", "with_native"]) == 0


def test_unknown_environment_is_refused(tmp_path):
    budget = _budget_file(tmp_path)
    xml = _skips(tmp_path, extra=1)
    with pytest.raises(SystemExit) as info:
        skip_budget.main(["--junitxml", str(xml), "--budget", str(budget), "--check",
                          "--environment", "nope"])
    assert "unknown budget environment" in str(info.value)


def test_committed_budget_environments_are_consistent():
    doc = json.loads(skip_budget.DEFAULT_BUDGET.read_text(encoding="utf-8"))
    envs = doc["environments"]
    assert {"default", "with_native"} <= set(envs)
    # The top-level reasons are the default environment.
    assert doc["reasons"] == envs["default"]["reasons"]
    for name, env in envs.items():
        assert env["total"] == sum(env["reasons"].values()), name
    assert doc["total"] == envs["default"]["total"]
    # with_native proves native tests ran: no native/Vulkan reason may be budgeted there.
    for reason in envs["with_native"]["reasons"]:
        lowered = reason.lower()
        assert "native" not in lowered and "vulkan" not in lowered and "cq_hecs" not in lowered.replace("cq_hecs_exe", ""), reason
