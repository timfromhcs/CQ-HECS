# CQ-HECS Release Notes

**Version:** 3.3.0
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to `dist/RELEASE_NOTES_v3.3.0.md`,
> prepends the exact source commit and required CI run, and appends the SHA256
> values of the final assets.

---

## 1. What this release is

`v3.3.0` is a small hardening release on v3.2.0. It adds checkable UNSAT
certificates to the Python SAT surface (§3.1). The v3.2.0 content below is
unchanged and still applies:

`v3.2.0` was a stable feature release on the v3.1.0 base. It added:

1. **An MCP server** — `cq-hecs mcp`, newline-delimited JSON-RPC over stdio,
   no network listener, tools for run/analyze/SAT/models/hardware.
2. **SAT model enumeration and exact MaxSAT** — `cq-hecs sat models|maxsat`.
3. **A Studio Hardware lab** — every committed real-QPU evaluation and the
   finite P-vs-NP probes in one view (`/api/hardware`).
4. **A multi-backend 10,000-shot replication** — the pinned 25-circuit suite on
   three IBM backends, all `H-V3-8 SUPPORTED`.
5. **A standalone Windows build** — `cqhecs-3.3.0-windows-x64.zip`
   (PyInstaller onedir), smoke-tested outside the repository.

No new simulation path and no performance claim. The frozen `M-FIT` verdicts
are unchanged.

## 2. Multi-backend 10,000-shot replication

The same 25 pinned `r-io-7` circuits ran externally on three IBM Quantum
backends at 10,000 shots per circuit, on a fixed physical chain per backend.
Every bit-order probe returned `00001`. Bootstrap: 5000 resamples, seed
20261030, circuits resampled.

| backend | IBM job | H-V3-8 | median ΔTV | 95 % CI | closer |
| :--- | :--- | :--- | ---: | ---: | ---: |
| `ibm_fez` | `dbie7sg1h92s73839ekg` | **SUPPORTED** | −0.032936 | [−0.038172, −0.023337] | 20/20 |
| `ibm_kingston` | `dbie9go1h92s73839i8g` | **SUPPORTED** | −0.027127 | [−0.031653, −0.019508] | 20/20 |
| `ibm_marrakesh` | `dbie8l6ne4hc73bedhl0` | **SUPPORTED** | −0.027340 | [−0.041416, −0.021543] | 20/20 |

Post-hoc `M-FIT-2` vs the frozen `M-FIT`: median −0.000481 / +0.000296 /
−0.000550; every 95 % CI contains 0 → **inconclusive** on all three. No
`X`-gate anomaly was detected on any IBM backend; the 0.531 flip remains
Rigetti-specific. H-V3-9 (“M-FIT-2 beats M-FIT”) remains **not supported**.

Reproduce: `python scripts/evaluate_ibm_10k.py` (no QPU access needed).
Evidence: `research/v4/evidence/ibm_10k/`.

## 3. SAT surface

- `SAT`: a model was found and verified clause by clause;
- `UNSAT`: exhaustive search finished; since v3.3.0 it carries a tree-resolution certificate that `check_refutation` replays (§3.1);
- `UNKNOWN`: timeout or node budget; never reported as `UNSAT`.
- `models`: `COMPLETE` only when the solver showed no further model exists;
  `LIMIT` and `TIMEOUT` are reported explicitly. Cross-checked against brute
  force on random formulas.
- `maxsat`: exact weighted MaxSAT by exhaustive enumeration, **refuses above
  20 variables**. It is not a scalable MaxSAT solver.

### 3.1 UNSAT certificates (new in v3.3.0)

`cqhecs.sat.solve(..., certify=True)` follows an UNSAT verdict with a second
search that uses unit propagation only (pure-literal elimination preserves
satisfiability but is not a resolution step) and records a tree-resolution
refutation: one unit-propagation conflict per leaf, one resolution per inner
node. `check_refutation` is a separate, search-independent replay. `certified`
is true only after that replay passes. If the two searches disagree the result
is `UNKNOWN`; if the certificate exceeds its time or 200,000-step budget the
verdict stays exhaustive-`UNSAT` with `certified=false` and a note. `sweep`
disables certification so measured runtimes are unchanged. Checked against
CaDiCaL 1.5.3 (python-sat) on random formulas, with four source mutants of the
checker and the certifying search. Tree resolution is exponentially weaker than
CDCL proofs; this is a correctness check, not a speed claim.

## 4. Standalone executable

`cqhecs-3.3.0-windows-x64.zip` contains `cq-hecs/cq-hecs.exe` and its
`_internal/` runtime (Python, NumPy, Qiskit, Qiskit Aer, Studio assets and the
packaged `r-io-7` snapshot). It is a convenience build of the same package,
not a second implementation. `scripts/build_exe.ps1` builds it and fails
unless `version`, `sat solve`, `run name:bell` and the Studio `/api/health`
smoke tests pass. The one-file mode is not used: a 518 MB one-file build failed
to extract `bcrypt` at runtime.

## 5. Independent oracle (from v3.1.0)

`r-qr-1`: GHZ widths 2–128, QFT, Clifford+T, brickwork, Grover,
Bernstein–Vazirani, Deutsch–Jozsa and a depth-30 mirror. Every total-variation
distance is below the 99th percentile of 400 finite-shot resamples from the
exact CQ-HECS distribution. QuantumRings is a classical simulator, not a QPU.

## 5.1 First IBM run: `ibm_fez`, 1000 shots (from v3.1.0)

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

- `M-FIT-2` is post-hoc. The 10k replication is one suite, one day, on IBM
  Heron backends only.
- Exact MaxSAT refuses above 20 variables; native `UNSAT` and `python_bridge.sat_engine` still have no proof object.
- The Windows build is x64 only and unsigned.
- QuantumRings is a classical simulator, not a QPU.
- The IonQ pilot is 100–200 shots and cannot evaluate H-V3-8.
- No `P = NP` or ETH claim. A finite SAT sweep is not a lower bound.
- The noise path is exact only up to 10 qubits; above that it refuses.

## 8. Install

```bash
python -m pip install cqhecs-3.3.0-py3-none-any.whl
cq-hecs doctor
cq-hecs studio
cq-hecs mcp      # stdio MCP server
```

## 9. Documentation

- `CHANGELOG.md` — `[3.3.0]` section.
- `research/v4/FINDINGS.md` — corrected finding and reproductions.
- `research/v4/COMPLEXITY_AND_ETH.md` — complexity boundaries.
- `docs/STUDIO.md` — UI and HTTP API.
