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

    # The changelog must contain a section for the released version. An
    # [Unreleased] section is allowed on top (in-progress development).
    changelog_version = re.search(
        r"^##\s+\[?\[" + re.escape(VERSION) + r"\]?\]",
        _read("CHANGELOG.md"),
        re.MULTILINE,
    )
    if not changelog_version:
        problems.append(
            f"CHANGELOG.md has no '## [{VERSION}]' section for the released version"
        )

    # RELEASE_NOTES.md must not still describe an old version as current.
    notes = _read("RELEASE_NOTES.md")
    projected = re.findall(r"\bv?(?:0\.1\.0|0\.2\.0)\b", notes)
    if projected:
        problems.append(
            "RELEASE_NOTES.md references version(s) "
            f"{sorted(set(projected))}; it must describe {VERSION} only"
        )

    # Surfaces that report the version at runtime must agree too. Historical
    # records (CHANGELOG, release_tracking.json, benchmark archives) are
    # intentionally excluded here.
    for relative, pattern, name in (
        (
            "include/cq_hecs_api.h",
            r'#define CQ_HECS_VERSION\s+"([^"]+)"',
            "C API version macro",
        ),
        (
            "python_bridge/cq_hecs.py",
            r'^__version__\s*=\s*"([^"]+)"',
            "python_bridge version",
        ),
        (
            "python/cqhecs/__init__.py",
            r'^__version__\s*=\s*"([^"]+)"',
            "legacy cqhecs shim version",
        ),
        (
            "python/cq_hecs/__init__.py",
            r'^__version__\s*=\s*"([^"]+)"',
            "legacy cq_hecs shim version",
        ),
        (
            "tests/test_c_api.py",
            r'assertEqual\(ver,\s*"([^"]+)"\)',
            "C API version test",
        ),
    ):
        match = re.search(pattern, _read(relative), re.MULTILINE)
        if not match:
            problems.append(f"{name} not found in {relative}")
        elif match.group(1) != VERSION:
            problems.append(
                f"{name} in {relative} is {match.group(1)!r}, "
                f"expected {VERSION!r}"
            )

    # The native CLI must derive its version from CQ_HECS_VERSION rather than
    # hardcoding a release string.
    main_cpp = _read("src/main.cpp")
    hardcoded_cli = re.search(r'"CQ-HECS v\d+\.\d+\.\d+', main_cpp)
    if hardcoded_cli:
        problems.append(
            "src/main.cpp hardcodes a CLI version string; use CQ_HECS_VERSION"
        )

    # Packaging scripts must derive the version; a literal vX.Y.Z would drift.
    for relative in ("scripts/package_release.ps1", "scripts/smoke_test.ps1"):
        literal = sorted(set(re.findall(
            r"\bv\d+\.\d+\.\d+\b", _read(relative)
        )))
        if literal:
            problems.append(
                f"{relative} hardcodes version(s) {literal}; "
                "derive them from scripts/version.py"
            )

    # The README wheel example and API reference must show the current version.
    readme = _read("README.md")
    if f"cqhecs-{VERSION}-py3-none-any.whl" not in readme:
        problems.append(
            f"README.md does not show the current wheel name cqhecs-{VERSION}"
        )
    if f'"{VERSION}"' not in _read("docs/API_REFERENCE.md"):
        problems.append(
            f"docs/API_REFERENCE.md does not document version {VERSION!r}"
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