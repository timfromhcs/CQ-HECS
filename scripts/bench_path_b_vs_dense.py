#!/usr/bin/env python3
"""W3-04 (P1-04): measure Path B against a plain dense statevector.

Path B is a Bravyi-Smith-Smolin branch decomposition that contracts onto a dense
statevector; it is *not* a true stabilizer-rank method with an extent advantage. This
script measures, on a fixed seeded corpus, whether Path B ever beats a plain dense
statevector (Qiskit ``Statevector``) at the same width and T-count. It decides nothing by
itself: the outcome is a measured input to the P1-04 decision (relabel / reimplement /
re-order), not an asymptotic or competitive claim.

    python scripts/bench_path_b_vs_dense.py --quick
    python scripts/bench_path_b_vs_dense.py --out research/v7/evidence/PATHB_DOMINANCE.json

Timings are for this machine and this Python build only.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cqhecs import __version__  # noqa: E402
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend  # noqa: E402

SCHEMA = "hcs.pathb.vs_dense.v1"
DEFAULT_OUT = ROOT / "research" / "v7" / "evidence" / "PATHB_DOMINANCE.json"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {type(exc).__name__}"


def build_circuit(n: int, t_count: int, seed: int):
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(n)
    for q in range(n):
        qc.h(q)
    for layer in range(2):
        for q in range(layer, n - 1, 2):
            qc.cx(q, q + 1)
    for i in range(t_count):
        qc.t((i * 7 + 3) % n)  # spread the T gates; deterministic
    return qc


def time_dense(qc, repeat: int) -> List[float]:
    from qiskit.quantum_info import Statevector

    walls = []
    for _ in range(repeat):
        started = time.perf_counter()
        Statevector(qc)
        walls.append(time.perf_counter() - started)
    return walls


def time_path_b(qc, shots: int, seed: int, repeat: int) -> List[float]:
    backend = PathBStabilizerRankBackend()
    walls = []
    for _ in range(repeat):
        started = time.perf_counter()
        backend.execute(qc, shots=shots, seed=seed)
        walls.append(time.perf_counter() - started)
    return walls


def corpus(quick: bool):
    widths = (8, 10, 12) if quick else (8, 10, 12, 14, 16)
    t_counts = (0, 4, 8) if quick else (0, 2, 4, 6, 8)
    for n in widths:
        for t in t_counts:
            yield n, t


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON report path")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--shots", type=int, default=2000)
    parser.add_argument("--quick", action="store_true", help="smaller width/T grid")
    args = parser.parse_args(argv)

    report: Dict[str, Any] = {
        "schema": SCHEMA,
        "cqhecs_version": __version__,
        "git_sha": _git("rev-parse", "HEAD"),
        "worktree_dirty_files": [ln for ln in _git("status", "--short").splitlines() if ln],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "repeat": args.repeat,
        "shots": args.shots,
        "note": (
            "Path B is a branch decomposition that contracts onto a dense statevector, "
            "not a true stabilizer-rank method. Timings are this machine only; the "
            "result is a measured input to P1-04, not an asymptotic or competitive claim."
        ),
        "cases": [],
    }
    for n, t_count in corpus(args.quick):
        qc = build_circuit(n, t_count, seed=1000 + n * 10 + t_count)
        entry: Dict[str, Any] = {"num_qubits": n, "t_count": t_count, "branches": 1 << t_count}
        try:
            dense = time_dense(qc, args.repeat)
            path_b = time_path_b(qc, args.shots, seed=42, repeat=args.repeat)
            entry["dense_median_seconds"] = round(statistics.median(dense), 6)
            entry["path_b_median_seconds"] = round(statistics.median(path_b), 6)
            entry["ratio_path_b_over_dense"] = round(
                entry["path_b_median_seconds"] / entry["dense_median_seconds"], 4
            ) if entry["dense_median_seconds"] > 0 else None
            entry["state"] = "RUN"
        except Exception as exc:  # noqa: BLE001 - a case that cannot run is recorded, not hidden
            entry["state"] = "ERROR"
            entry["reason"] = f"{type(exc).__name__}: {exc}"
        report["cases"].append(entry)
        print(
            f"n={n:2d} T={t_count}: "
            + (
                f"dense={entry['dense_median_seconds']:.4f}s path_b={entry['path_b_median_seconds']:.4f}s "
                f"ratio={entry['ratio_path_b_over_dense']}"
                if entry["state"] == "RUN"
                else f"{entry['state']}: {entry.get('reason')}"
            )
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
