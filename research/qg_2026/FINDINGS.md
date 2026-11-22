# FINDINGS.md

First-class record of positive, negative and inconclusive results. Session 1 established
the local foundation; the findings below are **engineering/model** findings, not physical
results about gravity.

## F-01 — No Quantum Gravity work existed prior to this campaign
Greenfield confirmation (BASELINE.md). All QG artifacts are new on this branch.

## F-02 — Open Quantum SDK key is a Client ID + Secret pair (not a single token)
The supplied `s_…` value authenticates as neither a JWT nor a complete key; docs and the
401 response agree. → `BLOCKED` (B-1). Consequence: the entire live-simulator/QPU branch of
the campaign is gated; local work is unaffected.

## F-03 — The BMV effective model has closed-form entanglement measures
`U_ZZ(θ)` on `|+>|+>` yields concurrence and negativity `|sin θ|` and `|sin θ|/2`
respectively (verified against the dense matrix in `tests/test_quantum_gravity_bmv.py`).
This supplies an independent oracle for the local slice **without** any QPU.

## F-04 — Majorana algebra + JW mapping reproduce the SYK spectrum
The seeded q=4 SYK Hamiltonian built from the Jordan–Wigner Majorana map is Hermitian,
respects the anticommutator algebra, and matches the dense independent spectrum to
float64 tolerance (`tests/test_quantum_gravity_syk.py`). No claim about spacetime.

## F-05 — Declared noise channels are trace-preserving; the witness degrades monotonically
The Kraus channels (dephasing, amplitude damping, single/two-qubit depolarizing) are
trace-preserving and positive on random states; the negativity witness falls
monotonically with the declared noise, and the θ=0 null stays separable under noise
(`tests/test_quantum_gravity_noise.py`). A modelled device, **not** a measurement.

## F-06 — Bounded Z2 lattice gauge toy model satisfies its gauge constraints exactly
The `qg.gauge.z2.v1` Hamiltonian `H = -Σ_p B_p` commutes with every Gauss generator
`G_v = Π X` (`[H,G_v]=0`), the generators and plaquette operators are involutions and
mutually commuting, the spectrum is integer, and the `+1` subspace is preserved
(`tests/test_quantum_gravity_gauge.py`). A finite constraint model; **not** a
quantum-gravity or LQG result.

## F-07 — Open Quantum QPU transport validated on Rigetti Cepheus-1-108q (real hardware)
Four preregistered jobs ran on a live `QPU` (Public/Standard, 4 Spark credits). Raw counts and
the calibration snapshot are under `research/qg_2026/raw/qpu_smoke/` with an evidence manifest.

| circuit | ideal support | observed in-support | dominant |
|---|---|---|---|
| basis (`x q0`) | {01} | 0.899 | `01` (0.899) |
| bell | {00,11} | 0.954 | `11` (0.485) |
| ghz3 | {000,111} | 0.906 | `000` (0.471) |
| mirror (`x;x`) | {00} | 0.979 | `00` (0.979) |

- Bit order is **little-endian** (q0 = rightmost character): `x q[0]` returns `01`.
- The `|1>`-preparation circuit is ~10% worse than the `|0>` return-to-zero (97.9%):
  consistent with excited-state decay / asymmetric readout. A **device-characterisation**
  result; not a gravity result.
- Count totals equal shots; measurement registers and calibration retrieval validated.

## F-08 — BMV effective-phase entanglement signal observed on a live QPU (Rigetti)
A 5-point phase scan (theta in {0, pi/8, pi/4, 3pi/8, pi/2}) in the Y(x)Z and Z(x)Y bases, plus
X(x)X at theta in {0, pi/4, pi/2}, 1000 shots each (13 jobs total). Raw counts + manifests are
under `research/qg_2026/raw/bmv_qpu/` and `raw/bmv_scan2/`; the combined scan is in
`processed/bmv_phase_scan.json`.

| theta | <Y(x)Z> | <Z(x)Y> | sin(theta) |
|---|---|---|---|
| 0 | +0.014 | +0.012 | 0.000 |
| pi/8 | +0.298 | +0.386 | 0.383 |
| pi/4 | +0.616 | +0.666 | 0.707 |
| 3pi/8 | +0.734 | +0.820 | 0.924 |
| pi/2 | +0.854 | +0.874 | 1.000 |

`<X(x)X>` = 0.954 / 0.818 / 0.808 at theta = 0 / pi/4 / pi/2.

- Monotone increase tracking `sin(theta)`; the measured correlator sits at **0.779-1.009x sin(theta)**
  across the YZ and ZY bases (device attenuation; the two bases differ by up to ~0.23 at pi/8), and
  the theta=0 **null control is consistent with 0** (no false signal). Per-point ratios and standard
  errors are in `processed/bmv_phase_scan.json` (YZ/ZY ratios: 0.779/0.871/0.794/0.854 and
  1.009/0.942/0.888/0.874).
- Noise attenuation is consistent with the Stage-2 smoke device characterisation; per-point
  finite-shot 95% intervals are in `processed/bmv_phase_scan.json`.
- Scientific status: the declared finite two-qubit **model** is reproduced on hardware within the
  noise envelope. This does **not** establish a gravitational interaction (see L-A3, L-A4).
## F-09 — Stage-4 SYK v1 run INVALID (exact-vs-Trotter mislabel + non-inverse mirror)
The first SYK submission (`raw/syk_qpu/`) compared the hardware against the **exact** matrix
exponential (ideal P(000) 0.428 forward, 1.0 mirror) while the circuit actually executed was the
**first-order Trotter** approximation (ideal 0.232584), and the "mirror" (`evolve(T)` then
`evolve(-T)`) is not a true inverse, so it was not a return-to-zero test. Re-simulating the
exported QASM confirms sim P(000)=0.2326 (forward) and 0.0103 (that mirror). The run is therefore
recorded as **INVALID** evidence; a corrected v3 (`qasm/syk_qpu_v3/`) with verified semantics and
a true `forward + forward.inverse()` mirror was preregistered and submitted. This is a
compilation-and-design finding, not a hardware result.

## F-10 — Stage-4 SYK QPU test INCONCLUSIVE (forward vs mirror mutually inconsistent)
Corrected v3 (`raw/syk_qpu_v3/`, semantics verified by re-simulation): the true return-to-zero
mirror gave **P(000)=0.947** [0.933, 0.961], but the forward circuit gave **P(000)=0.118**
[0.098, 0.138] against a Trotter ideal of **0.2326**.

These two hardware results are mutually inconsistent under a standard noise model. An Aer
depolarizing scan found **no single two-qubit error rate** that yields both a near-uniform
forward (0.118) and a near-perfect mirror (0.947): reproducing the forward needs strong noise,
which collapses the mirror to ~0.1–0.2. A pure forward state whose Z-basis distribution is flat
cannot in general be recovered to `000` at 94.7% by the exact inverse.

Conclusion: the SYK QPU comparison is **INCONCLUSIVE**; no SYK hardware claim is made. Candidate
follow-up: transpile forward and mirror through one pipeline (shared layout, e.g. the Qiskit
plugin sampler) and fit a device-noise model on held-out calibration. Recorded as a
first-class inconclusive result.

## F-11 — Reproducibility, the ⟨X⊗X⟩(θ) trend, and the SYK layout constraint
- **BMV drift repeat** (θ=π/2, identical circuit bytes, new run): ⟨Y⊗Z⟩ 0.820 (original 0.854,
  Δ −0.034), ⟨Z⊗Y⟩ 0.812 (original 0.874, Δ −0.062) — the Stage-3 result reproduces within ~0.06.
- **⟨X⊗X⟩(θ)** (5 points): 0.954 at θ=0, then 0.810 / 0.818 / 0.792 / 0.808 at θ = π/8, π/4,
  3π/8, π/2. Ideal is 1.0 for all θ. The θ=0 point is higher because `rz(0)` makes the two CXs
  cancel; for θ>0 the coherence-sensitive correlator is reduced ~20% by device noise (roughly
  flat in θ). A device-characterisation observation.
- **SYK no-rewiring retry (v4) FAILED**: the platform requires **contiguous virtual qubits** with
  `disable_qubit_rewiring`, so the 3-qubit circuit cannot be pinned to a connected physical triple
  (0/1/2 are disconnected). The 2 credits were refunded. This supports the F-10 hypothesis that the
  forward/mirror discrepancy is layout-related, and means F-10 cannot be resolved by this route.

## Negative / not-yet results
- No Trotter/randomised evolution yet (QG-SYK-02) → `NOT_RUN`.
- No QPU evidence (QG-SYK-03) → `BLOCKED` (B-1).
None of these may be reported as supported.
