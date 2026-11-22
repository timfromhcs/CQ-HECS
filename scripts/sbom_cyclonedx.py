"""CycloneDX 1.5 SBOM and licence inventory from installed distribution metadata.

    python scripts/sbom_cyclonedx.py --name cq-hecs-wheel --version 7.0.0 \
        --metadata-root <venv>/Lib/site-packages --exclude cqhecs \
        --artifact dist/cqhecs-7.0.0-py3-none-any.whl \
        --out dist/cqhecs-7.0.0-wheel.cdx.json --licences-out dist/cqhecs-7.0.0-wheel.licences.json

Component data comes from the ``*.dist-info/METADATA`` files found under each
``--metadata-root`` (a venv site-packages directory, or a PyInstaller ``_internal`` folder),
so the SBOM lists what is actually in the artifact's environment, not what pyproject declares.
A licence that the metadata does not state is written as ``UNVERIFIED``; nothing is guessed.

Frozen bundles: pass ``--bundle-dir <_internal>`` (and, if available, ``--pyz-toc <build>/PYZ-00.toc``)
together with the build venv's site-packages as ``--metadata-root``; a distribution is then listed
only if one of its top-level modules is actually in the bundle (directory/extension names or PYZ
module names).  PyInstaller does not copy most dist-info folders into the bundle, so this is how the
bundled set is recovered; modules that are bundled under a different top-level name are not seen.

Wheel SBOM accuracy: pass ``--closure-of cqhecs`` to list only the runtime dependency closure of that
distribution (its own ``Requires-Dist`` entries without extras, followed transitively) instead of every
distribution that happens to be installed in the venv.  Venv tooling (setuptools and its vendored
packages, wheel, pip) is therefore not reported unless the root actually requires it.  The root must be
installed in the metadata root, otherwise the run fails.  Environment markers other than ``extra`` are
not evaluated: a conditional dependency that is installed is listed, one that is not installed is
recorded under the root's ``cqhecs:closure-not-installed`` property.

Build identity: ``--source-revision <40-hex sha>`` (default $CQHECS_SOURCE_SHA / $GITHUB_SHA) is written
to the root component as a ``cqhecs:source-revision`` property and, with ``--source-repository`` (default
$GITHUB_REPOSITORY), as a CycloneDX ``vcs`` external reference.

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


def dependency_closure(comps: Sequence[Dict[str, Any]], roots: Sequence[str]) -> Dict[str, Any]:
    """Transitive Requires-Dist closure of ``roots`` over the installed ``comps``.

    Returns {"components": [...] (roots excluded, sorted), "not_installed": [...]}.  Raises
    LookupError when a root is not installed.
    """
    by = {norm(c["name"]): c for c in comps}
    for r in roots:
        if norm(r) not in by:
            raise LookupError(f"closure root {r!r} is not installed in the metadata root")
    keep: Dict[str, Dict[str, Any]] = {}
    missing: set = set()
    stack = [norm(r) for r in roots]
    visited = set(stack)
    while stack:
        cur = by[stack.pop()]
        for req in cur["requires"]:
            if req in by:
                if req not in visited:
                    visited.add(req)
                    stack.append(req)
            else:
                missing.add(req)
    root_set = {norm(r) for r in roots}
    keep = {k: by[k] for k in visited if k not in root_set}
    return {"components": [keep[k] for k in sorted(keep)], "not_installed": sorted(missing)}


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
          root_licence: str, timestamp: Optional[str], source_revision: Optional[str] = None,
          source_repository: Optional[str] = None, closure_not_installed: Sequence[str] = ()) -> Dict[str, Any]:
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
    seed: List[Any] = [name, version, [(c["name"], c["version"]) for c in comps]]
    if source_revision:
        seed.append(source_revision)
    serial = uuid.uuid5(NAMESPACE, json.dumps(seed))
    meta: Dict[str, Any] = {
        "tools": {"components": [{"type": "application", "name": "cq-hecs scripts/sbom_cyclonedx.py"}]},
        "component": {
            "type": "application", "bom-ref": root_ref, "name": name, "version": version,
            "licenses": [{"license": {"id": root_licence}}],
            "hashes": [{"alg": "SHA-256", "content": sha256_file(a)} for a in artifacts],
            "properties": [{"name": "cqhecs:artifact-file", "value": a.name} for a in artifacts],
        },
    }
    root = meta["component"]
    if source_revision:
        root["properties"].append({"name": "cqhecs:source-revision", "value": source_revision})
        if source_repository:
            root["externalReferences"] = [
                {"type": "vcs", "url": f"https://github.com/{source_repository}/commit/{source_revision}"}
            ]
    if closure_not_installed:
        root["properties"].append({"name": "cqhecs:closure-not-installed", "value": ",".join(closure_not_installed)})
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
    ap.add_argument("--closure-of", action="append", default=[],
                    help="list only the runtime dependency closure of this installed distribution (repeatable)")
    ap.add_argument("--source-revision", default=None, help="40-hex commit; default $CQHECS_SOURCE_SHA or $GITHUB_SHA")
    ap.add_argument("--source-repository", default=None, help="owner/name for the vcs reference; default $GITHUB_REPOSITORY")
    ap.add_argument("--root-licence", default="Apache-2.0")
    ap.add_argument("--timestamp", default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--licences-out", type=Path, default=None)
    a = ap.parse_args(argv)

    ts = a.timestamp
    if ts is None and os.environ.get("SOURCE_DATE_EPOCH", "").isdigit():
        ts = datetime.fromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rev = a.source_revision or os.environ.get("CQHECS_SOURCE_SHA") or os.environ.get("GITHUB_SHA")
    if rev is not None and not re.fullmatch(r"[0-9a-f]{40}", rev.lower()):
        ap.error(f"--source-revision must be a 40-hex commit sha, got {rev!r}")
    rev = rev.lower() if rev else None
    repo = a.source_repository or os.environ.get("GITHUB_REPOSITORY")
    not_installed: List[str] = []
    if a.closure_of:
        everything = collect(a.metadata_root, [], bundled_names(a.bundle_dir, a.pyz_toc))
        try:
            clo = dependency_closure(everything, a.closure_of)
        except LookupError as exc:
            ap.error(str(exc))
        skip = {norm(e) for e in a.exclude}
        comps = [c for c in clo["components"] if norm(c["name"]) not in skip]
        not_installed = clo["not_installed"]
    else:
        comps = collect(a.metadata_root, a.exclude, bundled_names(a.bundle_dir, a.pyz_toc))
    for spec in a.extra_component:
        n, v, lic, basis = (spec.split("|") + ["", "", "", ""])[:4]
        comps.append({"name": n, "version": v or "UNKNOWN", "licence": lic or UNVERIFIED,
                      "licence_basis": basis or "not opened", "requires": [], "home": "", "extra": True})
    comps.sort(key=lambda c: norm(c["name"]))
    bom = build(a.name, a.version, comps, a.artifact, a.root_licence, ts, rev, repo, not_installed)
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
