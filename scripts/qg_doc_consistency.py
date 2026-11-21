#!/usr/bin/env python3
"""QG documentation consistency check (W3-21 / D9).

The Quantum Gravity campaign records drifted from the evidence: STATUS.md said
"21/25 Spark" and "M6/M7 BLOCKED (B-1)" next to a completed 25/25 campaign, and the
F-08 prose stated a ratio range narrower than its own table. This checker derives the
facts from the data and fails when a document contradicts them. It checks:

1. STATUS.md carries one campaign total (25 / 25) and no resolved-blocker contradiction.
2. The F-08 prose ratio range brackets the ratios recomputed from
   ``processed/bmv_phase_scan.json``.
3. Relative Markdown links in the QG docs resolve (the uncommitted mission file
   ``QGRAVITY.md`` is allow-listed).

Exit 0 on pass, 1 on any inconsistency.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QG = ROOT / "research" / "qg_2026"
MISSION_ALLOWLIST = {"QGRAVITY.md"}


def check_status(problems: list) -> None:
    status = (QG / "STATUS.md").read_text(encoding="utf-8")
    if "25 / 25 Spark" not in status:
        problems.append("STATUS.md does not state the campaign total '25 / 25 Spark'")
    if "21/25 Spark" in status:
        problems.append("STATUS.md still says '21/25 Spark' next to the completed campaign")
    if "BLOCKED (B-1" in status:
        problems.append("STATUS.md still marks a milestone 'BLOCKED (B-1)' although B-1 is resolved")


def ratios_from_data() -> list:
    data = json.loads((QG / "processed" / "bmv_phase_scan.json").read_text(encoding="utf-8"))
    ratios = []
    for point in data["points"]:
        # F-08's range is about the YZ/ZY phase scan; the XX basis is a different
        # observable with its own (different) ratio and is not part of that range.
        if point.get("basis") not in ("YZ", "ZY"):
            continue
        expected = point.get("expected_sin")
        correlator = point.get("correlator")
        if expected in (None, 0) or correlator is None:
            continue
        ratio = point.get("ratio")
        if ratio is None or abs(ratio - correlator / expected) > 1e-3:
            raise ValueError(
                f"processed point {point.get('circuit_id')}: ratio {ratio!r} != "
                f"correlator/expected_sin {correlator / expected!r}"
            )
        ratios.append(ratio)
    return ratios


def check_f08(problems: list) -> None:
    findings = (QG / "FINDINGS.md").read_text(encoding="utf-8")
    try:
        ratios = ratios_from_data()
    except (ValueError, KeyError, FileNotFoundError) as exc:
        problems.append(f"processed/bmv_phase_scan.json is inconsistent: {exc}")
        return
    if not ratios:
        problems.append("no F-08 ratios could be derived from the processed data")
        return
    low, high = min(ratios), max(ratios)
    # The prose must contain a range that brackets the measured ratios; a range that
    # understates the low end (the D9 defect) is not accepted.
    ranges = [
        (float(a), float(b))
        for a, b in re.findall(r"(\d\.\d+)-(\d\.\d+)x\s*sin", findings)
    ]
    if not any(a <= low + 1e-3 and b >= high - 1e-3 for a, b in ranges):
        problems.append(
            f"F-08 prose range {ranges} does not bracket the measured ratios "
            f"[{low:.3f}, {high:.3f}]"
        )


def check_links(problems: list) -> None:
    files = list(QG.glob("*.md"))
    lab = ROOT / "docs" / "QUANTUM_GRAVITY_LAB.md"
    if lab.is_file():
        files.append(lab)
    for path in files:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            if not target or Path(target).name in MISSION_ALLOWLIST:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                problems.append(f"{path.relative_to(ROOT)} links to missing {target!r}")


def main() -> int:
    problems: list = []
    check_status(problems)
    check_f08(problems)
    check_links(problems)
    if problems:
        print("QG doc consistency FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("QG doc consistency OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
