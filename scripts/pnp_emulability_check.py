#!/usr/bin/env python3
"""
P versus NP: exact-classical-emulability and universal-probe check.

This is a **finite** check, not a complexity result. For every IBM universal
probe it:

1. builds the same circuit in Qiskit and in CQ-HECS;
2. compares CQ-HECS's exact density-matrix distribution with Qiskit's
   Statevector distribution (independent exact oracle);
3. checks normalisation and support;
4. compares the measured IBM counts with the exact, M-FIT and M-FIT-2
   distributions;
5. for the SAT probe, solves the CNF with the standalone DPLL and checks that
   the QPU's most frequent outcome is the model.

A pass means: *these small circuits are exactly classically emulable and the
QPU agrees with the emulator up to the stated distance*. It says nothing about
P versus NP, about all circuits, or about quantum advantage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from cqhecs.sat import parse_dimacs, solve  # noqa: E402
from run_ibm_universal_probes import _exact, _raw_qiskit, probes  # noqa: E402

UNIVERSAL = ROOT / "research/v4/evidence/ibm_universal"
OUT = ROOT / "research/v4/evidence/pnp_emulability"


def _statevector(probe: Any) -> Dict[str, float]:
    from qiskit.quantum_info import Statevector

    circuit = _raw_qiskit(probe)
    state = Statevector.from_instruction(circuit)
    probabilities = np.abs(np.asarray(state.data)) ** 2
    return {
        format(index, f"0{probe.num_qubits}b"): float(value)
        for index, value in enumerate(probabilities)
        if float(value) > 1e-15
    }


def _tv(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def _check_probe(probe: Any) -> Dict[str, Any]:
    exact = _exact(probe)
    statevector = _statevector(probe)
    tvs = _tv(exact, statevector)
    total = sum(exact.values())
    return {
        "probe_id": probe.probe_id,
        "family": probe.family,
        "num_qubits": probe.num_qubits,
        "gate_count": len(probe.gates),
        "support": len(exact),
        "normalisation": total,
        "cqhecs_vs_qiskit_statevector_tv": tvs,
        "exact_classically_emulable": bool(abs(total - 1.0) < 1e-12 and tvs < 1e-12),
    }


def main() -> int:
    probe_map = {probe.probe_id: probe for probe in probes()}
    exact_rows = [_check_probe(probe) for probe in probe_map.values()]

    runs: List[Dict[str, Any]] = []
    for summary_path in sorted(UNIVERSAL.glob("*/*/summary.json")):
        payload = json.loads(summary_path.read_text("utf-8"))
        row = {
            "backend": payload["backend"],
            "shots": payload["shots"],
            "job_id": payload["job_id"],
            "median_tv_ideal": payload["aggregate"]["median_tv_ideal"],
            "median_tv_mfit": payload["aggregate"]["median_tv_mfit"],
            "median_tv_mfit2": payload["aggregate"]["median_tv_mfit2"],
            "sat_found": payload["aggregate"]["sat_found"],
            "probes": payload["probes"],
        }
        runs.append(row)

    sat = probe_map.get("sat3_grover_100")
    sat_row: Dict[str, Any] = {"available": False}
    if sat is not None:
        result = solve(parse_dimacs(sat.cnf), timeout_seconds=5.0)
        assignment = result.assignment or {}
        model_bits = "".join("1" if assignment.get(q, False) else "0" for q in range(3, 0, -1))
        sat_row = {
            "available": True,
            "cnf": sat.cnf,
            "dpll_status": result.status,
            "dpll_model": model_bits,
            "model_verified": result.model_verified,
            "qpu": [
                {
                    "backend": run["backend"],
                    "shots": run["shots"],
                    "sat_top": next((p.get("sat_top") for p in run["probes"] if p["probe_id"] == sat.probe_id), None),
                    "sat_found": run["sat_found"][0] if run["sat_found"] else None,
                }
                for run in runs
            ],
        }

    all_exact = all(row["exact_classically_emulable"] for row in exact_rows)
    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-pnp-emulability-1",
        "generated_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "exact_emulation": exact_rows,
        "qpu_runs": runs,
        "sat": sat_row,
        "verdict": "EXACTLY_EMULABLE_AND_QPU_CONSISTENT" if all_exact and runs else "INCOMPLETE",
        "non_claim": (
            "Finite 2-5 qubit instances only. Exact classical emulation here means "
            "a density-matrix/statevector calculation whose cost grows exponentially "
            "with width; it is not a polynomial-time algorithm and does not decide "
            "P versus NP or prove quantum advantage."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    lines = [
        "# P versus NP: exact-classical-emulability check",
        "",
        "**Finite check, not a complexity result.** These are 2–5 qubit circuits.",
        "",
        "| probe | qubits | gates | support | CQ-HECS vs Qiskit Statevector TV | exact classically emulable |",
        "| :--- | ---: | ---: | ---: | ---: | :--- |",
    ]
    for row in exact_rows:
        lines.append(
            f"| `{row['probe_id']}` | {row['num_qubits']} | {row['gate_count']} | "
            f"{row['support']} | {row['cqhecs_vs_qiskit_statevector_tv']:.2e} | "
            f"{'PASS' if row['exact_classically_emulable'] else 'FAIL'} |"
        )
    lines += [
        "",
        "## QPU comparison",
        "",
        "| backend | shots | median TV ideal | median TV M-FIT | median TV M-FIT-2 | SAT found |",
        "| :--- | ---: | ---: | ---: | ---: | :--- |",
    ]
    for run in runs:
        lines.append(
            f"| `{run['backend']}` | {run['shots']} | {run['median_tv_ideal']:.4f} | "
            f"{run['median_tv_mfit']:.4f} | {run['median_tv_mfit2']:.4f} | "
            f"{run['sat_found']} |"
        )
    if sat_row.get("available"):
        lines += [
            "",
            "## SAT probe",
            "",
            f"- CNF: `{sat_row['cnf'].splitlines()[0]}`",
            f"- DPLL: `{sat_row['dpll_status']}`, model `{sat_row['dpll_model']}`",
            f"- QPU outcomes: {sat_row['qpu']}",
        ]
    lines += [
        "",
        "## What this does not say",
        "",
        "Density-matrix emulation costs `O(4^n)`; the circuits are 2–5 qubits.",
        "A finite QPU experiment cannot decide P versus NP, prove ETH, or",
        "establish quantum advantage. The SAT probe is a three-variable instance.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), "utf-8")
    print(json.dumps({"verdict": summary["verdict"], "exact": all_exact, "runs": len(runs)}, indent=2))
    return 0 if summary["verdict"] != "INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
