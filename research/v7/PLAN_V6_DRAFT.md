# CQ-HECS First Plan (Wave-1 integration)

Date: 2026-11-21. Baseline: `main`, version 5.0.0. Method: integration of Wave-1 repo audits and web research for 10 parts. This plan is a proposal, not a record of work done.

## Honesty and confidence notes (read first)

- Repo claims below cite file paths taken from the Wave-1 audits. I did not re-open the repo in this integration step. Line numbers can drift. Every "defect" is a claim to reproduce with a failing test before any fix (AGENTS.md section 2.4).
- Web claims cite only URLs that appear in the findings. Many findings rest on search excerpts, not full page reads. Almost no licence was actually verified. Treat every licence as "unverified" unless this plan says otherwise. Only Qiskit Aer, TensorCircuit and Qiskit MCP servers (Apache-2.0), QuEST, Qulacs and Radix (MIT), and mcp-solver (MIT, per its README) were stated in findings.
- Conflicting or soft evidence:
  - SAT Competition 2025: one slide excerpt lists CaDiCaL-SC2025 first on the sequential main track. The IJCAI 2026 paper says AE-Kissat-MAB won main and SAT. This is unreconciled. Do not quote a winner.
  - MCP spec 2026-07-28 (stateless, `server/discover`, tasks extension) comes from the changelog page only. Its release status versus draft is unconfirmed. Hint-field names (`readOnlyHint` etc.) were not confirmed.
  - The `cq_hecs_core` CPU-only build: one audit says CMake text leaves it unclear. Research/v7/EXECUTION_LOG.md reportedly records a CPU-only CTest pass (15 tests). The CMake text was read, not run. Needs a run.
  - Baseline numbers conflict between research/v7/BASELINE.md / TEST_MATRIX.md (older counts) and BASELINE_W0.md (2814 passed, 109 skipped, 61 web, 21 CTest). Use BASELINE_W0.md as the working baseline and reconcile the others.
  - A2A v1.0 details are secondary-source only. Amazon Braket API research returned nothing.
- Not researched: Vercel deployment provenance, Windows Vulkan runtime packaging, and any real UI screenshots of SAT tools. SOTA benchmark numbers were collected for none of the comparators.

---

## 1. Current state: what CQ-HECS can and cannot do

### Can do (evidence from audits)

| Area | Capability | Evidence |
|---|---|---|
| Quantum paths | Four capability-first paths from one gate manifest: A stabilizer (<=4096 qubits), B low-T dense-branch sum (<=22 qubits), C untruncated disk-paged MPS with swap routing, D sparse-Pauli observables with per-observable discarded-mass bound. Fail-closed router, forced paths never reroute, dynamic circuits refused. | `cqhecs/router.py`, `cqhecs/gate_manifest.py`, `path_*.py` |
| Planning | Dry-run `ExecutionPlan` (digest, interaction summary, heuristic estimates, rejection reasons, `plan_check` after run). Exposed through Python, CLI (inside analyze), MCP, Studio. | `cqhecs/execution_plan.py` |
| Observables | X/Y/Z Pauli observables in Path D, H4-PAULI-01 SUPPORTED_IN_SCOPE. | `research/v7/TASKS.md:17` |
| Noise | CPTP channels with Kraus checks, `BackendProfile` schema 1.0/2.0, IBM calibration import without clipping, offline `FakeHardwareBackend` (<=10 qubits density matrix), measured M-FIT-2 profiles, preregistered 25-job suite with FIT/EVAL split. | `cqhecs/hardware_bridge.py`, `calibration_import.py`, `noise_fit.py`, `openquantum_suite.py` |
| Hardware boundary | Fail-closed real-hardware stub; modes IDEAL/NOISY/REAL separated; provenance card `hcs.run.v2`. | `hardware_bridge.py:1266-1299`, `cqhecs/provenance.py` |
| Quantum Gravity layer | BMV two-qubit model with closed-form oracles; sparse q=4 SYK (dense <=8 qubits) with evolution, Loschmidt, Trotter scan, OTOC; Z2 gauge toy; declared noise with Hoeffding interval; deterministic QASM + manifests; CLI/Studio/MCP local surfaces for BMV only. Real-QPU evidence on rigetti:cepheus-1-108q (25/25 Spark), failures recorded honestly. | `cqhecs/quantum_gravity/*`, `research/qg_2026/*` |
| SAT | Strict DIMACS, scan and watched DPLL, tree-resolution certificate, exact #SAT (DPLL and bounded-width separator, `count_models(method=auto)`), independent DRAT checker, OMNIWAVE exhaustive cube search with DRAT proof, optional CaDiCaL adapter, unified portfolio. | `cqhecs/sat.py`, `sat_separator.py`, `drat.py`, `omniwave/`, `unified.py` |
| Native | C++20 core with C ABI, Vulkan primitives, `-DCQ_ENABLE_VULKAN=OFF` CPU-only lane, `cq_core_build_capabilities()`, ASan/UBSan lane (4 tests), lavapipe CI. | `CMakeLists.txt`, `src/cq_c_api.cpp`, `.github/workflows/ci.yml` |
| Web | Rust/WASM f64 statevector in a worker, optional WebGPU f32 with WASM cross-check for n<=20, safe-run limits, SAT lab, EN/DE/FR, run card export, axe + Playwright (32 e2e). | `web/src/*`, `web/e2e/*` |
| Studio / API / MCP | Loopback-only Studio with bearer token and request caps; CLI with exit-code contract and one-JSON-document stdout; stdio MCP with 11 tools; typed `hcs.run.v2` schema. | `cqhecs/studio/app.py`, `cqhecs/cli.py`, `cqhecs/mcp_server.py` |
| Release | Wheel and sdist, clean-venv smoke, SHA-pinned Actions, CI gate on exact SHA before tagging, checksum file and hand-written SPDX SBOM. | `.github/workflows/release.yml` |
| Verification | W0 baseline 2814 passed / 109 skipped; 60 hand-written source mutants (60/60 killed in v7 evidence); coverage floor 70%; pinned external Lean/Comparator/nanoda evidence for a third-party artifact; per-version evidence ledgers. | `research/v7/BASELINE_W0.md`, `scripts/run_mutation_tests.py` |

### Cannot do (current limits)

- Dynamic circuits (mid-circuit measure, reset, feed-forward) on every path. No classical-bit remapping.
- Path B is a dense 2^T-branch statevector sum with a 22-qubit wall, not a true stabilizer-rank method.
- Path C uses identity site order only. Planner cut metric is not an upper bound. No decision diagrams, no graph-aware tensor-network contraction, no checkpoint/resume, no learned or calibrated router (H4-ROUTE-01 DEFERRED).
- No transpile-to-native-basis before noise. No uncalibrated-gate warning. IBM-only calibration import. No error mitigation. Noisy density matrix capped at 10 qubits. No provider adapter: real QPU runs happen only through an external script.
- SAT: no CDCL, no preprocessing, no LRAT pipeline in the package, no cube-and-conquer, Python GIL limits OMNIWAVE, general CNF-to-XOR extraction absent. In-repo engines are far slower than CaDiCaL.
- QG: SYK and gauge cannot be run from CLI/Studio/MCP. SYK Trotter circuits (`qasm/syk_qpu_v3`, `v5`) are not reproducible from code. No QG UI anywhere. SYK capped at 8 qubits. Live QPU blocked until a new key is supplied (STATUS.md).
- Native: not an end-to-end GPU simulator. No CPU-vs-Vulkan differential, no device-loss tests, no GPU timing split.
- Web: WebGPU refuses mid-circuit measure and gate noise. WebGPU is not exercised in CI. Cancel is `worker.terminate()`. Run card has all error fields null.
- Studio: no i18n, composer not keyboard-operable, no design tokens or component catalogue.
- MCP: protocol 2024-11-05 hard-coded, no tool annotations, no `outputSchema`, errors as protocol errors, unbounded timeouts.
- Release: no PyPI, no signing or provenance, no native binaries in releases, floors-only SBOM, no supply-chain automation.

### Defects and honesty risks found (reproduce before fixing)

| # | Claim | Part | Evidence |
|---|---|---|---|
| D1 | Path A returns counts summing to 100, not requested shots, when n>30 and the tableau is nontrivial. Disclosed only in metadata `sampled_shots`. | P1 | `path_a_stabilizer.py:290-292` |
| D2 | Runner ledger guard sums only `submitted` events: ledger has 27 submitted, 2 refunded, so the guard reads 27 > 25 and refuses all future submits. Corrupt ledger lines are skipped silently (budget fails open). `collect` ignores `oq` exit codes and always logs "collected". `submit` is not idempotent. | P2 | `scripts/run_qg_openquantum_campaign.py:90-106, 374-431` |
| D3 | `solve_unified` labels CaDiCaL UNSAT as "DRAT proof checked" whenever status is UNSAT, even if the proof check was rejected, undecided or disabled. Default first engine (watched) emits uncertified UNSAT. `UnifiedResult` has no `certified` field. A proof check can overrun the stated total timeout (max(10 s, 2x timeout)). | P4 | `unified.py:184,192`, `sat_external.py:91` |
| D4 | Uncalibrated gates are simulated noiseless while the result is still labelled NOISY_CLASSICAL with a hardware profile id. `create_linear_profile` stamps `capture_timestamp` with the current time. | P2 | `hardware_bridge.py:1153-1160, ~1090` |
| D5 | Web run card `modeOf()` ignores `xflip` and per-qubit `p01/p10`, so such noisy runs export as SAMPLED. No `device.lost` handling in WebGPU. | P6 | `web/src/provenance.ts`, `web/src/gpu.ts` |
| D6 | Native Vulkan legacy engine ignores `VkResult` on fence/submit/wait with an infinite timeout. C ABI `cq_apply_*` return void on null/out-of-range; `cq_apply_rz` uses a bare cast to fixed point. | P5 | `src/vulkan_engine.cpp:531-534`, `src/cq_c_api.cpp:30-108` |
| D7 | MCP failures are generic -32000 protocol errors; `timeout`, `workers`, `waves`, `limit` are unbounded. | P8 | `mcp_server.py:230,275,365,412` |
| D8 | Release uses unpinned `setuptools`/`wheel`/`build`; SBOM lists dependency floors and uses `datetime.now`; SECURITY.md supports only 4.0.x; classifiers claim Production/Stable and C++ though the wheel is pure Python. `package_release.ps1` deletes `dist` and ships the historical `docs/ARCHITECTURE.md`. | P9 | `release.yml:166-167`, `SECURITY.md`, `scripts/package_release.ps1` |
| D9 | Stale QG board: STATUS.md says 21/25 and "M6 BLOCKED" next to "25/25 complete"; FINDINGS F-08 states a 0.85-1.0x range while the table gives about 0.78; the F-10 Aer scan script is not in the repo; `QGRAVITY.md` links dangle in this worktree. | P3 | `research/qg_2026/*` |
| D10 | Path B silently skips branches with weight <= 1e-15 without recording discarded mass; stale comment says n<=16 while limit is 22. Path A has its own regex QASM parser beside `circuit_parsing.py`. | P1 | `path_b_stabilizer_rank.py:124-145`, `path_a_stabilizer.py:511-546` |
| D11 | Evidence drift: `tests/test_mutation_harness_meta.py:11` says "35-mutant", the harness has 60. Two baseline files with different counts. 109 skips are not budgeted. | P10 | as cited |

---

## 2. Gaps in AGENTS_V6.md

AGENTS_V6.md has backlog items T6-01..T6-13 and waves W0-W9. Items per part that the audits found missing:

| Gap | Part | Why it matters |
|---|---|---|
| No quantum-path item at all except QG ExecutionPlan (T6-01). M6 (Path C ordering) and H4-ROUTE-01 are DEFERRED and not carried over. E1-E4 candidates have no task. No Stim/Aer differential or router-regret benchmark. | P1 | AGENTS.md section 7.2 requires these oracles. |
| Only T6-09 and T6-10 touch noise/hardware. No basis-aware noise (H4-NOISE-01), no calibration schema v3, no uncalibrated-gate policy, no provider adapter, no runner fixes, no mitigation. | P2 | D2 and D4 are live honesty issues. |
| No task to make SYK circuits reproducible, wire SYK/gauge into surfaces, test the runner offline, or reconcile qg_2026 status files. | P3 | F-10 INCONCLUSIVE cannot be reproduced. |
| Only T6-08 "keep budgets + proof soundness" with no acceptance criterion. No certified field, proof deadline, DRAT performance, LRAT lane, count schema, CDCL, XOR, benchmark harness. | P4 | D3 conflicts with the W5 gate "every UNSAT certificate replayed". |
| T6-04 has no oracle, tolerance policy or software-vs-hardware ICD split. No ABI versioning, wider sanitizer coverage, fuzzing, GPU timing split, CPU-only packaging, legacy-engine removal. | P5 | AGENTS_V6.md:126 promises sanitizers. |
| T6-05/T6-06 lack a design (WebGPU CI lane, cooperative cancel, run-card error scope, low-memory tests, plan schema sharing). | P6 | WebGPU is untested in CI. |
| Only T6-02 for UI. No WCAG 2.2 criteria, design tokens, composer accessibility, Studio i18n, canonical-UI decision, H4-UX-01 measurement. | P7 | axe cannot check keyboard operability or target size. |
| Only T6-01 for the surface. No MCP spec conformance, annotations, `outputSchema`, `isError`, resources, schemas/OpenAPI, shared service layer, `llms.txt` refresh. AGENTS_V6.md:88 says freeze contracts but only `hcs.run.v2` has a schema. | P8 | D7. |
| T6-07 names CPU/Vulkan EXEs but `release.yml` builds none. No signing, provenance, PyPI, reproducibility, SBOM quality, Dependabot/Scorecard, Vercel gating, deployed-SHA check. | P9 | Claimed assets must match published assets. |
| T6-11 generic. No mutant targets for QG/router/plan, no external-checker lanes, no skip budget, no formal lemmas, no T6-13 audit checklist, no ledger reconciliation. | P10 | D11. |

---

## 3. Prioritized roadmap (by part)

Effort: S <= 1 day, M 2-4 days, L > 4 days (agent-days, rough). Risk: L/M/H. "Wave" refers to section 5. Each item must ship with a failing-first test (AGENTS.md section 2.4) and a status per section 2.3.

### P1 Quantum paths (owner: quantum algorithms)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P1-01 | Fix Path A 100-shot cap (D1): proper batch sampling or typed refusal; migration note | M | L | Counts sum to requested shots, or a typed refusal; no silent truncation | Stim sampler (optional) and statistical test vs tableau marginals; `scripts/verify_no_silent_truncation.py` extended | R0 |
| P1-02 | Path B hygiene (D10): record discarded mass for skipped branches, fix stale comment; unify Path A parsers with `circuit_parsing.parse_circuit` | S | L | Parse parity tests; discarded mass visible in result | Dense statevector oracle; parser parity corpus | R0 |
| P1-03 | Optional oracle lane: Stim for A, Qiskit Aer for A/B/C on a shared circuit corpus; also seeds the router benchmark corpus | M | L | Lane runs in nightly; skipped = NOT RUN, never PASS | Stim, Aer, dense statevector | R2 |
| P1-04 | Honest Path B: either relabel as exact low-T dense method, or prototype a sparse/extent-based method (research only) | S relabel / L method | M | Docs and `PATH_CAPABILITIES` match code; any new method beats B on a declared family | Dense oracle; Aer extended_stabilizer as comparator (Aer docs mark it approximate) | R3 / R6 |
| P1-05 | Path C logical-to-site ordering planner (opt-in `ordering=identity|auto|<heuristic>`), un-defer M6 | L | M | Meets AGENTS.md section 3.3 promotion gate: wins on >=2 families, no material regression, no mapping mismatch | Exhaustive permutations for small n; dense oracle; injected-mapping-bug test; cotengra as external comparator (licence unverified) | R3 |
| P1-06 | Router cost calibration on a held-out circuit-family benchmark (H4-ROUTE-01); fix the planner cut metric so it uses the chosen order and admits swap overhead | M | L | Regret and refusal rates recorded; thresholds changed only if held-out wins | Corpus from P1-03; preregistered split | R3 |
| P1-07 | Generalized Pauli grammar and phase checks beyond current X/Y/Z, coefficient-basis statement in docs | M | M | Bound >= observed error on random small circuits; basis documented | Dense-matrix oracle; PauliPropagation.jl as comparator (licence unverified) | R3 |
| P1-08 | Observable-first planner (Path D vs forward MPS vs tableau) | M | M | Certified scope never extended to counts | Exact small-circuit oracle | R6 |
| P1-09 | Dynamic circuits in Path A (measure-and-correct Clifford) with re-specified classical-bit semantics | L | H | Spec first; typed refusal for everything else | Stim, Aer | R6 (spec only before) |
| P1-10 | Research prototypes: QMDD vs MQT DDSIM, graph-aware TN contraction vs quimb/cotengra, MPS checkpoint/resume (E1, E2, E4) under `research/v7/prototypes/`, not imported by stable code | L | M-H | Hypothesis ID and held-out benchmark per prototype; router change only after a win | Dense oracle; comparators | R6 |

### P2 Noise and hardware (owner: noise/hardware)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P2-01 | Fix runner ledger (D2): net spend = submitted - refunded; fail closed on unparsable lines; `collect` checks exit codes; `submit` idempotent by preparation_id; quote re-check | S | L | Real `JOB_LEDGER.jsonl` fixture yields spent=25 net; corrupt line aborts | Fake `oq` script; ledger fixtures with refund/fail/corrupt | R0 |
| P2-02 | Uncalibrated-gate policy `refuse|warn|ideal`; list uncovered gates in result and run card | S | L | No silently noiseless gate under a hardware profile id | Unit tests; existing tests that relied on skipping updated explicitly | R0 |
| P2-03 | Deterministic `create_linear_profile`; rename or relocate the unrelated `cqhecs/hardware/` miner namespace | S | L | Stable digests across runs | Digest-stability test | R0 |
| P2-04 | Calibration schema v3 (provider/job IDs, units, freshness window, uncertainty, label enum measured/synthetic/derived/post_hoc, layout provenance) plus migration; stale-calibration warning | M | M | Old profiles migrate; label never blurred in any surface | Pinned fixture hashes; schema tests | R2 |
| P2-05 | Basis-aware transpile-then-noise (H4-NOISE-01) with pinned layout; refuse unsupported ops | L | M | Beats frozen baseline on preregistered held-out data (CI excludes 0) else stays experimental | Dense oracle for lowering; Aer `NoiseModel.from_backend` differential on small cases (Aer is Apache-2.0) | R3 |
| P2-06 | Multi-vendor importers (IQM, Quantinuum, Rigetti, Open Quantum payload), extend `to_target()` beyond cx/rz/sx/x | M | M | Pinned fixtures per vendor; unknown fields marked unknown | Fixture hashes | R3 |
| P2-07 | Quote-time topology/layout preflight in runner (avoids the SYK disconnected-qubit failures) | M | M | A circuit that would fail is refused before spend | Fake provider contract test with coupling data | R3 |
| P2-08 | Provider adapter behind the fail-closed boundary: quote, submit, status, result, cancel; per-run authorization object; shared ledger guard; offline fake provider; no live calls in CI | L | H | Only after P2-01 and P8 elicitation design; live use needs explicit user authorization and a new key | Fake-provider contract tests | R5 (design R1) |
| P2-09 | Mitigation module (readout-matrix inversion with bounds, ZNE) as a distinct result mode; clean-room, not importing GPL Mitiq | M | M | Variance overhead reported; never reuses `exact`/`certified` fields | Validation on the existing 25-job dataset | R6 |
| P2-10 | Wider noisy simulation (trajectories or MPS noise, idle noise from durations) | L | M | Sampling error reported; seed-reproducible | Density-matrix oracle at n<=10 | R6 |
| P2-11 | Complete runner `analyse`/`report`; offline runner tests | S | L | `analyse` no longer prints NOT_RUN | As P2-01 | R2 |

### P3 Quantum gravity (owner: QG)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P3-01 | Reconcile STATUS/TASKS/BLOCKERS/FINDINGS; fix F-08 ratio; restore dangling `QGRAVITY.md` references; re-verify literature DOIs | S | L | One truthful board; each claim cites a file | Doc-consistency script | R0 |
| P3-02 | Move SYK Trotter QASM generation into `circuits.py` with seeded manifests; add the F-10 Aer replay script | M | L | v3/v5 QASM regenerated bit-identically; re-simulation test | Existing ED oracle; SHA-256 manifest | R2 |
| P3-03 | SYK and gauge in CLI/Studio/MCP through the `cqhecs.qg.experiment.v1` envelope (`qg run-local --model`) | M | L | One envelope, no inline CLI payload; parity test | Cross-surface JSON parity | R1 |
| P3-04 | QG ExecutionPlan (surface, qubit count, dense cap, estimated spend) on all surfaces (T6-01) | M | L | Refusals visible before run | Plan schema tests | R1 |
| P3-05 | Calibration-aware BMV noise model, fit on F-08 scan, validate on drift/XX data, Holm correction and circuit-level bootstrap | M | L | Preregistered; INCONCLUSIVE if CI crosses null | Held-out drift data | R3 |
| P3-06 | Implement QG-GAUGE-02 (leakage) and QG-SYK-04 (mirror decay) locally, zero spend | M | L | Local oracles agree | Exact evolution | R3 |
| P3-07 | SYK/OTOC beyond 8 qubits via sparse or Path C/D routing | L | M | ED cross-check at n<=8 | Dense ED | R6 |
| P3-08 | T6-09 follow-up (forward+mirror via one layout pipeline) | M | M | Needs new key and explicit credit authorization; offline replay first | Aer replay, held-out noise check | R5 gated |
| P3-09 | Literature pins for 2026 BMV variants and the Sycamore wormhole critique, with SOURCE_CLAIM labels; claim scope text "entanglement witness model only" | S | L | Each source has status label; critique shown next to original | Doc review | R2 |
| P3-10 | Cross-check `fermions.py` against an independent JW mapper (Qiskit Fermions/Nature as dev-only oracle, licence/maturity unverified) | S | L | Small Majorana strings match | Independent mapper | R2 |

### P4 SAT and OMNIWAVE (owner: SAT/proof)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P4-01 | Add `certified` and `proof_level` to `UnifiedResult`; fix proof labels from `SATResult.certified` (D3) | S | L | CaDiCaL UNSAT with rejected/undecided proof is not labelled checked | Tamper tests; brute force | R0 |
| P4-02 | Certified-first UNSAT policy and distinct `UNSAT_UNCERTIFIED` status; total deadline includes proof check | S | L | Elapsed <= timeout + epsilon in tests | Timing tests | R0 |
| P4-03 | Isolate optional python-sat/CaDiCaL tests in a subprocess; `doctor` line for solver availability (known Windows/py3.14 abort) | S | L | Suite survives abort; skip reason explicit | Subprocess harness | R0 |
| P4-04 | DRAT checker rewrite: two-watched-literal propagation, incremental trail, optional backward/core-first | M | M | Real CaDiCaL proofs checkable within budget; no valid=True on timeout | Differential vs `drat-trim`; tamper/mutation tests | R3 |
| P4-05 | LRAT emission plus pinned `lrat-check` and `cake_lpr` lane, label `CAKELPR_CHECKED_VECTOR` scoped to the vector | M | M | Nightly Linux lane; missing tool = NOT RUN | cake_lpr, drat-trim | R2 |
| P4-06 | Typed count contract (`hcs.sat.count.v1`) and separator DP integrated into unified with width preflight; decimal-string bigints | M | L | Exact vs brute force; UNKNOWN on budget; never partial count | Brute force, DPLL; Ganak/d4/SharpSAT-TD as optional external oracles (licences unverified) | R1 |
| P4-07 | Held-out benchmark harness vs pinned CaDiCaL/Kissat and exact counters; SAT and UNSAT separated; raw JSON | M | L | Preregistered split; hashes pinned; licence check for instances | pyperf-style metadata (see P10-07) | R2 |
| P4-08 | Sound CNF-to-XOR extractor with implication witness (H4-XOR-01) | L | M-H | No GF(2) contradiction promoted to UNSAT without accepted proof | Exhaustive small formulas; DRAT/LRAT replay | R3 |
| P4-09 | Proof-carrying preprocessing (units, pure literals, components first; bounded BVE with logged resolvents); refuse SBVA-style re-encoding for #SAT | M | M | #SAT multiplicity exact | Brute-force counts | R6 |
| P4-10 | Opt-in CDCL prototype with DRAT output (H4-CDCL-01); cube-and-conquer with CaDiCaL on cubes and proof stitching (research) | L | H | No default change; every UNSAT proof-checked | Differential vs CaDiCaL, scan DPLL | R6 |
| P4-11 | OMNIWAVE branch/scheduling experiments, one variable at a time (H4-OMNI-01) | L | M | Held-out wins only | Raw benchmark + ablation | R6 |

### P5 Native C++ and Vulkan (owner: native)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P5-01 | Check `VkResult` on submit/wait/fence with bounded timeout, map device loss to typed error (D6) | S | L | No hang on injected failure | Fault-injection hook; lavapipe lane | R0 |
| P5-02 | C ABI hardening: `cq_abi_version()`, `cq_last_error()`, error returns instead of void, defined RZ quantization policy, `memcpy` fix | S | L | Out-of-range and null tests; UBSan clean | New C ABI tests | R1 |
| P5-03 | Extend sanitizers to all CPU-pure CTests with leak check on; TSan lane; ASan on Vulkan tests under lavapipe | S | L | Lane green or defects recorded | CTest under sanitizers | R2 |
| P5-04 | CPU-vs-Vulkan differential per primitive (bit-exact for fixed-point, tolerance for float); software ICD vs hardware split; require a device on at least one lane | M | L | T6-04 gate with explicit tolerance table | CPU reference | R2 |
| P5-05 | Native-vs-Python parity corpus for shared gates (A, C); endianness and RZ quantization checks | M | L | Corpus passes both engines | Shared JSON corpus; Aer/Qulacs as dev-only oracles (Qulacs MIT per excerpt) | R2 |
| P5-06 | Verify `cq_hecs_core` loader-free under CPU-only, remove duplicate legacy engine, unify Vulkan API version | M | M | CPU-only lane builds each target; one engine | Binary-string check plus CTest | R3 |
| P5-07 | Capability report extension (version, AVX2, sanitizer, devices, software-ICD) and `install(EXPORT)` for CPU target | S | L | Report parity in CLI/MCP | ABI tests | R3 |
| P5-08 | GPU timing split (upload, alloc, dispatch, sync, verify) via timestamp queries; persistent buffers and sync2 only after the data | M | L | No GPU speedup claim without transfer-inclusive evidence (H4-GPU-01) | Raw JSON with hardware metadata | R6 |
| P5-09 | Native QASM/DIMACS fuzz harness under ASan | M | L | Nightly lane | libFuzzer/AFL++ | R6 |
| P5-10 | Prototype: Slang single-source shader for SPIR-V and WGSL; wgpu-native for running web kernels natively; Kompute comparison (research only) | L | H | Bit-checked vs CPU; labelled research | CPU reference | R6 |

### P6 Web / WASM / WebGPU (owner: web)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P6-01 | Single shared noise predicate for `modeOf()`, `simulate.ts`, `main.ts` (D5) | S | L | Each noise field flips mode | Unit test per field | R0 |
| P6-02 | WebGPU `device.lost` and `uncapturederror` handling, buffer cleanup in `finally`, visible fallback reason | S | L | Device-loss test falls back to WASM with reason | Simulated loss; T6-06 | R1 |
| P6-03 | Run-card error scope: f32 drift, binomial CI, trajectory caveat; schema bump with docs | M | L | No hard-coded nulls where data exists | Provenance schema tests | R1 |
| P6-04 | Conformance corpus through WASM and WebGPU (headless Chromium with software adapter or self-hosted GPU runner); report TV drift vs f64 and Python; NOT RUN if no adapter | M | M | T6-05 gate; lane never reports PASS when skipped | `quantum_conformance.json`; Qiskit statevector | R2 |
| P6-05 | Cooperative cancel (stop flag, wire `shouldStop`), worker-restart and failure tests, terminate as fallback | M | M | Cancel frees state; no partial result as complete | e2e + unit | R2 |
| P6-06 | WASM base-URL fix and SHA-256 integrity check; pin Rust toolchain and cargo lock so the rebuild-compare gate stays stable | S | L | Sub-path deploy works | Build check | R2 |
| P6-07 | GPU: sampled cross-check beyond n<=20, bind-group reuse, gate fusion | M | M | Transfer-inclusive timing before any speed claim | Benchmark JSON | R6 |
| P6-08 | Shared ExecutionPlan/refusal schema in the browser planner (replaces private `plan()`) | L | M | Plan JSON parity | Cross-surface fixture | R4 |
| P6-09 | Optional qasm-ts cross-check of the local parser (licence unchecked) | M | M | Parser parity on declared subset | qasm-ts, Qiskit | R6 |

### P7 Studio / UI / design (owner: UI)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P7-01 | Strengthen a11y gate: fail on moderate impact, add wcag22aa to Forge, scan error/running/cancelled/mobile states, add keyboard-only Bell-circuit e2e | S | L | Gate catches known contrast issues first | axe + Playwright | R1 |
| P7-02 | Keyboard- and touch-operable composer (roving tabindex, Enter/Delete, visible non-contextmenu delete) | M | M | WCAG 2.1.1 and 2.5.7/2.5.8 checklist passes | Keyboard e2e plus manual review | R4 |
| P7-03 | `prefers-color-scheme` default with toggle override; CI script computing token contrast in both themes | S | L | All token pairs meet target | Contrast script | R4 |
| P7-04 | i18n key-parity unit test (EN/DE/FR); decide canonical UI (web vs `cqhecs/studio/static`) and share one dictionary and one `esc()` helper | M | M | No missing key; no duplicate escape helpers | Parity test | R4 |
| P7-05 | Typed result-state component (EXACT/CERTIFIED/UNRESOLVED/UNKNOWN/REFUSED, error scope, engine, precision) shared by web, Studio and exported card | M | M | Display matches run-card JSON | Snapshot fixtures | R4 |
| P7-06 | QG Lab screens (catalog, BMV theta scan, SYK/gauge once P3-03 lands, run cards labelled by ExecutionSurface, evidence viewer, hypothesis status chips) with e2e + axe | L | M | Synthetic vs measured vs real-QPU never blurred; INCONCLUSIVE shown | e2e, axe, schema fixtures | R4 |
| P7-07 | Dataviz: ideal-vs-measured residuals, CI bars, noise-sweep comparison, SVG/PNG export, always with a data table; stay under bundle budget | M | L | Bundle budget gate green | Visual fixtures | R4 |
| P7-08 | Design tokens (W3C DTCG JSON) as single source feeding `styles.css` and `forge.css`; component gallery (Storybook or lightweight) with axe per story and screenshot regression | L | M | One token file; dev-only deps | Screenshot tests | R6 |
| P7-09 | Composer parity: undo/redo, parameter inputs, circuit diagram export; text-first QASM sync | L | M | Bound to the shared conformance corpus | Corpus tests | R6 |
| P7-10 | Notebook run-card widget (anywidget/marimo) as thin renderer of the JSON schema | M | L | Optional third surface, deferred if schemas unstable | Schema parity | R6 |

### P8 API / MCP / integration (owner: API)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P8-01 | Server-side clamps for `timeout`, `workers`, `waves`, `limit` equal to Studio's (D7); tool execution in a worker thread; `notifications/cancelled` returns UNKNOWN, never UNSAT | M | M | Ping works during a long call; clamps tested | Subprocess MCP tests | R0 (clamps) / R1 (threads) |
| P8-02 | Tool failures as `isError: true` with typed refusal payload; -32602 for bad arguments | S | L | Typed refusal visible to model | Extended `tests/test_mcp_server.py` | R1 |
| P8-03 | Shared service layer for run/plan/sat/qg used by CLI, MCP and Studio; unify `name:` and `preset:` inputs; add `cq-hecs plan`; cross-surface parity corpus | M | M | T6-01 "one schema" parity on one corpus | Parity test | R1 |
| P8-04 | Publish JSON Schemas (CLI JSON, MCP results, Studio, ExecutionPlan) under `docs/schemas/` and an OpenAPI 3.1 doc for Studio routes; contract test validates live responses; version all HTTP routes under `/api/v1` | M | L | Frozen before RC | Schema validation tests | R1 |
| P8-05 | MCP annotations, `outputSchema` and `structuredContent` (text mirror kept), tool `title`; protocol version negotiation with fallback to 2024-11-05 | M | M | Verify exact spec text first; both modes tested | Conformance tests; MCP Inspector | R1 |
| P8-06 | MCP resources and prompts: gate manifest, plan schema, device profiles, evidence ledger, run-card digests | M | L | Read-only | Resource tests | R3 |
| P8-07 | `llms.txt` and `llms-full.txt` refresh with CI check that tool names and version match `tools/list` and `pyproject` | S | L | Stale text removed | CI check | R0 |
| P8-08 | Studio programmatic auth (`--token` / env, token file mode 0600) | S | L | No leakage in logs | Security tests | R3 |
| P8-09 | Long runs as run-handle tools (submit/status/cancel/result) or tasks extension; elicitation-gated hardware tool in a separate, disabled-by-default server | L | H | Design only until P2-08; fail closed without elicitation | Fake-provider tests | R5 |
| P8-10 | Optional remote MCP (Streamable HTTP + OAuth) and A2A card | L | H | Only after threat model; deferred past 6.0.0 unless explicitly requested | n/a | Deferred |

### P9 Packaging, CI, release (owner: release)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P9-01 | Pin build tools via constraints in `release.yml`; fix SECURITY.md supported versions; extend `check_version.py` to SECURITY.md, classifiers and packaged docs list (D8) | S | L | Version check covers the new surfaces | `scripts/check_version.py` | R0 |
| P9-02 | Split release into unprivileged build job and privileged publish job; add GitHub Environment with required reviewer (human approval gate per AGENTS.md) | S-M | L | Build job has `contents: read` only | Workflow lint | R5 |
| P9-03 | Artifact attestations (SLSA build provenance) for wheel, sdist, checksums, SBOM; claim "Build L2" only | S | L | `gh attestation verify` passes | Verification step | R5 |
| P9-04 | Real SBOM from resolved clean-venv install (CycloneDX plus SPDX), include Rust crates and npm lock, optional PEP 770 embedding | M | L | Versions resolved, not floors | SBOM validation | R5 |
| P9-05 | Native release jobs (Windows CPU-only and Vulkan, Linux CPU) with clean-extract smoke test and checksums; fix `package_release.ps1` (no `dist` wipe, correct docs, unified checksum name) | M | M | Published assets equal the list in release notes | Asset-list gate | R5 |
| P9-06 | Reproducibility gate: build twice with `SOURCE_DATE_EPOCH`, compare hashes; report "not reproducible" honestly if so | M | L | Evidence file in `research/v7` | Hash diff | R5 |
| P9-07 | Supply-chain hygiene: Dependabot, OpenSSF Scorecard, zizmor, pip-audit/npm audit/cargo-audit, dependency-review | S | L | Findings triaged | Workflow runs | R5 |
| P9-08 | Web bundle release asset with embedded `version.json`; post-deploy SHA check; gate Vercel production on release gates (Vercel settings are a user-owned external action) | M | M | Deployed SHA equals tag SHA | Post-deploy job | R7 |
| P9-09 | PyPI trusted publishing with PEP 740 attestations after TestPyPI; MCP Registry `server.json` only after a public install channel exists | S-M | M | Needs explicit user authorization (irreversible, name availability unchecked) | TestPyPI dry run | After RC, user-gated |
| P9-10 | Optional native wheels via cibuildwheel + scikit-build-core (CPU-only first; Vulkan separate) | L | H | Pure-Python install path unchanged | Wheel smoke tests | Post-6.0 |

### P10 Verification and research discipline (owner: auditor)

| ID | Item | Effort | Risk | Acceptance gate | Oracle / test | Wave |
|---|---|---|---|---|---|---|
| P10-01 | Reconcile ledgers (D11): fix "35-mutant" docstring, merge BASELINE/BASELINE_W0 counts, write a v5-to-v6 baseline entry | S | L | One baseline number set | Doc check | R0 |
| P10-02 | Skip-budget gate (JUnit parse, fail on growth or on named test skipped); report NOT RUN lists | S | L | Budget file committed | CI step | R1 |
| P10-03 | Mutation coverage for `quantum_gravity`, `router.py`, `execution_plan.py`, `scheduler.py`, `provider.py`, plus new code per wave; fixed target list, kill threshold and equivalent-mutant policy | M | L | Survivors reported by severity | `run_mutation_tests.py` | R1 and each wave |
| P10-04 | Hypothesis stateful and differential properties (SAT scan vs watched vs OMNIWAVE vs separator vs brute force; Path A vs Stim; QG channels); seed/database policy; nightly larger profile | M | L | Derandomized in CI | Hypothesis | R2 |
| P10-05 | External-checker nightly lanes (drat-trim, lrat-check, cake_lpr, python-sat) that fail when they silently skip | M | M | NOT RUN is explicit | Linux CI | R2 |
| P10-06 | Preregistration manifest: hash of benchmark script, seeds and HYPOTHESES entry committed before runs; CI checks evidence JSON references it | M | L | Each H4-* claim traceable | Manifest checker | R2 |
| P10-07 | Benchmark metadata and statistics via pyperf (and asv-style versioning) for `scripts/*benchmark*.py` | M | L | Environment block in every raw result | pyperf | R2 |
| P10-08 | Coverage floors per critical package (sat, drat, omniwave) and trend artifact; optional second mutation tool (mutmut is Unix-only per search summary, so Linux CI; cosmic-ray alternative) as advisory cross-check | S-M | L | Trend JSON per commit | Coverage + mutation tools | R2 |
| P10-09 | Formalize 1-2 CQ-HECS lemmas in Lean (Path D triangle bound, separator recurrence) with pinned Linux lane and Comparator; label `FORMALIZED_LEMMA` only for the named lemma | L | M | Statement-to-code mapping reviewed | Lean, Comparator, nanoda | R6 |
| P10-10 | T6-13 audit checklist: gates, ledger diffs, exact-SHA checks, asset hashes | S | L | Checklist file used by independent auditor | Audit | R7 |

---

## 4. SOTA adoption table

Verdict legend: ORACLE = optional test/benchmark dependency only; PATTERN = copy design idea only; DEFER = not now; AVOID = do not bundle. "Licence" is what the findings stated; "unverified" means nobody opened the licence file.

### 4a. Programs and libraries

| Program | URL | Takeaway | Verdict | Licence status |
|---|---|---|---|---|
| Stim | https://github.com/quantumlib/stim | Clifford/QEC reference; compiled-sampler idea | ORACLE for Path A (P1-01, P1-03) | Unverified |
| Qiskit Aer | https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html | Method menu maps to paths A-D; MPS default untruncated; `extended_stabilizer` approximate | ORACLE (paths, noise, native parity) | Apache-2.0 (stated) |
| Aer NoiseModel | https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.NoiseModel.html | Basis-gate handling from backend properties | ORACLE and design reference (P2-05) | Apache-2.0 (Aer) |
| MQT DDSIM | https://mqt.readthedocs.io/projects/ddsim/en/stable/simulators/CircuitSimulator.html | Decision-diagram baseline for E1 | ORACLE/comparator in prototype only | Unverified |
| quimb + cotengra | https://cotengra.readthedocs.io/en/stable/ | Contraction trees, slicing; ordering comparator | ORACLE/comparator (P1-05, P1-10) | Unverified |
| NVIDIA cuQuantum | https://docs.nvidia.com/cuda/cuquantum/latest/custatevec/overview/index.html | Workspace-size queries, explicit bit order, dtype vs compute type | PATTERN for C ABI; benchmark reference only | Proprietary SDK licence, NVIDIA-only; AVOID bundling |
| PennyLane Lightning | https://pennylane.ai/devices/lightning-tensor | One capability card per device | PATTERN (capability cards) | Not checked |
| PauliPropagation.jl / paper | https://arxiv.org/html/2505.21606v1 | Unnormalised Pauli basis; state the coefficient basis | PATTERN and comparator (P1-07) | Unverified |
| TensorCircuit(-NG) | https://github.com/tencent-quantum-lab/tensorcircuit | Contraction path finder, slicing | PATTERN; DEFER ML bridge | Apache-2.0 (stated) |
| QuEST | https://github.com/QuEST-Kit/QuEST | One API many backends; tests compile where they cannot run | PATTERN (NOT RUN reporting, P5-07) | MIT (stated) |
| Qulacs | https://github.com/qulacs/qulacs | CPU statevector oracle | ORACLE (dev only) | MIT per excerpt |
| Kompute / Slang / wgpu-native | https://github.com/KomputeProject/kompute , https://shader-slang.org/ , https://github.com/gfx-rs/wgpu-native | Vulkan abstraction; single-source SPIR-V+WGSL; native WebGPU | Research prototypes only (P5-10) | Kompute Apache-2.0; others unverified |
| Khronos Vulkan sync guidance | https://www.khronos.org/blog/understanding-vulkan-synchronization | Timeline semaphores, Synchronization2 | PATTERN after P5-08 data | n/a |
| CaDiCaL / Kissat (SAT Comp 2025) | https://satcompetition.github.io/2025/satcomp25slides.pdf | Performance baseline; winner unreconciled | ORACLE/baseline (pinned versions) | Unverified |
| Ganak / d4 / SharpSAT-TD / gpmc | https://mccompetition.org/assets/files/2025/MC2025_awards.pdf | MC2025 exact counters | ORACLE for #SAT | Unverified |
| count-catcher | https://arxiv.org/abs/2610.36196 | Certified #SAT counts into Lean; unverified checker returned wrong counts | PATTERN (long-term trust level) | n/a |
| cake_lpr | https://github.com/tanyongkiam/cake_lpr | Verified LRAT checker | ORACLE lane (P4-05) | Unverified |
| SBVA | https://github.com/hgarrereyn/SBVA | SAT-only re-encoding | PATTERN; refuse for #SAT | Unverified |
| Cube-and-Conquer / Proof-Stitch | https://github.com/marijnheule/CnC | OMNIWAVE fronts as cubes | PATTERN (P4-10) | Unverified |
| BIRD / CryptoMiniSat | https://www.cs.toronto.edu/~meel/Papers/aaai19-sm.pdf | CNF-XOR with Gauss-Jordan | PATTERN (P4-08) | Unverified |
| Mitiq | https://github.com/unitaryfoundation/mitiq | ZNE/PEC reference | AVOID bundling (GPL-3.0 per search result); clean-room ZNE (P2-09) | GPL-3.0 |
| IBM NoiseLearner | https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/dev/noise-learner-noise-learner | Sparse Pauli-Lindblad; `dry_run` pattern | PATTERN (`dry_run` in runner); learned noise as preregistered hypothesis | n/a |
| Qiskit Fermions | https://www.ibm.com/quantum/blog/qiskit-fermions | Independent fermion mapper | ORACLE (P3-10) | Unverified, 0.1.0 reported |
| SYK / BMV literature | https://arxiv.org/abs/1806.02793 , https://link.aps.org/doi/10.1103/PhysRevD.109.105002 , https://www.nature.com/articles/s41534-026-01206-1 , https://link.aps.org/doi/10.1103/pg7l-f26t , https://www.alphaxiv.org/abs/2208.09489 | Cost baselines and claim-scope caveats | Literature pins (P3-09) | Preprints marked SOURCE_CLAIM |
| Wormhole experiment and critique | https://inqnet.caltech.edu/wormhole2022/ , https://arxiv.org/html/2301.03522 | Contested workload | Pin both together | n/a |
| webgpu-q | https://github.com/abgnydn/webgpu-q | f32 vs Float64 reference with fidelity bar | PATTERN only; its numbers unverified | Unchecked |
| WebGPU CTS | https://www.github.com/gpuweb/cts | Normative suite | Pinned smoke subset (P6-04) | n/a |
| qasm-ts | https://cdn.jsdelivr.net/npm/qasm-ts@2.1.4/docs/docs-readme.md | OpenQASM 2/3 parser | ORACLE parser cross-check (P6-09) | Unchecked |
| Pyodide | https://pyodide.org/en/0.24.0/usage/index.html | CPython in WASM worker | DEFER (Qiskit compatibility unconfirmed) | n/a |
| Hypothesis / HypoFuzz / Atheris | https://hypothesis.readthedocs.io/en/latest/how-to/external-fuzzers.html , https://github.com/Zac-HD/hypofuzz , https://github.com/SDLLABS/atheris | Stateful properties, coverage-guided fuzz | Adopt in Linux nightly (P10-04) | Unverified |
| mutmut / Cosmic Ray / Stryker schema | https://mutmut.readthedocs.io , https://pypi.org/project/cosmic-ray , https://stryker-mutator.io/docs/General/dashboard/ | Independent mutation cross-check; report schema | Advisory cross-check; emit schema locally, do not upload to hosted dashboard | Unverified |
| Lean Comparator / Validating Proofs | https://raw.githubusercontent.com/leanprover/comparator/master/README.md , https://lean-lang.org/doc/reference/4.29.0/ValidatingProofs/ | Statement match and axiom check; needs landrun (Linux) | Pinned Linux lane (P10-09) | n/a |
| pyperf / asv | https://github.com/psf/pyperf , https://asv.readthedocs.io/en/stable/tuning.html | Benchmark metadata and significance | Adopt (P10-07) | Unverified |
| OSF preregistration | https://www.cos.io/blog/choosing-preregistration-template-guide-for-researchers | External timestamp | Optional for final held-out claims | n/a |
| cibuildwheel / scikit-build-core | https://cibuildwheel.pypa.io/en/stable/options/ , https://scikit-build-core.readthedocs.io/en/latest/configuration/overrides.html | Native wheels | Post-6.0 (P9-10) | Unverified |
| CycloneDX / PEP 770 | https://github.com/CycloneDX/cyclonedx-python , https://peps.python.org/pep-0770/ | Real SBOM, embed in wheel | Adopt (P9-04) | Unverified |
| GitHub attestations / SLSA | https://docs.github.com/en/actions/concepts/security/artifact-attestations , https://slsa.dev/spec/v1.2/build-provenance | Provenance without key management | Adopt (P9-03) | n/a |
| PyPI attestations (PEP 740) | https://docs.pypi.org/attestations/ | Trusted publishing | User-gated (P9-09) | n/a |
| zizmor / Scorecard / reproducible-builds | https://github.com/zizmorcore/zizmor , https://openssf.org/projects/scorecard/ , https://reproducible-builds.org/specs/source-date-epoch/ | Workflow lint, posture signal, deterministic timestamps | Adopt (P9-06, P9-07) | Unverified |

### 4b. MCP and API references

| Reference | URL | Takeaway | Verdict |
|---|---|---|---|
| MCP spec 2026-07-28 (changelog, tools, authorization) | https://modelcontextprotocol.io/specification/2026-07-28/changelog , https://modelcontextprotocol.io/specification/2026-07-28/server/tools , https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization | `outputSchema`/`structuredContent`, `isError` vs protocol errors, resource links, handles, elicitation, tasks, cache hints | Adopt in dual mode with legacy fallback; verify spec status first (P8-02, P8-05) |
| Qiskit MCP servers (+ IBM docs page) | https://github.com/Qiskit/mcp-servers , https://quantum.cloud.ibm.com/docs/guides/qiskit-mcp-servers | Split servers by trust level; token via environment; `server.json`; MCP Inspector | PATTERN (read-only vs hardware split). Apache-2.0 (stated) |
| mcp-solver | https://github.com/szeider/mcp-solver | Server re-checks results, `self_check` states, addressable results | PATTERN for SAT tools. MIT per README |
| coda-mcp, YuChenSSR quantum-simulator MCP, barvhaim qiskit-mcp-server | https://pypi.org/project/coda-mcp/ , https://mcpservers.org/en/servers/YuChenSSR/quantum-simulator-mcp , https://github.com/barvhaim/qiskit-mcp-server | Existing quantum MCPs; none seen with typed refusals or certificates | Interop reference; licences unchecked |
| Qiskit Runtime REST, qBraid API v2 | https://quantum.cloud.ibm.com/docs/api/qiskit-runtime-rest , https://docs.qbraid.com/v2/api-reference | Job lifecycle, credits/usage endpoints | PATTERN for provider adapter (P2-08) |
| Quantum provenance paper (preprint) | https://arxiv.org/html/2608.08272v1 | Evidence-origin provenance contract | PATTERN for calibration schema v3; not a standard |
| OpenAPI latest, llms.txt | https://spec.openapis.org/oas/latest.html , https://llmstxt.org | Schema sharing; agent docs | Adopt (P8-04, P8-07) |
| OpenQASM spec, Braket subset docs | https://openqasm.com/ , https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm.html | Publish an explicit supported-subset table | Adopt policy; Braket page seen as snippet only |
| MCP Registry | https://modelcontextprotocol.io/registry/about | Needs a public install channel | After PyPI decision |
| Playwright MCP, Chrome DevTools MCP | https://playwright.dev/mcp/introduction , https://developer.chrome.com/blog/chrome-devtools-mcp | Agent-driven UI regression and profiling | Dev-only on loopback; pin versions (a supply-chain incident on a third-party devtools MCP package appeared in search) |
| Storybook MCP addon, shadcn/ui MCP, Figma MCP | https://storybook.js.org/docs/ai/mcp/overview , https://ui.shadcn.com/docs/mcp , https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server | Component docs for agents; token reading | Storybook addon only if P7-08 proceeds; Figma needs OAuth, read-to-DTCG only, human reviewed |
| lean-lsp-mcp | https://github.com/project-numina/lean-lsp-mcp | Lean goals and diagnostics for the Lean subagent | On-demand subagent only (per CLAUDE.md); pin version |
| A2A | https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year | Agent card discovery | DEFER; details unverified |

### 4c. Graphical design systems and UI references

| Reference | URL | Takeaway | Verdict |
|---|---|---|---|
| IBM Quantum Composer | https://quantum.cloud.ibm.com/docs/guides/composer | Linked editor + QASM + result panels; four-qubit limit without login (per a 2025 paper; closed source) | PATTERN only; add provenance and refusal states it lacks |
| Quirk | https://algassert.com/2016/05/22/quirk.html , https://github.com/strilanc/quirk | Live inline state displays, URL-encoded circuits | PATTERN; Apache-2.0 per author post; lightly maintained |
| Quantum Inspire editor | https://www.quantum-inspire.com/kbase/working-with-the-editor/ | Text editor with live chart | PATTERN |
| W3C Design Tokens | https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/ | Interchange format | Adopt as token source (P7-08); verify final field names |
| WCAG 2.2 | https://www.w3.org/TR/WCAG22/ | Target size 24x24, focus not obscured | Adopt criteria (P7-01) |
| Playwright accessibility docs | https://playwright.dev/docs/accessibility-testing | Automated scans find only some issues | Keep manual checks in gate |
| Carbon (data viz and accessibility) | https://www.carbondesignsystem.com/building-blocks/data-visualization/overview | Chart plus table plus text patterns | PATTERN; licence unverified |
| Observable Plot | https://observablehq.github.io/plot/features/plots | Declarative marks | DEFER; bundle budget and licence unverified |
| Linear redesign (LCH themes), Vercel Geist | https://linear.app/now/how-we-redesigned-the-linear-ui , https://vercel.com/geist/colors | Systematic elevation and categorical colours | Method only; no assets |
| Radix Primitives | https://github.com/radix-ui/primitives | Accessible headless components | MIT, but implies React; only for new panels if ever |
| SAT UI research: SATViz, SAT-Web | https://arxiv.org/html/2209.05838v2 , https://ceur-ws.org/Vol-4008/POS_paper08.pdf | Proof timeline, incidence graph, front tree | PATTERN for SAT lab (descriptions only; no live UI seen) |
| Error Correction Zoo (holographic codes) | https://errorcorrectionzoo.org/c/holographic_tensor | Prior art for an optional holography toy view | DEFER; label as toy |
| marimo anywidget | https://docs.marimo.io/api/inputs/anywidget/ | Notebook run-card widget | Optional (P7-10) |

---

## 5. Next big goal and implementation waves

### Next big goal: verifiable v6.0.0 release candidate (RC)

A tagged `v6.0.0-rc.1` built from one exact SHA, accepted only when all of the following are demonstrably true:

1. **No known honesty defect from section 1 (D1-D11) remains open**, each fixed with a regression test that failed before the fix.
2. **One contract across surfaces:** typed refusals, `certified`/`proof_level` fields, run-card error scope, ExecutionPlan schema, and QG envelope are identical in Python, CLI, MCP, Studio and web, validated by published schemas and a cross-surface parity corpus.
3. **Independent oracles run in CI or nightly** with NOT RUN reported explicitly: Stim/Aer (quantum), brute force + cross-solver (SAT), CPU-vs-Vulkan and native-vs-Python (native), Python-vs-WASM (and WebGPU where an adapter exists), external proof checkers.
4. **At least two promoted capabilities that pass their gates** (AGENTS.md section 12.1 rule): candidates are Path C ordering (P1-05), generalized Pauli observables (P1-07), basis-aware noise (P2-05), separator DP in unified (P4-06), sound CNF-to-XOR (P4-08). Any that fail stay research and are recorded as failed experiments.
5. **QG surfaces:** SYK/gauge runnable locally from all surfaces, QG Lab in web and Studio with axe + e2e, qg_2026 board reconciled, no live-QPU claim beyond recorded evidence.
6. **Release pipeline:** build/publish split, provenance attestation, resolved-version SBOM, native artifacts matching the claimed asset list, SHA check between tag, assets and deployed bundle.
7. **Local and remote gates green on the exact RC SHA**, an independent audit (T6-13 checklist, P10-10) signed off, `MIGRATION_V6.md` and release notes separating implemented / experimental / measured / formally checked / not supported.
8. **Version justification:** 6.0.0 is warranted only if caller-visible contracts break (MCP error semantics, `UnifiedResult` fields, run-card schema, counts behaviour from P1-01). If the audit finds the changes additive, the honest choice is 5.1.0. Decide at the end of R1.

Explicitly out of scope for the RC: PyPI publication, remote MCP, native wheels, live QPU runs (all need explicit user authorization or a new key), any asymptotic or "faster than CaDiCaL" claim.

### Wave sequence

Every wave runs the same bounded self-healing loop: reproduce, write failing test, fix root cause, focused test, subsystem suite, differential/property run, full gates at wave end, commit checkpoint. Maximum three meaningful repair cycles per root cause, then record BLOCKED with the reproducer and continue independent work. Reflection output (what failed, error delta) is appended to `research/v7/EXECUTION_LOG.md` (or a v8 directory if the team opens one). No wave merges to `main`; use a feature branch and PR with exact-SHA CI.

| Wave | Theme | Items | Exit gate |
|---|---|---|---|
| **R0** | Honesty fixes and board reconciliation (no new features) | P1-01, P1-02, P2-01, P2-02, P2-03, P3-01, P4-01, P4-02, P4-03, P5-01, P6-01, P8-01 (clamps), P8-07, P9-01, P10-01 | Every D1-D11 reproduced then fixed; baseline numbers reconciled; full local gates equal or better than W0 baseline with explicit skip list |
| **R1** | Contracts and schemas | P3-03, P3-04, P4-06, P5-02, P6-02, P6-03, P7-01, P8-01 (threads), P8-02, P8-03, P8-04, P8-05, P10-02, P10-03 | Schemas published and frozen; parity corpus green across CLI/MCP/Studio; MCP dual-mode tested; skip budget active; version-bump decision (6.0.0 vs 5.1.0) recorded |
| **R2** | Oracles and parity lanes | P1-03, P2-04, P2-11, P3-02, P3-09, P3-10, P4-05, P4-07, P5-03, P5-04, P5-05, P6-04, P6-05, P6-06, P10-04..P10-08 | Each lane reports PASS/FAIL/NOT RUN truthfully; preregistration manifest in place before any benchmark that decides a claim |
| **R3** | Capability promotions (each behind its own hypothesis gate) | P1-04 (relabel), P1-05, P1-06, P1-07, P2-05, P2-06, P2-07, P3-05, P3-06, P4-04, P4-08, P5-06, P5-07, P8-06, P8-08 | At least two promotions pass held-out gates; failures recorded as NOT_SUPPORTED/INCONCLUSIVE |
| **R4** | UX, Studio, web and QG Lab | P6-08, P7-02..P7-07 | axe and keyboard e2e green on all routes and states; i18n parity test; run cards match actual result data |
| **R5** | Release pipeline and provider boundary design | P9-02..P9-07, P2-08 and P8-09 (design plus fake-provider contract tests only), P3-08 (only if the user supplies a key and authorizes spend) | Pipeline dry-run produces attested artifacts and a reproducibility report; no live provider call in CI |
| **R6** | Research prototypes, opt-in only, time-boxed | P1-08..P1-10, P2-09, P2-10, P3-07, P4-09..P4-11, P5-08..P5-10, P6-07, P6-09, P7-08..P7-10, P10-09 | Each prototype has a hypothesis ID, held-out result and honest status; nothing becomes default without a gate; skipped prototypes are listed as DEFERRED, not shipped |
| **R7** | Release candidate hardening | P9-08, P10-10, final mutation/fuzz/resource sweeps, docs and `MIGRATION_V6.md`, version consistency, exact-SHA CI and preview checks, independent audit | `v6.0.0-rc.1` criteria 1-8 above all met or explicitly waived by the user in writing; publication itself needs user authorization |

Sequencing rationale: R0 and R1 remove false claims and freeze contracts before building on them. R2 gives independent oracles before R3 promotes any capability, so promotions are judged by evidence rather than by the system's own tests. R4 depends on the stable schemas from R1 and the SYK/gauge surface work. R5 waits for the contracts and fixes in R0-R1. R6 is deliberately last and optional so that the RC does not depend on research outcomes. Parallelism is possible inside a wave across parts, with one integration owner per AGENTS.md section 2.5.

### Open questions to take into the next wave

1. Is `cq_hecs_core` genuinely loader-free in CPU-only mode (run the lane, do not infer from CMake)?
2. Which MCP revision do target clients actually support; is 2026-07-28 final or draft, and what are the exact hint-field names?
3. Which comparator licences permit CI use or redistribution (Stim, DDSIM, quimb/cotengra, Ganak/d4/SharpSAT-TD, cake_lpr, PauliPropagation.jl)? Record in a licence register (none exists today).
4. Does an environment exist for a WebGPU conformance lane (software adapter versus self-hosted GPU runner)?
5. Which UI is canonical (web or Studio static), given Vercel deployment and Python packaging constraints?
6. Does the user want PyPI publication and a new Open Quantum key? Both are user-gated and not assumed.
7. Is the 6.0.0 major bump justified once the contract changes are listed (decide at R1 exit)?
8. How should WCAG 2.5.7 (dragging movements) be handled; it was not read in this research pass.
9. Does the Pyodide/Qiskit reference lane have any value, or should it stay off the plan?
