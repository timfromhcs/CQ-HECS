"""
Seeded differential fuzz used for the v2.5.2 audit (H-252-1, FINDINGS.md).

Draws random circuits over the gate manifest, runs them through the router,
each forced path (A-D) and the noisy density-matrix backend without noise, and
compares the output distribution with ``qiskit.quantum_info.Statevector``.
Exact probabilities must agree to 1e-6; sampled counts must lie within the
result's own Hoeffding TV bound (delta = 0.05, so about 5 % of comparisons may
exceed it by chance; a systematic defect shows as TV near 1).

Usage (from the repository root):

    PYTHONPATH=. python research/v2_5_2/differential_fuzz.py SEED COUNT

The audit ran seeds 1-4 with 200 circuits each (seed 1: 150 on the baseline).
"""

from __future__ import annotations

import math
import random
import sys
import warnings

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.router import FourPathRouter

warnings.filterwarnings("ignore")

G1 = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "sxdg", "id"]
G1P = {"rx": 1, "ry": 1, "rz": 1, "p": 1, "u1": 1, "u": 3, "u3": 3, "u2": 2, "r": 2}
G2 = ["cx", "cz", "swap", "cy", "ch", "cs", "csdg", "iswap", "dcx", "ecr", "csx"]
G2P = {"cp": 1, "cu1": 1, "crx": 1, "cry": 1, "crz": 1, "rzz": 1, "rxx": 1,
       "ryy": 1, "cu3": 3, "cu": 4}
G3 = ["ccx", "ccz", "cswap"]


def add_to_qiskit(qc, name, qubits, params):
    if name == "cu":
        qc.cu(*params, *qubits)
    elif name == "cu3":
        qc.cu(*params, 0.0, *qubits)
    elif name == "u2":
        qc.u(math.pi / 2, params[0], params[1], *qubits)
    else:
        getattr(qc, {"cu1": "cp", "u1": "p", "u3": "u"}.get(name, name))(*params, *qubits)


def random_circuit(rng, n, depth):
    ops = []
    for _ in range(depth):
        k = rng.random()
        if k < 0.45 or n < 2:
            if rng.random() < 0.5:
                ops.append((rng.choice(G1), [rng.randrange(n)], []))
            else:
                g = rng.choice(list(G1P))
                ops.append((g, [rng.randrange(n)], [rng.uniform(-4, 4) for _ in range(G1P[g])]))
        elif k < 0.9 or n < 3:
            a, b = rng.sample(range(n), 2)
            if rng.random() < 0.5:
                ops.append((rng.choice(G2), [a, b], []))
            else:
                g = rng.choice(list(G2P))
                ops.append((g, [a, b], [rng.uniform(-4, 4) for _ in range(G2P[g])]))
        else:
            ops.append((rng.choice(G3), rng.sample(range(n), 3), []))
    return ops


def reference(ops, n, measured):
    qc = QuantumCircuit(n)
    for name, qubits, params in ops:
        add_to_qiskit(qc, name, qubits, params)
    probs = Statevector(qc).probabilities_dict()
    if measured is None:
        return probs
    out = {}
    for bits, p in probs.items():
        key = "".join(bits[::-1][q] for q in measured)[::-1]
        out[key] = out.get(key, 0.0) + p
    return out


def tv(a, b):
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def main(seed, count):
    rng = random.Random(seed)
    router = FourPathRouter()
    dm = NoisyDensityMatrixBackend()
    shots = 4000
    mismatches = 0
    stats = {}
    for it in range(count):
        n = rng.randint(1, 5)
        # Identity on every qubit fixes the register width for instruction lists.
        ops = [("id", [q], []) for q in range(n)] + random_circuit(rng, n, rng.randint(1, 12))
        measured = sorted(rng.sample(range(n), rng.randint(1, n))) if rng.random() < 0.5 else None
        circuit = ops + [("measure", [q], []) for q in (measured or [])]
        expected = reference(ops, n, measured)
        engines = [("router", lambda: router.route_and_execute(
            circuit, shots=shots, seed=it, require_counts=True))]
        for path in "ABCD":
            engines.append((f"path{path}", lambda path=path: router.route_and_execute(
                circuit, shots=shots, seed=it, preferred_path=path, require_counts=True)))
        engines.append(("dm", lambda: dm.simulate(circuit, shots=shots, seed=it)))
        for label, run in engines:
            try:
                res = run()
            except Exception as exc:  # refusals are counted, not compared
                key = (label, "refused:" + type(exc).__name__)
                stats[key] = stats.get(key, 0) + 1
                continue
            state = res.state.value
            stats[(label, state)] = stats.get((label, state), 0) + 1
            if state not in ("EXACT", "CERTIFIED"):
                continue
            if res.probabilities:
                got, limit = res.probabilities, 1e-6
            else:
                total = sum(res.counts.values())
                got = {k: v / total for k, v in res.counts.items()}
                limit = (res.sampling_error_bound or 0.0) + (res.error_bound or 0.0)
            distance = tv(got, expected)
            if distance > limit + 1e-9:
                mismatches += 1
                print(f"MISMATCH {label} {state} tv={distance:.4g} limit={limit:.4g} circuit={circuit}")
    print("mismatches", mismatches)
    for key, value in sorted(stats.items()):
        print(key, value)
    return mismatches


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1,
         int(sys.argv[2]) if len(sys.argv) > 2 else 200)
