#!/usr/bin/env python3
"""
Universal / complexity-relevant probes on IBM Quantum.

This is an external real-QPU run, not an execution by the cqhecs package. It
runs a small suite of *universal* circuit families and algorithm primitives,
then asks two honest questions:

1. Does the fitted noise model (M-FIT / corrected M-FIT-2) predict these
   unseen circuits better than the ideal distribution?
2. Does a 3-qubit Grover search find the unique satisfying assignment of a
   small CNF?

Nothing here decides P versus NP. The instances are 2-5 qubits; a finite QPU
experiment is not a complexity separation. The point is to test the emulator's
noise model on out-of-distribution universal circuits and to keep the SAT
connection empirical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cqhecs.openquantum_suite import _qft, build_suite, fit_model, load_suite_run  # noqa: E402

Gate = Tuple[str, Tuple[int, ...], Tuple[float, ...]]


@dataclass(frozen=True)
class Probe:
    probe_id: str
    family: str
    num_qubits: int
    gates: Tuple[Gate, ...]
    purpose: str
    cnf: str = ""

    @property
    def qasm(self) -> str:
        from cqhecs.openquantum_suite import to_qasm

        return to_qasm(self.gates, self.num_qubits)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.qasm.encode("ascii")).hexdigest()

    def instructions(self) -> List[List[Any]]:
        body = [[name, list(q), list(p)] for name, q, p in self.gates]
        body.extend(["measure", [q], []] for q in range(self.num_qubits))
        return body


def _random_universal(n: int, depth: int, seed: int) -> List[Gate]:
    rng = np.random.default_rng(seed)
    gates: List[Gate] = []
    names = ("h", "s", "sdg", "t", "tdg", "x")
    for _ in range(depth):
        if n > 1 and rng.random() < 0.45:
            a, b = (int(v) for v in rng.choice(n, size=2, replace=False))
            gates.append(("cx", (a, b), ()))
        else:
            gates.append((str(rng.choice(names)), (int(rng.integers(n)),), ()))
    return gates


def _iqp(n: int, layers: int) -> List[Gate]:
    gates: List[Gate] = []
    for layer in range(layers):
        gates.extend(("h", (q,), ()) for q in range(n))
        gates.extend(("t", (q,), ()) for q in range(n))
        for q in range(layer % 2, n - 1, 2):
            gates.append(("cx", (q, q + 1), ()))
    return gates


def _cz(n: int) -> List[Gate]:
    """Multi-controlled Z on all qubits (n >= 2), via H + MCX + H."""
    if n == 2:
        return [("cz", (0, 1), ())]
    if n == 3:
        return [("h", (2,), ()), ("ccx", (0, 1, 2), ()), ("h", (2,), ())]
    return [("h", (n - 1,), ()), ("mcx", tuple(range(n)), ()), ("h", (n - 1,), ())]


def _grover_oracle(n: int, target_bits: str) -> List[Gate]:
    """Phase oracle marking the displayed bitstring ``target_bits``.

    ``target_bits`` is written in the same order as a Qiskit count key
    (qubit n-1 ... qubit 0), so it is reversed before assigning to q0..q{n-1}.
    """
    if len(target_bits) != n:
        raise ValueError("target width mismatch")
    q0_first = target_bits[::-1]
    flips = [("x", (q,), ()) for q, bit in enumerate(q0_first) if bit == "0"]
    return flips + _cz(n) + flips


def _grover_diffusion(n: int) -> List[Gate]:
    gates: List[Gate] = [("h", (q,), ()) for q in range(n)]
    gates += [("x", (q,), ()) for q in range(n)]
    gates += _cz(n)
    gates += [("x", (q,), ()) for q in range(n)]
    gates += [("h", (q,), ()) for q in range(n)]
    return gates


def _grover(n: int, target_bits: str, iterations: int) -> List[Gate]:
    gates: List[Gate] = [("h", (q,), ()) for q in range(n)]
    for _ in range(iterations):
        gates += _grover_oracle(n, target_bits)
        gates += _grover_diffusion(n)
    return gates


def _simon2(secret: str = "11") -> List[Gate]:
    """2 data + 2 ancilla; f(x) = (x0, x0 xor x1) has kernel {00, secret}."""
    if secret != "11":
        raise ValueError("the fixed Simon oracle implements secret 11")
    # data q0,q1; ancilla q2,q3
    return [
        ("h", (0,), ()), ("h", (1,), ()),
        ("cx", (0, 2), ()),
        ("cx", (0, 3), ()), ("cx", (1, 3), ()),
        ("h", (0,), ()), ("h", (1,), ()),
    ]


def _mirror(n: int, depth: int, seed: int) -> List[Gate]:
    forward = [g for g in _random_universal(n, depth, seed) if g[0] != "sx"]
    inverse: List[Gate] = []
    inverse_map = {"h": "h", "x": "x", "cx": "cx", "s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}
    for name, qubits, params in reversed(forward):
        if name in ("rx", "ry", "rz"):
            inverse.append((name, qubits, (-params[0],)))
        else:
            inverse.append((inverse_map[name], qubits, ()))
    return forward + inverse


def _ghz(n: int) -> List[Gate]:
    gates: List[Gate] = [("h", (0,), ())]
    gates.extend(("cx", (q, q + 1), ()) for q in range(n - 1))
    return gates


def _qft5() -> List[Gate]:
    prep = [("x", (q,), ()) for q in (0, 2, 4)]  # |10101>, q0 rightmost
    return prep + _qft(list(range(5)))


def probes() -> List[Probe]:
    raw = [
        Probe("universal_ct5_d40", "universal", 5, tuple(_random_universal(5, 40, 101)),
              "random Clifford+T on a universal gate set"),
        Probe("iqp5_l3", "iqp", 5, tuple(_iqp(5, 3)),
              "instantaneous quantum polynomial circuit, 3 layers"),
        Probe("grover4_1011", "search", 4, tuple(_grover(4, "1011", 3)),
              "Grover search for |1011> (3 iterations)"),
        Probe("simon2_11", "period", 4, tuple(_simon2("11")),
              "Simon period finding, secret 11; data outcomes 00/11"),
        Probe("sat3_grover_100", "sat", 3, tuple(_grover(3, "100", 2)),
              "Grover over a 3-variable CNF with the unique model 100",
              cnf="p cnf 3 7\n3 2 1 0\n3 2 -1 0\n3 -2 1 0\n3 -2 -1 0\n-3 2 -1 0\n-3 -2 1 0\n-3 -2 -1 0\n"),
        Probe("qft5_10101", "qft", 5, tuple(_qft5()),
              "QFT of |10101>; all-to-all phases"),
        Probe("ghz5", "ghz", 5, tuple(_ghz(5)), "entanglement control"),
        Probe("mirror5_d30", "mirror", 5, tuple(_mirror(5, 30, 202)),
              "U U^-1 depth-30 error benchmark"),
    ]
    return [_decompose(probe) for probe in raw]


def _token(path: Path) -> str:
    if os.environ.get("QISKIT_IBM_TOKEN"):
        return os.environ["QISKIT_IBM_TOKEN"]
    payload = json.loads(path.read_text("utf-8"))
    token = payload.get("apikey") or payload.get("token") or payload.get("key")
    if not token:
        raise ValueError(f"{path} has no apikey/token field")
    return str(token)


def _pick_chain(backend: Any, length: int = 5) -> List[int]:
    edges = backend.coupling_map.get_edges()
    adjacency: Dict[int, List[int]] = {}
    for a, b in edges:
        adjacency.setdefault(int(a), []).append(int(b))
        adjacency.setdefault(int(b), []).append(int(a))
    try:
        props = backend.properties()
    except Exception:  # noqa: BLE001
        props = None

    def score(path: Sequence[int]) -> float:
        if props is None:
            return 0.0
        total = 0.0
        for q in path:
            try:
                total += float(props.readout_error(q))
            except Exception:  # noqa: BLE001
                pass
        return total

    best: Optional[List[int]] = None
    best_score = float("inf")
    for start in sorted(adjacency):
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            if len(path) == length:
                value = score(path)
                if value < best_score:
                    best, best_score = path, value
                continue
            for neighbour in adjacency.get(node, []):
                if neighbour not in path:
                    stack.append((neighbour, path + [neighbour]))
    if best is None:
        raise RuntimeError(f"{backend.name}: no connected {length}-qubit chain")
    return best


def _raw_qiskit(probe: Probe) -> Any:
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(probe.num_qubits, probe.num_qubits)
    for name, qubits, params in probe.gates:
        if name == "mcx":
            qc.mcx(list(qubits[:-1]), qubits[-1])
            continue
        method = getattr(qc, name)
        if params:
            method(*params, *qubits)
        else:
            method(*qubits)
    return qc


_1Q2Q_BASIS = ["h", "x", "s", "sdg", "t", "tdg", "rz", "rx", "ry", "cx"]


def _decompose(probe: Probe) -> Probe:
    """Lower multi-qubit gates to the exact 1q/2q basis used by the emulator."""
    from qiskit import transpile

    if not any(name in ("mcx", "ccx", "cz") for name, _q, _p in probe.gates):
        return probe
    raw = _raw_qiskit(probe)
    lowered = transpile(
        raw,
        basis_gates=_1Q2Q_BASIS,
        optimization_level=1,
        seed_transpiler=20261030,
    )
    gates: List[Gate] = []
    for instruction in lowered.data:
        name = instruction.operation.name
        if name in ("barrier", "measure"):
            continue
        qubits = tuple(lowered.find_bit(q).index for q in instruction.qubits)
        params = tuple(float(p) for p in (instruction.operation.params or ()))
        gates.append((name, qubits, params))
    return Probe(probe.probe_id, probe.family, probe.num_qubits, tuple(gates), probe.purpose, probe.cnf)


def _qiskit(probe: Probe) -> Any:
    qc = _raw_qiskit(probe)
    qc.measure(list(range(probe.num_qubits)), list(range(probe.num_qubits)))
    return qc


def _exact(probe: Probe) -> Dict[str, float]:
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

    result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
        probe.instructions(), shots=1, seed=0
    )
    if not result.probabilities:
        raise RuntimeError(f"{probe.probe_id}: exact engine returned no probabilities")
    return {str(k): float(v) for k, v in result.probabilities.items() if float(v) > 1e-15}


def _model_probabilities(probe: Probe, model: Any) -> Dict[str, float]:
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

    result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
        probe.instructions(), noise_model=model, shots=1, seed=0
    )
    if not result.probabilities:
        return {}
    return {str(k): float(v) for k, v in result.probabilities.items() if float(v) > 1e-15}


def _tv(counts: Mapping[str, int], probabilities: Mapping[str, float]) -> float:
    total = sum(counts.values())
    support = set(counts) | set(probabilities)
    return 0.5 * sum(abs(counts.get(k, 0) / total - probabilities.get(k, 0.0)) for k in support)


def _null(probabilities: Mapping[str, float], shots: int, rng: np.random.Generator) -> float:
    states = list(probabilities)
    p = np.array([probabilities[s] for s in states], dtype=float)
    p = p / p.sum()
    values = []
    for _ in range(200):
        sample = rng.choice(states, size=shots, p=p)
        unique, counts = np.unique(sample, return_counts=True)
        values.append(_tv({str(s): int(c) for s, c in zip(unique, counts)}, probabilities))
    return float(np.quantile(values, 0.99))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="ibm_marrakesh")
    parser.add_argument("--shots", type=int, default=10000)
    parser.add_argument("--config", default=str(ROOT / "apikey.json"))
    parser.add_argument("--out", default=str(ROOT / "research/v4/evidence/ibm_universal"))
    parser.add_argument("--fit-root", default=None, help="25-job run used to fit the noise model")
    args = parser.parse_args(argv)

    from qiskit import transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    key = _token(Path(args.config))
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=key)
    usage_before = service.usage()
    backend = service.backend(args.backend)
    chain = _pick_chain(backend, 5)
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
    (out_root / "counts").mkdir(exist_ok=True)
    (out_root / "qasm").mkdir(exist_ok=True)
    if backend.properties() is not None:
        (out_root / "calibration.json").write_bytes(
            (json.dumps(backend.properties().to_dict(), indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
        )

    fit_root = Path(args.fit_root) if args.fit_root else ROOT / "research/v4/evidence/ibm_10k" / backend.name.replace("-", "_")
    model2 = None
    model1 = None
    if fit_root.is_dir():
        from cqhecs.noise_fit import fit_profile

        model2, _profile = fit_profile(fit_root)
        run = load_suite_run(fit_root)
        model1 = fit_model({j.job_id: j for j in build_suite()}, run.counts)

    rng = np.random.default_rng(20261030)
    rows = []
    for index, probe in enumerate(items):
        data = result[index].data
        field = list(data.keys())[0]
        counts = {str(k).replace(" ", ""): int(v) for k, v in data[field].get_counts().items()}
        exact = _exact(probe)
        row: Dict[str, Any] = {
            "probe_id": probe.probe_id,
            "family": probe.family,
            "num_qubits": probe.num_qubits,
            "purpose": probe.purpose,
            "shots": args.shots,
            "qasm_sha256": probe.sha256,
            "counts": counts,
            "exact_top": sorted(exact.items(), key=lambda kv: -kv[1])[:8],
            "tv_ideal": _tv(counts, exact),
            "null_p99": _null(exact, args.shots, rng),
        }
        if model1 is not None:
            p1 = _model_probabilities(probe, model1.noise_model(probe))
            row["tv_mfit"] = _tv(counts, p1)
        if model2 is not None:
            p2 = _model_probabilities(probe, model2.noise_model(probe))
            row["tv_mfit2"] = _tv(counts, p2)
        if probe.family == "sat":
            top = max(counts.items(), key=lambda kv: kv[1])[0]
            row["sat_expected"] = "100"
            row["sat_cnf"] = probe.cnf
            row["sat_top"] = top
            row["sat_found"] = top == "100"
        rows.append(row)
        (out_root / "counts" / f"{probe.probe_id}.json").write_bytes(
            (json.dumps(counts, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        (out_root / "qasm" / f"{probe.probe_id}.qasm").write_bytes(probe.qasm.encode("ascii"))

    summary = {
        "schema_version": "1.0",
        "dataset_id": "r-ibm-universal-1",
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots": args.shots,
        "fixed_chain": chain,
        "usage_before": usage_before,
        "usage_after": usage_after,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probes": rows,
        "aggregate": {
            "n": len(rows),
            "median_tv_ideal": float(np.median([r["tv_ideal"] for r in rows])),
            "median_tv_mfit": float(np.median([r["tv_mfit"] for r in rows])) if model1 is not None else None,
            "median_tv_mfit2": float(np.median([r["tv_mfit2"] for r in rows])) if model2 is not None else None,
            "sat_found": [r.get("sat_found") for r in rows if r["family"] == "sat"],
        },
        "non_claim": (
            "These are 2-5 qubit universal/algorithmic probes, not a P versus NP "
            "experiment. A QPU run cannot separate complexity classes. The SAT "
            "probe is a finite 3-variable instance."
        ),
    }
    (out_root / "summary.json").write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(json.dumps(summary["aggregate"], indent=2))
    print(f"wrote {out_root}")
    print(f"remaining={usage_after['usage_remaining_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
