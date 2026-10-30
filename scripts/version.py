#!/usr/bin/env python3
"""
Single source of truth for the project version.

Run ``python scripts/version.py`` to print the version, or
``python scripts/check_version.py`` to verify that every public version surface
agrees with :data:`VERSION`.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The canonical version. Every release artifact and document must match this.
VERSION = "3.3.0"


def package_version() -> str:
    """Reads __version__ from the checked-out package."""
    init = (REPO_ROOT / "cqhecs" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', init, re.MULTILINE)
    if not match:
        raise RuntimeError("cqhecs/__init__.py does not define __version__")
    return match.group(1)


def main() -> int:
    print(package_version())
    return 0


if __name__ == "__main__":
    sys.exit(main())