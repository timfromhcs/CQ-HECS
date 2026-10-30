#!/usr/bin/env python3
"""
Cross-check CQ-HECS against the independent QuantumRings 128-qubit simulator.

QuantumRings is a *classical* simulator, not a QPU. The point of this script is
an independent oracle: the same noiseless circuit is run on two engines, and
the measured counts are compared with CQ-HECS's exact distribution. A failure is
published; nothing is tuned until it passes.

The account key is read from ``quantumrings.conf`` (or the standard per-user
location) and is never printed, logged or written to the evidence folder.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cqhecs import __version__  # noqa: E402
from cqhecs.openquantum_suite import to_qasm  # noqa: E402

Gate = Tuple[str, Tuple[int, ...], Tuple[float, ...]]


# ---------------------------------------------------------------------------
# circuits (independent of the Open Quantum suite builders)
# ---------------------------------------------------------------------------


def _ghz(n: int) -> List[Gate]:
    gates: List[Gate] = [("h", (0,), ())]
    gates.extend(("cx", (q, q + 1), ()) for q in range(n - 1))
    return gates


def _cp(control: int, target: int, angle: float) -> List[Gate]:
    half = angle / 2.0
    return [
        ("rz", (control,), (half,)),
        ("cx", (control, target), ()),
        ("rz", (target,), (-half,)),
        ("cx", (control, target), ()),
        ("rz", (target,), (half,)),
    ]


def _qft(n: int) -> List[Gate]:
    gates: List[Gate] = []
    for top in range(n - 1, -1, -1):
        gates.append(("h", (top,), ()))
        for qubit in range(top):
            gates.extend(_cp(qubit, top, math.pi / (2.0 ** (top - qubit))))
    for qubit in range(n // 2):
        a, b = qubit, n - 1 - qubit
        gates.extend([("cx", (a, b), ()), ("cx", (b, a), ()), ("cx", (a, b), ())])
    return gates


_SELF_INVERSE = {"h": "h", "x": "x", "cx": "cx", "s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}


def _invert(gates: Sequence[Gate]) -> List[Gate]:
    out: List[Gate] = []
    for name, qubits, params in reversed(gates):
        if name in ("rx", "ry", "rz"):
            out.append((name, qubits, (-params[0],)))
        elif name in _SELF_INVERSE:
            out.append((_SELF_INVERSE[name], qubits, ()))
        else:
            raise ValueError(f"no inverse for {name}")
    return out


def _random_clifford_t(n: int, depth: int, seed: int) -> List[Gate]:
    rng = np.random.default_rng(seed)
    names = ("h", "s", "sdg", "t", "tdg", "x", "sx")
    gates: List[Gate] = []
    for _ in range(depth):
        if n > 1 and rng.random() < 0.4:
            a, b = (int(v) for v in rng.choice(n, size=2, replace=False))
            gates.append(("cx", (a, b), ()))
        else:
            gates.append((str(rng.choice(names)), (int(rng.integers(n)),), ()))
    return gates


def _brickwork(n: int, layers: int, seed: int) -> List[Gate]:
    rng = np.random.default_rng(seed)
    gates: List[Gate] = []
    for layer in range(layers):
        for q in range(n):
            a, b, c = (float(v) for v in rng.uniform(0.0, 2.0 * math.pi, size=3))
            gates.extend([("rz", (q,), (a,)), ("ry", (q,), (b,)), ("rz", (q,), (c,))])
        for q in range(layer % 2, n - 1, 2):
            gates.append(("cx", (q, q + 1), ()))
    return gates


def _grover3() -> List[Gate]:
    gates: List[Gate] = [("h", (q,), ()) for q in range(3)]
    # oracle: CZ on |111> = H(2) CCX(0,1,2) H(2); QR has no ccx, so decompose.
    # CCX(a,b,c) = H(c) CX(b,c) Tdg(c) CX(a,c) T(c) CX(b,c) Tdg(c) CX(a,c)
    #             T(b) T(c) H(c) CX(a,b) T(a) Tdg(b) CX(a,b)
    a, b, c = 0, 1, 2
    gates.extend([
        ("h", (c,), ()),
        ("cx", (b, c), ()), ("tdg", (c,), ()), ("cx", (a, c), ()), ("t", (c,), ()),
        ("cx", (b, c), ()), ("tdg", (c,), ()), ("cx", (a, c), ()), ("t", (b,), ()),
        ("t", (c,), ()), ("h", (c,), ()), ("cx", (a, b), ()), ("t", (a,), ()),
        ("tdg", (b,), ()), ("cx", (a, b), ()),
    ])
    # diffusion
    gates.extend([("h", (q,), ()) for q in range(3)])
    gates.extend([("x", (q,), ()) for q in range(3)])
    gates.extend([("h", (c,), ()), ("cx", (b, c), ()), ("tdg", (c,), ()),
                  ("cx", (a, c), ()), ("t", (c,), ()), ("cx", (b, c), ()),
                  ("tdg", (c,), ()), ("cx", (a, c), ()), ("t", (b,), ()),
                  ("t", (c,), ()), ("h", (c,), ()), ("cx", (a, b), ()),
                  ("t", (a,), ()), ("tdg", (b,), ()), ("cx", (a, b), ())])
    gates.extend([("x", (q,), ()) for q in range(3)])
    gates.extend([("h", (q,), ()) for q in range(3)])
    return gates


def _bernstein_vazirani(secret: str) -> Tuple[List[Gate], int]:
    n = len(secret)
    anc = n
    gates: List[Gate] = [("x", (anc,), ()), ("h", (anc,), ())]
    gates.extend(("h", (q,), ()) for q in range(n))
    for q, bit in enumerate(reversed(secret)):
        if bit == "1":
            gates.append(("cx", (q, anc), ()))
    gates.extend(("h", (q,), ()) for q in range(n))
    gates.extend([("h", (anc,), ()), ("x", (anc,), ())])
    return gates, n + 1


def _deutsch_jozsa(n: int) -> Tuple[List[Gate], int]:
    anc = n
    gates: List[Gate] = [("x", (anc,), ()), ("h", (anc,), ())]
    gates.extend(("h", (q,), ()) for q in range(n))
    gates.extend(("cx", (q, anc), ()) for q in range(n))
    gates.extend(("h", (q,), ()) for q in range(n))
    gates.extend([("h", (anc,), ()), ("x", (anc,), ())])
    return gates, n + 1


def _mirror(n: int, depth: int, seed: int) -> List[Gate]:
    forward = [g for g in _random_clifford_t(n, depth, seed) if g[0] != "sx"]
    return forward + _invert(forward)


@dataclass(frozen=True)
class Circuit:
    circuit_id: str
    family: str
    num_qubits: int
    gates: Tuple[Gate, ...]

    @property
    def qasm(self) -> str:
        return to_qasm(self.gates, self.num_qubits)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.qasm.encode("ascii")).hexdigest()


def suite() -> List[Circuit]:
    circuits: List[Circuit] = []

    def add(circuit_id: str, family: str, n: int, gates: Sequence[Gate]) -> None:
        circuits.append(
            Circuit(
                circuit_id=circuit_id,
                family=family,
                num_qubits=n,
                gates=tuple((name, tuple(q), tuple(float(p) for p in params)) for name, q, params in gates),
            )
        )

    for n in (2, 3, 5, 10, 20, 30, 64, 100, 128):
        add(f"ghz{n}", "ghz", n, _ghz(n))
    for n in (4, 6, 8):
        add(f"qft{n}", "qft", n, _qft(n))
    for n, depth, seed in ((6, 20, 11), (8, 24, 12), (10, 28, 13)):
        add(f"clifford_t{n}_d{depth}", "clifford_t", n, _random_clifford_t(n, depth, seed))
    for n, layers, seed in ((6, 3, 21), (8, 3, 22)):
        add(f"brickwork{n}_l{layers}", "brickwork", n, _brickwork(n, layers, seed))
    add("grover3_111", "algorithm", 3, _grover3())
    bv, n_bv = _bernstein_vazirani("10110")
    add("bv5_10110", "algorithm", n_bv, bv)
    dj, n_dj = _deutsch_jozsa(4)
    add("dj4_balanced", "algorithm", n_dj, dj)
    add("mirror6_d30", "mirror", 6, _mirror(6, 30, 31))
    return circuits


# ---------------------------------------------------------------------------
# engines
# ---------------------------------------------------------------------------


def _qr_circuit(gates: Sequence[Gate], n: int) -> Any:
    from QuantumRingsLib import QuantumCircuit

    qc = QuantumCircuit(n, n)
    for name, qubits, params in gates:
        method = getattr(qc, name)
        if params:
            method(*params, *qubits)
        else:
            method(*qubits)
    qc.measure(list(range(n)), list(range(n)))
    return qc


def _exact_probabilities(circuit: Circuit) -> Dict[str, float]:
    """Exact CQ-HECS distribution, or the analytic GHZ law above 10 qubits."""
    if circuit.family == "ghz" and circuit.num_qubits > 10:
        return {
            "0" * circuit.num_qubits: 0.5,
            "1" * circuit.num_qubits: 0.5,
        }
    instructions = [[name, list(q), list(params)] for name, q, params in circuit.gates]
    instructions.extend(["measure", [q], []] for q in range(circuit.num_qubits))
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

    result = NoisyDensityMatrixBackend(max_qubits=10).simulate(instructions, shots=1, seed=0)
    if not result.probabilities:
        raise RuntimeError(f"{circuit.circuit_id}: exact engine returned no probabilities ({result.state})")
    return {str(k): float(v) for k, v in result.probabilities.items() if float(v) > 1e-15}


def _tv(counts: Mapping[str, int], probabilities: Mapping[str, float]) -> float:
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("empty counts")
    support = set(counts) | set(probabilities)
    return 0.5 * sum(
        abs(counts.get(state, 0) / total - probabilities.get(state, 0.0)) for state in support
    )


def _null_tv(probabilities: Mapping[str, float], shots: int, rng: np.random.Generator) -> np.ndarray:
    states = list(probabilities)
    p = np.array([probabilities[state] for state in states], dtype=float)
    p = p / p.sum()
    values = []
    for _ in range(400):
        sample = rng.choice(states, size=shots, p=p)
        unique, counts = np.unique(sample, return_counts=True)
        measured = {str(state): int(count) for state, count in zip(unique, counts)}
        values.append(_tv(measured, probabilities))
    return np.array(values)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _load_credentials(config: Path) -> Tuple[str, str]:
    parser = configparser.ConfigParser()
    if not parser.read(config):
        raise FileNotFoundError(f"no QuantumRings config at {config}")
    section = parser["default"] if parser.has_section("default") else parser[parser.sections()[0]]
    name = section.get("email") or section.get("name")
    token = section.get("key") or section.get("token")
    if not name or not token:
        raise ValueError("config needs email/name and key/token")
    return name, token


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "quantumrings.conf"))
    parser.add_argument("--backend", default="scarlet_quantum_rings")
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--out", default=str(ROOT / "research/v4/evidence/quantumrings"))
    parser.add_argument("--no-write", action="store_true", help="Print the table only")
    args = parser.parse_args(argv)

    import QuantumRingsLib
    from QuantumRingsLib import QuantumRingsProvider

    name, token = _load_credentials(Path(args.config))
    provider = QuantumRingsProvider(token=token, name=name)
    account = provider.active_account()
    backend = provider.get_backend(args.backend)

    out_root = Path(args.out) / args.backend
    counts_dir = out_root / "counts"
    qasm_dir = out_root / "qasm"
    if not args.no_write:
        counts_dir.mkdir(parents=True, exist_ok=True)
        qasm_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(20261030)
    rows: List[Dict[str, Any]] = []
    print(f"CQ-HECS {__version__} vs QuantumRings {QuantumRingsLib.__version__} on {args.backend}")
    print(f"{'circuit':24s} {'n':>4s} {'TV':>8s} {'null p99':>9s} {'z':>7s}  verdict")
    for circuit in suite():
        exact = _exact_probabilities(circuit)
        started = time.perf_counter()
        qc = _qr_circuit(circuit.gates, circuit.num_qubits)
        result = backend.run(qc, shots=args.shots, mode="sync").result()
        counts = {str(k).replace(" ", ""): int(v) for k, v in result.get_counts().items()}
        elapsed = time.perf_counter() - started
        if sum(counts.values()) != args.shots:
            raise RuntimeError(
                f"{circuit.circuit_id}: QuantumRings returned {sum(counts.values())} shots, expected {args.shots}"
            )
        tv = _tv(counts, exact)
        null = _null_tv(exact, args.shots, rng)
        mean, p99 = float(null.mean()), float(np.quantile(null, 0.99))
        z = (tv - mean) / float(null.std() or 1.0)
        passed = tv <= p99
        rows.append(
            {
                "circuit_id": circuit.circuit_id,
                "family": circuit.family,
                "num_qubits": circuit.num_qubits,
                "gate_count": len(circuit.gates),
                "qasm_sha256": circuit.sha256,
                "shots": args.shots,
                "tv": tv,
                "null_mean": mean,
                "null_p99": p99,
                "z": z,
                "pass": bool(passed),
                "seconds": elapsed,
                "exact_support_size": len(exact),
                "qr_top": sorted(counts.items(), key=lambda item: -item[1])[:8],
                "exact_top": sorted(exact.items(), key=lambda item: -item[1])[:8],
            }
        )
        print(
            f"{circuit.circuit_id:24s} {circuit.num_qubits:4d} {tv:8.5f} {p99:9.5f} {z:7.2f}  "
            f"{'PASS' if passed else 'FAIL'}"
        )
        if not args.no_write:
            (qasm_dir / f"{circuit.circuit_id}.qasm").write_bytes(circuit.qasm.encode("ascii"))
            (counts_dir / f"{circuit.circuit_id}.json").write_text(
                json.dumps(counts, indent=2, sort_keys=True) + "\n", "utf-8"
            )

    failures = [row for row in rows if not row["pass"]]
    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-qr-1",
        "cqhecs_version": __version__,
        "quantumrings_sdk_version": QuantumRingsLib.__version__,
        "backend": args.backend,
        "account_max_qubits": account.get("max_qubits"),
        "shots": args.shots,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "circuits": rows,
        "aggregate": {
            "n": len(rows),
            "passed": len(rows) - len(failures),
            "failed": len(failures),
            "max_tv": max((row["tv"] for row in rows), default=0.0),
            "verdict": "PASS" if not failures else "FAIL",
        },
        "note": (
            "QuantumRings is an independent classical simulator, not a QPU. The noiseless "
            "distribution is compared with CQ-HECS's exact distribution; the null column is "
            "the 99th percentile of 400 finite-shot resamples from that exact distribution. "
            "The account exposes a qubit ceiling, not a debit balance."
        ),
    }
    if not args.no_write:
        (out_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", "utf-8")
        lines = [
            "# r-qr-1 — independent QuantumRings cross-check",
            "",
            f"- CQ-HECS: `{__version__}`",
            f"- QuantumRings SDK: `{QuantumRingsLib.__version__}` on `{args.backend}`",
            f"- {args.shots} shots per circuit; {len(rows)} circuits",
            f"- Verdict: **{summary['aggregate']['verdict']}** "
            f"({summary['aggregate']['passed']}/{len(rows)} pass)",
            "",
            "| circuit | qubits | TV | null p99 | z | verdict |",
            "| :--- | ---: | ---: | ---: | ---: | :--- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['circuit_id']}` | {row['num_qubits']} | {row['tv']:.6f} | "
                f"{row['null_p99']:.6f} | {row['z']:+.2f} | "
                f"{'PASS' if row['pass'] else 'FAIL'} |"
            )
        lines.extend(
            [
                "",
                "QuantumRings is a classical simulator, not a QPU. A pass means the two",
                "independent engines agree within finite-shot noise on these circuits.",
                "It is not a hardware claim, a complexity result, or a P = NP statement.",
                "",
            ]
        )
        (out_root / "REPORT.md").write_text("\n".join(lines), "utf-8")
        print(f"\nwrote {out_root}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
