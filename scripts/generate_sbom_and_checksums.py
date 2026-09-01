"""
Release Artifact, Checksum, and SBOM Generator for CQ-HECS v0.1.0.
Generates:
- Python sdist and wheel packages in dist/
- SHA256 checksum file (dist/sha256sums.txt)
- SPDX 2.3 JSON Software Bill of Materials (dist/cqhecs-sbom.spdx.json)
- Updates audit/release_tracking.json with artifact provenance
"""

import os
import sys
import json
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
    cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(DIST_DIR), str(ROOT_DIR)]
    subprocess.run(cmd, check=True)

    # Also build sdist via setup.py
    cmd_sdist = [sys.executable, "setup.py", "sdist", "--dist-dir", str(DIST_DIR)]
    subprocess.run(cmd_sdist, check=True, cwd=ROOT_DIR)


def generate_checksums() -> dict:
    print("[2/4] Generating SHA256 checksums...")
    checksums = {}
    lines = []
    for f in sorted(DIST_DIR.iterdir()):
        if f.is_file() and not f.name.endswith(".txt") and not f.name.endswith(".json"):
            digest = sha256_file(f)
            checksums[f.name] = digest
            lines.append(f"{digest}  {f.name}")
            print(f"  {f.name}: {digest}")

    sums_path = DIST_DIR / "sha256sums.txt"
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    checksums["sha256sums.txt"] = sha256_file(sums_path)
    return checksums


def generate_spdx_sbom(commit_sha: str) -> dict:
    print("[3/4] Generating SPDX 2.3 JSON SBOM...")
    now_iso = datetime.now(timezone.utc).isoformat()
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "CQ-HECS-v0.1.0-SBOM",
        "documentNamespace": f"https://github.com/timfromhcs/CQ-HECS/spdxdocs/cqhecs-v0.1.0-{commit_sha[:8]}",
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
                "versionInfo": "0.1.0",
                "downloadLocation": "https://github.com/timfromhcs/CQ-HECS/releases/tag/v0.1.0",
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
                        "referenceLocator": "pkg:pypi/cqhecs@0.1.0"
                    },
                    {
                        "referenceCategory": "OTHER",
                        "referenceType": "git-commit",
                        "referenceLocator": commit_sha
                    }
                ]
            },
            {
                "SPDXID": "SPDXRef-Package-NumPy",
                "name": "numpy",
                "versionInfo": ">=1.20",
                "downloadLocation": "https://pypi.org/project/numpy/",
                "licenseConcluded": "BSD-3-Clause"
            },
            {
                "SPDXID": "SPDXRef-Package-Qiskit",
                "name": "qiskit",
                "versionInfo": ">=1.1.0",
                "downloadLocation": "https://pypi.org/project/qiskit/",
                "licenseConcluded": "Apache-2.0"
            }
        ]
    }

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
    checksums = generate_checksums()
    generate_spdx_sbom(head_sha)
    update_audit_tracking(head_sha, checksums)


if __name__ == "__main__":
    main()
