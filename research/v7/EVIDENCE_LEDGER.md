# Evidence ledger (v4.0.0)

Each shipped claim maps to code, a test or measurement, and a trust label. Labels
follow AGENTS.md section 4.4; nothing here is "formally verified".

| ID | Claim | Code | Evidence | Label / status |
|---|---|---|---|---|
| E-01 | The plan is built without allocating a backend | `cqhecs/execution_plan.py` | `test_dry_run_allocates_no_backend` (all four backend constructors and `execute` poisoned) | tested |
| E-02 | Plan selection equals the router's; capability comes only from the manifest | `execution_plan.py`, `router.py` | `test_plan_matches_router_selection_and_manifest` over 5 circuit families | tested |
| E-03 | Forced incapable path is refused, never rerouted | `_plan_from_props` | `test_forced_unsupported_path_...`, mutant "ExecutionPlan reroutes a forced incapable path" killed | tested + mutation |
| E-04 | Python, CLI, MCP and Studio return the same plan JSON | `cli.py`, `mcp_server.py`, `studio/app.py` | `test_cli_mcp_studio_return_the_python_plan` | tested |
| E-05 | Plan estimates are heuristics | `_estimate_path` | `estimate_quality="heuristic"`, saturation test | documented limitation |
| E-06 | `count_models(method="separator")` returns the exact count | `cqhecs/sat_separator.py` | 3,000+ exhaustive 3-variable formulas, 300 random vs brute force + DPLL, 3 mutants killed | tested + mutation (exact counting; no proof object is produced) |
| E-07 | Budget/deadline refusals never return a partial count | `count_by_elimination`, `count_models` | `test_table_budget_returns_unknown_...`, `test_deadline_returns_unknown` | tested |
| E-08 | Separator is faster on bounded-width families and slower on high-width random 3-SAT | `scripts/sat_separator_benchmark.py` | `evidence/sat_separator_bench.json` (3 repeats, 11 families, one machine) | measured, finite, no general claim |
| E-09 | DPLL counter no longer raises `RecursionError` | `sat.py:_count_models_dpll` | `test_dpll_counter_refuses_deep_recursion_instead_of_crashing` (red before fix) | tested |
| E-10 | Path D native X/Y/Z values equal Qiskit within 1e-9 (untruncated) | `path_d_sparse_pauli.py` | 120 random circuits, exhaustive 1-/2-qubit tables | tested vs independent oracle |
| E-11 | Each observable's true error <= its own bound | `evaluate_pauli_observables` | 150 truncated circuits (>50 with nonzero bound), mutant "bound never accumulates" killed | tested + mutation (float64 roundoff not in the bound) |
| E-12 | Y phase is correct | `pauli_observable_from_ops` | table tests + mutant "Y loses its phase" killed | tested |
| E-13 | Native C++ core and shaders unaffected | `src/`, `shaders/` | CTest 21/21, 13/13 SPIR-V | tested (Windows only) |
| E-14 | Web app unaffected | `web/` | 17/17 unit, 13/13 Playwright + axe (local) | tested |

## Claims explicitly NOT made

No claim of a complexity improvement; no comparison with external counters or
Pauli-propagation tools; no formal verification; no GPU/Vulkan end-to-end claim; no
statement about real QPU hardware; the plan's estimates are not guarantees; no
statement about any ETH/SETH/P-vs-NP question.

---

# V7 section (E3, 2026-11-22): evidence ledger for 7.0.0 (release candidate)

Append-only: everything above this line is the v4.0.0 record and is unchanged. Starting SHA `25e16e5`;
candidate HEAD at writing `38e799b3650e74a47d3a72184da50b5a85d5bb8b` (branch `release/v7-stable`, PR #55).
The tree at writing carries uncommitted Wave E edits by other agents, so nothing below is a claim about a
clean final freeze SHA; the integrator re-checks every row at the final freeze.

How to read the "SHA basis" column: Wave A-D evidence files were written while the work was still
uncommitted on a shared tree, and the work then landed in the commits named. `freeze` means the figure was
produced or recorded after `38e799b` (commit time 2026-11-22 07:38 +0100). `integrator-recorded` means the
number comes from `evidence/waveE_E2.md` (the integrator's freeze block) and was not re-run by E3. `not re-run`
means E3 read the file but did not repeat the command.

Labels follow AGENTS_V7 / AGENTS.md 4.4. `FORMALIZED_LEMMA` applies to the named lemma only; nothing in this
ledger is `FORMALLY_VERIFIED_COMPONENT`.

## V7.1 Evidence-file index (every Wave A-E file, with what it supports)

| Evidence file | Landed in | Supports (claim IDs below) | State |
|---|---|---|---|
| `evidence/waveA_A1.md` | `438c8c4` | E-V7-01, 02, 03 | read; focused run 203 passed, 14 skipped; full suite not run by A1 |
| `evidence/waveA_A2.md` | `5f12cb5` | E-V7-04, 05 | read; ctest 26/26 (Vulkan), 15/15 (CPU), MSVC ASan 9/9; GCC/Clang lane NOT_RUN |
| `evidence/waveA_A3.md` | `65cacd8` | E-V7-06 | read; web 91 unit, 63 Playwright at that SHA (superseded by C1 numbers) |
| `evidence/waveA_A4.md` | `b610224` | E-V7-07, 08, 09 | read; 441 separator tests, 1314 SAT-family passed, python-sat child isolation |
| `evidence/waveA_A5.md` | `2049073` | E-V7-10, 11 | read; full suite 2896/109 at `6fe4f01`; Lean L-STAB-01 / L-PAULI-01 |
| `evidence/waveB_B1.md` | `508334b` | E-V7-12 | read; 44 + 94 passed |
| `evidence/waveB_B2.md` | `bf85277` | E-V7-13 | read; 261 passed; replay 353 checks, 0 failed |
| `evidence/waveB_B3.md` | `48f5882` | E-V7-14 | read; QG UI 45 + 34 pytest, 14 Playwright |
| `evidence/waveB_B4.md` | `9b094c4` | E-V7-15 | read; 15 new + 65 passed, 4 skipped |
| `evidence/waveB_B5.md` | `ace3c1a` | E-V7-16 | read; 85 passed; E/F/G all `RESEARCH_ONLY` |
| `evidence/waveC_C1.md` | `d56c5cc` | E-V7-17 | read; web 167 unit, Playwright 128 passed / 1 skipped |
| `evidence/waveC_C2.md` | `f4dc089` | E-V7-18 | read; packaged at an earlier base, dirty tree, Python 3.14.6 (see PACKAGING_AUDIT) |
| `evidence/waveC_C3.md` | `133ae64` | E-V7-02, 19 | read; service layer, QG routes, calibration v3 policy |
| `evidence/waveC_C4.md` | `440e367` | E-V7-20 | read; 63 doc-consistency tests (E3 re-ran 81 with the language tests, see waveE_E3.md) |
| `evidence/waveC_C5.md` | `51969fd` | E-V7-21, 22 | read; 205 passed + 14 strict xfail at that SHA; mutation 95/95 on a snapshot copy |
| `evidence/waveD_D1.md` | `c655e92` | E-V7-23 | read; repeated-operand refusal, `eval` removed from `python_bridge` |
| `evidence/waveD_D2.md` | `c631cf8` | E-V7-24 | read; SEC-M1, SEC-L1..L5, P-01 fixed; 182 + 798 passed |
| `evidence/waveD_D3.md` | `f912160` | E-V7-05, 25 | read; typed Vulkan refusal, `/Brepro`, release asset policy (workflows NOT run) |
| `evidence/waveD_D4.md` | `6260495` | E-V7-26 | read; Studio plan panel, 6 pytest + real-browser axe |
| `evidence/waveD_D5.md` | `c098971` | E-V7-11, 21, 27 | read; Lean L-RESULT-01; Python 3.14 lane; audit skeletons |
| `evidence/waveE_E2.md` | uncommitted | E-V7-28 | integrator freeze block (`freeze_sha` `38e799b`); E2 did not re-run it |
| `evidence/waveE_E3.md` | uncommitted | this section | E3 commands and results |
| `evidence/lean_freeze_build.txt` | uncommitted | E-V7-29 | `lake build` at freeze, exit 0 |
| `evidence/LEAN_BUILD.md`, `LEAN_ENV.md` | earlier W4 commits | E-V7-10, 29 | toolchain and pin record |
| `evidence/PATHB_DOMINANCE.json`, `sat_separator_bench.json`, `waveA_A4_separator_calibration.json` | W3/A4 | E-V7-08, 12 | raw measurements |
| `evidence/waveE_E1.md`, `waveE_E4.md`, `waveE_E5.md` | not present when E3 wrote this | none | `NOT_RUN` by E3: add rows when those files exist; `waveE_E5.md` wins over `waveE_E2.md` on any freeze number |

## V7.2 Claim-to-evidence rows

| ID | Claim | Code | Evidence / command | SHA basis | Label / status |
|---|---|---|---|---|---|
| E-V7-01 | MCP server answers `ping` during a solve, cancels with a typed `CANCELLED` result (no verdict), negotiates protocol revisions up to 2025-06-18 | `cqhecs/mcp_server.py` | `tests/test_mcp_cancel.py` 6, `tests/test_mcp_protocol.py` 22; A1 | landed `438c8c4`; not re-run | tested; compute is abandoned, not stopped; later MCP revisions NOT_RUN |
| E-V7-02 | One service layer; Python, CLI, MCP and Studio return the same plan and typed errors | `cqhecs/service.py` | `tests/test_cross_surface_parity.py` 9; C3 | `438c8c4`, `133ae64`; not re-run | tested on a 6-case corpus |
| E-V7-03 | Studio guard (Host/Origin allow-list, bearer token, JSON-only, bounded drain) is in the tree; OpenAPI is generated and route-drift guarded | `cqhecs/studio/app.py`, `schemas/studio.openapi.json` | `tests/test_studio_security.py` 21, `tests/test_schema_contracts.py` 13 passed / 1 skipped | not re-run | tested; `openapi_spec_validator` absent (NOT_RUN) |
| E-V7-04 | Native C ABI refuses unsupported wide T/RZ circuits and reports timeouts as no-verdict; Vulkan failures are checked, fault-injected and device loss is latched | `src/`, `include/cq_hecs_api.h` | A2: ctest Vulkan 26/26 and CPU-only 15/15; BCP differential 1,052,908 cells, 0 mismatches; fault-injection suites | `5f12cb5`; ctest counts integrator-recorded at freeze | tested locally on one AMD iGPU, MSVC, Windows; the hosted Linux job also passed CTest 26/26 on llvmpipe (`waveE_E3.md`) |
| E-V7-05 | `cq_hecs.exe` without a Vulkan ICD refuses (exit 3, `vulkan_unavailable`) instead of printing `VERIFIED`; MSVC Release binaries reproduce bit-for-bit across two builds of two targets | `src/main.cpp`, `CMakeLists.txt` | `tests/test_native_vulkan_refusal.py` 7 passed; hashes in D3 | `f912160`; not re-run | tested; reproducibility shown for `cq_hecs.exe` and `cq_hecs_core.dll` on this machine only; red run on the pre-fix binary NOT_RUN |
| E-V7-06 | Web falls back from a lost WebGPU device to WASM; keyboard/touch composer; XSS and low-memory cases covered | `web/src/fallback.ts` etc. | A3: 91 unit, 63 Playwright (superseded by E-V7-17 figures) | `65cacd8` | tested; screen-reader use NOT_RUN |
| E-V7-07 | External CaDiCaL runs in an isolated child; a crashed, lying or garbage child gives `UNKNOWN`/uncertified; a clean result followed by an abnormal exit is re-verified by the parent with a warning | `cqhecs/sat_external.py` | `tests/test_sat_external_isolated.py` 12 (11 without python-sat); 56 passed with python-sat on 3.14 (D5) | `b610224`; D5 on a throwaway venv | tested; the underlying python-sat exit abort is OPEN (B-V7-01) |
| E-V7-08 | Separator counting preflights its table bound `2**(w+1)` and returns `UNKNOWN` before allocating; observed table never exceeded the bound in 31 rows | `cqhecs/sat_separator.py` | `evidence/waveA_A4_separator_calibration.json`; `tests/test_sat_separator.py` (441 passed with its neighbours) | `b610224` | measured, finite; the bound is an upper bound, not a runtime estimate |
| E-V7-09 | DRAT tamper matrix: truncations, reorderings, wrong formula, false proofs rejected; budget exhaustion gives `valid=None` | `cqhecs/drat.py` | `tests/test_drat_tamper.py` 16 | `b610224` | `DRAT_CHECKED` by the in-repo checker only; no LRAT reader exists in-repo |
| E-V7-10 | Lean workspace builds; L-BOUND-01 (Path D bound), L-STAB-01 (tableau symplectic invariant), L-PAULI-01 (Pauli rules) are checked | `formal/CQHECS/{Bound,Pauli,Stabilizer}.lean` | `lake build` exit 0; `PrintAxioms`: only `propext`, `Classical.choice`, `Quot.sound`; A5 | `2049073`; rebuilt at freeze, E-V7-29 | `FORMALIZED_LEMMA`, specification models only; not refinement-linked; Comparator/nanoda NOT_RUN for these |
| E-V7-11 | Spec-correspondence tests tie the Lean statements to Path A and Path D behaviour (132 tests) | `tests/test_stabilizer_spec_correspondence.py`, `tests/test_path_d_spec_correspondence.py` | A5: 66 + 269 passed (Qiskit 2.6.1, Stim 1.16.0 present) | `2049073`; not re-run | tested vs independent oracles |
| E-V7-12 | Path B drops branches with weight at most 1e-15 and reports the mass; Path C reports discarded spectral mass as a diagnostic, not a bound; Path B is slower than a dense statevector on every measured case | `path_b_*.py`, `path_c_*.py` | B1: 44 + 94 passed; `PATHB_DOMINANCE.json` | `508334b`; not re-run | tested; dominance is a finite measurement on one machine |
| E-V7-13 | QG workbench: competing BMV models, SYK Trotter oracle, Z2 leakage, plan parity, offline replay of the historical campaign (353 checks, 0 failed) | `cqhecs/quantum_gravity/` | B2: 261 passed | `bf85277`; `replay.py` is edited at writing (not re-run) | tested for finite models; no physical claim; historical campaigns immutable |
| E-V7-14 | QG workspaces in Web and Studio: Run disabled until assumptions are confirmed, typed refusal, no console errors | `web/src/qg*.ts`, Studio static | B3: 14 Playwright, 8 Studio tabs at 1280 and 360 px | `48f5882` | tested in Chromium; Studio smoke was an ad hoc script until D4 added `studio_ui_e2e.mjs` |
| E-V7-15 | Noise calibration v3: FIT/EVAL separation enforced, channel checks, provenance labels | `cqhecs/calibration_v3.py` | B4: `tests/test_noise_governance.py` 15 passed; 65 passed, 4 skipped neighbours | `9b094c4` | tested; VALIDATION split, transpilation and held-out QPU evaluation NOT_RUN |
| E-V7-16 | Paths E (2D tensor network), F and G are `RESEARCH_ONLY`; the router is unchanged | `tests/research_prototypes/` | B5: 85 passed; outcomes E `INCONCLUSIVE`, F and G `NOT_SUPPORTED` for promotion | `ace3c1a` | research record; absent from stable defaults |
| E-V7-17 | Shared web/Python conformance corpus (21 circuits, 4 refusals), run-card import, state and visual specs, WebGPU precision declared | `web/scripts/export_shared_conformance.py`, `docs/CONFORMANCE.md` | C1: web unit 167/167; Playwright 128 passed, 1 skipped (WebGPU conformance, no adapter). E3 re-ran `npm test` on the working tree: 167/167 | `d56c5cc`; Playwright integrator-recorded | tested in Chromium; WebGPU f32 on a real adapter only partially (E5 `RUN_PARTIAL`, one AMD RDNA2 adapter, 20 cases, worst TV 7.8e-8); Firefox/WebKit NOT_RUN |
| E-V7-18 | Reproducible wheel; sdist reproducible after normalisation; onedir EXE and native CPU/Vulkan zips with CycloneDX SBOMs and a SHA-256 manifest | `scripts/package_*.py`, `scripts/sbom_cyclonedx.py`, `scripts/build_exe.ps1` | C2 on a dirty tree; rebuilt at `38e799b` (hashes in PACKAGING_AUDIT) | `f4dc089`; `38e799b` artifacts integrator-recorded | tested outside the repo with a clean venv, non-admin; clean-machine install NOT_RUN |
| E-V7-19 | QG plan is served on CLI, MCP, Studio and the service; paid Open Quantum routes are typed refusals; local QG path imports no network module | `cqhecs/service.py`, `cqhecs/studio/app.py` | C3 (AST no-network test) | `133ae64`; `service.py` edited at writing | tested; no QPU call made by any V7 task |
| E-V7-20 | Docs describe the current tree; one authoritative architecture file; migration notes exist | `ARCHITECTURE.md`, `MIGRATION_V7.md` | `tests/test_doc_consistency_v7.py` 63 (C4); 81 with the language tests (E3 re-run) | `440e367`; re-run on the dirty tree | tested for the pinned statements only; see CLAIM_AUDIT |
| E-V7-21 | Mutation harness has 95 mutants and the count pin is a floor, not a literal | `scripts/run_mutation_tests.py`, `tests/test_mutation_harness_meta.py` | C5/D5: 95/95 killed on a snapshot copy; freeze run `mutation_freeze.txt` 95/95 (E3 read its last lines) | snapshot; freeze integrator-recorded | tested by listed patches only; the baseline 64 in `BASELINE_V7.md` is history |
| E-V7-22 | Fuzz, property and resource tests for requests, DIMACS, QASM, cancellation | `tests/test_fuzz_*.py`, `tests/test_resource_limits.py` | C5: 205 passed, 14 strict xfail at `51969fd`; the xfails became passing tests in D1/D2 | `51969fd`, `c655e92`, `c631cf8` | tested; hypothesis `derandomize=True` |
| E-V7-23 | Repeated gate operands (`cx q[0],q[0]`) are refused in parsing before routing; `eval` removed from `python_bridge` (SEC-M2) | `gate_manifest.py`, `circuit_parsing.py`, `python_bridge/qasm_engine.py` | D1: `tests/test_circuit_repeated_operands.py`; old-vs-new differential on 25 legal expressions | `c655e92`; not re-run | tested; non-grammar angle text now refused (behaviour change, listed in MIGRATION_V7) |
| E-V7-24 | DIMACS header capped at 1,000,000 variables; strict ASCII integer tokens; big counts serialised exactly; Studio/MCP typed errors; occupied Studio port exits 4 | `cqhecs/sat.py`, `studio/app.py`, `mcp_server.py`, `cli.py` | D2: 182 + 798 passed, 15 skipped | `c631cf8`; not re-run | tested; the cap lives in `parse_dimacs`, a directly built `CNF(...)` is not capped |
| E-V7-25 | Release asset set is defined by `package.yml` and consumed by `release.yml`; the tag must be an ancestor of `main` | `.github/workflows/{package,release}.yml` | `tests/test_native_release_workflow.py` 16 passed (D3); `release.yml` is edited at writing | `f912160` | linted; `package.yml` ran once on the PR at `38e799b` (2 of 5 jobs failed, 1 skipped, `waveE_E3.md`); `release.yml` has not run (B-V7-09) |
| E-V7-26 | Studio shows the ExecutionPlan with rejected-candidate reasons, ESTIMATE labels, typed refusal and error states | `cqhecs/studio/static/app.js` | `tests/test_studio_plan_ui.py` 6; real headless Chromium at 1280 and 360 px, axe critical+serious 0 | `6260495` | tested in Chromium; Firefox/WebKit, screen reader and Studio i18n NOT_RUN |
| E-V7-27 | Lean L-RESULT-01: seven lemmas on the `SimulationResult` state/flag table; Python pin enumerates all 16 flag combinations | `formal/CQHECS/Result.lean`, `tests/test_formal_result_contract.py` | D5: `lake build` 8711 jobs, 3 pytest | `c098971` | `FORMALIZED_LEMMA` for the named statements only |
| E-V7-28 | Freeze numbers at `38e799b`: Python 4269 passed / 134 skipped / 0 failed; mutation 95/95 in place; web unit 167/167; Playwright 128 passed, 1 skipped; ctest 26/26 (Vulkan) and 15/15 (CPU) | n/a | `evidence/waveE_E2.md` block; `freeze_pytest.txt` last line read by E3 (4269 passed, 134 skipped, 1 deselected, Python 3.13.13) | `38e799b`, integrator-recorded | partial: the skip-budget gate FAILS on that run (TEST_MATRIX V7, B-V7-11) |
| E-V7-29 | Lean workspace builds at freeze: `Build completed successfully (8711 jobs)`, Lean 4.33.1 | `formal/` | `evidence/lean_freeze_build.txt` (exit 0, 2026-11-22 08:20 UTC) | after `38e799b` | `FORMALIZED_LEMMA` scope only |

## V7.3 Claims explicitly NOT made in 7.0.0

No claim about P versus NP, ETH or SETH. No claim of a speedup over CaDiCaL, sharpSAT, d4, Qiskit Aer, Stim or
any Pauli-propagation tool. No end-to-end GPU claim (Vulkan was exercised on one AMD iGPU; WebGPU f32 on a real
adapter is NOT_RUN). No claim that Paths E, F, G or the Path C ordering are shipped features. No CDCL, no
CNF-to-XOR extraction. No LRAT, `drat-trim` or `cake_lpr` verdict. No formal verification of any component:
the Lean work is specification-level lemmas. No claim about the physical world from the QG workbench (finite
models only), and no QPU job was submitted by any V7 task. Hardware-noise claims rest on the historical
external dataset (`r-io-7`), not on this release.
