"""Shared conformance corpus (T6-05 / W13): one set of cases, every surface.

    python web/scripts/export_shared_conformance.py            # write the fixture
    python web/scripts/export_shared_conformance.py --check    # exit 1 if the file is stale

Writes ``web/tests/fixtures/shared_conformance.json`` (schema ``hcs.conformance.shared.v1``).

The corpus is consumed by three independent implementations:

* Python reference: ``tests/test_web_shared_conformance.py`` (Qiskit Statevector oracle, the
  four-path router, Path C dense contraction);
* browser WebAssembly f64: ``web/tests/shared_conformance.test.ts`` (Node) and
  ``web/e2e/conformance.spec.ts`` (the real page and worker);
* browser WebGPU f32: ``web/e2e/conformance.spec.ts`` when the machine exposes an adapter,
  otherwise reported NOT_RUN. The Node test additionally runs a clearly labelled f32 *emulation*
  of the WGSL kernel (Math.fround); that is evidence for the tolerance, not a WebGPU result.

Semantics stated in the file and checked by every consumer:

* qubit ``q`` is bit ``q`` of the basis index (little endian, Qiskit convention);
* a count key lists classical bits ``c[n-1] ... c[0]`` (leftmost character is the highest bit);
* with no ``measure`` statement every qubit is measured into the classical bit of the same index;
* phase policy: amplitudes agree up to one global phase (it is unobservable); probabilities agree
  exactly (within tolerance). Relative phases are compared: ``s-interference`` fails if S is
  conjugated;
* the state norm is 1 within tolerance.

Features that are NOT common are written into the case, not hidden: the Python four-path
simulator refuses classical-bit remapping and mid-circuit measurement, so those cases carry
``python.status = "REFUSED"``; the browser executes them. The test asserts the refusal, so a
silent change of either side shows up as a failing test.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT = REPO_ROOT / "web" / "tests" / "fixtures" / "shared_conformance.json"
SCHEMA = "hcs.conformance.shared.v1"
TOLERANCE_F64 = 1e-12
GPU_MAX_QUBITS = 12
GPU_TOLERANCE = {"max_abs_probability_diff": 5e-6, "total_variation": 1e-5}


def qasm(qubits: int, clbits: int, body: List[str]) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{qubits}];"]
    if clbits:
        lines.append(f"creg c[{clbits}];")
    lines.extend(f"{statement};" for statement in body)
    return "\n".join(lines) + "\n"


def random_circuit(num_qubits: int, depth: int, seed: int) -> List[str]:
    """Deterministic mixed circuit over gates both implementations share."""
    rng = random.Random(seed)
    one = ["h", "s", "t", "x", "z", "sdg", "tdg"]
    body: List[str] = [f"h q[{q}]" for q in range(num_qubits)]
    for _ in range(depth):
        kind = rng.choice(["one", "one", "rot", "cx", "cz", "cp", "swap", "ccx"])
        qs = rng.sample(range(num_qubits), 3 if kind == "ccx" else (2 if kind in ("cx", "cz", "cp", "swap") else 1))
        if kind == "one":
            body.append(f"{rng.choice(one)} q[{qs[0]}]")
        elif kind == "rot":
            body.append(f"{rng.choice(['rx', 'ry', 'rz'])}({rng.uniform(0.1, 3.0):.6f}) q[{qs[0]}]")
        elif kind == "cp":
            body.append(f"cp({rng.uniform(0.1, 3.0):.6f}) q[{qs[0]}],q[{qs[1]}]")
        elif kind == "ccx":
            body.append(f"ccx q[{qs[0]}],q[{qs[1]}],q[{qs[2]}]")
        else:
            body.append(f"{kind} q[{qs[0]}],q[{qs[1]}]")
    return body


def qft_body(n: int) -> List[str]:
    body: List[str] = ["x q[0]", "x q[2]"] if n >= 3 else ["x q[0]"]
    for j in range(n):
        body.append(f"h q[{j}]")
        for k in range(j + 1, n):
            body.append(f"cp({math.pi / 2 ** (k - j):.16f}) q[{k}],q[{j}]")
    for a in range(n // 2):
        body.append(f"swap q[{a}],q[{n - 1 - a}]")
    return body


def case_specs() -> List[Dict[str, Any]]:
    """name, family, QASM, the intent of the case."""
    ghz12 = ["h q[0]"] + [f"cx q[{i}],q[{i + 1}]" for i in range(11)]
    return [
        {"name": "bell", "family": "entanglement", "qasm": qasm(2, 0, ["h q[0]", "cx q[0],q[1]"])},
        {"name": "ghz-3", "family": "entanglement", "qasm": qasm(3, 0, ["h q[0]", "cx q[0],q[1]", "cx q[1],q[2]"])},
        {"name": "ghz-12", "family": "gpu-range-edge", "qasm": qasm(12, 0, ghz12)},
        {"name": "s-interference", "family": "phase", "qasm": qasm(1, 0, ["h q[0]", "s q[0]", "h q[0]"])},
        {"name": "t-interference", "family": "phase", "qasm": qasm(1, 0, ["h q[0]", "t q[0]", "h q[0]", "t q[0]", "h q[0]"])},
        {"name": "rx-rz", "family": "phase", "qasm": qasm(1, 0, ["rx(0.7) q[0]", "rz(0.4) q[0]"])},
        {"name": "global-phase-only", "family": "phase-policy", "qasm": qasm(1, 0, ["rz(1.0) q[0]"])},
        {"name": "controlled-phase", "family": "phase", "qasm": qasm(2, 0, ["h q[0]", "h q[1]", "cp(1.0471975511965976) q[0],q[1]", "h q[0]", "h q[1]"])},
        {"name": "control-direction", "family": "operand-order", "qasm": qasm(2, 0, ["x q[0]", "cx q[1],q[0]"])},
        {"name": "endianness-x-q0", "family": "endianness", "qasm": qasm(3, 0, ["x q[0]"])},
        {"name": "endianness-x-q2", "family": "endianness", "qasm": qasm(3, 0, ["x q[2]"])},
        {"name": "endianness-x-q1-q3", "family": "endianness", "qasm": qasm(4, 0, ["x q[1]", "x q[3]"])},
        {"name": "toffoli", "family": "multi-control", "qasm": qasm(3, 0, ["x q[0]", "x q[1]", "ccx q[0],q[1],q[2]"])},
        {"name": "swap-network", "family": "permutation", "qasm": qasm(3, 0, ["x q[0]", "swap q[0],q[2]", "swap q[2],q[1]"])},
        {"name": "qft-4", "family": "qft", "qasm": qasm(4, 0, qft_body(4))},
        {"name": "mixed-6-seed11", "family": "mixed-random", "qasm": qasm(6, 0, random_circuit(6, 30, 11))},
        {"name": "mixed-10-seed7", "family": "gpu-range", "qasm": qasm(10, 0, random_circuit(10, 40, 7))},
        # Measurement mapping.
        {"name": "measure-identity", "family": "measurement-map", "qasm": qasm(3, 3, ["x q[0]", "x q[2]", "measure q[0] -> c[0]", "measure q[1] -> c[1]", "measure q[2] -> c[2]"])},
        {"name": "measure-partial", "family": "measurement-map", "qasm": qasm(3, 1, ["x q[1]", "measure q[1] -> c[0]"])},
        {"name": "measure-remap", "family": "measurement-map", "qasm": qasm(3, 3, ["x q[0]", "measure q[0] -> c[2]", "measure q[1] -> c[0]", "measure q[2] -> c[1]"])},
        {"name": "measure-mid-circuit", "family": "dynamic", "qasm": qasm(2, 2, ["x q[0]", "measure q[0] -> c[0]", "cx q[0],q[1]", "measure q[1] -> c[1]"])},
    ]


DIVERGENCES: Dict[str, str] = {}  # C1-FIND-01 fixed in Wave D1: repeated operands are refused everywhere


def refusal_specs() -> List[Dict[str, Any]]:
    """Inputs that every surface must refuse, never run."""
    return [
        {"name": "refuse-unknown-gate", "qasm": qasm(1, 0, ["frobnicate q[0]"]), "why": "gate not in any manifest"},
        {"name": "refuse-qubit-out-of-range", "qasm": qasm(2, 0, ["h q[2]"]), "why": "operand outside the register"},
        {"name": "refuse-repeated-operand", "qasm": qasm(2, 0, ["cx q[0],q[0]"]), "why": "control equals target"},
        {"name": "refuse-no-register", "qasm": 'OPENQASM 2.0;\ninclude "qelib1.inc";\n', "why": "no qreg"},
    ]


# ---------------------------------------------------------------- oracle (Qiskit only)

def oracle(text: str) -> Dict[str, Any]:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    circuit = QuantumCircuit.from_qasm_str(text)
    unitary = QuantumCircuit(circuit.num_qubits)
    measures: List[Tuple[int, int]] = []
    for inst in circuit.data:
        qs = [circuit.find_bit(q).index for q in inst.qubits]
        if inst.operation.name == "measure":
            measures.append((qs[0], circuit.find_bit(inst.clbits[0]).index))
        elif inst.operation.name != "barrier":
            unitary.append(inst.operation, qs)
    state = Statevector.from_instruction(unitary)
    names = [inst.operation.name for inst in circuit.data if inst.operation.name != "barrier"]
    first = names.index("measure") if "measure" in names else len(names)
    terminal = all(name == "measure" for name in names[first:])
    return {"circuit": circuit, "state": state, "measures": measures, "num_clbits": circuit.num_clbits, "terminal": terminal}


def classical_distribution(probabilities: np.ndarray, num_qubits: int, pairs: List[Tuple[int, int]], width: int) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for index, p in enumerate(probabilities):
        if p < 1e-15:
            continue
        value = 0
        for q, c in pairs:
            if (index >> q) & 1:
                value |= 1 << c
        key = format(value, f"0{width}b")
        out[key] = out.get(key, 0.0) + float(p)
    return dict(sorted(out.items()))


def sampler_counts(circuit, shots: int) -> Dict[str, int]:
    """Second, sampling-based Qiskit view of the measured register (deterministic cases)."""
    from qiskit.primitives import StatevectorSampler

    result = StatevectorSampler(seed=5).run([circuit], shots=shots).result()[0]
    register = circuit.cregs[0].name
    return dict(getattr(result.data, register).get_counts())


def python_status(text: str) -> Dict[str, Any]:
    from cqhecs.router import EntanglementAdaptiveRouter

    try:
        result = EntanglementAdaptiveRouter().route_and_execute(text, shots=64, seed=1)
        return {"status": "SUPPORTED", "state": getattr(getattr(result, "state", None), "value", str(getattr(result, "state", "")))}
    except Exception as exc:  # noqa: BLE001 - the type name is the recorded evidence
        return {"status": "REFUSED", "error_type": type(exc).__name__, "reason": str(exc).splitlines()[0][:160]}


def build_case(spec: Dict[str, Any]) -> Dict[str, Any]:
    info = oracle(spec["qasm"])
    state = info["state"]
    n = state.num_qubits
    probs = np.asarray(state.probabilities(), dtype=float)
    if abs(float(probs.sum()) - 1.0) > 1e-12:
        raise SystemExit(f"{spec['name']}: probabilities sum to {probs.sum()!r}")
    explicit_pairs = list(info["measures"])
    pairs = explicit_pairs if explicit_pairs else [(q, q) for q in range(n)]
    width = max(info["num_clbits"], max(c for _, c in pairs) + 1) if explicit_pairs else n
    distribution = classical_distribution(probs, n, pairs, width)
    deterministic = len(distribution) == 1
    entry: Dict[str, Any] = {
        "name": spec["name"],
        "family": spec["family"],
        "qasm": spec["qasm"],
        "num_qubits": n,
        "num_clbits": width,
        "measurement_map": [[q, c] for q, c in pairs],
        "measurement_map_explicit": bool(explicit_pairs),
        "probabilities_sparse": {str(i): float(p) for i, p in enumerate(probs) if p > 1e-15},
        "classical_distribution": distribution,
        "deterministic_counts": deterministic,
        "phase_policy": "amplitudes equal up to one global phase; probabilities exact",
        # WebGPU refuses mid-circuit measurement (typed refusal), so only
        # terminal-measurement circuits are in its declared range.
        "webgpu": {"in_declared_range": n <= GPU_MAX_QUBITS and bool(info["terminal"])},
        "python": python_status(spec["qasm"]),
    }
    if n <= 4:
        entry["amplitudes"] = [[float(a.real), float(a.imag)] for a in np.asarray(state.data)]
    entry["terminal_measurements"] = bool(info["terminal"])
    if explicit_pairs and deterministic and info["terminal"]:
        sampled = sampler_counts(info["circuit"], 512)
        if set(sampled) != set(distribution) or sampled[next(iter(distribution))] != 512:
            raise SystemExit(f"{spec['name']}: Qiskit sampler disagrees with the analytic classical map: {sampled} vs {distribution}")
    return entry


def build() -> Dict[str, Any]:
    import qiskit

    cases = [build_case(spec) for spec in case_specs()]
    refusals = []
    for spec in refusal_specs():
        entry = {**spec, "expected": "REFUSED", "python": python_status(spec["qasm"])}
        if entry["python"]["status"] != "REFUSED":
            # Recorded, not hidden: the corpus keeps the expected refusal and names the divergence
            # (finding C1-FIND-01: the Python parser accepts a repeated operand and returns EXACT).
            entry["known_divergence"] = DIVERGENCES.get(spec["name"], "UNEXPLAINED")
            if entry["known_divergence"] == "UNEXPLAINED":
                raise SystemExit(f"{spec['name']}: the Python side did not refuse and no divergence is recorded")
        refusals.append(entry)
    return {
        "schema": SCHEMA,
        "generated_by": "web/scripts/export_shared_conformance.py",
        "oracle": f"Qiskit {qiskit.__version__} Statevector (+ StatevectorSampler for measured deterministic cases)",
        "semantics": {
            "endianness": "little: qubit q is bit q of the basis index",
            "count_key_order": "c[n-1] ... c[0], leftmost character is the highest classical bit",
            "default_measurement": "no measure statement: every qubit q is read into classical bit q",
            "phase_policy": "amplitudes are compared after removing one global phase; probabilities directly",
            "norm": "state norm is 1 within the tolerance",
        },
        "tolerance_f64": TOLERANCE_F64,
        "webgpu": {
            "precision": "f32",
            "declared_max_qubits": GPU_MAX_QUBITS,
            "tolerance": GPU_TOLERANCE,
            "note": "outside this range or without an adapter the WebGPU column is NOT_RUN, never green",
        },
        "cases": cases,
        "refusals": refusals,
    }


FLOAT_DECIMALS = 12


def _quantize(obj: Any) -> Any:
    """Round every float to FLOAT_DECIMALS so regeneration is byte-identical across BLAS/CPU builds.

    The last 1-2 ulps of a float64 probability differ between platforms (observed: ...97 vs ...96 on
    Linux). Consumers compare with tolerances far above 1e-12, so no semantic information is lost.
    """
    if isinstance(obj, float):
        return round(obj, FLOAT_DECIMALS) + 0.0
    if isinstance(obj, dict):
        return {k: _quantize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_quantize(v) for v in obj]
    return obj


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when the committed fixture differs")
    args = parser.parse_args(argv)
    text = json.dumps(_quantize(build()), indent=2) + "\n"
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current.replace("\r\n", "\n") != text:
            print(f"STALE: {OUTPUT.relative_to(REPO_ROOT)} differs from a fresh generation", file=sys.stderr)
            return 1
        print("shared conformance fixture is current")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}: {len(json.loads(text)['cases'])} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
