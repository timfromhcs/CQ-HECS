# P versus NP: exact-classical-emulability check

**Finite check, not a complexity result.** These are 2–5 qubit circuits.

| probe | qubits | gates | support | CQ-HECS vs Qiskit Statevector TV | exact classically emulable |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `universal_ct5_d40` | 5 | 40 | 8 | 3.61e-16 | PASS |
| `iqp5_l3` | 5 | 36 | 32 | 1.76e-15 | PASS |
| `grover4_1011` | 4 | 202 | 16 | 2.62e-15 | PASS |
| `simon2_11` | 4 | 7 | 16 | 3.33e-16 | PASS |
| `sat3_grover_100` | 3 | 73 | 8 | 4.69e-16 | PASS |
| `qft5_10101` | 5 | 58 | 32 | 4.82e-16 | PASS |
| `ghz5` | 5 | 5 | 2 | 1.11e-16 | PASS |
| `mirror5_d30` | 5 | 60 | 1 | 9.99e-16 | PASS |

## QPU comparison

| backend | shots | median TV ideal | median TV M-FIT | median TV M-FIT-2 | SAT found |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `ibm_fez` | 10000 | 0.1275 | 0.0958 | 0.0961 | [True] |
| `ibm_marrakesh` | 10000 | 0.1367 | 0.1018 | 0.0997 | [True] |
| `ibm_marrakesh` | 50000 | 0.1399 | 0.1049 | 0.1026 | [True] |

## SAT probe

- CNF: `p cnf 3 7`
- DPLL: `SAT`, model `100`
- QPU outcomes: [{'backend': 'ibm_fez', 'shots': 10000, 'sat_top': '100', 'sat_found': True}, {'backend': 'ibm_marrakesh', 'shots': 10000, 'sat_top': '100', 'sat_found': True}, {'backend': 'ibm_marrakesh', 'shots': 50000, 'sat_top': '100', 'sat_found': True}]

## What this does not say

Density-matrix emulation costs `O(4^n)`; the circuits are 2–5 qubits.
A finite QPU experiment cannot decide P versus NP, prove ETH, or
establish quantum advantage. The SAT probe is a three-variable instance.
