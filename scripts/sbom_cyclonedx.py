"""CycloneDX 1.5 SBOM and licence inventory from installed distribution metadata.

    python scripts/sbom_cyclonedx.py --name cq-hecs-wheel --version 5.0.0 \
        --metadata-root <venv>/Lib/site-packages --exclude cqhecs \
        --artifact dist/cqhecs-5.0.0-py3-none-any.whl \
        --out dist/cqhecs-5.0.0-wheel.cdx.json --licences-out dist/cqhecs-5.0.0-wheel.licences.json

Component data comes from the ``*.dist-info/METADATA`` files found under each
``--metadata-root`` (a venv site-packages directory, or a PyInstaller ``_internal`` folder),
so the SBOM lists what is actually in the artifact's environment, not what pyproject declares.
A licence that the metadata does not state is written as ``UNVERIFIED``; nothing is guessed.

Frozen bundles: pass ``--bundle-dir <_internal>`` (and, if available, ``--pyz-toc <build>/PYZ-00.toc``)
together with the build venv's site-packages as ``--metadata-root``; a distribution is then listed
only if one of its top-level modules is actually in the bundle (directory/extension names or PYZ
module names).  PyInstaller does not copy most dist-info folders into the bundle, so this is how the
bundled set is recovered; modules that are bundled under a different top-level name are not seen.

Determinism: components are sorted; no wall-clock time is written (pass ``--timestamp`` or set
SOURCE_DATE_EPOCH to add one); serialNumber is a UUIDv5 over the sorted component list.
This is an inventory, not a vulnerability audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

NAMESPACE = uuid.UUID("6f1c5f0e-9a52-5c1e-8a56-0c9f5c8a4d11")  # fixed, arbitrary
UNVERIFIED = "UNVERIFIED"


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_distribution(meta: Path) -> Optional[Dict[str, Any]]:
    try:
        msg = Parser().parsestr(meta.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    name, version = msg.get("Name"), msg.get("Version")
    if not name or not version:
        return None
    expr = msg.get("License-Expression")
    lic_field = msg.get("License")
    classifiers = [c.split("::")[-1].strip() for c in msg.get_all("Classifier") or [] if c.startswith("License ::")]
    if expr:
        licence, basis = expr.strip(), "metadata License-Expression"
    elif lic_field and len(lic_field.strip()) < 80 and "\n" not in lic_field.strip():
        licence, basis = lic_field.strip(), "metadata License field"
    elif classifiers:
        licence, basis = " OR ".join(sorted(set(classifiers))), "metadata Trove classifier"
    elif lic_field:
        licence, basis = f"{UNVERIFIED} (full licence text embedded; not parsed)", "metadata License field (text)"
    else:
        licence, basis = UNVERIFIED, "metadata declares no licence"
    requires = [
        norm(re.split(r"[ ;<>=!~\[(]", r.strip(), maxsplit=1)[0])
        for r in msg.get_all("Requires-Dist") or []
        if "extra ==" not in r
    ]
    return {
        "name": name, "version": version, "licence": licence, "licence_basis": basis,
        "requires": sorted(set(requires)), "home": msg.get("Home-page") or msg.get("Project-URL") or "",
    }


def top_levels(dist_info: Path) -> List[str]:
    """Top-level importable names of an installed distribution (top_level.txt, else RECORD)."""
    tl = dist_info / "top_level.txt"
    if tl.is_file():
        return [x.strip() for x in tl.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
    rec = dist_info / "RECORD"
    names = set()
    if rec.is_file():
        for line in rec.read_text(encoding="utf-8", errors="replace").splitlines():
            first = line.split(",", 1)[0].replace("\\", "/").split("/", 1)[0]
            if first and first not in ("..", "__pycache__") and not first.endswith((".dist-info", ".data", ".libs")):
                names.add(first.split(".")[0])
    return sorted(names)


def bundled_names(bundle_dir: Optional[Path], pyz_toc: Optional[Path]) -> Optional[set]:
    if bundle_dir is None and pyz_toc is None:
        return None
    names: set = set()
    if bundle_dir is not None:
        for p in bundle_dir.iterdir():
            names.add(p.name.split(".")[0].lower())
    if pyz_toc is not None:
        import ast

        toc = ast.literal_eval(pyz_toc.read_text(encoding="utf-8"))
        for entry in toc[1]:
            names.add(entry[0].split(".")[0].lower())
    return names


def collect(roots: Sequence[Path], exclude: Sequence[str], present: Optional[set] = None) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    skip = {norm(e) for e in exclude}
    for root in roots:
        for meta in sorted(root.rglob("*.dist-info/METADATA")):
            d = read_distribution(meta)
            if not d or norm(d["name"]) in skip:
                continue
            if present is not None:
                mods = {m.lower() for m in top_levels(meta.parent)}
                if not (mods & present):
                    continue
            seen.setdefault(norm(d["name"]), d)
    return [seen[k] for k in sorted(seen)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def licence_entry(c: Dict[str, Any]) -> Dict[str, Any]:
    """CycloneDX licence entry. Only a metadata License-Expression is emitted as an SPDX
    expression; every other string is carried as a free-text name (never promoted to an id)."""
    if c["licence_basis"] == "metadata License-Expression":
        return {"expression": c["licence"]}
    return {"license": {"name": c["licence"]}}


def build(name: str, version: str, comps: List[Dict[str, Any]], artifacts: Sequence[Path],
          root_licence: str, timestamp: Optional[str]) -> Dict[str, Any]:
    components = []
    for c in comps:
        ref = (f"extra:{norm(c['name'])}@{c['version']}" if c.get("extra")
               else f"pkg:pypi/{norm(c['name'])}@{c['version']}")
        entry: Dict[str, Any] = {
            "type": "library",
            "bom-ref": ref,
            "name": c["name"],
            "version": c["version"],
            "licenses": [licence_entry(c)],
            "properties": [{"name": "cqhecs:licence-basis", "value": c["licence_basis"]}],
        }
        if not c.get("extra"):
            entry["purl"] = ref
        components.append(entry)
    root_ref = f"cqhecs-artifact:{name}@{version}"
    direct = [(f"extra:{norm(c['name'])}@{c['version']}" if c.get("extra")
               else f"pkg:pypi/{norm(c['name'])}@{c['version']}") for c in comps]
    serial = uuid.uuid5(NAMESPACE, json.dumps([name, version, [(c["name"], c["version"]) for c in comps]]))
    meta: Dict[str, Any] = {
        "tools": {"components": [{"type": "application", "name": "cq-hecs scripts/sbom_cyclonedx.py"}]},
        "component": {
            "type": "application", "bom-ref": root_ref, "name": name, "version": version,
            "licenses": [{"license": {"id": root_licence}}],
            "hashes": [{"alg": "SHA-256", "content": sha256_file(a)} for a in artifacts],
            "properties": [{"name": "cqhecs:artifact-file", "value": a.name} for a in artifacts],
        },
    }
    if timestamp:
        meta["timestamp"] = timestamp
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": meta,
        "components": components,
        "dependencies": [{"ref": root_ref, "dependsOn": direct}],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--metadata-root", action="append", required=True, type=Path)
    ap.add_argument("--exclude", action="append", default=[], help="distribution name to leave out (the root itself)")
    ap.add_argument("--artifact", action="append", default=[], type=Path, help="file whose SHA-256 is recorded")
    ap.add_argument("--bundle-dir", type=Path, default=None, help="PyInstaller _internal folder")
    ap.add_argument("--pyz-toc", type=Path, default=None, help="PyInstaller PYZ-00.toc from the build work dir")
    ap.add_argument("--extra-component", action="append", default=[],
                    help="non-Python component 'name|version|licence|basis' (licence UNVERIFIED if not opened)")
    ap.add_argument("--root-licence", default="Apache-2.0")
    ap.add_argument("--timestamp", default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--licences-out", type=Path, default=None)
    a = ap.parse_args(argv)

    ts = a.timestamp
    if ts is None and os.environ.get("SOURCE_DATE_EPOCH", "").isdigit():
        ts = datetime.fromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    comps = collect(a.metadata_root, a.exclude, bundled_names(a.bundle_dir, a.pyz_toc))
    for spec in a.extra_component:
        n, v, lic, basis = (spec.split("|") + ["", "", "", ""])[:4]
        comps.append({"name": n, "version": v or "UNKNOWN", "licence": lic or UNVERIFIED,
                      "licence_basis": basis or "not opened", "requires": [], "home": "", "extra": True})
    comps.sort(key=lambda c: norm(c["name"]))
    bom = build(a.name, a.version, comps, a.artifact, a.root_licence, ts)
    a.out.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if a.licences_out:
        inv = {
            "artifact": a.name, "version": a.version,
            "note": "Licence strings are copied from each distribution's own METADATA. UNVERIFIED means the "
                    "metadata states none or only an unparsed text; the licence file was not opened here.",
            "components": [{k: c[k] for k in ("name", "version", "licence", "licence_basis")} for c in comps],
            "unverified": sorted(c["name"] for c in comps if c["licence"].startswith(UNVERIFIED)),
        }
        a.licences_out.write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {a.out}: {len(comps)} components, "
          f"{sum(c['licence'].startswith(UNVERIFIED) for c in comps)} with UNVERIFIED licence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
