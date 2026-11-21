# EXECUTION_LOG.md

Append-only. UTC ISO-8601. One entry per coherent checkpoint.

## 2026-11-21 — session 1

- `git fetch origin --prune`; recon of `main` and all remote branches. Local `main` ==
  `origin/main` @ `fa1cc87`; version 5.0.0. No QG work upstream.
- Created branch `research/quantum-gravity-studio`.
- Added campaign secret patterns to `.gitignore`; created `research/qg_2026/` scaffold.
- Read `cqhecs/result.py`, `cqhecs/provenance.py`, `scripts/run_openquantum_suite.py`,
  `cqhecs/openquantum_suite.py` to fix the integration contracts.
- Probed Open Quantum auth (read-only): 401 with SDK Key used as token; docs confirm the
  key is a Client ID + Client Secret pair → **blocker B-1** (secret missing).
- Established baseline: 2820 tests collected; focused subset 268 passed; version check OK.
- Wrote `PLAN.md`, `BASELINE.md`, `STATUS.md`, `TASKS.md`, `BLOCKERS.md`,
  `LITERATURE_MAP.md`, `HYPOTHESES.md`, `METHOD_CATALOG.md`, `EXPERIMENT_PROTOCOL.md`.
- Implemented `cqhecs/quantum_gravity/` (models, fermions, hamiltonians, observables,
  references, circuits, results, catalog, errors) + tests (M3–M5).
- Implemented `scripts/run_qg_openquantum_campaign.py` (M6): `doctor`, `discover`,
  `generate`, `validate` runnable; `quote/submit/collect` gated on B-1.
- Results: `generate`/`validate` OK (6 BMV circuits + 2 model cards, digests verified);
  `doctor` → BLOCKED (B-1) with no secret printed.
- Tests: 67 quantum-gravity tests pass; 335 pass in the focused regression gate; CLI
  `selftest --cases 2` PASS.
- Added `docs/QUANTUM_GRAVITY_LAB.md`.
- flake8 (`--select=E9,F`) clean on all new files.

(Commit SHA recorded below once pushed.)

Commit: `ab27578` — "feat(qg): Quantum Gravity research layer + campaign runner (qg-2026-01)".

## 2026-11-21 — session 1 (continued): M8 local API + MCP

- Added Studio routes `GET /api/qg/v1/{health,catalog,models}` and
  `POST /api/qg/v1/experiments/{validate,preview,run-local}` (StudioState methods,
  loopback + bearer token; every response tagged `CLASSICAL_REFERENCE`; spend 0).
- Added MCP tools `cqhecs_qg_catalog`, `cqhecs_qg_circuit_preview`, `cqhecs_qg_run_local`
  (stdio, local-only).
- Tests: `test_quantum_gravity_studio.py` 5 passed; `test_mcp_server.py` 9 passed;
  `test_studio.py`+`test_studio_security.py` 37 passed. flake8 (E9,F) clean.
- Fix note: the first placement of the QG methods landed inside a module-level helper;
  relocated into `StudioState` (verified `hasattr(StudioState, "qg_health")`).

## 2026-11-21 — session 1 (continued): CLI surface

- Added `cq-hecs qg {catalog,preview,run-local}` with `--format json`; local, exact,
  spend = 0. Tests: `test_cli_contract.py` 37 passed. flake8 clean.

## 2026-11-21 — session 1 (continued): Track A noise model (QG-BMV-03)

- Added `cqhecs/quantum_gravity/noise.py`: Kraus channels (dephasing, amplitude damping,
  single/two-qubit depolarizing), asymmetric readout, seeded sampling, rigorous Hoeffding
  `Z⊗Z` estimator, and `witness_under_noise` (NOISY_CLASSICAL).
- Tests: `test_quantum_gravity_noise.py` 14 passed (trace/positivity, monotone witness
  decay, separable null under noise). Honest status: channel model verified locally;
  the device comparison stays `NOT_RUN` (B-1).

## 2026-11-21 — session 1 (continued): full-suite gate

- `python -m pytest tests/ -q` → **2789 passed, 105 skipped, 1 deselected** (~5:49).
- Commits on `research/quantum-gravity-studio`: `ab27578`, `a126e08`, `9138a5b`, `9ff9ad6`.

## 2026-11-21 — session 1 (continued): Track C gauge toy (QG-GAUGE-01)

- Added `cqhecs/quantum_gravity/gauge.py` (`qg.gauge.z2.v1`): bounded Z2 square-lattice
  toy with Gauss generators, plaquette operators and `H=-Σ B_p`; dense <= 8 links.
- Tests: `test_quantum_gravity_gauge.py` 10 passed (`[H,G_v]=0`, involutions, integer
  spectrum, physical-subspace preservation). Recorded as a bridge, not a gravity result.
- Pushed branch `research/quantum-gravity-studio`; opened PR #54; remote CI in progress.

## 2026-11-21 — session 1 (continued): B-1 resolved + live QPU smoke (M6/M7)

- Client Secret supplied; `oq.py setup` → login OK (org Tim Stark, Spark 25, Full 0).
- Preregistered Stage-2 smoke (`QPU_SMOKE.md`); validated 4 circuits; quoted 4 credits
  (Public/Standard) on `rigetti:cepheus-1-108q`; **submitted 4 jobs** (JOB_LEDGER.jsonl).
- B-1 → FIXED. Results pending collection.

## 2026-11-21 — session 1 (continued): QPU smoke results (REAL HARDWARE)

- All 4 jobs reached `Completed`; counts + calibration downloaded.
- In-support fractions: basis 0.899, bell 0.954, ghz3 0.906, mirror 0.979.
- Bit order = little-endian (q0 rightmost). `|1>`-state error ~10% (excited-state/readout).
- Evidence: `research/qg_2026/raw/qpu_smoke/` + `EVIDENCE_MANIFEST.json`;
  analysis `processed/qpu_smoke_analysis.json`. Spark spent 4/25.

## 2026-11-21 — session 1 (continued): BMV QPU witness submitted (Stage 3)

- Preregistered `QPU_BMV.md`: 9 circuits (θ ∈ {0, π/4, π/2} × {Y⊗Z, Z⊗Y, X⊗X}), locally
  verified (`<Y⊗Z>=<Z⊗Y>=sinθ`, `<X⊗X>=1`).
- Quoted 9 credits on `rigetti:cepheus-1-108q` (Public/Standard); **9 jobs submitted**,
  cumulative **13 / 25**. Results pending.

## 2026-11-21 — session 1 (continued): BMV QPU results (REAL HARDWARE)

- 9/9 jobs `Completed`. Correlators: ⟨Y⊗Z⟩ 0.014/0.616/0.854 and ⟨Z⊗Y⟩ 0.012/0.666/0.874 for
  θ=0/π4/π2; ⟨X⊗X⟩ 0.954/0.818/0.808. θ=0 null consistent with 0.
- Records: FINDINGS F-08, `processed/bmv_qpu_analysis.json`, `raw/bmv_qpu/EVIDENCE_MANIFEST.json`.
- Spark spent **13 / 25** (0 refunded).

## 2026-11-21 — session 1 (continued): BMV phase-scan extension

- Preregistered + submitted θ ∈ {π/8, 3π/8} × {Y⊗Z, Z⊗Y} (4 circuits, 4 credits), locally
  verified to give sinθ. Cumulative **17 / 25**. Results pending collection.
