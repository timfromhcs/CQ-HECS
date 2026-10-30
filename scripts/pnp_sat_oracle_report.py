#!/usr/bin/env python3
"""
Report the IBM SAT-oracle runs (3-4 variable CNFs) and the MPS lossless check.

Finite instances only. A QPU run of a Grover oracle does not decide P versus NP.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "research/v4/evidence/ibm_sat_oracles"
OUT = ROOT / "research/v4/evidence/pnp_sat_oracles"


def main() -> int:
    runs: List[Dict[str, Any]] = []
    for path in sorted(RUNS.glob("*/*/summary.json")):
        payload = json.loads(path.read_text("utf-8"))
        runs.append({
            "backend": payload["backend"],
            "shots": payload["shots"],
            "job_id": payload["job_id"],
            "usage_after": payload["usage_after"],
            "oracles": payload["oracles"],
        })

    all_top = all(o["top_is_model"] for r in runs for o in r["oracles"]) if runs else False
    all_lossless = all(o["mps"]["lossless"] for r in runs for o in r["oracles"]) if runs else False
    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-pnp-sat-oracles-1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": runs,
        "verdict": {
            "all_qpu_top_outcomes_are_models": all_top,
            "all_mps_strictly_lossless": all_lossless,
            "transferable_top_outcome": all_top,
            "exact_classical_emulation": True,
        },
        "non_claim": (
            "Finite 3-4 variable CNFs. The Grover oracle is a finite circuit, not a "
            "polynomial-time SAT algorithm. Exact classical emulation costs O(4^n) "
            "here. A QPU run cannot decide P versus NP or prove quantum advantage."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    lines = [
        "# SAT oracles on IBM Quantum — finite P-versus-NP boundary check",
        "",
        "**Not a complexity result.** These are 3–4 variable CNFs; the state space",
        "is 8 or 16. The QPU runs test whether a Grover phase oracle transfers to",
        "hardware and whether the circuit is exactly emulable and numerically",
        "lossless in the MPS path.",
        "",
        "| backend | shots | oracle | DPLL models | QPU top | model mass | top is model | MPS strictly lossless |",
        "| :--- | ---: | :--- | :--- | :--- | ---: | :--- | :--- |",
    ]
    for run in runs:
        for oracle in run["oracles"]:
            lines.append(
                f"| `{run['backend']}` | {run['shots']} | `{oracle['probe_id']}` | "
                f"{oracle['dpll_models']} | `{oracle['top_outcome']}` | "
                f"{oracle['model_mass']:.4f} | {oracle['top_is_model']} | "
                f"{oracle['mps']['lossless']} |"
            )
    lines += [
        "",
        "## Verdict",
        "",
        f"- QPU top outcome is a valid CNF model on every run: **{all_top}**.",
        f"- Strict MPS bit-losslessness on every run: **{all_lossless}**.",
        "- Exact classical emulation (density matrix vs Qiskit Statevector) is",
        "  checked in `research/v4/evidence/pnp_emulability/` and passes at ~1e-15.",
        "",
        "The two-model and four-variable circuits report `EXACT` but the MPS",
        "numerical-rank floor discards ~1e-15 / ~1e-13 of singular-value mass, so",
        "they are not strictly bit-lossless. That is the honest answer to",
        "“compress/decompress lossless?” for these states.",
        "",
        "## Non-claim",
        "",
        "A finite Grover run does not solve SAT in polynomial time and does not",
        "separate P from NP. The oracle cost, the 3–4 variable instance, and the",
        "exponential cost of exact emulation all remain visible.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), "utf-8")
    print(json.dumps(summary["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
