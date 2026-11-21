"""Deterministic circuit / QASM generation and circuit manifests.

Only the tested Track-A family is compiled here: the two-qubit BMV effective-phase
circuit and its null controls. SYK circuit compilation arrives with the Trotter slice; it
is deliberately not stubbed to look complete.

QASM is emitted deterministically: OpenQASM 2.0, ASCII, LF line endings, one gate per
line, so the SHA-256 of the bytes is stable across platforms.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

CIRCUIT_MANIFEST_SCHEMA = "cqhecs.qg.circuit_manifest.v1"


def sha256_text(text: str) -> str:
    """SHA-256 of ``text`` under a fixed LF policy, so the digest is line-ending independent."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def bmv_qasm(theta: float, local_phase_a: float = 0.0, local_phase_b: float = 0.0) -> str:
    """OpenQASM 2.0 for ``Rz(b) Rz(a) U_ZZ(theta) |+>|+>`` with terminal measurement.

    ``U_ZZ(theta) = exp(-i (theta/2) Z(x)Z)`` is lowered with the identity
    ``CX (I (x) Rz(theta)) CX = exp(-i (theta/2) Z (x) Z)``.
    """
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[2];",
        "creg c[2];",
        "h q[0];",
        "h q[1];",
        "cx q[0],q[1];",
        f"rz({theta:.17g}) q[1];",
        "cx q[0],q[1];",
        f"rz({local_phase_a:.17g}) q[0];",
        f"rz({local_phase_b:.17g}) q[1];",
        "measure q -> c;",
    ]
    return "\n".join(lines) + "\n"


def bmv_null_qasm() -> str:
    """The ``theta=0`` control: interaction is the identity, state stays separable."""
    return bmv_qasm(0.0, 0.0, 0.0)


def build_bmv_manifest(theta_values: Sequence[float]) -> Dict[str, Any]:
    """Return a deterministic circuit manifest for a frozen set of ``theta`` values."""
    circuits: List[Dict[str, Any]] = []
    for index, theta in enumerate(theta_values):
        qasm = bmv_qasm(float(theta))
        circuits.append(
            {
                "circuit_id": f"qg-bmv-zz-{index:03d}",
                "family": "bmv_zz_sweep",
                "model_id": "qg.bmv.zz.v1",
                "parameters": {"theta": float(theta)},
                "qasm": qasm,
                "qasm_sha256": sha256_text(qasm),
                "qubits": 2,
                "cregs": {"c": 2},
            }
        )
    null_qasm = bmv_null_qasm()
    circuits.append(
        {
            "circuit_id": "qg-bmv-zz-null",
            "family": "bmv_null",
            "model_id": "qg.bmv.zz.v1",
            "parameters": {"theta": 0.0},
            "qasm": null_qasm,
            "qasm_sha256": sha256_text(null_qasm),
            "qubits": 2,
            "cregs": {"c": 2},
        }
    )
    return {
        "schema": CIRCUIT_MANIFEST_SCHEMA,
        "family": "bmv_zz",
        "generator": "cqhecs.quantum_gravity.circuits.bmv_qasm",
        "theta_values": [float(t) for t in theta_values],
        "count": len(circuits),
        "circuits": circuits,
    }


def write_manifest(manifest: Dict[str, Any], directory: Path | str, *, embed_qasm: bool = True) -> Path:
    """Write ``CIRCUIT_MANIFEST.json`` and the per-circuit ``.qasm`` files.

    Each QASM file is written with LF endings; the manifest stores the SHA-256 of the
    exact bytes written, so the digest can be re-checked later.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stored = json.loads(json.dumps(manifest))  # deep copy
    for circuit in stored["circuits"]:
        qasm_file = directory / f"{circuit['circuit_id']}.qasm"
        qasm_file.write_bytes(circuit["qasm"].replace("\r\n", "\n").encode("ascii"))
        if not embed_qasm:
            circuit.pop("qasm", None)
        circuit["qasm_file"] = qasm_file.name
    target = directory / "CIRCUIT_MANIFEST.json"
    target.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def default_theta_values() -> Tuple[float, ...]:
    """A frozen, declared sweep (radians): zero, weak, intermediate, near-maximal."""
    import math

    return (0.0, math.pi / 8.0, math.pi / 4.0, math.pi / 2.0, 3.0 * math.pi / 4.0)
