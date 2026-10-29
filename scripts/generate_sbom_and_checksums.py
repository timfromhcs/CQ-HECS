"""
Release Artifact, Checksum, and SBOM Generator for CQ-HECS.
The version is derived from scripts/version.py, never hardcoded.
Generates:
- Python sdist and wheel packages in dist/
- SHA256 checksum file (dist/sha256sums.txt)
- SPDX 2.3 JSON Software Bill of Materials (dist/cqhecs-sbom.spdx.json)
- Updates audit/release_tracking.json with artifact provenance
"""

import sys
import json
import re
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
AUDIT_FILE = ROOT_DIR / "audit" / "release_tracking.json"


def get_git_head_sha() -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else "UNKNOWN"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_distribution():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/4] Building wheel and source distribution...")
    # One canonical builder: `python -m build` produces both the wheel and the
    # sdist from pyproject.toml; setup.py no longer exists as a separate path.
    for entry in ("build", "wheel", "setuptools"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", entry],
            check=True,
        )
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(DIST_DIR)],
        check=True,
        cwd=ROOT_DIR,
    )


def generate_checksums() -> dict:
    print("[3/4] Generating SHA256 checksums...")
    checksums = {}
    lines = []
    # Every published asset gets a hash, including the SBOM and the release
    # notes; only the checksum file itself is excluded (it cannot hash itself).
    for f in sorted(DIST_DIR.iterdir()):
        if not f.is_file() or f.name == "sha256sums.txt":
            continue
        digest = sha256_file(f)
        checksums[f.name] = digest
        lines.append(f"{digest}  {f.name}")
        print(f"  {f.name}: {digest}")

    sums_path = DIST_DIR / "sha256sums.txt"
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    checksums["sha256sums.txt"] = sha256_file(sums_path)
    return checksums


def _dependency_floors() -> list:
    """Reads the actual dependency floors from pyproject.toml, so the SBOM
    cannot drift from the real packaging metadata (e.g. an older NumPy
    minimum)."""
    raw = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    deps_section = re.search(
        r"^dependencies\s*=\s*\[(.*?)^\]", raw, re.MULTILINE | re.DOTALL
    )
    if not deps_section:
        return []
    floors = []
    for spec in re.findall(r'"([^"]+)"', deps_section.group(1)):
        name = spec.split(">")[0].split("<")[0].split("=")[0].strip()
        floor_match = re.search(r">=?\s*([0-9][^\",]+)", spec)
        floors.append((name, floor_match.group(1).strip() if floor_match else "any"))
    return floors


def generate_spdx_sbom(commit_sha: str) -> dict:
    print("[2/4] Generating SPDX 2.3 JSON SBOM...")
    now_iso = datetime.now(timezone.utc).isoformat()
    # The version comes from the single source of truth, never hardcoded here.
    from version import VERSION as RELEASE_VERSION
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"CQ-HECS-v{RELEASE_VERSION}-SBOM",
        "documentNamespace": (
            f"https://github.com/timfromhcs/CQ-HECS/spdxdocs/"
            f"cqhecs-v{RELEASE_VERSION}-{commit_sha[:8]}"
        ),
        "creationInfo": {
            "created": now_iso,
            "creators": [
                "Tool: CQ-HECS Provenance Generator v1.0",
                "Organization: timfromhcs"
            ]
        },
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-CQ-HECS",
                "name": "cqhecs",
                "versionInfo": RELEASE_VERSION,
                "downloadLocation": (
                    "https://github.com/timfromhcs/CQ-HECS/releases/tag/"
                    f"v{RELEASE_VERSION}"
                ),
                "filesAnalyzed": False,
                "homepage": "https://github.com/timfromhcs/CQ-HECS",
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "copyrightText": "Copyright (c) 2026 timfromhcs",
                "description": "CQ-HECS: Classical Four-Path Quantum Circuit Simulation Engine",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/cqhecs@{RELEASE_VERSION}"
                    },
                    {
                        "referenceCategory": "OTHER",
                        "referenceType": "git-commit",
                        "referenceLocator": commit_sha
                    }
                ]
            }
        ]
    }
    # Runtime dependency entries derive from pyproject.toml rather than
    # hand-maintained copies that can silently disagree.
    licenses = {"numpy": "BSD-3-Clause", "qiskit": "Apache-2.0"}
    for name, floor in _dependency_floors():
        sbom["packages"].append({
            "SPDXID": f"SPDXRef-Package-{name.capitalize()}",
            "name": name,
            "versionInfo": floor,
            "downloadLocation": f"https://pypi.org/project/{name}/",
            "licenseConcluded": licenses.get(name),
        })

    sbom_path = DIST_DIR / "cqhecs-sbom.spdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
    return sbom


def update_audit_tracking(commit_sha: str, checksums: dict):
    print("[4/4] Updating audit/release_tracking.json...")
    if not AUDIT_FILE.exists():
        data = {}
    else:
        data = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))

    data["release_artifacts"] = {
        "dist_directory": str(DIST_DIR.relative_to(ROOT_DIR)),
        "commit_sha": commit_sha,
        "checksums": checksums,
        "sbom_file": "dist/cqhecs-sbom.spdx.json"
    }

    AUDIT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Release artifacts and audit tracking updated successfully.")


def main():
    head_sha = get_git_head_sha()
    build_distribution()
    # The SBOM is a published asset, so it must exist before hashing.
    generate_spdx_sbom(head_sha)
    checksums = generate_checksums()
    update_audit_tracking(head_sha, checksums)


if __name__ == "__main__":
    main()
