"""Copy third-party licence files for a frozen bundle into the bundle folder.

    python scripts/package_notices.py --app-dir dist/cq-hecs --metadata-root <build venv site-packages> \
        --pyz-toc <work>/cq-hecs/PYZ-00.toc --licence-file LICENSE [--extra-file PyInstaller=<COPYING.txt>]

PyInstaller copies almost no ``*.dist-info`` licence files into the bundle, so the bundled
BSD/Apache/MIT packages would be redistributed without their notices.  This finds the
distributions that are really bundled (same rule as scripts/sbom_cyclonedx.py), copies each one's
licence/notice files from its dist-info to ``<app-dir>/licences/<name>-<version>/`` and writes
``<app-dir>/THIRD_PARTY_NOTICES.txt``.  A distribution with no licence file is listed as such;
nothing is invented.  Native libraries vendored inside those wheels (``*.libs``) are covered only
by the licence expression their wheel declares.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Sequence

_spec = importlib.util.spec_from_file_location("sbom_cyclonedx", Path(__file__).with_name("sbom_cyclonedx.py"))
sbom = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["sbom_cyclonedx"] = sbom
_spec.loader.exec_module(sbom)  # type: ignore[union-attr]

LICENCE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def licence_files(dist_info: Path) -> List[Path]:
    found: List[Path] = []
    lic_dir = dist_info / "licenses"
    if lic_dir.is_dir():
        found += [p for p in sorted(lic_dir.rglob("*")) if p.is_file()]
    found += [p for p in sorted(dist_info.iterdir())
              if p.is_file() and p.name.upper().startswith(LICENCE_NAMES)]
    return found


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app-dir", required=True, type=Path)
    ap.add_argument("--metadata-root", action="append", required=True, type=Path)
    ap.add_argument("--pyz-toc", type=Path, default=None)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--licence-file", type=Path, default=None, help="this project's LICENSE")
    ap.add_argument("--extra-file", action="append", default=[], help="NAME=PATH of a further licence file")
    a = ap.parse_args(argv)

    internal = a.app_dir / "_internal"
    present = sbom.bundled_names(internal if internal.is_dir() else a.app_dir, a.pyz_toc)
    out = a.app_dir / "licences"
    out.mkdir(parents=True, exist_ok=True)
    lines = ["Third-party notices for the CQ-HECS application folder.",
             "Licence strings are copied from each distribution's METADATA; files are copied from its dist-info.", ""]
    n_missing = 0
    skip = {sbom.norm(e) for e in a.exclude}
    for root in a.metadata_root:
        for meta in sorted(root.rglob("*.dist-info/METADATA")):
            d = sbom.read_distribution(meta)
            if not d or sbom.norm(d["name"]) in skip or sbom.norm(d["name"]) == "cqhecs":
                continue
            mods = {m.lower() for m in sbom.top_levels(meta.parent)}
            if present is not None and not (mods & present):
                continue
            files = licence_files(meta.parent)
            dest = out / f"{sbom.norm(d['name'])}-{d['version']}"
            for f in files:
                target = dest / f.relative_to(meta.parent / "licenses") if "licenses" in f.parts else dest / f.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, target)
            if not files:
                n_missing += 1
            lines.append(f"{d['name']} {d['version']}: {d['licence']} [{d['licence_basis']}] - "
                         + (f"{len(files)} licence file(s) in licences/{dest.name}/" if files
                            else "NO LICENCE FILE IN THE DISTRIBUTION (not invented here)"))
    if a.licence_file and a.licence_file.is_file():
        shutil.copyfile(a.licence_file, a.app_dir / "LICENSE")
        lines.insert(2, "CQ-HECS itself: Apache-2.0, see LICENSE.")
    for spec in a.extra_file:
        name, _, path = spec.partition("=")
        p = Path(path)
        if p.is_file():
            d = out / re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            d.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, d / p.name)
            lines.append(f"{name}: licence file {p.name} copied to licences/{d.name}/")
        else:
            lines.append(f"{name}: licence file not found at {path} (not copied)")
            n_missing += 1
    lines.append("")
    lines.append("Not inventoried: the CPython runtime and the Microsoft Visual C++ runtime DLLs shipped in _internal.")
    (a.app_dir / "THIRD_PARTY_NOTICES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"notices written to {a.app_dir} ({n_missing} entries without a licence file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
