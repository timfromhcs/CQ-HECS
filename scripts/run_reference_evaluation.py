#!/usr/bin/env python3
"""
Reproduce the v3 W4 real-reference evaluation on the vendored ``r-io-5`` data.

The script never downloads anything and never edits the dataset. It verifies
every pinned SHA-256, runs the preregistered H-V3-1 evaluation, prints the
aggregate, and writes the complete result to ``research/v3/evidence``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cqhecs.reference import evaluate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(REPO_ROOT / "tests" / "data" / "quantum_noise_transfer"),
        help="directory holding the verified r-io-5 files",
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "research" / "v3" / "evidence" / "r_io_5_evaluation.json"),
        help="where to write the full JSON result",
    )
    parser.add_argument("--bootstrap", type=int, default=5000, help="bootstrap resamples")
    parser.add_argument("--seed", type=int, default=20261030, help="bootstrap seed")
    args = parser.parse_args(argv)

    result = evaluate(Path(args.data_dir), bootstrap_samples=args.bootstrap, seed=args.seed)
    payload = result.to_dict()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", "utf-8")

    aggregate = payload["aggregate"]
    print(f"dataset       : {payload['dataset_id']} {payload['dataset_sha256']}")
    print(f"unique circuits: {aggregate['n_circuits']}")
    print(f"median dTV    : {aggregate['median_delta_tv']:+.6f}")
    print(f"95% CI        : [{aggregate['ci95_low']:+.6f}, {aggregate['ci95_high']:+.6f}]")
    print(f"verdict       : {aggregate['verdict']}")
    exploratory = aggregate.get("exploratory_identifiable")
    if exploratory:
        print(
            "identifiable  : "
            f"n={exploratory['n']} median={exploratory['median_delta_tv']:+.6f} "
            f"CI=[{exploratory['ci95_low']:+.6f}, {exploratory['ci95_high']:+.6f}] "
            f"({exploratory['verdict']}, exploratory)"
        )
    print(f"wrote         : {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
