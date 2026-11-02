"""Export a cross-implementation circuit corpus: Qiskit as the reference.

The browser engine is an independent implementation. The honest way to compare it with
the Python side is a fixed corpus of small circuits with a stated qubit order and a stated
tolerance, evaluated by an oracle that shares no code with either.

The oracle here is Qiskit's statevector simulator. Each case is written as OpenQASM 2 text
(the same text the browser parses), so the case is not a table of pre-computed matrices
that both sides could agree on by construction.

    python scripts/export_web_circuit_conformance.py

writes ``web/tests/fixtures/circuit_conformance.json``; ``web/tests/circuit_conformance.test.ts``
parses the QASM with the browser's own parser, compiles it, runs it through the
WebAssembly core and compares the probabilities.

Semantics both sides must agree on, stated in the file:

* qubit ``q`` is bit ``q`` of the basis index (little-endian, Qiskit convention);
* probabilities are ``|amplitude|^2`` in basis-index order;
* tolerance ``1e-12`` for the f64 WebAssembly path.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import qiskit
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "web" / "tests" / "fixtures" / "circuit_conformance.json"
TOLERANCE = 1e-12


def qasm(qubits: int, clbits: int, body: List[str]) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{qubits}];"]
    if clbits:
        lines.append(f"creg c[{clbits}];")
    lines.extend(f"{statement};" for statement in body)
    return "\n".join(lines) + "\n"


def cases() -> List[Dict[str, Any]]:
    return [
        {
            "name": "bell",
            "qasm": qasm(2, 0, ["h q[0]", "cx q[0],q[1]"]),
        },
        {
            "name": "ghz-3",
            "qasm": qasm(3, 0, ["h q[0]", "cx q[0],q[1]", "cx q[1],q[2]"]),
        },
        {
            # Interference with an imaginary phase: probabilities alone hide a sign error,
            # so this case is the one that catches a conjugated S gate.
            "name": "s-interference",
            "qasm": qasm(1, 0, ["h q[0]", "s q[0]", "h q[0]"]),
        },
        {
            "name": "rx-rz",
            "qasm": qasm(1, 0, ["rx(0.7) q[0]", "rz(0.4) q[0]"]),
        },
        {
            "name": "controlled-phase",
            "qasm": qasm(2, 0, ["h q[0]", "h q[1]", "cp(1.0471975511965976) q[0],q[1]", "h q[0]", "h q[1]"]),
        },
        {
            # Direction check: x on qubit 0, then a CNOT whose control is qubit 1 (which is
            # still |0>). A swapped control/target changes the answer.
            "name": "control-direction",
            "qasm": qasm(2, 0, ["x q[0]", "cx q[1],q[0]"]),
        },
    ]


def reference(qasm_text: str) -> List[float]:
    circuit = QuantumCircuit.from_qasm_str(qasm_text)
    state = Statevector.from_instruction(circuit)
    probabilities = state.probabilities()
    return [float(value) for value in probabilities]


def build() -> Dict[str, Any]:
    entries = []
    for case in cases():
        probabilities = reference(case["qasm"])
        total = sum(probabilities)
        if abs(total - 1.0) > 1e-12:
            raise SystemExit(f"{case['name']}: reference probabilities sum to {total!r}, not 1")
        entries.append({**case, "probabilities": probabilities})
    return {
        "schema": "hcs.web.circuit-conformance.v1",
        "generated_by": "scripts/export_web_circuit_conformance.py",
        "oracle": f"Qiskit {qiskit.__version__} Statevector",
        "notes": [
            "qubit q is bit q of the basis index (little-endian, Qiskit convention)",
            "probabilities are |amplitude|^2 in basis-index order",
            "the QASM text is the case: the browser parses and compiles it itself",
        ],
        "tolerance": TOLERANCE,
        "cases": entries,
    }


def main() -> int:
    document = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}: {len(document['cases'])} cases, oracle {document['oracle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
