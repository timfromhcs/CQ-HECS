"""Write Qiskit Statevector references for the web emulator tests."""

import json
import math
import random
from pathlib import Path

from qiskit import QuantumCircuit, qasm2
from qiskit.quantum_info import Statevector

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "qiskit_statevectors.json"
ONE = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx"]
ROT = ["rx", "ry", "rz", "p"]


def random_circuit(n: int, depth: int, rng: random.Random) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    for _ in range(depth):
        kind = rng.random()
        if kind < 0.35:
            getattr(qc, rng.choice(ONE))(rng.randrange(n))
        elif kind < 0.55:
            getattr(qc, rng.choice(ROT))(rng.uniform(-math.pi, math.pi), rng.randrange(n))
        elif kind < 0.62:
            qc.u(rng.uniform(0, math.pi), rng.uniform(-math.pi, math.pi), rng.uniform(-math.pi, math.pi), rng.randrange(n))
        elif n >= 2 and kind < 0.85:
            a, b = rng.sample(range(n), 2)
            gate = rng.choice(["cx", "cy", "cz", "ch", "swap", "cp", "crz"])
            if gate in ("cp", "crz"):
                getattr(qc, gate)(rng.uniform(-math.pi, math.pi), a, b)
            else:
                getattr(qc, gate)(a, b)
        elif n >= 3:
            a, b, c = rng.sample(range(n), 3)
            getattr(qc, rng.choice(["ccx", "cswap"]))(a, b, c)
    return qc


def main() -> None:
    rng = random.Random(20261030)
    cases = []
    for k in range(40):
        n = 1 + k % 8
        qc = random_circuit(n, 6 + 3 * n, rng)
        sv = Statevector.from_instruction(qc).data
        cases.append({
            "qasm": qasm2.dumps(qc),
            "num_qubits": n,
            "re": [float(a.real) for a in sv],
            "im": [float(a.imag) for a in sv],
        })
    OUT.write_text(json.dumps({"generator": "qiskit Statevector", "cases": cases}) + "\n", "utf-8")
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
