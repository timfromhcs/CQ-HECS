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
