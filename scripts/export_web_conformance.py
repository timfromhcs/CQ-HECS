"""Export the browser conformance corpus: one declared set of circuits, two engines.

The browser engine is not the Python engine. It is an independent Rust/WebAssembly
implementation, and the only honest way to compare them is a fixed corpus with a fixed
qubit order and a stated tolerance. This script defines that corpus:

* each case is a qubit count, a list of operations (target qubit, control bitmask and the
  2x2 matrix as eight floats), and the probabilities a dense reference computes;
* the reference here is plain NumPy linear algebra written from the same matrix
  definitions - not the Python simulator - so a mistake in the browser engine is visible
  as a mismatch, and a mistake in this script is visible in review.

    python scripts/export_web_conformance.py

writes ``web/tests/fixtures/quantum_conformance.json``, which
``web/tests/conformance.test.ts`` replays through the WebAssembly core.

Semantics that both sides must agree on, and which the file states in ``notes``:

* qubit ``q`` is bit ``q`` of the basis index (little-endian);
* ``ctrl`` is a bitmask; ``0`` means no control;
* the matrix is row-major ``[re00, im00, re01, im01, re10, im10, re11, im11]``;
* probabilities are ``|amplitude|^2`` in basis-index order.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "web" / "tests" / "fixtures" / "quantum_conformance.json"

SQRT1_2 = math.sqrt(0.5)
TOLERANCE = 1e-12


def phase(lam: float) -> Tuple[float, ...]:
    return (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, math.cos(lam), math.sin(lam))


def u3(theta: float, phi: float, lam: float) -> Tuple[float, ...]:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return (
        c, 0.0,
        -math.cos(lam) * s, -math.sin(lam) * s,
        math.cos(phi) * s, math.sin(phi) * s,
        math.cos(phi + lam) * c, math.sin(phi + lam) * c,
    )


H = (SQRT1_2, 0.0, SQRT1_2, 0.0, SQRT1_2, 0.0, -SQRT1_2, 0.0)
X = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0)


def _matrix_parts(m: Sequence[float]) -> np.ndarray:
    return np.array(
        [
            [complex(m[0], m[1]), complex(m[2], m[3])],
            [complex(m[4], m[5]), complex(m[6], m[7])],
        ],
        dtype=np.complex128,
    )


def reference(qubits: int, ops: Sequence[Dict[str, Any]]) -> List[float]:
    """Dense statevector with bit q = qubit q; returns probabilities per basis index."""
    state = np.zeros(1 << qubits, dtype=np.complex128)
    state[0] = 1.0
    for op in ops:
        target = int(op["target"])
        ctrl = int(op["ctrl"])
        matrix = _matrix_parts(op["m"])
        tbit = 1 << target
        for index in range(1 << qubits):
            if index & tbit:
                continue
            if index & ctrl != ctrl:
                continue
            other = index | tbit
            low, high = state[index], state[other]
            state[index] = matrix[0, 0] * low + matrix[0, 1] * high
            state[other] = matrix[1, 0] * low + matrix[1, 1] * high
    return [complex(amplitude) for amplitude in state]


def op(target: int, matrix: Sequence[float], ctrl: int = 0) -> Dict[str, Any]:
    return {"target": target, "ctrl": ctrl, "m": [float(value) for value in matrix]}


def cases() -> List[Dict[str, Any]]:
    return [
        {
            "name": "bell",
            "qubits": 2,
            "ops": [op(0, H), op(1, X, ctrl=1 << 0)],
        },
        {
            "name": "ghz-3",
            "qubits": 3,
            "ops": [op(0, H), op(1, X, ctrl=1 << 0), op(2, X, ctrl=1 << 1)],
        },
        {
            # H S H leaves |+> with an asymmetric phase: the probabilities are still
            # uniform, but the amplitudes are not, so any sign error in the imaginary part
            # of the S matrix shows up in the amplitude comparison below.
            "name": "phase-interference",
            "qubits": 1,
            "ops": [op(0, H), op(0, phase(math.pi / 2)), op(0, H)],
        },
        {
            "name": "u3-0.7-0.3-1.1",
            "qubits": 1,
            "ops": [op(0, u3(0.7, 0.3, 1.1))],
        },
        {
            # Controlled phase between H layers: probabilities depend on the phase, so an
            # engine that ignores the control bit cannot pass this case.
            "name": "controlled-phase",
            "qubits": 2,
            "ops": [op(0, H), op(1, H), op(1, phase(math.pi / 3), ctrl=1 << 0), op(0, H), op(1, H)],
        },
        {
            # Direction check: x on qubit 0 then a gate controlled by qubit 1 (which is 0)
            # must do nothing at all.
            "name": "control-direction",
            "qubits": 2,
            "ops": [op(0, X), op(0, H, ctrl=1 << 1)],
        },
    ]


def build() -> Dict[str, Any]:
    entries = []
    for case in cases():
        amplitudes = reference(case["qubits"], case["ops"])
        probabilities = [float(abs(amplitude) ** 2) for amplitude in amplitudes]
        total = sum(probabilities)
        if abs(total - 1.0) > 1e-12:
            raise SystemExit(f"{case['name']}: reference probabilities sum to {total!r}, not 1")
        entries.append(
            {
                **case,
                "probabilities": probabilities,
                "amplitudes": [[float(a.real), float(a.imag)] for a in amplitudes],
            }
        )
    return {
        "schema": "hcs.web.conformance.v1",
        "generated_by": "scripts/export_web_conformance.py",
        "notes": [
            "qubit q is bit q of the basis index (little-endian)",
            "ctrl is a bitmask; 0 means no control",
            "matrix is row-major [re00, im00, re01, im01, re10, im10, re11, im11]",
            "probabilities are |amplitude|^2 in basis-index order",
        ],
        "tolerance": TOLERANCE,
        "cases": entries,
    }


def main() -> int:
    document = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}: {len(document['cases'])} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
