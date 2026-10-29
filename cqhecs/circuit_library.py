"""
Small library of named circuits used by the CLI, tests and examples.

Keeping these in one place means the CLI, the differential tests and the
documentation all exercise the same well-understood circuits.
"""

from __future__ import annotations
from typing import Any, Callable, Dict

from qiskit import QuantumCircuit


def ghz(num_qubits: int = 8) -> QuantumCircuit:
    """GHZ state: maximally entangled, |00..0> + |11..1>."""
    qc = QuantumCircuit(num_qubits, name=f"ghz{num_qubits}")
    qc.h(0)
    for i in range(num_qubits - 1):
        qc.cx(i, i + 1)
    return qc


def bell() -> QuantumCircuit:
    """Bell state on 2 qubits."""
    qc = QuantumCircuit(2, name="bell")
    qc.h(0)
    qc.cx(0, 1)
    return qc


def clifford_chain(num_qubits: int = 6) -> QuantumCircuit:
    """Pure Clifford circuit: exact stabilizer tableau (Path A)."""
    qc = QuantumCircuit(num_qubits, name="clifford_chain")
    for q in range(num_qubits):
        qc.h(q)
    for q in range(num_qubits - 1):
        qc.cx(q, q + 1)
        qc.s(q)
    return qc


def low_t_rank(num_qubits: int = 4) -> QuantumCircuit:
    """A few T gates: suitable for the stabilizer rank decomposition (Path B)."""
    qc = QuantumCircuit(num_qubits, name="low_t_rank")
    qc.h(0)
    qc.cx(0, 1)
    qc.t(1)
    qc.tdg(0)
    qc.rz(0.37, 1)
    for q in range(2, num_qubits):
        qc.h(q)
    return qc


def mps_chain(num_qubits: int = 6, depth: int = 3) -> QuantumCircuit:
    """Moderate entanglement: suitable for the untruncated MPS (Path C)."""
    qc = QuantumCircuit(num_qubits, name="mps_chain")
    for _ in range(depth):
        for q in range(num_qubits):
            qc.ry(0.37, q)
        for q in range(num_qubits - 1):
            qc.cx(q, q + 1)
        for q in range(num_qubits):
            qc.rz(0.21, q)
    return qc


def sparse_pauli(num_qubits: int = 4, depth: int = 4) -> QuantumCircuit:
    """High T-count and high entanglement: suitable for Path D."""
    qc = QuantumCircuit(num_qubits, name="sparse_pauli")
    for _ in range(depth):
        for q in range(num_qubits):
            qc.h(q)
            qc.t(q)
            qc.rz(0.53, q)
        for q in range(num_qubits - 1):
            qc.cx(q, q + 1)
        qc.swap(0, num_qubits - 1)
    return qc


def toffoli_adder() -> QuantumCircuit:
    """1-bit full adder (a, b, cin -> sum, cout) from CCX/CX on inputs |111>."""
    qc = QuantumCircuit(4, name="toffoli_adder")
    qc.x([0, 1, 2])
    qc.ccx(0, 1, 3)
    qc.cx(0, 1)
    qc.ccx(1, 2, 3)
    qc.cx(1, 2)
    qc.cx(0, 1)
    return qc


def qft(num_qubits: int = 4) -> QuantumCircuit:
    """Quantum Fourier transform of a basis state, using controlled phases."""
    qc = QuantumCircuit(num_qubits, name=f"qft{num_qubits}")
    qc.x(0)
    for target in reversed(range(num_qubits)):
        qc.h(target)
        for control in reversed(range(target)):
            qc.cp(3.141592653589793 / 2 ** (target - control), control, target)
    for i in range(num_qubits // 2):
        qc.swap(i, num_qubits - 1 - i)
    return qc


def ising_trotter(num_qubits: int = 6, steps: int = 3) -> QuantumCircuit:
    """Transverse-field Ising Trotter steps built from RZZ and RX."""
    qc = QuantumCircuit(num_qubits, name=f"ising{num_qubits}")
    for _ in range(steps):
        for i in range(num_qubits - 1):
            qc.rzz(0.4, i, i + 1)
        for i in range(num_qubits):
            qc.rx(0.3, i)
    return qc


def _measured(circuit: QuantumCircuit) -> QuantumCircuit:
    """Returns a copy of `circuit` with all qubits measured."""
    measured = circuit.copy()
    measured.measure_all()
    return measured


#: Registry of builtin circuits addressable as ``name:<key>`` on the CLI.
BUILTIN_CIRCUITS: Dict[str, Callable[[], QuantumCircuit]] = {
    "ghz8": lambda: ghz(8),
    "ghz16": lambda: ghz(16),
    "bell": bell,
    "clifford6": lambda: clifford_chain(6),
    "low_t_rank4": lambda: low_t_rank(4),
    "mps6": lambda: mps_chain(6),
    "sparse_pauli4": lambda: sparse_pauli(4),
    "ghz8_measured": lambda: _measured(ghz(8)),
    "bell_measured": lambda: _measured(bell()),
    "toffoli_adder": lambda: _measured(toffoli_adder()),
    "qft4": lambda: qft(4),
    "ising6": lambda: ising_trotter(6),
}


def build_builtin_circuit(name: str) -> Any:
    """
    Returns the builtin circuit registered under `name`.

    Raises:
        ValueError: If `name` is not a known builtin.
    """
    try:
        return BUILTIN_CIRCUITS[name]()
    except KeyError as exc:
        raise ValueError(
            f"Unknown builtin circuit '{name}'. "
            f"Available: {sorted(BUILTIN_CIRCUITS)}"
        ) from exc