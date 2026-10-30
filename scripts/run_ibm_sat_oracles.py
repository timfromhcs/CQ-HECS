#!/usr/bin/env python3
"""
SAT/oracle probes for the P-versus-NP boundary on real IBM hardware.

Three 3-4 variable CNFs are encoded as Grover phase oracles:

* one unique 3-variable model (`100`);
* two 3-variable models (`100`, `011`) with an oracle that marks both;
* one unique 4-variable model (`1011`).

The run reports the QPU's success probability, the DPLL model, and the exact
classical emulation check. It does **not** decide P versus NP: these are 8-16
state spaces, and the oracle is a finite circuit.

The lossless-simulation question is checked locally: the Path C MPS result must
report full numerical rank and zero discarded singular-value mass.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from cqhecs.sat import parse_dimacs, solve  # noqa: E402
from run_ibm_universal_probes import (  # noqa: E402
    Probe,
    _decompose,
    _exact,
    _grover_diffusion,
    _grover_oracle,
    _pick_chain,
    _qiskit,
    _token,
    _tv,
)


def _grover_multi(n: int, targets: Sequence[str], iterations: int) -> List[Tuple[str, Tuple[int, ...], Tuple[float, ...]]]:
    gates = [("h", (q,), ()) for q in range(n)]
    for _ in range(iterations):
        for target in targets:
            gates += _grover_oracle(n, target)
        gates += _grover_diffusion(n)
    return gates


def _cnf_two_3() -> str:
    return "p cnf 3 6\n3 2 1 0\n3 2 -1 0\n3 -2 1 0\n-3 2 -1 0\n-3 -2 1 0\n-3 -2 -1 0\n"


def _cnf_unique_4(target: str = "1011") -> str:
    clauses = []
    for value in range(16):
        bits = format(value, "04b")
        if bits == target:
            continue
        clause = []
        for index, bit in enumerate(bits):
            # bits is q3..q0; DIMACS variable 1 is q0, variable 4 is q3.
            variable = 4 - index
            clause.append(-variable if bit == "1" else variable)
        clauses.append(" ".join(str(x) for x in clause) + " 0")
    return "p cnf 4 15\n" + "\n".join(clauses) + "\n"


def probes() -> List[Probe]:
    raw = [
        Probe(
            "sat3_unique_100",
            "sat",
            3,
            tuple(_grover_multi(3, ["100"], 2)),
            "unique 3-variable CNF model 100",
            "p cnf 3 7\n3 2 1 0\n3 2 -1 0\n3 -2 1 0\n3 -2 -1 0\n-3 2 -1 0\n-3 -2 1 0\n-3 -2 -1 0\n",
        ),
        Probe(
            "sat3_two_100_011",
            "sat",
            3,
            tuple(_grover_multi(3, ["100", "011"], 1)),
            "two 3-variable CNF models 100 and 011",
            _cnf_two_3(),
        ),
        Probe(
            "sat4_unique_1011",
            "sat",
            4,
            tuple(_grover_multi(4, ["1011"], 3)),
            "unique 4-variable CNF model 1011",
            _cnf_unique_4("1011"),
        ),
    ]
    return [_decompose(probe) for probe in raw]


def _mps_lossless(probe: Probe) -> Dict[str, Any]:
    from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend

    result = PathCMPSExactBackend().execute(probe.instructions(), shots=64, seed=0)
    meta = result.metadata
    return {
        "state": result.state.value,
        "max_observed_chi": meta.get("max_observed_chi"),
        "discarded_singular_value_sum": meta.get("discarded_singular_value_sum"),
        "numerical_rank_truncation_applied": meta.get("numerical_rank_truncation_applied"),
        "bond_dimension_truncation_applied": meta.get("bond_dimension_truncation_applied"),
        "lossless": bool(
            meta.get("discarded_singular_value_sum") == 0.0
            and meta.get("numerical_rank_truncation_applied") is False
            and meta.get("bond_dimension_truncation_applied") is False
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="ibm_marrakesh")
    parser.add_argument("--shots", type=int, default=10000)
    parser.add_argument("--config", default=str(ROOT / "apikey.json"))
    parser.add_argument("--out", default=str(ROOT / "research/v4/evidence/ibm_sat_oracles"))
    args = parser.parse_args(argv)

    from qiskit import transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    key = _token(Path(args.config))
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=key)
    usage_before = service.usage()
    backend = service.backend(args.backend)
    chain = _pick_chain(backend, 4)
    items = probes()
    circuits = [
        transpile(
            _qiskit(probe),
            backend=backend,
            initial_layout=chain[: probe.num_qubits],
            optimization_level=1,
            seed_transpiler=20261030,
        )
        for probe in items
    ]
    print(f"backend={backend.name} pending={backend.status().pending_jobs} chain={chain}")
    print(f"probes={len(circuits)} shots={args.shots} remaining={usage_before['usage_remaining_seconds']}")
    sampler = SamplerV2(mode=backend)
    job = sampler.run([(circuit,) for circuit in circuits], shots=args.shots)
    print(f"submitted job_id={job.job_id()}")
    result = job.result()
    usage_after = service.usage()

    out_root = Path(args.out) / backend.name.replace("-", "_") / f"{args.shots}"
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, probe in enumerate(items):
        data = result[index].data
        field = list(data.keys())[0]
        counts = {str(k).replace(" ", ""): int(v) for k, v in data[field].get_counts().items()}
        exact = _exact(probe)
        cnf = parse_dimacs(probe.cnf)
        solved = solve(cnf, timeout_seconds=5.0)
        models = []
        from itertools import product

        for values in product((False, True), repeat=probe.num_qubits):
            assignment = {q + 1: v for q, v in enumerate(values)}
            if cnf.is_satisfied(assignment):
                models.append("".join("1" if assignment[q] else "0" for q in range(probe.num_qubits, 0, -1)))
        top = max(counts.items(), key=lambda kv: kv[1])[0]
        mass = sum(counts.get(model, 0) for model in models) / sum(counts.values())
        rows.append({
            "probe_id": probe.probe_id,
            "probe_family": probe.family,
            "num_qubits": probe.num_qubits,
            "shots": args.shots,
            "job_id": job.job_id(),
            "cnf": probe.cnf,
            "dpll_status": solved.status,
            "dpll_models": models,
            "top_outcome": top,
            "top_is_model": top in models,
            "model_mass": mass,
            "tv_ideal": _tv(counts, exact),
            "counts": counts,
            "mps": _mps_lossless(probe),
        })
        print(probe.probe_id, "top", top, "models", models, "mass", round(mass, 4), "mps_lossless", rows[-1]["mps"]["lossless"])

    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-ibm-sat-oracles-1",
        "backend": backend.name,
        "shots": args.shots,
        "job_id": job.job_id(),
        "fixed_chain": chain,
        "usage_before": usage_before,
        "usage_after": usage_after,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "oracles": rows,
        "non_claim": (
            "Finite 3-4 variable SAT instances. A QPU run cannot decide P versus NP; "
            "the Grover oracle is not a polynomial-time SAT algorithm. The MPS "
            "lossless field is a numerical-rank check for these small circuits only."
        ),
    }
    (out_root / "summary.json").write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(f"wrote {out_root}")
    print(f"remaining={usage_after['usage_remaining_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
