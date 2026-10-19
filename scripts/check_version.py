#!/usr/bin/env python3
"""
Fails when a public version surface disagrees with scripts/version.py.

Release versions must never be hardcoded independently in several scripts and
workflows. This validator is the mechanical check for that, and is run in CI.

Exit codes: 0 all surfaces agree, 1 at least one mismatch.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import VERSION, package_version, REPO_ROOT  # noqa: E402


def _read(relative: str) -> str:
    path = REPO_ROOT / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def check() -> list:
    """Returns a list of human-readable mismatch descriptions."""
    problems = []

    actual = package_version()
    if actual != VERSION:
        problems.append(
            f"cqhecs/__init__.py declares {actual!r} but "
            f"scripts/version.py declares {VERSION!r}"
        )

    # pyproject.toml must agree with the canonical version.
    pyproject = _read("pyproject.toml")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        problems.append("pyproject.toml has no [project] version field")
    elif match.group(1) != VERSION:
        problems.append(
            f"pyproject.toml version is {match.group(1)!r}, expected {VERSION!r}"
        )

    # CMake project version must agree.
    cmake = _read("CMakeLists.txt")
    match = re.search(r"project\(\s*\S+\s+VERSION\s+([0-9.]+)", cmake)
    if match and match.group(1) != VERSION:
        problems.append(
            f"CMakeLists.txt project VERSION is {match.group(1)!r}, "
            f"expected {VERSION!r}"
        )

    # CITATION.cff must agree.
    citation = _read("CITATION.cff")
    match = re.search(r"^version:\s*(\S+)", citation, re.MULTILINE)
    if match and match.group(1).strip('"') != VERSION:
        problems.append(
            f"CITATION.cff version is {match.group(1)!r}, expected {VERSION!r}"
        )

    # The SBOM generator must not hardcode a stale version.
    sbom = _read("scripts/generate_sbom_and_checksums.py")
    stale = sorted(set(re.findall(r"v?0\.1\.0", sbom)))
    if stale:
        problems.append(
            "scripts/generate_sbom_and_checksums.py hardcodes "
            f"{stale}; it must derive the version from scripts/version.py"
        )

    # The release workflow must not hardcode asset filenames or body paths.
    workflow = _read(".github/workflows/release.yml")
    stale = sorted(set(re.findall(
        r"v0\.\d+\.\d+-(?:py3-none-any\.whl|tar\.gz)|RELEASE_NOTES_v0\.\d+\.\d+\.md",
        workflow,
    )))
    if stale:
        problems.append(
            f".github/workflows/release.yml hardcodes asset names {stale}; "
            "they must be resolved dynamically"
        )

    # SECURITY.md must not advertise a different supported major line.
    security = _read("SECURITY.md")
    if re.search(r"\|\s*4\.5\.x\s*\|", security):
        problems.append(
            "SECURITY.md advertises support for 4.5.x, which is not the "
            f"current version line ({VERSION})"
        )

    return problems


def main() -> int:
    problems = check()
    if problems:
        print("Version consistency check FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"Version consistency OK: all surfaces report {VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())