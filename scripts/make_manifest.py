"""Deterministic SHA-256 manifest of release artifacts.

    python scripts/make_manifest.py DIR --out DIR/SHA256SUMS        # write
    python scripts/make_manifest.py DIR --verify DIR/SHA256SUMS     # verify (exit 1 on any mismatch)

Format is the common `sha256sum` one ("<hex>  <name>", LF, ASCII, sorted by name), so
`sha256sum -c` also works.  The manifest never lists itself.  No timestamps are written.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(directory: Path, exclude: Sequence[str] = ("SHA256SUMS",)) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in sorted(directory.iterdir(), key=lambda q: q.name):
        if p.is_file() and p.name not in exclude:
            out[p.name] = sha256_file(p)
    return out


def render(entries: Dict[str, str]) -> str:
    return "".join(f"{digest}  {name}\n" for name, digest in sorted(entries.items()))


def parse(text: str) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        if len(digest) != 64 or not name:
            raise ValueError(f"malformed manifest line: {line!r}")
        entries[name] = digest
    return entries


def verify(directory: Path, manifest: Path) -> List[str]:
    """Return a list of problems (empty = every listed file matches, nothing unlisted)."""
    problems: List[str] = []
    listed = parse(manifest.read_text(encoding="ascii"))
    actual = collect(directory, exclude=(manifest.name,))
    for name, digest in listed.items():
        p = directory / name
        if not p.is_file():
            problems.append(f"missing: {name}")
        elif sha256_file(p) != digest:
            problems.append(f"MISMATCH: {name}")
    for name in actual:
        if name not in listed:
            problems.append(f"unlisted file: {name}")
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", type=Path)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--out", type=Path)
    grp.add_argument("--verify", type=Path)
    a = ap.parse_args(argv)
    if a.out:
        entries = collect(a.directory, exclude=(a.out.name,))
        a.out.write_text(render(entries), encoding="ascii", newline="\n")
        print(f"wrote {a.out} ({len(entries)} files)")
        return 0
    problems = verify(a.directory, a.verify)
    for p in problems:
        print(p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
