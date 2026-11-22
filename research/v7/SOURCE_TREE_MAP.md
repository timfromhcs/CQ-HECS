# SOURCE_TREE_MAP.md — repository surface inventory (V7 W0)

Created 2026-11-21 on branch `agent/v6-rc` (base `25e16e5`, v5.0.0). A map of the surfaces the
V7 mission touches, with the owning V7 wave. Version/summary of each surface is in
`FEATURE_COVERAGE.md`.

## Top level

- `AGENTS.md`, `AGENTS_V6.md`, `AGENTS_V7.md` — agent mission contracts (V4, V6, V7; V7 governs).
- `PLAN.md` (German, 18 sections + milestones M0–M12), `ARCHITECTURE.md` (canonical), `docs/ARCHITECTURE.md` (historical v2).
- `README.md`, `README.de.md`, `README.fr.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `CITATION.cff`.
- `CHANGELOG.md`, `RELEASE_NOTES.md`, `MIGRATION_V4.md`, `MIGRATION_V5.md`, `QGRAVITY.md` (untracked, maintainer), `GEMINI.md`, `GEMINI_HANDOFF.md`, `llms.txt`.
- `pyproject.toml`, `CMakeLists.txt`, `pytest.ini`, `requirements.txt`, `constraints/`, `requirements/`.
- `cloudbuild.yaml`, `build.bat`, `.github/workflows/{ci,nightly,release}.yml`.

## Python package `cqhecs/` (V7 W5, W6, W8, W9, W11, W12)

- Core: `router.py`, `execution_plan.py`, `circuit_analyzer.py`, `circuit_parsing.py`, `circuit_library.py`, `result.py`, `provenance.py`, `gate_manifest.py`, `gate_lowering.py`, `scheduler.py` (Vulkan planner; not a driver), `expectation.py`, `backend.py`, `selftest.py`, `reference.py`.
- `backends/`: `path_a_stabilizer.py`, `path_b_stabilizer_rank.py`, `path_c_mps_exact.py`, `path_d_sparse_pauli.py`, `noisy_density_matrix.py`, `dense_reference.py`.
- SAT: `sat.py`, `sat_external.py` (optional CaDiCaL), `sat_separator.py`, `unified.py`, `drat.py`, `omniwave/{engine,field,bcp,gf2,quadratic,boundary,learned,gpu}.py`.
- Hardware/noise: `hardware_bridge.py`, `calibration_import.py`, `noise_fit.py`, `noisy_expectation.py`, `device_profiles.py`, `provider.py`, `openquantum_suite.py`.
- QG: `quantum_gravity/{catalog,models,circuits,hamiltonians,fermions,gauge,noise,observables,references,results,errors}.py`.
- Interfaces: `cli.py`, `mcp_server.py`, `studio/{app,omniwave_lab}.py` + `studio/{static,data}`.
- Other: `sha/` (FIPS-180-4 reference + SHA Forge), `hardware/` (miner research bridge, loopback-only).

## Native `src/`, `include/`, `shaders/` (V7 W11)

- `src/`: `cq_c_api.cpp`, `cq_hecs_api.cpp`, `main.cpp`, `stabilizer_tableau.cpp`, `mps_sampler.cpp`, `tensor_network.cpp`, `sat_solver.cpp`, `constraint_solver.cpp`, `algebra/`, `bindings/`, `stabilizer/`, `vulkan/`, `vulkan_engine.cpp`, `hybrid_engine.cpp`, plus ARX/CORDIC/residual/tiered-storage modules.
- `include/`: `cq/`, `cq_hecs/`, `cqhecs/`, `cq_hecs_api.h`.
- `python_bridge/`, `python/` (legacy shims).

## Web `web/` (V7 W13)

- `web/src/`: `main.ts`, `composer.ts`, `circuit.ts`, `simulate.ts`, `core.ts`, `gpu.ts`, `engine.worker.ts`, `protocol.ts`, `provenance.ts`, `noise_predicate.ts`, `wasm_url.ts`, `i18n.ts`, `sat.ts`, `satcert.ts`, `profiles.ts`, `device.ts`, `charts.ts`, `styles.css`, `forge/` (SHA Forge).
- `web/wasm/` (Rust `src/lib.rs`, `Cargo.*`, `rust-toolchain.toml`), `web/public/cqhecs_core.wasm` (built), `web/dist/`.
- `web/{index,forge}.html`, `web/vite.config.ts`, `web/playwright.config.ts`, `web/tests/` (unit), `web/e2e/` (Playwright + axe), `web/scripts/` (budget/contrast/deploy checks).

## Windows EXE (V7 W14)

- `scripts/build_exe.ps1` (PyInstaller onedir), `scripts/package_release.ps1`, `scripts/smoke_test.ps1`.

## Studio/API/MCP (V7 W12)

- `cqhecs/studio/app.py` (loopback HTTP, bearer token), `cqhecs/mcp_server.py` (stdio JSON-RPC, 11 tools), `cqhecs/cli.py`.

## Evidence and research (V7 W2, W3, W17)

- `research/`: `v2..v7`, `next_stable`, `qg_2026`, `sha_forge`. `research/v7/` holds this mission's
  records (`BASELINE*.md`, `PLAN_COVERAGE.md`, `FEATURE_COVERAGE.*`, `CLAIM_AUDIT.md`,
  `LITERATURE_MAP.md`, `HYPOTHESES.md`, `FINDINGS.md`, `DECISIONS.md`, `BLOCKERS.md`,
  `TEST_MATRIX.md`, `EXECUTION_LOG.md`, `WAVE3_REPORT.md`, `migration/`, `evidence/`).
- `benchmarks/{sat,qasm}`, `audit/`.

## Tests and CI (V7 W3, W15, W16)

- `tests/` (~2899 passing locally): `tests/python/`, `tests/cpp/`, `tests/data/`, plus top-level
  `test_*.py` and `test_*.cpp`. Harnesses: `scripts/run_mutation_tests.py` (64 mutants),
  `scripts/skip_budget.py`, `scripts/qg_doc_consistency.py`, `scripts/check_version.py`,
  `scripts/verify_no_silent_truncation.py`, `scripts/verify_vulkan_shaders.py`.
- CI: static/smoke, Linux Vulkan full suite, Linux CPU-only, Windows Vulkan; release.yml
  (build + tag on main push). Helpers: `scripts/build_exe.ps1`, `scripts/package_release.ps1`.

## Surfaces not present on this checkout

- No Lean project (`lakefile*`/`lean-toolchain` absent; `lean`/`lake` not installed) → V7 **W4
  NOT_RUN** here.
- `QGRAVITY.md` exists as an untracked maintainer file (committed to this branch's history is
  `AGENTS_V7.md` only).
