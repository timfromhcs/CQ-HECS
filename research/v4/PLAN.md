# v4 plan — measured noise, an independent oracle, and an experiment UI

**Status:** implemented 2026-10-30. See `FINDINGS.md` for the measured results.
**Inputs:** the 25 measured `r-io-7` jobs, the QuantumRings 128-qubit SDK
licence, and the existing v3 research corpus.
**Rule that does not change:** a correct refusal beats a plausible wrong
answer. Nothing below claims `P = NP`, proves the Exponential Time Hypothesis,
or invents a measurement.

---

## 0. What the inputs actually are

### 0.1 `r-io-7` is real measured data

25 jobs, 1000 shots, one backend (`rigetti:cepheus-1-108q`), circuits pinned by
SHA-256 before submission. The committed evidence is in
`research/v3/evidence/openquantum/rigetti_cepheus-1-108q/`.

The preregistered model `M-FIT` (mean readout + one CX parameter) is frozen.
Its verdict `SUPPORTED` stands and is not re-tuned.

### 0.2 The `OQ-02` qubit-0 marginal is not readout error

`EMULATOR_BUILD_PLAN.md` §1.1 reads `OQ-02` (`X` on all five qubits) as
`P(0|1) = 0.531` on qubit 0. Three probes contradict that reading:

| probe | circuit | qubit-0 marginal |
| :--- | :--- | ---: |
| `OQ-01` | `X` twice (identity) | `P(1) = 0.070` |
| `OQ-02` | `X` on all five | `P(1) = 0.469` |
| `OQ-03` | `X` on qubit 0 only | `P(1) = 0.507` |
| `OQ-09` | GHZ-5 (no `X`) | `P(1) = 0.486` |

A measurement error would depress `OQ-09` as well; it does not. `OQ-03` shows
the same ~50 % flip with a single `X`, so the defect follows the `X` gate on
qubit 0, not the readout. Any model that installs `0.531` as a readout matrix
over-corrects every GHZ circuit.

This is the v4 finding that drives W1.

### 0.3 QuantumRings is a local 128-qubit simulator, not a credit meter

`quantumrings.conf` unlocks `scarlet_quantum_rings` with `max_qubits = 128`.
The SDK runs locally; the account exposes a qubit ceiling, not a debit balance.
We use it as an **independent noiseless oracle** for cross-engine validation.
The key is read from the config file and is never printed, logged or committed.

### 0.4 `P = NP` and ETH remain open

The literature scan (`COMPLEXITY_AND_ETH.md`) records what is known and what
this software can measure. A finite SAT sweep is an empirical curve, not a
proof of ETH; a simulator run is not a complexity separation.

---

## 1. Work packages

### W1 — `M-FIT-2`: identify the `X` anomaly and fit per qubit

**Change:** new `cqhecs/noise_fit.py` and `cq-hecs noise-fit`.

- `p01[q]` from `OQ-01` (identity, so no `X` error).
- `p10[q]` from `OQ-02` for qubits without an anomaly.
- For qubits whose `OQ-02` marginal is an outlier (`|p10 - median| > 0.25`),
  fit `p10[q]` on the padded GHZ jobs instead and record why.
- Fit one global CX depolarizing parameter on `OQ-04`/`OQ-05`.
- Solve the `X` bit-flip probability from `OQ-03` given the fitted readout.
- Emit a versioned JSON profile with a `provenance` block and an explicit
  `identifiability` warning list.

**Acceptance:**

- Deterministic: two runs on the same input produce byte-identical JSON.
- On `r-io-7` the FIT residual is lower than `M-FIT`'s 0.2286.
- The held-out EVAL median ΔTV is lower than `M-FIT`'s −0.071905, reported as
  **exploratory and post-hoc**, with the same bootstrap seed.
- A test fails if `0.531` is installed as qubit 0 readout error.

### W2 — Sound SAT engine and phase-transition lab

**Change:** new `cqhecs/sat.py`, `cq-hecs sat solve|sweep`.

The existing `python_bridge` DPLL hashes only the first 32 assigned variables
and treats a hash hit as an explored branch. Beyond 32 variables that can prune
a fresh branch and report a false `UNSAT`; a timeout is also reported as
`UNSAT`. The new engine is separate and sound:

- status is `SAT`, `UNSAT` **only after exhaustive search**, or `UNKNOWN` on
  timeout;
- SAT models are verified clause by clause;
- UNSAT carries no proof object and says so;
- deterministic variable order and seed;
- counters for decisions, propagations, conflicts.

The UI adds a random 3-SAT sweep around ratio 4.26. The output is an empirical
runtime curve with an explicit “this is not ETH” note.

### W3 — Studio: a local experiment UI

**Change:** `cqhecs/studio/` served by `cq-hecs studio`.

Zero new runtime dependencies (Python standard library + the existing engine).

- **Circuit lab:** QASM or preset, ideal/noisy, forced path, shots, seed;
  histogram, path decision, state, error classes, wall time.
- **Noise lab:** `M-FIT` vs `M-FIT-2` vs measured `r-io-7`, per job and
  aggregate; sliders for readout and CX parameters; every number traceable.
- **SAT lab:** DIMACS or random 3-SAT, model/UNSAT/UNKNOWN, counters, sweep.
- **Evidence:** the 25 jobs, their digests, measured counts and TV table.
- **Research:** `P`/`NP`, ETH and the OpenAI-math corpus, with non-claims.

The server binds `127.0.0.1` by default, accepts a bounded JSON body, and
serves only bundled static files. It never reads credentials.

### W4 — Independent oracle cross-check (`r-qr-1`)

**Change:** `scripts/quantumrings_crosscheck.py`,
`research/v4/evidence/quantumrings/`.

Run a fixed noiseless suite on QuantumRings and compare it with exact CQ-HECS
distributions:

- GHZ at widths 2–128 (analytic distribution; Path A);
- QFT, random Clifford+T, brickwork, Grover, Bernstein–Vazirani,
  Deutsch–Jozsa, mirror circuits at ≤ 10 qubits (exact density matrix).

Each circuit is pinned by its gate list and QASM SHA-256. The report gives
TV distance, a shot-noise null quantile, and PASS/FAIL per circuit. A failure
is published, not hidden.

### W5 — Documentation and release hygiene

- `docs/STUDIO.md`, `research/v4/COMPLEXITY_AND_ETH.md`,
  `research/v4/FINDINGS.md`.
- README: quick start for the studio, corrected noise story, new SAT surface,
  and the same non-claims.
- CHANGELOG + version surfaces.

---

## 2. Order

| Order | Package | Depends on | Risk |
| ---: | :--- | :--- | :--- |
| 1 | W2 | — | low |
| 2 | W1 | — | medium (changes the noise story) |
| 3 | W3 | W1, W2 | medium (new surface) |
| 4 | W4 | W3 (to display) | low (local simulator) |
| 5 | W5 | all | low |

## 3. Non-goals

- No claim that the emulator is “nature”. It is a classical model; the
  noiseless oracle is still a classical simulator.
- No claim that cleaning noise recovers the true quantum state. Readout
  inversion is an assumption, reported as one.
- No `P = NP` claim, no ETH proof, no “quantum advantage” claim from a
  classical sweep.
- No credential in the repository, a log, or an artifact.

## 4. Definition of done

1. `pytest` green locally, including new tests.
2. Studio serves and every endpoint is covered by a test.
3. `r-qr-1` evidence committed with a PASS/FAIL table.
4. Local CI-equivalent checks green (`check_version`, truncation audit,
   compileall, flake8 fatal, wheel smoke).
5. Branch pushed; GitHub Actions green; failures fixed until green.
6. README states the corrected finding and the non-claims in the same place
   as the numbers.
