#!/usr/bin/env python3
"""Release-status wording consistency gate (F-12).

Several public surfaces describe the release status in prose ("unreleased", "no tag exists",
"will be attached"). ``check_version.py`` checks version numbers only, so these wordings can
drift apart: one file says "released", another still says "candidate". This gate lists every such
surface and checks they all agree for one of two modes:

    python scripts/release_flip_check.py --mode candidate   # the tree is a release candidate
    python scripts/release_flip_check.py --mode released    # the one flip commit has been applied
    python scripts/release_flip_check.py --list             # print the surfaces and exit

``candidate``: every surface must still carry its candidate wording (nothing claims a release
that does not exist).
``released``: no surface may carry candidate wording, and no file may keep a stray candidate
phrase (``RESIDUAL_PATTERNS``).

The gate is offline and read-only. It does not check that a tag or release exists; do that with
the post-release checklist in docs/RELEASE_PROCESS.md section 6. It never flips anything itself.
Exit status: 0 consistent, 1 inconsistent, 2 usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import VERSION  # noqa: E402

_V = re.escape(VERSION)


@dataclass(frozen=True)
class Surface:
    name: str
    path: str
    #: Regex that matches the candidate wording of this surface.
    candidate: str


SURFACES: List[Surface] = [
    Surface("README banner", "README.md",
            r"Development tree \(`[^`]*` release candidate[^)]*unreleased\)"),
    Surface("README EXE text", "README.md",
            r"will be attached to the release once"),
    Surface("README release-artifacts row", "README.md",
            r"\| Release artifacts \|[^|\n]*not published"),
    Surface("README not-run row (no tag)", "README.md",
            r"a release publication \(no tag exists yet\)"),
    Surface("RELEASE_NOTES date line", "RELEASE_NOTES.md",
            r"\*\*Release date:\*\*[^\n]*\(planned; no tag exists"),
    Surface("RELEASE_NOTES artifacts row", "RELEASE_NOTES.md",
            r"\| Release artifacts \|[^|\n]*not published, no tag exists"),
    Surface("RELEASE_NOTES_DRAFT artifacts row", "RELEASE_NOTES_DRAFT.md",
            r"\| Release artifacts \|[^|\n]*not published, no tag exists"),
    Surface("CHANGELOG heading", "CHANGELOG.md",
            rf"^## \[{_V}\] - [^\n]*\(unreleased candidate\)"),
    Surface("CHANGELOG candidate note", "CHANGELOG.md",
            rf"Release candidate: no `v{_V}` tag or GitHub release exists yet"),
]

#: Phrases that must not survive in released mode anywhere in these files, even if a surface
#: above was reworded. Catches a half-done flip.
RESIDUAL_PATTERNS = [
    r"\bunreleased candidate\b",
    r"release candidate on branch",
    r"no tag exists",
    r"nothing is published yet",
    r"will be attached to the release once",
    r"planned; no tag",
]
RESIDUAL_FILES = ["README.md", "RELEASE_NOTES.md", "RELEASE_NOTES_DRAFT.md"]


def _read(root: Path, rel: str) -> Optional[str]:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def check(mode: str, root: Path = ROOT) -> List[str]:
    """Return a list of problems; empty means every surface is consistent for ``mode``."""
    if mode not in ("candidate", "released"):
        raise ValueError(f"unknown mode {mode!r}")
    problems: List[str] = []
    cache = {}
    for s in SURFACES:
        text = cache.setdefault(s.path, _read(root, s.path))
        if text is None:
            problems.append(f"{s.name}: {s.path} is missing")
            continue
        found = re.search(s.candidate, text, re.MULTILINE) is not None
        if mode == "candidate" and not found:
            problems.append(f"{s.name} ({s.path}): candidate wording not found")
        if mode == "released" and found:
            problems.append(f"{s.name} ({s.path}): still carries candidate wording")
    if mode == "released":
        # CHANGELOG is excluded: historic entries legitimately say "unreleased candidate".
        for rel in RESIDUAL_FILES:
            text = cache.setdefault(rel, _read(root, rel))
            if text is None:
                continue
            for pat in RESIDUAL_PATTERNS:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    line = text.count("\n", 0, m.start()) + 1
                    problems.append(f"residual candidate phrase {m.group(0)!r} at {rel}:{line}")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", choices=("candidate", "released"))
    ap.add_argument("--list", action="store_true", help="list the surfaces and exit")
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    if args.list:
        for s in SURFACES:
            print(f"{s.path}: {s.name}")
        return 0
    if not args.mode:
        ap.error("--mode is required unless --list is given")
    problems = check(args.mode, args.root)
    if problems:
        print(f"release_flip_check: INCONSISTENT for mode={args.mode} (version {VERSION})")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"release_flip_check: OK mode={args.mode} version={VERSION} surfaces={len(SURFACES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
