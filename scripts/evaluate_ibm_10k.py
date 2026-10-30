#!/usr/bin/env python3
"""
Evaluate the committed 10,000-shot IBM runs of the pinned ``r-io-7`` suite.

The counts were measured externally; this script never submits a job. For each
backend under ``research/v4/evidence/ibm_10k`` it runs the preregistered
H-V3-8 evaluation and the post-hoc M-FIT-2 comparison with the same bootstrap
seed as the 1k ``ibm_fez`` run, writes the three JSON files next to the counts,
and writes a cross-backend summary. A non-SUPPORTED verdict is published as is.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cqhecs.noise_fit import dump_profile, evaluate_exploratory  # noqa: E402
from cqhecs.openquantum_suite import evaluate_suite  # noqa: E402

BACKENDS = ("ibm_fez", "ibm_kingston", "ibm_marrakesh")


def _dump(payload) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def evaluate_backend(root: Path, bootstrap: int) -> dict:
    evaluation = evaluate_suite(root, bootstrap_samples=bootstrap)
    exploratory = evaluate_exploratory(root, bootstrap_samples=bootstrap)
    (root / "h_v3_8_evaluation.json").write_text(_dump(evaluation), "utf-8")
    (root / "m_fit_2_profile.json").write_text(dump_profile(exploratory["profile"]), "utf-8")
    (root / "m_fit_2_exploratory.json").write_text(_dump(exploratory), "utf-8")
    agg = evaluation["aggregate"]
    return {
        "backend": root.name,
        "h_v3_8": {
            "verdict": agg.get("verdict"),
            "median_delta_tv": agg.get("median_delta_tv"),
            "ci95_low": agg.get("ci95_low"),
            "ci95_high": agg.get("ci95_high"),
            "n_eval": agg.get("n_eval"),
            "n_noisy_better": agg.get("n_noisy_better"),
        },
        "m_fit_2": {
            "status": exploratory.get("status"),
            "vs_ideal": exploratory.get("vs_ideal"),
            "vs_m_fit": exploratory.get("vs_m_fit"),
            "anomalies": exploratory["profile"].get("anomalies", []),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT / "research" / "v4" / "evidence" / "ibm_10k"),
        help="directory holding one sub-folder per backend",
    )
    parser.add_argument("--bootstrap", type=int, default=5000, help="bootstrap resamples")
    args = parser.parse_args(argv)

    root = Path(args.root)
    rows = []
    for backend in BACKENDS:
        folder = root / backend
        if not folder.is_dir():
            print(f"{backend:14s}: missing, skipped")
            continue
        row = evaluate_backend(folder, args.bootstrap)
        rows.append(row)
        h = row["h_v3_8"]
        print(
            f"{backend:14s}: {h['verdict']} median dTV {h['median_delta_tv']:+.6f} "
            f"CI [{h['ci95_low']:+.6f}, {h['ci95_high']:+.6f}]"
        )
    summary = {
        "schema_version": "1.0",
        "suite": "r-io-7",
        "shots_per_circuit": 10000,
        "bootstrap_samples": args.bootstrap,
        "backends": rows,
        "note": (
            "External IBM measurements of the pinned 25-circuit suite. H-V3-8 is "
            "preregistered; M-FIT-2 is post-hoc. No retuning after the counts."
        ),
    }
    (root / "summary_evaluation.json").write_text(_dump(summary), "utf-8")
    print(f"wrote {root / 'summary_evaluation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
