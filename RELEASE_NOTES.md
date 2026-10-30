# CQ-HECS Release Notes

**Version:** 2.6.0
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to `dist/RELEASE_NOTES_v2.6.0.md`,
> prepends the exact source commit and required CI run, and appends the SHA256
> values of the final assets.

---

## 1. What this release is

`v2.6.0` adds three measured surfaces on top of the v2.5.2 corrections:

1. **`M-FIT-2`** — a per-qubit noise fit from the 25 measured `r-io-7` jobs,
   plus the identification correction that motivated it.
2. **CQ-HECS Studio** — a local experiment UI (`cq-hecs studio`) for circuits,
   noise, SAT and the measured evidence.
3. **A sound SAT engine** — `cq-hecs sat solve|sweep`, with explicit
   `SAT`/`UNSAT`/`UNKNOWN` semantics.

It also adds an independent-engine cross-check (`r-qr-1`, 21/21 circuits) and a
five-job IonQ pilot plus a higher-statistics identification batch
(`r-qpu-pilot-1`) that spent the two 25-credit Spark balances. Both batches are
queued as of 2026-10-30; neither is a quantum-hardware claim for this package.

No new simulation path, no performance claim, no change to the frozen `M-FIT`
verdict.

## 2. The measured finding

`research/v3/EMULATOR_BUILD_PLAN.md` read `OQ-02` as a 53.1 % qubit-0 readout
error. The probes disagree:

| probe | circuit | qubit-0 marginal |
| :--- | :--- | ---: |
| `OQ-01` | `X` twice (identity) | `P(1) = 0.070` |
| `OQ-02` | `X` on all five | `P(1) = 0.469` |
| `OQ-03` | `X` on qubit 0 only | `P(1) = 0.507` |
| `OQ-09` | GHZ-5, no `X` | `P(1) = 0.486` |

A readout matrix would depress `OQ-09` too. It does not. The defect follows the
`X` gate on qubit 0. `M-FIT-2` fits `p10[0]` on the padded GHZ ladder and solves
an `X` bit-flip of 0.536.

| model | FIT TV | EVAL median ΔTV | 95 % CI | jobs closer |
| :--- | ---: | ---: | ---: | ---: |
| `M-FIT` (frozen) | 0.228625 | −0.071905 | [−0.135899, −0.006703] | 14/20 |
| `M-FIT-2` | **0.120899** | **−0.105360** | [−0.132644, −0.042472] | **16/20** |

`M-FIT-2` is post-hoc and exploratory. The preregistered `M-FIT` verdict
remains `SUPPORTED`; confirmation of `M-FIT-2` needs a fresh backend and split.

## 3. Studio

```bash
cq-hecs studio
# http://127.0.0.1:8765/
```

- Circuit lab: QASM or preset, forced path, ideal / `M-FIT` / `M-FIT-2`.
- Noise lab: per-qubit parameters, FIT residual, per-job measured-vs-model ΔTV.
- SAT lab: sound verdicts and a random-3-SAT sweep.
- Evidence: all 25 jobs with circuit digests and provider job IDs.
- Research: `P` vs `NP`, ETH, OpenAI math, with non-claims.

The server uses only the standard library and the existing package. It binds to
loopback, serves only bundled files, and never reads credentials. See
`docs/STUDIO.md`.

## 4. SAT semantics

- `SAT`: a model was found and verified clause by clause.
- `UNSAT`: exhaustive search finished. No proof object is produced; the result
  says so.
- `UNKNOWN`: timeout or node budget. Never reported as `UNSAT`.

The old `python_bridge/sat_engine.py` demonstrator is not the supported surface:
its branch hash covers only the first 32 variables and it reported a timeout as
`UNSAT`.

## 5. Verification

| Gate | Result |
| :--- | :--- |
| Python suite | **585 passed**, 4 skipped, 1 opt-in `slow` gate (~110 s) |
| CTest | 19/19 |
| Source mutation | 35/35 |
| Metamorphic selftest | 12/12 |
| Independent oracle | 21/21 PASS (`r-qr-1`) |
| Version consistency | all surfaces report `2.6.0` |

## 6. Known limits

- `M-FIT-2` is post-hoc; one backend, one day, 1000 shots per job.
- QuantumRings is a classical simulator, not a QPU.
- The IonQ pilot is five jobs at 100 shots; it cannot evaluate H-V3-8.
- No `P = NP` or ETH claim. A finite SAT sweep is not a lower bound.
- The noise path is exact only up to 10 qubits; above that it refuses.

## 7. Install

```bash
python -m pip install cqhecs-2.6.0-py3-none-any.whl
cq-hecs doctor
cq-hecs studio
```

## 8. Documentation

- `CHANGELOG.md` — `[2.6.0]` section.
- `research/v4/FINDINGS.md` — measured findings and reproductions.
- `research/v4/COMPLEXITY_AND_ETH.md` — complexity boundaries.
- `docs/STUDIO.md` — UI and HTTP API.
