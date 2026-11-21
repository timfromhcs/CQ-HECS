// Bell |00>+|11>. Expect ~50% one string, ~50% its bitwise complement.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
