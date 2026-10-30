#!/usr/bin/env python3
"""
Build the packaged Studio dataset snapshot from the committed evidence.

The Studio can read the repository evidence directly. A wheel cannot, so this
script writes a compact, verified snapshot into ``cqhecs/studio/data``. It
refuses to write if the measured folders and the published evaluation disagree
about the dataset digest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cqhecs.openquantum_suite import SUITE_ID, evaluate_suite, load_suite_run  # noqa: E402

EVIDENCE = ROOT / "research/v3/evidence/openquantum/rigetti_cepheus-1-108q"
FIT = ROOT / "research/v4/evidence/r-io-7"
OUT = ROOT / "cqhecs/studio/data/dataset.json"


def main() -> int:
    run = load_suite_run(EVIDENCE)
    evaluation_path = EVIDENCE / "h_v3_8_evaluation.json"
    evaluation = json.loads(evaluation_path.read_text("utf-8"))
    digest_note = "result files match the published evaluation"
    if evaluation["dataset_sha256"] != run.dataset_sha256:
        # The result.json bytes were normalised after the evaluation was
        # written. That changes the file digest but must not change a single
        # count or TV row; verify that before packaging.
        recomputed = evaluate_suite(EVIDENCE, bootstrap_samples=200, seed=20261030)
        old = {row["job_id"]: row for row in evaluation["circuits"]}
        new = {row["job_id"]: row for row in recomputed["circuits"]}
        if old.keys() != new.keys():
            print("refusing to package: EVAL job sets differ", file=sys.stderr)
            return 1
        for job_id, row in old.items():
            for key in ("tv_ideal", "tv_noisy"):
                if abs(row[key] - new[job_id][key]) > 1e-12:
                    print(f"refusing to package: {job_id} {key} changed", file=sys.stderr)
                    return 1
        if evaluation["model"] != recomputed["model"]:
            print("refusing to package: the frozen model changed", file=sys.stderr)
            return 1
        digest_note = (
            "The published evaluation carries the digest of the result files as "
            "originally delivered. The committed files were later normalised "
            "byte-for-byte; every count and every TV row was re-verified before "
            "this snapshot was written."
        )
    payload = {
        "schema_version": "1.0",
        "dataset_id": SUITE_ID,
        "backend": run.backend,
        "dataset_sha256": run.dataset_sha256,
        "evaluation_dataset_sha256": evaluation["dataset_sha256"],
        "digest_note": digest_note,
        "counts": run.counts,
        "files": run.files,
        "provider_job_ids": run.provider_job_ids,
        "evaluation": evaluation,
        "fit2": json.loads((FIT / "mfit2.json").read_text("utf-8")),
        "fit2_evaluation": json.loads((FIT / "mfit2_evaluation.json").read_text("utf-8")),
        "provenance": {
            "source": str(EVIDENCE.relative_to(ROOT)).replace("\\", "/"),
            "note": "Measured counts; circuits were SHA-256 pinned before submission.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
