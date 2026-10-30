#!/usr/bin/env python3
"""
Run the pinned r-io-7 circuits on IBM Quantum and save them as a fresh dataset.

This is an **external** real-QPU run, not an execution by the ``cqhecs``
package. It uses the same 25 SHA-256-pinned circuits as ``r-io-7``, a fixed
5-qubit physical chain (so logical qubit q maps to the same physical qubit in
every job), 1000 shots, and the IBM Runtime Sampler.

Usage:
    python scripts/run_ibm_suite.py --mode pilot
    python scripts/run_ibm_suite.py --mode full

The API key is read from ``apikey.json`` (``{"apikey": "..."}``) or
``QISKIT_IBM_TOKEN``. It is never printed, logged or written to the evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cqhecs.openquantum_suite import DEFAULT_SHOTS, build_suite  # noqa: E402

DEFAULT_OUT = ROOT / "research/v4/evidence/ibm"
PILOT_JOBS = ("OQ-01", "OQ-02", "OQ-03", "OQ-09")


def _token(path: Path) -> str:
    if os.environ.get("QISKIT_IBM_TOKEN"):
        return os.environ["QISKIT_IBM_TOKEN"]
    payload = json.loads(path.read_text("utf-8"))
    token = payload.get("apikey") or payload.get("token") or payload.get("key")
    if not token:
        raise ValueError(f"{path} has no apikey/token field")
    return str(token)


def _path_readout(backend: Any, path: Sequence[int]) -> float:
    try:
        props = backend.properties()
    except Exception:  # noqa: BLE001
        return 0.0
    total = 0.0
    for q in path:
        try:
            total += float(props.readout_error(q))
        except Exception:  # noqa: BLE001
            pass
    return total


def _pick_chain(backend: Any, length: int = 5) -> List[int]:
    """Shortest connected physical chain with the lowest summed readout error."""
    edges = backend.coupling_map.get_edges()
    adjacency: Dict[int, List[int]] = {}
    for a, b in edges:
        adjacency.setdefault(int(a), []).append(int(b))
        adjacency.setdefault(int(b), []).append(int(a))
    best: Optional[List[int]] = None
    best_score = float("inf")
    for start in sorted(adjacency):
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            if len(path) == length:
                score = _path_readout(backend, path)
                if score < best_score:
                    best, best_score = path, score
                continue
            for neighbour in adjacency.get(node, []):
                if neighbour not in path:
                    stack.append((neighbour, path + [neighbour]))
    if best is None:
        raise RuntimeError(f"{backend.name}: no connected {length}-qubit chain")
    return best


def _counts_from_pub(pub_result: Any) -> Dict[str, int]:
    data = pub_result.data
    keys = list(data.keys())
    if not keys:
        raise RuntimeError("Sampler result has no data fields")
    counts = data[keys[0]].get_counts()
    return {str(key).replace(" ", ""): int(value) for key, value in counts.items()}


def qiskit_circuit(job: Any) -> Any:
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(job.num_qubits, job.num_qubits)
    for name, qubits, params in job.gates:
        method = getattr(qc, name)
        if params:
            method(*params, *qubits)
        else:
            method(*qubits)
    qc.measure(list(range(job.num_qubits)), list(range(job.num_qubits)))
    return qc


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--shots", type=int, default=DEFAULT_SHOTS)
    parser.add_argument("--backend", default=None, help="IBM backend name (default: least busy)")
    parser.add_argument("--config", default=str(ROOT / "apikey.json"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--dry-run", action="store_true", help="Transpile only; submit nothing")
    args = parser.parse_args(argv)

    from qiskit import qasm2, transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    token = _token(Path(args.config))
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token)
    usage_before = service.usage()
    backend = (
        service.backend(args.backend)
        if args.backend
        else service.least_busy(operational=True, simulator=False, min_num_qubits=5)
    )
    chain = _pick_chain(backend, 5)
    print(f"backend={backend.name} qubits={backend.num_qubits} pending={backend.status().pending_jobs}")
    print(f"fixed chain={chain} readout_sum={_path_readout(backend, chain):.6f}")
    print(f"usage_remaining_seconds={usage_before.get('usage_remaining_seconds')}")

    jobs = build_suite()
    selected = [job for job in jobs if args.mode == "full" or job.job_id in PILOT_JOBS]
    circuits = []
    metadata = []
    for job in selected:
        # Build from the gate list, not the QASM text: Qiskit's OpenQASM 2
        # parser does not define ``sx``, which the pinned suite uses.
        qc = qiskit_circuit(job)
        transpiled = transpile(
            qc,
            backend=backend,
            initial_layout=chain[: job.num_qubits],
            optimization_level=1,
            seed_transpiler=20261030,
        )
        circuits.append(transpiled)
        metadata.append(
            {
                "job_id": job.job_id,
                "name": job.name,
                "num_qubits": job.num_qubits,
                "qasm_sha256": job.sha256,
                "transpiled_qasm_sha256": hashlib.sha256(
                    qasm2.dumps(transpiled).encode("ascii")
                ).hexdigest(),
                "transpiled_depth": int(transpiled.depth()),
                "transpiled_size": int(transpiled.size()),
            }
        )
    print(f"circuits={len(circuits)} shots={args.shots} mode={args.mode}")
    if args.dry_run:
        for row in metadata:
            print(row)
        return 0

    sampler = SamplerV2(mode=backend)
    started = time.time()
    job = sampler.run([(circuit,) for circuit in circuits], shots=args.shots)
    print(f"submitted job_id={job.job_id()}")
    result = job.result()
    elapsed = time.time() - started
    usage_after = service.usage()

    out_root = Path(args.out) / ("pilot_" + args.mode if args.mode == "pilot" else args.mode) / backend.name.replace("-", "_")
    # A single stable folder per backend for the full run keeps load_suite_run simple.
    if args.mode == "full":
        out_root = Path(args.out) / backend.name.replace("-", "_")
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        props = backend.properties().to_dict()
    except Exception:  # noqa: BLE001
        props = None
    if props is not None:
        (out_root / "calibration.json").write_bytes(
            (json.dumps(props, indent=2, default=str, sort_keys=True) + "\n").encode("utf-8")
        )

    for index, job_def in enumerate(selected):
        folder = out_root / job_def.job_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "circuit.qasm").write_bytes(job_def.qasm.encode("ascii"))
        counts = _counts_from_pub(result[index])
        if sum(counts.values()) != args.shots:
            raise RuntimeError(
                f"{job_def.job_id}: {sum(counts.values())} shots returned, expected {args.shots}"
            )
        (folder / "result.json").write_bytes(
            (json.dumps(counts, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        (folder / "job.json").write_bytes(
            (
                json.dumps(
                    {
                        "job": {
                            "id": job.job_id(),
                            "backend": backend.name,
                            "status": "Completed",
                        },
                        "dataset_id": "r-ibm-1",
                        "shots": args.shots,
                        "fixed_chain": chain,
                        "transpiled_qasm": qasm2.dumps(circuits[index]),
                        "metadata": metadata[index],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        )

    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-ibm-1",
        "mode": args.mode,
        "backend": backend.name,
        "num_qubits_backend": backend.num_qubits,
        "fixed_chain": chain,
        "shots": args.shots,
        "job_id": job.job_id(),
        "circuits": metadata,
        "usage_before": usage_before,
        "usage_after": usage_after,
        "wall_seconds": elapsed,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": (
            "External IBM Quantum run, not an execution by the cqhecs package. "
            "The 25 circuits are the SHA-256-pinned r-io-7 circuits; the fixed "
            "physical chain makes logical qubit q map to the same physical qubit "
            "in every job. Calibration is stored when the backend exposes it."
        ),
    }
    (out_root / "summary.json").write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(f"wrote {out_root}")
    print(f"usage_remaining_seconds={usage_after.get('usage_remaining_seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
