#!/usr/bin/env python3
"""
Extract device noise profiles from the committed real-QPU evidence.

For every backend that ran the pinned r-io-7 suite, read the fitted M-FIT-2
profile (per-qubit readout p01/p10, X-gate bit-flip, readout-corrected CX
depolarizing) plus its measured validation (H-V3-8 and M-FIT-2 vs ideal), and
write one JSON that the Python package, the Studio, the executable and the web
emulator all load. Nothing is fitted here: the numbers come straight from the
evaluation files, so a profile is exactly as good as its evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCES = (
    # id, vendor, label, shots per circuit, evidence folder
    ("rigetti_cepheus", "Rigetti", "Rigetti Cepheus-1-108Q", 1000,
     "research/v3/evidence/openquantum/rigetti_cepheus-1-108q"),
    ("ibm_fez", "IBM", "IBM ibm_fez (Heron)", 10000, "research/v4/evidence/ibm_10k/ibm_fez"),
    ("ibm_kingston", "IBM", "IBM ibm_kingston (Heron)", 10000, "research/v4/evidence/ibm_10k/ibm_kingston"),
    ("ibm_marrakesh", "IBM", "IBM ibm_marrakesh (Heron)", 10000, "research/v4/evidence/ibm_10k/ibm_marrakesh"),
    ("iqm_garnet", "IQM", "IQM Garnet", 500, "research/v3/evidence/openquantum/iqm_garnet"),
)

OUTPUTS = (
    REPO_ROOT / "cqhecs" / "studio" / "data" / "device_profiles.json",
    REPO_ROOT / "web" / "public" / "device_profiles.json",
)


def _load(path: Path):
    return json.loads(path.read_text("utf-8"))


def extract(profile_id: str, vendor: str, label: str, shots: int, folder: Path) -> dict | None:
    needed = ("m_fit_2_profile.json", "m_fit_2_exploratory.json", "h_v3_8_evaluation.json")
    if not all((folder / name).is_file() for name in needed):
        return None
    profile = _load(folder / "m_fit_2_profile.json")
    exploratory = _load(folder / "m_fit_2_exploratory.json")
    evaluation = _load(folder / "h_v3_8_evaluation.json")
    readout = sorted(profile["readout"], key=lambda r: r["qubit"])
    agg = evaluation["aggregate"]
    return {
        "id": profile_id,
        "vendor": vendor,
        "label": label,
        "backend": evaluation.get("backend") or profile["provenance"].get("backend"),
        "dataset_id": profile["provenance"].get("dataset_id"),
        "dataset_sha256": profile["provenance"].get("dataset_sha256"),
        "shots_per_circuit": shots,
        "measured_qubits": len(readout),
        "p01": [round(float(r["p01"]), 6) for r in readout],
        "p10": [round(float(r["p10"]), 6) for r in readout],
        "x_bitflip": [round(float(r.get("x_bitflip", 0.0)), 6) for r in readout],
        "cx_depolarizing": float(profile["cx_depolarizing"]["readout_corrected"]),
        "anomalies": profile.get("anomalies", []),
        "validation": {
            "h_v3_8": agg.get("verdict"),
            "median_delta_tv_m_fit": agg.get("median_delta_tv"),
            "ci95": [agg.get("ci95_low"), agg.get("ci95_high")],
            "m_fit_2_vs_ideal_median": exploratory["vs_ideal"]["median"],
            "m_fit_2_vs_ideal_ci95": [exploratory["vs_ideal"]["ci95_low"], exploratory["vs_ideal"]["ci95_high"]],
            "n_eval": exploratory["vs_ideal"]["n"],
            "status": exploratory.get("status"),
        },
        "evidence": str(folder.relative_to(REPO_ROOT)).replace("\\", "/"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed files are stale")
    args = parser.parse_args(argv)
    profiles = []
    for profile_id, vendor, label, shots, rel in SOURCES:
        entry = extract(profile_id, vendor, label, shots, REPO_ROOT / rel)
        if entry is None:
            print(f"{profile_id:16s}: evidence incomplete, skipped", file=sys.stderr)
            continue
        profiles.append(entry)
        print(f"{profile_id:16s}: cx={entry['cx_depolarizing']:.4f} "
              f"p01={entry['p01']} p10={entry['p10']} H-V3-8={entry['validation']['h_v3_8']}")
    document = {
        "schema": "cqhecs.device_profiles/1.0",
        "model": "M-FIT-2 (per-qubit readout, X bit-flip, 2-qubit depolarizing after CX)",
        "note": (
            "Fitted from external QPU measurements of the pinned r-io-7 suite. Qubits beyond "
            "the measured ones reuse the mean measured readout; that extrapolation is an "
            "assumption, not a measurement. M-FIT-2 is post-hoc."
        ),
        "profiles": profiles,
    }
    text = json.dumps(document, indent=2) + "\n"
    stale = False
    for target in OUTPUTS:
        if args.check:
            stale |= not target.is_file() or target.read_text("utf-8") != text
        else:
            target.write_text(text, "utf-8")
    if args.check and stale:
        print("device_profiles.json is stale; run scripts/export_device_profiles.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
