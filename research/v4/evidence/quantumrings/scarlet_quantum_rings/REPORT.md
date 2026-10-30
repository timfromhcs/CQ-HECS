# r-qr-1 — independent QuantumRings cross-check

- CQ-HECS: `2.6.0`
- QuantumRings SDK: `0.12.2` on `scarlet_quantum_rings`
- 4096 shots per circuit; 21 circuits
- Verdict: **PASS** (21/21 pass)

| circuit | qubits | TV | null p99 | z | verdict |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `ghz2` | 2 | 0.018066 | 0.019783 | +2.61 | PASS |
| `ghz3` | 3 | 0.000732 | 0.018313 | -1.25 | PASS |
| `ghz5` | 5 | 0.001221 | 0.018069 | -1.08 | PASS |
| `ghz10` | 10 | 0.004150 | 0.019534 | -0.46 | PASS |
| `ghz20` | 20 | 0.002441 | 0.021245 | -0.76 | PASS |
| `ghz30` | 30 | 0.006836 | 0.019531 | +0.15 | PASS |
| `ghz64` | 64 | 0.016357 | 0.021973 | +2.05 | PASS |
| `ghz100` | 100 | 0.007812 | 0.019534 | +0.39 | PASS |
| `ghz128` | 128 | 0.007812 | 0.016858 | +0.47 | PASS |
| `qft4` | 4 | 0.023193 | 0.035422 | -0.19 | PASS |
| `qft6` | 6 | 0.046143 | 0.061533 | -0.72 | PASS |
| `qft8` | 8 | 0.093994 | 0.110596 | -1.14 | PASS |
| `clifford_t6_d20` | 6 | 0.027588 | 0.031016 | +2.18 | PASS |
| `clifford_t8_d24` | 8 | 0.018066 | 0.028813 | +0.28 | PASS |
| `clifford_t10_d28` | 10 | 0.025146 | 0.036624 | +0.22 | PASS |
| `brickwork6_l3` | 6 | 0.034976 | 0.050115 | -1.09 | PASS |
| `brickwork8_l3` | 8 | 0.065777 | 0.082951 | -1.58 | PASS |
| `grover3_111` | 3 | 0.015869 | 0.027593 | -0.09 | PASS |
| `bv5_10110` | 6 | 0.000000 | 0.000000 | +0.00 | PASS |
| `dj4_balanced` | 5 | 0.000000 | 0.000000 | +0.00 | PASS |
| `mirror6_d30` | 6 | 0.000000 | 0.000000 | +0.00 | PASS |

QuantumRings is a classical simulator, not a QPU. A pass means the two
independent engines agree within finite-shot noise on these circuits.
It is not a hardware claim, a complexity result, or a P = NP statement.
