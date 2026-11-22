#!/usr/bin/env python3
"""Skip budget (W4-20).

A skipped test is not a pass. This gate makes skip growth visible: it parses a JUnit XML
report, groups the skipped tests by their reason, and compares the counts against a
committed budget. A new skip reason, or a reason whose count grows, fails the gate so a
silently disabled or environment-dropped test cannot hide.

    python scripts/skip_budget.py --junitxml report.xml --check
    python scripts/skip_budget.py --junitxml report.xml --record

The budget lives in research/v7/SKIP_BUDGET.json. Counts may only change with an
explicit `--record` and a reason in the commit message; fewer skips are always allowed.

Environments. A skipped test is environmental, so the budget may carry per-environment
ceilings (budget key "environments", each with its own "reasons" and a "description" and
per-reason "justifications"). `--environment NAME` selects one; without it the top-level
"reasons" apply (the default environment: no native build, no optional extras). A reason
that is absent from an environment's budget is NOT budgeted there: it fails the gate, which
is how the "with native build" environment proves that native-dependent tests really ran.
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUDGET = ROOT / "research" / "v7" / "SKIP_BUDGET.json"
SCHEMA = "hcs.skip_budget.v1"


def _reason(testcase: ET.Element) -> str:
    skipped = testcase.find("skipped")
    if skipped is None:
        return ""
    text = (skipped.get("message") or skipped.text or skipped.get("type") or "skipped").strip()
    return text.splitlines()[0].strip() or "skipped"


def parse_junit(path: Path) -> Dict[str, int]:
    """Counts of skipped tests, grouped by reason, from a JUnit XML file."""
    tree = ET.parse(path)
    counts: Dict[str, int] = {}
    for testcase in tree.iter("testcase"):
        reason = _reason(testcase)
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def compare(budget: Dict[str, int], counts: Dict[str, int]) -> List[str]:
    """Problems: an unbudgeted skip reason, or a reason that exceeds its budget."""
    problems: List[str] = []
    for reason, count in sorted(counts.items()):
        allowed = budget.get(reason)
        if allowed is None:
            problems.append(f"unbudgeted skip reason ({count}x): {reason!r}")
        elif count > allowed:
            problems.append(f"skip count grew for {reason!r}: {count} > budget {allowed}")
    return problems


def select_budget(budget_doc: dict, environment: str | None) -> Dict[str, int]:
    """The per-reason ceilings for `environment` (None -> the top-level default)."""
    if not environment:
        return budget_doc.get("reasons", {})
    environments = budget_doc.get("environments", {})
    if environment not in environments:
        raise SystemExit(f"unknown budget environment {environment!r}; known: {sorted(environments)}")
    return environments[environment].get("reasons", {})


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--junitxml", required=True, help="JUnit XML report to parse")
    parser.add_argument("--budget", default=str(DEFAULT_BUDGET))
    parser.add_argument("--record", action="store_true", help="write the current counts as the budget")
    parser.add_argument("--check", action="store_true", help="fail on unbudgeted or grown skips")
    parser.add_argument("--environment", default=None,
                        help="budget environment to check/record (default: the top-level reasons)")
    args = parser.parse_args(argv)

    counts = parse_junit(Path(args.junitxml))
    total = sum(counts.values())
    budget_path = Path(args.budget)

    if args.record:
        budget_path.parent.mkdir(parents=True, exist_ok=True)
        budget_path.write_text(
            json.dumps({"schema": SCHEMA, "total": total, "reasons": counts}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"recorded {total} skipped tests across {len(counts)} reasons -> {budget_path}")
        return 0

    if args.check:
        budget_doc = json.loads(budget_path.read_text(encoding="utf-8"))
        problems = compare(select_budget(budget_doc, args.environment), counts)
        if problems:
            print("Skip budget FAILED:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print(f"Skip budget OK: {total} skipped tests, no new or grown reason"
              + (f" (environment {args.environment})" if args.environment else ""))
        return 0

    print(json.dumps({"schema": SCHEMA, "total": total, "reasons": counts}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
