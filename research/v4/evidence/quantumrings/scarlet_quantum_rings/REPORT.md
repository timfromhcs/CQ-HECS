# r-qr-1 — independent QuantumRings cross-check

- CQ-HECS: `3.1.0`
- QuantumRings SDK: `0.12.2` on `scarlet_quantum_rings`
- 4096 shots per circuit; 21 circuits
- Verdict: **PASS** (21/21 pass)

| circuit | qubits | TV | null p99 | z | verdict |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `ghz2` | 2 | 0.002686 | 0.019783 | -0.77 | PASS |
| `ghz3` | 3 | 0.014648 | 0.018313 | +2.02 | PASS |
| `ghz5` | 5 | 0.002197 | 0.018069 | -0.86 | PASS |
| `ghz10` | 10 | 0.011963 | 0.019534 | +1.16 | PASS |
| `ghz20` | 20 | 0.000977 | 0.021245 | -1.06 | PASS |
| `ghz30` | 30 | 0.000244 | 0.019531 | -1.35 | PASS |
| `ghz64` | 64 | 0.000000 | 0.021973 | -1.28 | PASS |
| `ghz100` | 100 | 0.006592 | 0.019534 | +0.13 | PASS |
| `ghz128` | 128 | 0.002686 | 0.016858 | -0.77 | PASS |
| `qft4` | 4 | 0.018555 | 0.035422 | -1.14 | PASS |
| `qft6` | 6 | 0.053955 | 0.061533 | +0.99 | PASS |
| `qft8` | 8 | 0.096191 | 0.110596 | -0.66 | PASS |
| `clifford_t6_d20` | 6 | 0.015869 | 0.031016 | -0.15 | PASS |
| `clifford_t8_d24` | 8 | 0.009766 | 0.028813 | -1.55 | PASS |
| `clifford_t10_d28` | 10 | 0.025635 | 0.036624 | +0.32 | PASS |
| `brickwork6_l3` | 6 | 0.041923 | 0.050115 | +0.42 | PASS |
| `brickwork8_l3` | 8 | 0.067301 | 0.082951 | -1.24 | PASS |
| `grover3_111` | 3 | 0.020020 | 0.027593 | +0.85 | PASS |
| `bv5_10110` | 6 | 0.000000 | 0.000000 | +0.00 | PASS |
| `dj4_balanced` | 5 | 0.000000 | 0.000000 | +0.00 | PASS |
| `mirror6_d30` | 6 | 0.000000 | 0.000000 | +0.00 | PASS |

QuantumRings is a classical simulator, not a QPU. A pass means the two
independent engines agree within finite-shot noise on these circuits.
It is not a hardware claim, a complexity result, or a P = NP statement.
