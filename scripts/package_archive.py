"""Deterministic zip of a directory: sorted entries, fixed timestamp, forward slashes.

    python scripts/package_archive.py --src DIR --out FILE.zip --root-name NAME
    python scripts/package_archive.py --normalize-targz dist/cqhecs-7.0.0.tar.gz

``--normalize-targz`` rewrites a setuptools sdist in place with sorted members, a fixed mtime,
uid/gid 0 and a zero gzip header time (setuptools stamps the build time into both).

``BUILD-INFO.json`` (version, source commit, build date from SOURCE_DATE_EPOCH, builder) is added
to the zip root folder when a source SHA is given (``--source-sha``, or the CQHECS_SOURCE_SHA /
GITHUB_SHA environment variable on the command line; ``--no-build-info`` disables it).  It never
touches ``--normalize-targz`` and the wheel/sdist, so their reproducibility is unchanged.  No run id
or wall clock is written, so the zip stays byte-reproducible for one commit.

Two runs over identical bytes give identical archive bytes (modulo nothing: no
timestamps, no uid/gid, fixed permissions, fixed compression level).
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
import tarfile
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Sequence

FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # fixed stamp, not a build time


BUILD_INFO_NAME = "BUILD-INFO.json"
DEFAULT_EPOCH = "1767225600"
_SHA_RE = re.compile(r"[0-9a-f]{40}")


def build_info_bytes(version: str, source_sha: str, builder: str, epoch: Optional[str] = None) -> bytes:
    """Deterministic BUILD-INFO.json content. The build date is SOURCE_DATE_EPOCH, never the clock."""
    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError(f"source sha must be 40 lowercase hex characters, got {source_sha!r}")
    e = epoch if epoch is not None else os.environ.get("SOURCE_DATE_EPOCH", DEFAULT_EPOCH)
    if not str(e).isdigit():
        raise ValueError(f"SOURCE_DATE_EPOCH must be an integer, got {e!r}")
    doc = {
        "schema": "cqhecs-build-info/1",
        "version": version,
        "source_sha": source_sha,
        "build_date": datetime.fromtimestamp(int(e), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "build_date_basis": "SOURCE_DATE_EPOCH",
        "builder": builder,
    }
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def make_zip(src: Path, out: Path, root_name: str, extra_files: Optional[Dict[str, bytes]] = None) -> int:
    """``extra_files`` maps a name relative to the root folder to its bytes (e.g. BUILD-INFO.json)."""
    src = src.resolve()
    files = sorted(p for p in src.rglob("*") if p.is_file())
    extra_files = dict(extra_files or {})
    for name in extra_files:
        if (src / name).exists():
            raise ValueError(f"refusing to overwrite {name} that already exists in the source tree")
    entries = [(f"{root_name}/{p.relative_to(src).as_posix()}", p, None) for p in files]
    entries += [(f"{root_name}/{n}", None, d) for n, d in extra_files.items()]
    entries.sort(key=lambda t: t[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for arc, p, data in entries:
            info = zipfile.ZipInfo(arc, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # fixed, so the archive does not depend on the host OS
            suffix = Path(arc).suffix.lower()
            info.external_attr = (0o755 if suffix in (".exe", "") else 0o644) << 16
            if data is None:
                with open(p, "rb") as fh:
                    data = fh.read()
            zf.writestr(info, data, compresslevel=6)
    return len(entries)


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
    ap.add_argument("--source-sha", default=None, help="40-hex commit; default $CQHECS_SOURCE_SHA or $GITHUB_SHA")
    ap.add_argument("--build-version", default=None, help="version for BUILD-INFO.json; default scripts/version.py")
    ap.add_argument("--builder", default=None, help="builder identity; default derived from GitHub env, else 'local'")
    ap.add_argument("--no-build-info", action="store_true", help="do not add BUILD-INFO.json")
    a = ap.parse_args(argv)
    if a.normalize_targz:
        n = normalize_targz(a.normalize_targz)
        print(f"normalized {a.normalize_targz} ({n} members)")
        return 0
    if not (a.src and a.out and a.root_name):
        ap.error("--src, --out and --root-name are required")
    extra: Dict[str, bytes] = {}
    sha = a.source_sha or os.environ.get("CQHECS_SOURCE_SHA") or os.environ.get("GITHUB_SHA")
    if sha and not a.no_build_info:
        version = a.build_version
        if version is None:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import version as _version  # scripts/version.py

            version = _version.package_version()
        if not version:
            ap.error("cannot determine the version for BUILD-INFO.json; pass --build-version")
        builder = a.builder
        if builder is None:
            repo, wf = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_WORKFLOW")
            builder = f"github-actions:{repo}:{wf}" if repo and wf else "local"
        extra[BUILD_INFO_NAME] = build_info_bytes(version, sha.lower(), builder)
    n = make_zip(a.src, a.out, a.root_name, extra)
    print(f"wrote {a.out} ({n} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
