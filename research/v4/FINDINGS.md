# v4 findings — measured noise, an independent oracle, and a sound SAT engine

**Date:** 2026-10-30. **Status:** measured and reproducible; the noise model is
post-hoc and exploratory.

This file records what changed after reading the 25 measured `r-io-7` jobs and
running an independent noiseless cross-check. It does not revise the frozen
`M-FIT` verdict.

---

## 1. The `OQ-02` qubit-0 marginal is an `X`-gate anomaly, not readout

`research/v3/EMULATOR_BUILD_PLAN.md` §1.1 interpreted `OQ-02` (`X` on all five
qubits) as `P(0|1) = 0.531` on qubit 0. Four probes contradict that:

| probe | circuit | qubit-0 marginal | what it means |
| :--- | :--- | ---: | :--- |
| `OQ-01` | `X` twice (identity) | `P(1) = 0.070` | readout `P(1|0)` |
| `OQ-02` | `X` on all five | `P(1) = 0.469` | readout + `X` error |
| `OQ-03` | `X` on qubit 0 only | `P(1) = 0.507` | the same flip with one `X` |
| `OQ-09` | GHZ-5, no `X` | `P(1) = 0.486` | no flip without `X` |

A measurement assignment error would depress `OQ-09` too. It does not. The
defect follows the `X` gate on qubit 0, so installing `0.531` as a readout
matrix over-corrects every GHZ circuit. `M-FIT-2` therefore fits `p10[0]` on the
padded GHZ ladder and reports the `X` bit-flip separately.

**Result:** `p10[0] = 0.03`, `X` bit-flip on qubit 0 `= 0.536`, all other
qubits `0`.

## 2. `M-FIT-2` fits better and predicts the hold-out better

`M-FIT-2` uses per-qubit readout, one global CX depolarizing term, and an
`X` bit-flip on the anomalous qubit. It is **post-hoc**: it was written after
the 25 jobs existed.

| model | FIT residual (mean TV on `OQ-04/05`) | EVAL median ΔTV | 95 % CI | EVAL jobs closer |
| :--- | ---: | ---: | ---: | ---: |
| `M-FIT` (frozen, preregistered) | 0.228625 | −0.071905 | [−0.135899, −0.006703] | 14/20 |
| `M-FIT-2` (this work) | **0.120899** | **−0.105360** | [−0.132644, −0.042472] | **16/20** |

The frozen `H-V3-8` verdict is unchanged: `SUPPORTED`. `M-FIT-2` is a mechanism
check on the same data, **not** a preregistered confirmation. Confirmation needs
a fresh backend and a fresh split. The artifact is
`research/v4/evidence/r-io-7/mfit2.json`; the scored rows are in
`mfit2_evaluation.json`.

The fit does **not** claim a 1-qubit gate error: on the padded GHZ jobs a
uniform 1q depolarizing term is collinear with the CX term. The model keeps it
at zero and says so in `identifiability.one_qubit_gate_error`.

## 3. Independent oracle: 21/21 circuits agree with QuantumRings

QuantumRings is a classical simulator (CPU backend here), not a QPU. It is used
as an independent noiseless oracle. 21 circuits, 4096 shots each, widths 2–128:

- GHZ at 2, 3, 5, 10, 20, 30, 64, 100, 128;
- QFT at 4, 6, 8;
- random Clifford+T at 6, 8, 10;
- brickwork at 6, 8;
- Grover-3, Bernstein–Vazirani-5, Deutsch–Jozsa-4, a depth-30 mirror.

Every total-variation distance is below the 99th percentile of 400 finite-shot
resamples from the exact CQ-HECS distribution. Aggregate: **PASS, 21/21**,
maximum TV 0.1038 (the 8-qubit QFT, whose distribution is spread over 256
outcomes at 4096 shots). Evidence:
`research/v4/evidence/quantumrings/scarlet_quantum_rings/`.

This validates the exact paths against a second engine. It is not a hardware
claim and not a complexity result.

## 4. The old SAT demonstrator can report a false `UNSAT`

`python_bridge/sat_engine.py` hashes only the first 32 assigned variables and
treats a table hit as an already-explored branch. Above 32 variables that can
prune a fresh branch. It also returns `(False, None)` on timeout, which `solve`
reports as `UNSAT`, with `verified = True`.

The supported engine (`cqhecs/sat.py`) is separate:

- `SAT` only with a clause-by-clause verified model;
- `UNSAT` only after exhaustive search, with **no** proof object and an
  explicit note;
- `UNKNOWN` on timeout or node budget;
- deterministic counters and variable order.

`tests/test_sat_soundness.py` checks the result against brute force for small
formulas, the pigeonhole benchmark, contradictory units, malformed DIMACS, a
node-budget cutoff, and determinism.

## 5. What is not claimed

- The emulator is not nature. A readout inversion is an assumption, not a
  measurement of the true state.
- `M-FIT-2` is not confirmed on a fresh backend.
- QuantumRings is not quantum hardware.
- The SAT sweep is not a proof of ETH and says nothing about `P = NP`.
- No credential is written to the repository, an artifact, or a log.

## 6. Reproduce

```bash
python -m cqhecs.cli noise-fit \
  --data-dir research/v3/evidence/openquantum/rigetti_cepheus-1-108q \
  --out research/v4/evidence/r-io-7

python scripts/build_studio_data.py
python -m cqhecs.cli sat solve benchmarks/sat/pigeonhole_6_5.cnf
python -m cqhecs.cli sat sweep --sizes 10,15,20,25 --ratios 3.0,4.26,6.0 --trials 5
python scripts/quantumrings_crosscheck.py --shots 4096
python -m cqhecs.cli studio
```
