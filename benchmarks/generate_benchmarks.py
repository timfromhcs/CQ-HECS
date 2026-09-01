#!/usr/bin/env python3
"""
Benchmark instance generator for QASM circuits and DIMACS CNF files.
"""

import random
from pathlib import Path

out_dir = Path(__file__).parent
qasm_dir = out_dir / "qasm"
sat_dir = out_dir / "sat"
qasm_dir.mkdir(exist_ok=True)
sat_dir.mkdir(exist_ok=True)

# 1. GHZ-300 circuit
ghz_path = qasm_dir / "ghz_300.qasm"
with open(ghz_path, "w", encoding="utf-8") as f:
    f.write('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[300];\ncreg c[300];\nh q[0];\n')
    for i in range(299):
        f.write(f"cx q[{i}], q[{i+1}];\n")
    for i in range(300):
        f.write(f"measure q[{i}] -> c[{i}];\n")
print(f"Generated {ghz_path}")

# 2. QFT-300 circuit
qft_path = qasm_dir / "qft_300.qasm"
with open(qft_path, "w", encoding="utf-8") as f:
    f.write('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[300];\ncreg c[300];\n')
    for j in range(300):
        f.write(f"h q[{j}];\n")
        for k in range(1, min(8, 300 - j)):
            f.write(f"cp(pi/{2**k}) q[{j+k}], q[{j}];\n")
    for i in range(300):
        f.write(f"measure q[{i}] -> c[{i}];\n")
print(f"Generated {qft_path}")

# 3. Pigeonhole 6-into-5 CNF (Unsatisfiable)
pigeon_path = sat_dir / "pigeonhole_6_5.cnf"
clauses = []
for i in range(1, 7):
    clauses.append([(i - 1) * 5 + j for j in range(1, 6)])
for j in range(1, 6):
    for i1 in range(1, 7):
        for i2 in range(i1 + 1, 7):
            clauses.append([-((i1 - 1) * 5 + j), -((i2 - 1) * 5 + j)])

with open(pigeon_path, "w", encoding="utf-8") as f:
    f.write("c Pigeonhole principle: 6 pigeons in 5 holes (Unsatisfiable benchmark)\n")
    f.write(f"p cnf 30 {len(clauses)}\n")
    for c in clauses:
        f.write(" ".join(map(str, c)) + " 0\n")
print(f"Generated {pigeon_path} ({len(clauses)} clauses)")

# 4. Hard 3-SAT (50 variables, 218 clauses - Phase Transition Ratio)
uf50_path = sat_dir / "uf50_hard.cnf"
random.seed(1337)
n_vars = 50
n_clauses = 218
uf50_clauses = []
for _ in range(n_clauses):
    vars_chosen = random.sample(range(1, n_vars + 1), 3)
    clause = [v if random.random() > 0.5 else -v for v in vars_chosen]
    uf50_clauses.append(clause)

with open(uf50_path, "w", encoding="utf-8") as f:
    f.write("c Hard 3-SAT instance at phase transition ratio 4.36 (50 variables, 218 clauses)\n")
    f.write(f"p cnf {n_vars} {len(uf50_clauses)}\n")
    for c in uf50_clauses:
        f.write(" ".join(map(str, c)) + " 0\n")
print(f"Generated {uf50_path} ({len(uf50_clauses)} clauses)")
