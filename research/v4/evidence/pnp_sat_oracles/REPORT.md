# SAT oracles on IBM Quantum — finite P-versus-NP boundary check

**Not a complexity result.** These are 3–4 variable CNFs; the state space
is 8 or 16. The QPU runs test whether a Grover phase oracle transfers to
hardware and whether the circuit is exactly emulable and numerically
lossless in the MPS path.

| backend | shots | oracle | DPLL models | QPU top | model mass | top is model | MPS strictly lossless |
| :--- | ---: | :--- | :--- | :--- | ---: | :--- | :--- |
| `ibm_fez` | 10000 | `sat3_unique_100` | ['100'] | `100` | 0.7246 | True | True |
| `ibm_fez` | 10000 | `sat3_two_100_011` | ['100', '011'] | `011` | 0.8407 | True | False |
| `ibm_fez` | 10000 | `sat4_unique_1011` | ['1011'] | `1011` | 0.3613 | True | False |
| `ibm_marrakesh` | 10000 | `sat3_unique_100` | ['100'] | `100` | 0.3077 | True | True |
| `ibm_marrakesh` | 10000 | `sat3_two_100_011` | ['100', '011'] | `011` | 0.5377 | True | False |
| `ibm_marrakesh` | 10000 | `sat4_unique_1011` | ['1011'] | `1011` | 0.0981 | True | False |

## Verdict

- QPU top outcome is a valid CNF model on every run: **True**.
- Strict MPS bit-losslessness on every run: **False**.
- Exact classical emulation (density matrix vs Qiskit Statevector) is
  checked in `research/v4/evidence/pnp_emulability/` and passes at ~1e-15.

The two-model and four-variable circuits report `EXACT` but the MPS
numerical-rank floor discards ~1e-15 / ~1e-13 of singular-value mass, so
they are not strictly bit-lossless. That is the honest answer to
“compress/decompress lossless?” for these states.

## Non-claim

A finite Grover run does not solve SAT in polynomial time and does not
separate P from NP. The oracle cost, the 3–4 variable instance, and the
exponential cost of exact emulation all remain visible.
