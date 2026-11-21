# Wave 3 report — honesty fixes and reconciliation (AGENTS_V6.md)

Date: 2026-11-21. Branch: `agent/v6-rc` (renamed from `claude/repo-status-agents-v6-49d8ca`).
Base: `origin/main` = `25e16e5c7054be09d6493b062f19f8476dbf2bcd` (v5.0.0). This is a record of work
done, not a plan. It supersedes `PLAN_V6_DRAFT.md` where the two differ.

> Nothing was pushed, no version was bumped, no release was published and no credit was spent.
> All changes are local commits on the feature branch.

## Commits on `agent/v6-rc` (oldest first)

| SHA | Summary |
|---|---|
| 20c3f17 | docs(v7): W0 baseline (prior agent) |
| 60bb34d | feat(native): CPU-only build via `-DCQ_ENABLE_VULKAN=OFF` (T6-03, prior agent) |
| 7cf2c3b | feat(native): CPU-only CI lane + `cq_core_build_capabilities()` (prior agent) |
| 5ab028a | docs(v7): wave 1/2 evidence + draft/refined plan (prior agent) |
| f16dbb5 | fix(web): shared noise predicate, explicit precision, stable WebGPU refusal (W3-12, D5) |
| 722b7be | feat(sat): `certified` + `proof_level`; a rejected proof is never "checked" (W3-09, D3) |
| a3f5ab4 | fix(hardware): uncovered gates visible instead of silently noiseless (W3-06/W3-07, D4) |
| 659885e | fix(path-a): stop silently truncating the requested shot count (W3-01, D1) |
| 70a145e | fix(qg): fail-closed campaign ledger with net-spend accounting (W3-05, D2) |
| 85887b7 | chore(sat,release): frozen SAT baseline + pinned build constraints (W3-08, W3-17) |
| 8ea4ad6 | fix(mcp): server-side bounds for timeout/waves/workers/limit/node_budget (W3-15, D7) |
| 6fa932a | style(hardware): drop unused `time` import |
| 933e14e | docs(v7): Wave 3 report, migration notes, ledger and changelog |
| fad5efb | fix(release): honest version surfaces — SECURITY.md, classifiers, version check (W3-18, D8) |
| b14f617 | test(mutation): correct the stale mutant count and guard it (W3-19, D11) |

## Tasks completed this session (with evidence)

| Task | Defect | What changed | Regression evidence |
|---|---|---|---|
| W3-01 | D1 | Path A `sample()` no longer caps wide non-all-equal circuits at 100 shots. It draws every requested shot, or raises `PathAShotBudgetError` (a `ValueError`) when `shots * n` exceeds `MAX_RESAMPLE_WORK`. Truncation only with an explicit `max_resample_shots`. | `tests/test_path_a_shots.py` (5) |
| W3-05 | D2 | Campaign ledger is fail-closed (invalid JSON / unknown event / missing id / bad credit → `LedgerError`) and nets spend = submitted + unresolved intents − confirmed refunds. `main()` turns a `LedgerError` into a clean JSON failure with exit code 3. | `tests/test_runner_ledger.py` (14); real ledger nets to exactly 25.0/25 |
| W3-06 | D4 | `BackendProfile.uncovered_gates()` lists gates with no calibrated channel; `FakeHardwareBackend(uncovered_gate_policy="warn"|"refuse"|"ideal")`; `SimulationResult.uncovered_gates` + metadata + `to_dict`. | `tests/test_uncovered_gates.py` (12) |
| W3-07 | D4 | `create_linear_profile` no longer stamps `capture_timestamp` with the current time (a synthetic profile must not look like a dated calibration); digest is deterministic. | in `tests/test_uncovered_gates.py` |
| W3-08 | — | `scripts/sat_baseline_snapshot.py` + archived `research/v7/evidence/SAT_BASELINE_pre_R0.json` (taken at 5ab028a, before D3). | script reproduces |
| W3-09 | D3 | `SATResult.proof_status` + `UnifiedResult.certified`/`proof_level`; `solve_unified(require_certified=...)`; an uncertified/rejected proof is never labelled "DRAT proof checked". | `tests/test_unified_solver.py` (+6) |
| W3-12 | D5 | `web/src/noise_predicate.ts` is the single predicate used by the simulator, planner and run card; engine precision is explicit (`f64`/`f32`/`n/a`); WebGPU card carries `cross_check_tv`; refusal carries the stable `WEBGPU_UNSUPPORTED_CIRCUIT` code. | `web/tests/noise_predicate.test.ts` (+10); web 71/71 |
| W3-15 | D7 | MCP bounds `timeout` (0.01–30 s), `waves` (1–16), `workers` (1–8), models `limit` (1–1000), `node_budget` (1–1e7) like the Studio, and refuses out-of-range input. | `tests/test_mcp_server.py` (+4) |
| W3-17 | — | `requirements/build-constraints.txt` (setuptools/wheel/build pins via `PIP_CONSTRAINT`). | build metadata |
| W3-18 | D8 | `SECURITY.md` advertises the 5.0.x line (not 4.0.x); classifiers are `Beta` without the C++ classifier; `check_version.py` asserts both. | `scripts/check_version.py` (verified: the old table fails) |
| W3-19 | D11 | mutation meta-test said "35-mutant" while the harness has 60; corrected and guarded by a count assertion. | `tests/test_mutation_harness_meta.py` (6, 1 slow) |

## Gates run (this checkout)

| Gate | Command | Result |
|---|---|---|
| Version | `python scripts/check_version.py` | PASS (5.0.0) |
| Truncation audit | `python scripts/verify_no_silent_truncation.py` | PASS |
| Compile | `python -m compileall -q cqhecs tests scripts python_bridge` | PASS |
| Lint | `flake8 ... --select=E9,F` | clean |
| Python | `python -m pytest tests/ -q` | **2862 passed, 105 skipped, 1 deselected** (390.9 s; W0 baseline: 2814/109) |
| Mutation | `python scripts/run_mutation_tests.py` | 60/60 killed |
| Web unit + build | `cd web && npm test && npm run build` | 71/71; tsc + bundle budget green |

## Not run / deferred (honest)

- **W3-10** (total deadline covers proof checking in `sat_external`/OMNIWAVE). Deferred: a correct
  fix bounds the proof budget by the *remaining* grand deadline, which needs a deadline threaded
  from `unified` into each engine. The current `max(10, 2×timeout)` overrun is documented but not
  yet fixed. See `BLOCKERS.md` B-005.
- **W3-02 / W3-03 / W3-04** (Path B hygiene, Path C exact-label audit, Path B vs dense): not started.
- **W3-11** (python-sat child-process isolation): NOT RUN — `python-sat` is not installed here.
- **W3-13 / W3-14 / W3-16 / W3-20 / W3-21**: not started (axe tags, Rust pin, llms.txt,
  licence register, QG board reconciliation).
- Web e2e (`npm run e2e`): NOT RUN (Playwright browsers not verified here).
- Native CTest: not re-run after the prior agent's CPU-only work (W0 recorded 21/21).
- W3-10, D12 and the whole of Waves 4–11 remain open.

## Next steps (highest value first)

1. W3-10 deadline threading (D3 second half).
2. W3-03 Path C "exact" label audit (D12) across CLI/Studio/web.
3. W3-02 Path B hygiene (D10) and W3-04 Path B vs dense measurement.
4. W3-20 licence register and W3-21 QG board reconciliation.
5. Enter Wave 4 (contracts/schemas) once Wave 3 exits.
