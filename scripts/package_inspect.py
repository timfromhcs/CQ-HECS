"""Inspect a built wheel / sdist / directory for packaging defects.

    python scripts/package_inspect.py dist/cqhecs-5.0.0-py3-none-any.whl [more archives] [--json out.json]

Checks (each reported; exit 1 if any FAIL):
  * required members are present (Studio static incl. qg.js, Studio data, entry point, licence);
  * no forbidden members: research raw evidence, credentials/.env/keys, caches, test trees in
    the wheel, spec/build leftovers;
  * no member text contains a developer-machine path (C:\\Users\\..., D:\\QHCS..., /home/...);
  * no member text looks like a credential (private key block, token prefixes).

Binary members are scanned as bytes.  An archive that cannot be read is a FAIL, not a skip.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REQUIRED_WHEEL = (
    "cqhecs/__init__.py",
    "cqhecs/cli.py",
    "cqhecs/mcp_server.py",
    "cqhecs/studio/app.py",
    "cqhecs/studio/static/index.html",
    "cqhecs/studio/static/app.js",
    "cqhecs/studio/static/qg.js",
    "cqhecs/studio/static/style.css",
    "cqhecs/studio/data/dataset.json",
    "cqhecs/studio/data/device_profiles.json",
    "cqhecs/quantum_gravity/__init__.py",
)
REQUIRED_WHEEL_SUFFIX = ("dist-info/METADATA", "dist-info/entry_points.txt", "dist-info/RECORD")
REQUIRED_SDIST = ("pyproject.toml", "README.md", "LICENSE", "schemas/studio.openapi.json")

FORBIDDEN_PATTERNS = (
    (r"(^|/)\.env(\.|$)", "dotenv file"),
    (r"(?i)(^|/)[^/]*(secret|credential|passw(or)?d|api[_-]?key)[^/]*$", "credential-named path"),
    (r"\.(pem|key|p12|pfx|jks)$", "key material extension"),
    (r"(^|/)id_(rsa|ed25519|ecdsa)", "ssh key"),
    (r"(^|/)__pycache__/", "bytecode cache"),
    (r"\.py[co]$", "bytecode"),
    (r"(^|/)research/", "research raw evidence tree"),
    (r"(^|/)\.git(/|$)", "git metadata"),
    (r"(^|/)(node_modules)/", "node_modules"),
    (r"(^|/)(cq-hecs\.spec)$", "PyInstaller spec leftover"),
    (r"(^|/)(openquantum|ibm)[-_]?(token|key|credentials?)", "provider credential file"),
)
FORBIDDEN_WHEEL_ONLY = ((r"^(tests|benchmarks|audit|web|scripts)/", "non-runtime tree in the wheel"),)

LOCAL_PATH = re.compile(
    rb"(?i)(?:[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+|[A-Z]:[\\/]+QHCS|/home/[a-z][a-z0-9._-]+/|/Users/[A-Za-z][A-Za-z0-9._-]+/)"
)
SECRETISH = re.compile(
    rb"(-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
    rb"|sk-[A-Za-z0-9]{32,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})"
)
# A scan hit inside text that *documents* these patterns (the security tooling) is not a leak.
SCAN_EXEMPT = re.compile(r"(^|/)(security_audit|package_inspect|test_property_security_audit|test_packaging[a-z_]*)\.py$")


def iter_members(path: Path) -> Iterable[Tuple[str, bytes]]:
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file():
                yield p.relative_to(path).as_posix(), p.read_bytes()
    elif path.suffix == ".whl" or path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if not n.endswith("/"):
                    yield n, z.read(n)
    elif path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path) as t:
            for m in sorted(t.getmembers(), key=lambda m: m.name):
                if m.isfile():
                    name = m.name.split("/", 1)[1] if "/" in m.name else m.name  # strip pkg-ver/
                    yield name, t.extractfile(m).read()  # type: ignore[union-attr]
    else:
        raise ValueError(f"unsupported artifact type: {path}")


BINARY_SUFFIX = (".pyd", ".dll", ".exe", ".so", ".dylib", ".lib", ".pdb", ".pyz", ".pkg", ".spv", ".npy", ".npz")


def machine_markers(extra: Sequence[str] = ()) -> List[bytes]:
    """Strings that identify THIS build machine (home directory, repository checkout, extras).

    Third-party binaries legitimately embed their upstream authors' build paths, so a generic
    path pattern is applied to first-party and text content only; these markers are searched
    in every member, binary or not."""
    out = {str(Path.home()), str(Path(__file__).resolve().parent.parent), *extra}
    marks: List[bytes] = []
    for s in out:
        if len(s) > 6:
            for variant in (s, s.replace("\\", "/"), s.replace("/", "\\")):
                marks.append(variant.lower().encode("utf-8", "replace"))
    return sorted(set(marks))


def inspect(path: Path, extra_markers: Sequence[str] = ()) -> Dict[str, object]:
    kind = "wheel" if path.suffix == ".whl" else "sdist" if path.name.endswith((".tar.gz", ".tgz")) else "dir"
    members: Dict[str, bytes] = {}
    findings: List[Dict[str, str]] = []
    try:
        members = dict(iter_members(path))
    except Exception as exc:  # noqa: BLE001
        return {"artifact": path.name, "kind": kind, "status": "FAIL",
                "findings": [{"severity": "FAIL", "what": f"unreadable archive: {exc}"}], "members": 0}

    names = set(members)

    def add(sev: str, what: str, where: str = "") -> None:
        findings.append({"severity": sev, "what": what, "where": where})

    if kind == "wheel":
        for req in REQUIRED_WHEEL:
            if req not in names:
                add("FAIL", "required member missing", req)
        for suf in REQUIRED_WHEEL_SUFFIX:
            if not any(n.endswith(suf) for n in names):
                add("FAIL", "required dist-info member missing", suf)
        if not any("dist-info/licenses/" in n and n.rsplit("/", 1)[-1].startswith("LICENSE") for n in names):
            add("FAIL", "licence file missing from dist-info/licenses")
    if kind == "sdist":
        for req in REQUIRED_SDIST:
            if req not in names:
                add("FAIL", "required sdist member missing", req)
        if not any(n.startswith("cqhecs/studio/static/qg.js") for n in names):
            add("FAIL", "required sdist member missing", "cqhecs/studio/static/qg.js")

    for n in sorted(names):
        for pat, label in FORBIDDEN_PATTERNS:
            if re.search(pat, n):
                add("FAIL", f"forbidden member ({label})", n)
        if kind == "wheel":
            for pat, label in FORBIDDEN_WHEEL_ONLY:
                if re.search(pat, n):
                    add("FAIL", f"forbidden member ({label})", n)

    markers = machine_markers(extra_markers)
    for n, data in members.items():
        if SCAN_EXEMPT.search(n):
            continue
        low = data.lower()
        for mk in markers:
            if mk in low:
                add("FAIL", "this build machine's path in content", f"{n}: {mk.decode('utf-8', 'replace')}")
                break
        binary = n.lower().endswith(BINARY_SUFFIX)
        # In a frozen-bundle directory only our own package is ours; third-party files there
        # (e.g. numpy's DELVEWHEEL record, scipy .pyd) carry their upstream authors' paths.
        first_party = kind != "dir" or n.startswith(("cqhecs/", "_internal/cqhecs/"))
        if not first_party:
            continue
        m = None if (binary and not n.startswith(("cqhecs/", "_internal/cqhecs/"))) else LOCAL_PATH.search(data)
        if m:
            add("FAIL", "developer-machine path in content", f"{n}: {m.group(0)[:60].decode('utf-8', 'replace')}")
        s = None if (binary and not n.startswith(("cqhecs/", "_internal/cqhecs/"))) else SECRETISH.search(data)
        if s:
            add("FAIL", "credential-shaped string in content", f"{n}: {s.group(0)[:12].decode('utf-8', 'replace')}...")

    fails = [f for f in findings if f["severity"] == "FAIL"]
    return {
        "artifact": path.name,
        "kind": kind,
        "status": "FAIL" if fails else "PASS",
        "members": len(names),
        "findings": findings,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artifacts", nargs="+", type=Path)
    ap.add_argument("--marker", action="append", default=[], help="extra machine-specific string to forbid")
    ap.add_argument("--json", dest="json_out", type=Path, default=None)
    a = ap.parse_args(argv)
    reports = [inspect(p, a.marker) for p in a.artifacts]
    for r in reports:
        print(f"[{r['status']}] {r['artifact']} ({r['kind']}, {r['members']} members)")
        for f in r["findings"]:  # type: ignore[union-attr]
            print(f"    {f['severity']}: {f['what']} {f.get('where', '')}")
    if a.json_out:
        a.json_out.write_text(json.dumps(reports, indent=2, sort_keys=True), encoding="utf-8")
    return 1 if any(r["status"] == "FAIL" for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
