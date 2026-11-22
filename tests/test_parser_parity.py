"""D10 (W3-02): Path A must not carry its own duplicate circuit parser.

``PathAStabilizerBackend`` used to define a private regex QASM parser and a
Qiskit-object parser beside ``cqhecs.circuit_parsing.parse_circuit``, even though
``execute`` already called the shared parser. They were dead code and a drift risk, so
they are removed. This pins their absence and that the shared parser agrees on a QASM
string and the equivalent Qiskit circuit.
"""
from qiskit import QuantumCircuit

from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.circuit_parsing import parse_circuit

QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""


def test_path_a_has_no_private_duplicate_parser():
    assert not hasattr(PathAStabilizerBackend, "_parse_qasm_str")
    assert not hasattr(PathAStabilizerBackend, "_parse_qiskit")


def _signature(circuit):
    instructions, num_qubits = parse_circuit(circuit)
    gates = [(ins[0], tuple(ins[1])) for ins in instructions if ins[0] not in ("measure", "barrier", "id")]
    return num_qubits, gates


def test_parse_circuit_agrees_for_qasm_and_the_equivalent_qiskit_circuit():
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    assert _signature(QASM) == _signature(qc)
