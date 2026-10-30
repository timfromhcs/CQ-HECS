# ACTIVE HANDOFF — CQ-HECS v3.2.0 (2026-10-30)

**Read this first.** It supersedes the v3.0.0 mission text at the bottom of
`GEMINI.md` for the current work. The repository is mid-flight: v3.1.0 is
released, v3.2.0 is implemented but **not committed, tested end-to-end, merged
or released**.

> **Honesty rule:** do not claim `P = NP`, ETH, a QPU execution by this
> package, a GPU-accelerated simulator, or “lossless for arbitrary states”.
> A finite experiment is a finite experiment. A simulation is not a QPU.

---

## 0. TL;DR — where to start

1. `git status` is dirty on `agent/v3.2-pnp-oracles`. Commit or review the v3.2
   work first. PR **#31** is open and mergeable:
   <https://github.com/timfromhcs/CQ-HECS/pull/31>
2. Run the full test loop for the v3.2 changes. The last full run was **623
   passed, 1 deselected**, with 3 failures only because the native binary still
   reported 3.1.0. After rebuilding the native core, those 3 version tests pass
   (626 expected); re-run the full suite to confirm.
3. Finish the **standalone executable**. The one-file build exists
   (`dist/cq-hecs.exe`, **518,558,428 bytes**) but fails at runtime with
   `Failed to extract bcrypt\_bcrypt.pyd: decompression resulted in return
   code -3!`. The build script is still `--onefile`; the `--onedir` build was
   interrupted. See §5.
4. Evaluate the already-measured **10k-shot IBM runs** (`ibm_10k/*`). They have
   counts but no `h_v3_8_evaluation.json` / `m_fit_2_*` yet. This is the
   highest-value evidence work left. See §6.
5. Do not submit more IBM jobs blindly: the open-plan budget is **589 / 600 s
   used, 11 s left**.
6. After CI is green: merge, release **v3.2.0**, attach the exe/zip, verify
   hashes, then rotate/delete every provider key.

---

## 1. Current git and release state

| Item | State |
| :--- | :--- |
| `main` | v3.1.0 released; merge commit `24b1561` |
| v3.1.0 release | <https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.1.0> |
| Current branch | `agent/v3.2-pnp-oracles` |
| PR #31 | open, mergeable, <https://github.com/timfromhcs/CQ-HECS/pull/31> |
| `scripts/version.py` | **3.2.0** |
| Uncommitted v3.2 work | MCP server, SAT models/MaxSAT, Studio hardware lab, exe build script, version bump, README/CHANGELOG |
| Generated but untracked | `cq-hecs.spec` (PyInstaller), `dist/cq-hecs.exe` (ignored) |
| IBM budget | **11 s remaining**, 589 s used |
| OpenQuantum pilot | 8 jobs still queued; not collected |

`git status --short` at handoff:

```
M CHANGELOG.md CITATION.cff CMakeLists.txt README.md SECURITY.md
M cqhecs/__init__.py cqhecs/cli.py cqhecs/sat.py cqhecs/studio/app.py
M cqhecs/studio/static/app.js cqhecs/studio/static/index.html
M docs/API_REFERENCE.md include/cq_hecs_api.h pyproject.toml
M python/cq_hecs/__init__.py python/cqhecs/__init__.py python_bridge/cq_hecs.py
M scripts/version.py tests/test_c_api.py tests/test_studio.py
?? cq-hecs.spec cqhecs/mcp_server.py scripts/build_exe.ps1 tests/test_mcp_server.py
```

---

## 2. What is already implemented (v3.2.0, uncommitted)

### 2.1 MCP server — `cqhecs/mcp_server.py`, `cq-hecs mcp`

- Newline-delimited JSON-RPC over stdio; no SDK, no network listener.
- Methods: `initialize`, `ping`, `tools/list`, `tools/call`.
- Tools: `cqhecs_run`, `cqhecs_analyze`, `cqhecs_sat_solve`,
  `cqhecs_sat_models`, `cqhecs_hardware`.
- `tests/test_mcp_server.py` passes (3 tests).
- **Gap:** no SSE/HTTP transport (stdio only); no prompt/resource primitives;
  no auth (stdio is local). Add a `cq-hecs mcp --http` only behind an explicit
  bind/auth design, or stay stdio.

### 2.2 SAT — `cqhecs/sat.py`, `cq-hecs sat solve|models|maxsat|sweep`

- Sound DPLL: `SAT` verified model; `UNSAT` after exhaustive search without a
  proof object; `UNKNOWN` on timeout/node budget.
- `enumerate_models(formula, limit, timeout)` — blocking clauses; status
  `COMPLETE` / `LIMIT` / `TIMEOUT`; returns models.
- `max_sat(formula, clause_weights, max_vars=20)` — exact exhaustive MaxSAT,
  refuses above 20 variables. It is **not** a scalable MaxSAT solver.
- CLI models/maxsat work; **no dedicated test yet**. Add tests for
  COMPLETE/LIMIT/TIMEOUT and weighted MaxSAT.

### 2.3 Studio hardware lab — `/api/hardware`, UI view “06 Hardware”

- `StudioState.hardware()` summarizes Rigetti, IBM `ibm_fez`, QuantumRings,
  `pnp_emulability` and `pnp_sat_oracles`.
- New nav view + tables; `/api/hardware` covered in `tests/test_studio.py`.
- **Gaps:** no backend/dataset selector, no export JSON/CSV, no 10k-run rows
  yet, no solver-lab controls for `models`/`maxsat`. Add them.

### 2.4 v3.2 README/version

- Version bumped to **3.2.0** on the enforced surfaces.
- README status now lists Studio, MCP, SAT, oracle, exe and finite P-vs-NP
  probes.
- `CHANGELOG.md` has `[3.2.0]`; `RELEASE_NOTES.md` still says 3.1.0 and must be
  rewritten for 3.2.0 before release.
- `scripts/check_version.py` passes.

### 2.5 Evidence added earlier (already committed)

- `research/v4/evidence/ibm/ibm_fez/` — 25 circuits, 1000 shots, H-V3-8
  SUPPORTED, anomaly absent.
- `research/v4/evidence/pnp_emulability/` — 8 universal probes, CQ-HECS vs
  Qiskit Statevector TV ≤ 5e-15, QPU comparison.
- `research/v4/evidence/pnp_sat_oracles/` — 3 SAT oracles on two IBM backends;
  top outcome is a valid DPLL model on every run; strict MPS lossless is
  **false** for two-model/4-variable circuits (discarded ~1e-15/1e-13).
- Scripts: `run_ibm_universal_probes.py`, `run_ibm_sat_oracles.py`,
  `pnp_emulability_check.py`, `pnp_sat_oracle_report.py`.

---

## 3. The executable — current failure and the fix path

### 3.1 What happened

Attempted:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --name cq-hecs `
  --add-data "cqhecs\studio\static;cqhecs\studio\static" `
  --add-data "cqhecs\studio\data;cqhecs\studio\data" `
  --collect-submodules qiskit --collect-data qiskit `
  --collect-submodules qiskit_aer --collect-data qiskit_aer `
  cqhecs\cli.py
```

It produced a **518 MB** `dist/cq-hecs.exe`, but every launch fails:

```
[PYI-...:ERROR] Failed to extract bcrypt\_bcrypt.pyd: decompression resulted in return code -3!
[PYI-...:ERROR] Failed to extract entry: bcrypt\_bcrypt.pyd.
```

Likely cause: one-file extraction of a huge archive, antivirus/temp scanner, or
a PyInstaller/bcrypt mismatch. The binary never reaches `main()`.

### 3.2 Recommended fix

Use **onedir**, not onefile:

```powershell
python -m PyInstaller --noconfirm --clean --onedir --name cq-hecs `
  --add-data "cqhecs\studio\static;cqhecs\studio\static" `
  --add-data "cqhecs\studio\data;cqhecs\studio\data" `
  --collect-submodules qiskit --collect-data qiskit `
  --collect-submodules qiskit_aer --collect-data qiskit_aer `
  cqhecs\cli.py
```

Output: `dist/cq-hecs/cq-hecs.exe` plus `_internal/`.

- Smoke: `dist\cq-hecs\cq-hecs.exe version`, `sat solve`, `--format json run
  name:bell`, `studio --no-browser` on a free port.
- Zip `dist/cq-hecs/` as `cqhecs-3.2.0-windows-x64.zip` and attach that to the
  release, or ship both the zip and a small README.
- If `--onedir` still fails on `bcrypt`, inspect
  `build/cq-hecs/warn-cq-hecs.txt`; try `--exclude-module bcrypt` or
  `--hidden-import bcrypt` deliberately, and test the Qiskit backend.
- Alternative: Nuitka `--standalone` if PyInstaller remains brittle. Do not
  claim a working exe until the smoke tests pass on a clean machine.

Update `scripts/build_exe.ps1` from `--onefile` to `--onedir` (or add a
`-OneFile` switch) and make the smoke test mandatory. `cq-hecs.spec` is
generated; either commit a curated spec or delete it and keep the script.

### 3.3 Acceptance

- `dist/cq-hecs/cq-hecs.exe version` prints `cq-hecs 3.2.0`.
- `cq-hecs.exe sat solve benchmarks\sat\pigeonhole_6_5.cnf` returns UNSAT.
- `cq-hecs.exe --format json run name:bell --shots 64` returns counts.
- `cq-hecs.exe studio --no-browser --port 8765` serves `/api/health` with the
  packaged `r-io-7` snapshot from a directory outside the repo.
- Release asset SHA-256 recorded in `research/v3_2_0/RELEASE_AUDIT.md`.

---

## 4. Test loop that must be finished

Run from the repo root:

```powershell
python -m pytest -q
python -m flake8 --select=E9,F cqhecs python_bridge scripts tests
python scripts/check_version.py
python scripts/verify_no_silent_truncation.py
ctest --test-dir build -C Release --output-on-failure
python -m build
python -m twine check dist/cqhecs-3.2.0*
```

Then the CI matrix (Linux/Windows native, ASan/UBSan, Python 3.12–3.14,
static/package). Fix failures in a loop; do not merge a red PR.

Add tests that are currently missing:

- `tests/test_sat_models.py`: `COMPLETE` on a formula with 4 models; `LIMIT`
  when `limit < count`; weighted MaxSAT optimum; refusal above `max_vars`.
- `tests/test_mcp_server.py`: already 3 tests; add `cqhecs_sat_models` and
  `cqhecs_hardware` calls.
- `tests/test_studio.py`: already covers `/api/hardware`; add a test that the
  hardware view includes the IBM and P-vs-NP rows.
- `tests/test_exe_smoke.py` (optional, opt-in): skip unless
  `CQ_HECS_EXE` is set; run version/sat/run.
- `tests/test_ibm_10k.py`: after evaluating the 10k runs, verify job IDs,
  digests, bit order and evaluation verdicts.

---

## 5. Evidence tuning — highest-value work left

The following runs exist but are **not fully evaluated**:

| Path | Shots | Status |
| :--- | ---: | :--- |
| `research/v4/evidence/ibm_10k/ibm_fez/` | 10,000 | counts only; no evaluation |
| `research/v4/evidence/ibm_10k/ibm_kingston/` | 10,000 | counts only; no evaluation |
| `research/v4/evidence/ibm_10k/ibm_marrakesh/` | 10,000 | counts only; no evaluation |
| `research/v4/evidence/ibm_readout50k/pilot_pilot/ibm_fez/` | 50,000 | 4 readout probes |
| `research/v4/evidence/ibm_readout50k/pilot_pilot/ibm_marrakesh/` | 50,000 | 4 readout probes |
| `research/v4/evidence/ibm_universal/...` | 10k/50k | 8 probes; summary only |
| `research/v4/evidence/ibm_sat_oracles/...` | 10k | 3 SAT oracles; summary/report |

### 5.1 Evaluate each 10k backend

```python
from pathlib import Path
from cqhecs.openquantum_suite import evaluate_suite
from cqhecs.noise_fit import evaluate_exploratory, dump_profile
import json

for backend in ("ibm_fez", "ibm_kingston", "ibm_marrakesh"):
    root = Path("research/v4/evidence/ibm_10k") / backend
    ev = evaluate_suite(root, bootstrap_samples=5000)
    (root / "h_v3_8_evaluation.json").write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", "utf-8")
    ex = evaluate_exploratory(root, bootstrap_samples=5000)
    (root / "m_fit_2_profile.json").write_text(dump_profile(ex["profile"]), "utf-8")
    (root / "m_fit_2_exploratory.json").write_text(json.dumps(ex, indent=2, sort_keys=True) + "\n", "utf-8")
```

Acceptance/report:

- H-V3-8 verdict and median ΔTV per backend.
- M-FIT-2 vs ideal and vs M-FIT; anomaly list per backend.
- A cross-backend table (3 × 10k shots) in `research/v4/FINDINGS.md` and the
  Studio Hardware view.
- If a backend is INCONCLUSIVE or REJECTED, publish it; do not retune.

### 5.2 Readout 50k

Use the existing `fit_profile` / `pnp` check on `ibm_readout50k` to extract
`p01/p10` with binomial CIs and confirm whether qubit 0 is healthy. The
`ibm_kingston` 50k pilot was aborted before submission; its queued job was
cancelled. Do not spend the last 11 s on a new 50k job.

### 5.3 Universal and SAT oracles

- `pnp_emulability_check.py` is the mandatory universe check; it passes with
  `EXACTLY_EMULABLE_AND_QPU_CONSISTENT`.
- `pnp_sat_oracle_report.py` reports `all_qpu_top_outcomes_are_models = true`,
  `all_mps_strictly_lossless = false`.
- Add the 10k backend rows to the report once evaluated; keep the non-claims.

### 5.4 Missing evidence

- `ibm_fez` 20k universal job `dbieh601h92s7383a4pg` completed; the script was
  interrupted before writing counts. It can be recovered with
  `service.job("dbieh601h92s7383a4pg").result()` and saved under
  `ibm_universal/ibm_fez/20000/`; no QPU time is needed.
- The IonQ pilot (`research/v4/evidence/openquantum_pilot/`) is still queued;
  collect later with `scripts/collect_openquantum_pilot.py --collect`.

---

## 6. SAT-solver roadmap (the “more solvers” request)

Current engine is a sound DPLL. To become a real SAT/MaxSAT surface:

1. **CDCL** with watched literals, VSIDS, phase saving, restarts, clause
   learning. Keep the existing DPLL as a reference oracle; do not delete it.
2. **UNSAT proof**: emit DRAT and verify with `drat-trim` if available; if not,
   keep “no proof object” honest. A resolution proof is optional, but never
   label an unchecked search as “proven” beyond the existing exhaustive claim.
3. **Cardinality / pseudo-Boolean** constraints for SAT encodings.
4. **MaxSAT**: weighted partial MaxSAT with core-guided or linear-search
   algorithm; keep the exact ≤20-variable brute force as a test oracle.
5. **Model enumeration** with projection (project onto a subset of variables).
6. **Benchmarks**: pigeonhole, uf50, random 3-SAT at ratios 3.0–6.0, graph
   coloring, small factoring/ARX; report instances solved, decisions, conflicts,
   time, and `UNKNOWN` separately.
7. **Surfaces**: CLI, MCP tools, Studio SAT lab, JSON schema, deterministic
   seeds, no fabricated UNSAT.

Acceptance: cross-check CDCL against the DPLL/brute force on thousands of small
random formulas; every SAT model verified; every UNSAT either has a checked
proof or is explicitly exhaustive; timeouts are `UNKNOWN`.

---

## 7. UI/UX roadmap

The Studio is functional but still a lab tool. Add, in order:

- Dataset/backend selector (Rigetti, IBM 1k/10k, QuantumRings, P-vs-NP).
- Hardware view export (JSON/CSV) and a “copy provenance” button.
- SAT lab: model enumeration, MaxSAT weights, solver statistics, comparison
  table, and clear `UNKNOWN`/`UNSAT` badges.
- Circuit lab: side-by-side ideal vs M-FIT vs M-FIT-2, path comparison A–D,
  QASM download, screenshot/export.
- Command palette (`Ctrl+K`) and keyboard shortcuts (`1`–`7`, `Ctrl+Enter`).
- Accessibility: focus states, labels, reduced motion, high-contrast mode.
- Visual regression screenshots in `docs/assets/` after the changes.

Tests: every endpoint, empty/missing dataset state, oversized body, invalid
QASM, timeout/UNKNOWN, keyboard shortcuts, and a Playwright smoke if available.

---

## 8. Standalone exe details

- `scripts/build_exe.ps1` currently uses `--onefile`; change it to `--onedir`
  and run the smoke tests in §3.
- Bundle `cqhecs/studio/static` and `cqhecs/studio/data` explicitly.
- Include `qiskit`, `qiskit_aer`, `numpy`; test the Qiskit backend from the exe.
- The exe is a convenience artifact, not a second implementation. It must
  report the same version and results as the wheel.
- Add a `dist/cq-hecs/README.txt` with the data/licence notice.
- Release asset: zip the folder; do not commit binaries to git.

---

## 9. Vulkan / iGPU — what is true

- Native C++20 core and 12 SPIR-V shaders exist; `ctest` is 21/21 on Windows.
- CI has verified Vulkan compute dispatch with a software ICD (llvmpipe).
- The local GPU is an AMD Radeon iGPU; there is **no end-to-end Python GPU
  simulator** and no measured speedup claim.
- If adding a `cq-hecs vulkan` command, make it a **status/benchmark** surface:
  device name, driver, API version, selected queue, shader count, a measured
  primitive benchmark, and an explicit “not an end-to-end simulator” note.
- Do not claim “boosted” without before/after numbers on the same workload.

---

## 10. Release checklist for v3.2.0

1. Finish tests + exe + 10k evidence.
2. Commit on a branch, push, open PR; wait for all 7 CI jobs.
3. Merge to `main`.
4. Release workflow creates `v3.2.0`; verify tag = merge SHA.
5. Download every asset; recompute SHA-256; update
   `research/v3_2_0/RELEASE_AUDIT.md`.
6. Attach `cqhecs-3.2.0-windows-x64.zip` (exe folder) if not built by CI.
7. README must state the exe artifact, the 10k multi-backend result, and the
   finite P-vs-NP non-claim.
8. Rotate/delete all provider keys; `apikey.json`, `quantumrings.conf`,
   `sdk-key-*.json` are ignored and must never be committed.

---

## 11. Security / credentials

- **IBM key** is in `apikey.json` (ignored). 11 s of open-plan budget remains.
  Rotate it at <https://quantum.cloud.ibm.com/> when done.
- **Open Quantum** keys are in `sdk-key-*.json` (ignored); both 25-credit
  balances are spent. The 8 IonQ jobs are queued; collect them before deleting
  the keys, then rotate at <https://www.openquantum.com/keys>.
- `quantumrings.conf` is ignored; it is a local 128-qubit simulator licence,
  not a credit meter.
- Never print a token; never put one in evidence, logs, tests or a release.

---

## 12. Key files

| Path | Purpose |
| :--- | :--- |
| `cqhecs/sat.py` | DPLL, models, exact MaxSAT, sweep |
| `cqhecs/mcp_server.py` | stdio MCP server |
| `cqhecs/studio/app.py` | Studio API, hardware aggregation |
| `cqhecs/studio/static/` | UI (index/app/style/logo) |
| `cqhecs/noise_fit.py` | corrected M-FIT-2 |
| `scripts/run_ibm_suite.py` | 25-job IBM runner |
| `scripts/run_ibm_universal_probes.py` | universal probes |
| `scripts/run_ibm_sat_oracles.py` | SAT oracle runner |
| `scripts/pnp_emulability_check.py` | mandatory universe check |
| `scripts/pnp_sat_oracle_report.py` | SAT/lossless report |
| `scripts/build_exe.ps1` | standalone build (fix to onedir) |
| `tests/test_mcp_server.py` | MCP contract |
| `tests/test_pnp_*.py` | finite P-vs-NP evidence |

---

## 13. Definition of done

- All tests green locally and in CI; version surfaces 3.2.0.
- Exe smoke tests pass from a clean folder.
- 10k IBM runs evaluated and visible in the Hardware lab.
- SAT models/MaxSAT tested; every `UNSAT` is exhaustive or has a checked proof.
- README/RELEASE_NOTES/CHANGELOG all describe 3.2.0 honestly.
- Release v3.2.0 published with wheel, sdist, SBOM, checksums, exe zip.
- Keys rotated; no credential in git history or release assets.
