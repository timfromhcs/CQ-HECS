"""Build web/src/qg_snapshot.json from the committed research/qg_2026 evidence (read-only).

The web app cannot read the repository at run time, so the Evidence Ledger shows a snapshot
generated here. The snapshot is deterministic (no timestamps), carries the LF-normalised
SHA-256 of every source file, and is checked for drift by tests/test_quantum_gravity_studio_web.py.
It never reads research/qg_2026/raw or JOB_LEDGER.jsonl.

    python web/tests/qg_make_snapshot.py [--check]
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QG = ROOT / "research" / "qg_2026"
OUT = ROOT / "web" / "src" / "qg_snapshot.json"
ORACLE_OUT = ROOT / "web" / "tests" / "fixtures" / "qg_oracle.json"
SOURCES = [
    "MODEL_MANIFEST.json",
    "QUOTE_LEDGER.json",
    "qasm/CIRCUIT_MANIFEST.json",
    "processed/bmv_phase_scan.json",
    "processed/bmv_qpu_analysis.json",
    "processed/bmv_xx_trend.json",
    "processed/final_analysis.json",
    "processed/qpu_smoke_analysis.json",
    "processed/syk_qpu_analysis.json",
    "processed/syk_qpu_v3_analysis.json",
]
THETAS = [0.0, math.pi / 8, math.pi / 4, 3 * math.pi / 8, math.pi / 2, 0.1, 1.0, -0.5, math.pi]


def lf_sha(path: Path) -> tuple[str, int]:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest(), len(data)


def load(rel: str):
    return json.loads((QG / rel).read_text(encoding="utf-8"))


def build() -> tuple[dict, list]:
    sys.path.insert(0, str(ROOT))
    from cqhecs.quantum_gravity import catalog
    from cqhecs.quantum_gravity.circuits import bmv_qasm, sha256_text
    from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel

    cat = catalog()
    methods = [
        {k: m[k] for k in ("method_id", "title", "track", "surface", "assumptions", "observables",
                           "established", "cannot_establish", "references", "status") if k in m}
        for m in cat["methods"]
    ]
    files = []
    for rel in SOURCES:
        sha, size = lf_sha(QG / rel)
        files.append({"path": f"research/qg_2026/{rel}", "sha256": sha, "bytes": size})

    scan = load("processed/bmv_phase_scan.json")
    xx = load("processed/bmv_xx_trend.json")
    smoke = load("processed/qpu_smoke_analysis.json")
    syk3 = load("processed/syk_qpu_v3_analysis.json")
    final = load("processed/final_analysis.json")

    oracle = []
    for theta in THETAS:
        model = BMVEffectivePhaseModel(theta=theta)
        qasm = bmv_qasm(theta)
        oracle.append({
            "theta": theta,
            "concurrence": model.concurrence(),
            "negativity": model.negativity(),
            "entropy_bits": model.entropy(),
            "chsh_max": model.chsh_max(),
            "qasm_sha256": sha256_text(qasm),
            "qasm": qasm,
        })
    return {
        "schema": "cqhecs.web.qg_snapshot.v1",
        "campaign": cat["campaign_default"],
        "sha_policy": "sha256 of the file bytes with CRLF normalised to LF",
        "execution_surfaces": cat["execution_surfaces"],
        "tracks": cat["tracks"],
        "methods": methods,
        "files": files,
        "backend": scan["backend"],
        "bmv_scan": [
            {k: p[k] for k in ("basis", "circuit_id", "theta", "correlator", "std_err", "expected_sin", "shots")}
            for p in scan["points"]
        ],
        "bmv_xx": [
            {k: p[k] for k in ("theta", "xx", "ci95", "shots", "source")} for p in xx["points"]
        ],
        "smoke": [
            {"circuit_id": cid, "in_support_fraction": v["in_support_fraction"], "shots": v["shots"],
             "ideal_support": v["ideal_support"]}
            for cid, v in smoke["circuits"].items()
        ],
        "syk_v3": [
            {k: c[k] for k in ("circuit_id", "p000", "ci95", "ideal_p000", "uniform", "shots")}
            for c in syk3["circuits"]
        ],
        "syk_missing": [
            c["circuit_id"] for c in final["sections"].get("syk_v4", []) if c.get("status") == "missing"
        ],
    }, oracle


def render() -> tuple[str, str]:
    snap, oracle = build()
    def dump(obj: object) -> str:
        return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True) + "\n"

    return dump(snap), dump({"schema": "cqhecs.web.qg_oracle.v1", "points": oracle})


def main() -> int:
    snap_text, oracle_text = render()
    if "--check" in sys.argv:
        ok = (OUT.exists() and OUT.read_text(encoding="utf-8") == snap_text
              and ORACLE_OUT.exists() and ORACLE_OUT.read_text(encoding="utf-8") == oracle_text)
        return 0 if ok else 1
    OUT.write_text(snap_text, encoding="utf-8", newline="\n")
    ORACLE_OUT.write_text(oracle_text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(snap_text)} bytes) and {ORACLE_OUT} ({len(oracle_text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
