// Bit-order / deterministic basis test: prepare |10> (q0 excited), then measure.
// Expect a single deterministic bitstring; which string reveals the bit order.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;
