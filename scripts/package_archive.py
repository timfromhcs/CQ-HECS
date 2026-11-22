"""Deterministic zip of a directory: sorted entries, fixed timestamp, forward slashes.

    python scripts/package_archive.py --src DIR --out FILE.zip --root-name NAME
    python scripts/package_archive.py --normalize-targz dist/cqhecs-5.0.0.tar.gz

``--normalize-targz`` rewrites a setuptools sdist in place with sorted members, a fixed mtime,
uid/gid 0 and a zero gzip header time (setuptools stamps the build time into both).

Two runs over identical bytes give identical archive bytes (modulo nothing: no
timestamps, no uid/gid, fixed permissions, fixed compression level).
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Optional, Sequence

FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # fixed stamp, not a build time


def make_zip(src: Path, out: Path, root_name: str) -> int:
    src = src.resolve()
    files = sorted(p for p in src.rglob("*") if p.is_file())
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in files:
            arc = f"{root_name}/{p.relative_to(src).as_posix()}"
            info = zipfile.ZipInfo(arc, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # fixed, so the archive does not depend on the host OS
            info.external_attr = (0o755 if p.suffix.lower() in (".exe", "") else 0o644) << 16
            with open(p, "rb") as fh:
                zf.writestr(info, fh.read(), compresslevel=6)
    return len(files)


def normalize_targz(path: Path) -> int:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600"))
    with tarfile.open(path, "r:gz") as src:
        members = sorted(src.getmembers(), key=lambda m: m.name)
        payload = [(m, src.extractfile(m).read() if m.isfile() else None) for m in members]  # type: ignore[union-attr]
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as dst:
            for m, data in payload:
                m.mtime, m.uid, m.gid, m.uname, m.gname = epoch, 0, 0, "", ""
                m.pax_headers = {}
                dst.addfile(m, io.BytesIO(data) if data is not None else None)
    path.write_bytes(buf.getvalue())
    return len(payload)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--root-name")
    ap.add_argument("--normalize-targz", type=Path)
    a = ap.parse_args(argv)
    if a.normalize_targz:
        n = normalize_targz(a.normalize_targz)
        print(f"normalized {a.normalize_targz} ({n} members)")
        return 0
    if not (a.src and a.out and a.root_name):
        ap.error("--src, --out and --root-name are required")
    n = make_zip(a.src, a.out, a.root_name)
    print(f"wrote {a.out} ({n} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
