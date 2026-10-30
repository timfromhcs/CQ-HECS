# CQ-HECS Release Notes

**Version:** 3.1.0
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to `dist/RELEASE_NOTES_v3.1.0.md`,
> prepends the exact source commit and required CI run, and appends the SHA256
> values of the final assets.

---

## 1. What this release is

`v3.1.0` is a feature release on the v3.0.0 Stable base. It adds four measured
surfaces and does not change the frozen `M-FIT` verdict:

1. **CQ-HECS Studio** — a loopback-only experiment UI (`cq-hecs studio`).
2. **A standalone sound SAT surface** — `cq-hecs sat solve|sweep`.
3. **An independent-engine cross-check** — 21 noiseless circuits against the
   QuantumRings simulator; 21/21 pass within finite-shot noise.
4. **A corrected `M-FIT-2` identification** — the 0.531 qubit-0 marginal in
   `OQ-02` is an `X`-gate anomaly, not readout error.

No new simulation path and no performance claim.

## 2. The corrected noise finding

v3.0.0 installed `OQ-02`'s 0.531 qubit-0 marginal as a readout matrix. The
probes disagree:

| probe | circuit | qubit-0 marginal |
| :--- | :--- | ---: |
| `OQ-01` | `X` twice (identity) | `P(1) = 0.070` |
| `OQ-02` | `X` on all five | `P(1) = 0.469` |
| `OQ-03` | `X` on qubit 0 only | `P(1) = 0.507` |
| `OQ-09` | GHZ-5, no `X` | `P(1) = 0.486` |

A readout matrix would depress `OQ-09`; it does not. The corrected fit uses
`p10[0] = 0.03` and an `X` bit-flip of 0.536.

| model | FIT TV | EVAL ΔTV vs ideal | 95 % CI | jobs closer |
| :--- | ---: | ---: | ---: | ---: |
| `M-FIT` (frozen) | 0.228625 | −0.071905 | [−0.135899, −0.006703] | 14/20 |
| `M-FIT-2` (corrected) | **0.120899** | **−0.105360** | [−0.132644, −0.042472] | **16/20** |

Against `M-FIT` the paired median is −0.026455, 95 % CI
[−0.041286, +0.020742], so H-V3-9 (“M-FIT-2 beats M-FIT”) remains **not
supported**. `M-FIT-2` is post-hoc and exploratory; confirmation needs a fresh
backend and split.

## 3. Studio

```bash
cq-hecs studio
# http://127.0.0.1:8765/
```

- Circuit lab: QASM or preset, forced path, ideal / `M-FIT` / `M-FIT-2`.
- Noise lab: per-qubit parameters, FIT residual, per-job measured-vs-model ΔTV,
  and a CX override.
- SAT lab: sound verdicts and a random-3-SAT sweep.
- Evidence: all 25 `r-io-7` jobs with circuit digests and provider job IDs.
- Research: `P` vs `NP`, ETH, OpenAI math, with non-claims.

The server uses only the standard library and the existing package. It binds to
loopback, serves only bundled files, and never reads credentials. See
`docs/STUDIO.md`.

## 4. SAT semantics

The standalone surface (`cqhecs.sat`, `cq-hecs sat`) reports:

- `SAT`: a model was found and verified clause by clause;
- `UNSAT`: exhaustive search finished; no proof object is produced;
- `UNKNOWN`: timeout or node budget; never reported as `UNSAT`.

The native bridge (`python_bridge.sat_engine`) keeps its v3.0.0
`SAT_VERIFIED`/`UNSAT_PROVEN`/`TIMEOUT_UNKNOWN` vocabulary.

## 5. Independent oracle

`r-qr-1`: GHZ widths 2–128, QFT, Clifford+T, brickwork, Grover,
Bernstein–Vazirani, Deutsch–Jozsa and a depth-30 mirror. Every total-variation
distance is below the 99th percentile of 400 finite-shot resamples from the
exact CQ-HECS distribution. QuantumRings is a classical simulator, not a QPU.

## 5.1 Fresh backend: IBM `ibm_fez`

The same 25 pinned circuits ran externally on IBM Quantum `ibm_fez` (job
`dbidem5ep8hs73ankcvg`, 1000 shots, 9 s QPU time):

- H-V3-8: **`SUPPORTED`**, median ΔTV −0.036642, 95 % CI [−0.045217, −0.027301],
  20/20 EVAL jobs closer than ideal.
- The corrected M-FIT-2 found **no anomaly**; qubit 0 is healthy
  (`OQ-03 = 0.994`). The 0.531 flip is Rigetti-specific.
- M-FIT-2 vs M-FIT: +0.001688, CI [+0.000327, +0.004045], 5/20 → slightly
  worse than the frozen mean. H-V3-9 remains not supported.

Evidence: `research/v4/evidence/ibm/`.

## 6. Verification

Run by CI on the final commit: Python suite, CTest, source mutation gate,
metamorphic self-test, static/package smoke, ASan/UBSan and the Python
3.12–3.14 matrix. The README records the numbers for the released tree.

## 7. Known limits

- `M-FIT-2` is post-hoc; one backend, one day, 1000 shots per job.
- QuantumRings is a classical simulator, not a QPU.
- The IonQ pilot is 100–200 shots and cannot evaluate H-V3-8.
- No `P = NP` or ETH claim. A finite SAT sweep is not a lower bound.
- The noise path is exact only up to 10 qubits; above that it refuses.

## 8. Install

```bash
python -m pip install cqhecs-3.1.0-py3-none-any.whl
cq-hecs doctor
cq-hecs studio
```

## 9. Documentation

- `CHANGELOG.md` — `[3.1.0]` section.
- `research/v4/FINDINGS.md` — corrected finding and reproductions.
- `research/v4/COMPLEXITY_AND_ETH.md` — complexity boundaries.
- `docs/STUDIO.md` — UI and HTTP API.
