# QGRAVITY Campaign Plan — CQ-HECS Quantum Gravity Research Studio

Campaign id: `qg-2026-01`
Branch: `research/quantum-gravity-studio` (from `main` @ `fa1cc87`, `v5.0.0-1-gfa1cc87`)
Contract: `QGRAVITY.md` (repo root, untracked mission file)
Owner: autonomous agent; integrator = this branch.

This is the working plan derived from `QGRAVITY.md`. It states order, dependencies,
acceptance and the honest status of each item. A item is only `DONE` when its gate
below is met with reproducible evidence; a checkbox, plan or passing build is never
proof of a scientific or engineering objective.

## 0. Reconnaissance summary (what the repo is today)

- Local `main` == `origin/main` == `fa1cc87`; version surfaces all report `5.0.0`.
- No Quantum Gravity work exists yet: `research/qg_2026/`, `cqhecs/quantum_gravity/`,
  `scripts/run_qg_openquantum_campaign.py`, `docs/QUANTUM_GRAVITY_LAB.md` were all absent
  before this branch.
- All other remote branches are behind `main` (merged) except three with small unmerged
  deltas, none of which touch Quantum Gravity.
- Existing reusable contracts confirmed by reading source:
  - `cqhecs/result.py` → `SimulationResult`, `SimulationState` (EXACT/CERTIFIED/UNRESOLVED/FAILED),
    `ExecutionMode` (IDEAL_CLASSICAL/NOISY_CLASSICAL/REAL_HARDWARE), Hoeffding bounds.
  - `cqhecs/provenance.py` → `hcs.run.v2` run-card (`build`, `RunCard.write`, `validate`).
  - `cqhecs/openquantum_suite.py` + `scripts/run_openquantum_suite.py` → historical `r-io-7`
    patterns (read-only reference; must not be repurposed or re-submitted).
- `openquantum-sdk 1.0.0` is installed (Python 3.14.6).

## 1. Open Quantum credential status (blocker B-1)

Official docs: an SDK key is **two** values — Client ID (format `s_<uuid>`) and Client
Secret (`ref: docs.openquantum.com/core-sdk/authentication`). The value provided for this
campaign (`s_…`) matches the Client ID format; the Client **Secret** was not provided.
A read-only probe with it as a bearer token returned `401 UNAUTHORIZED`. No
`OPENQUANTUM_*` variables are set in the user environment and `accounts.json` is empty.

→ Until the Client Secret is supplied (env only), all paid/simulator work is `BLOCKED`.
All local work (Waves 0–2, integration, docs) proceeds independently.

## 2. Milestones (map to QGRAVITY waves/LOPs)

| M | Name | LOPs | Depends on | Gate |
|---|---|---|---|---|
| M0 | Baseline & safety | LOP-00 | — | starting SHA recorded; branch ≠ main; no user file lost; secrets gitignored |
| M1 | Literature & theory map | LOP-01 | M0 | dated sources + assumptions + competing models in `LITERATURE_MAP.md` |
| M2 | Hypotheses & preregistration | LOP-02 | M1 | frozen hypothesis registry + manifests + hashes committed before any paid job |
| M3 | Local BMV effective-phase model | LOP-03/04 | M2 | exact dense oracle + local CQ-HECS + null controls; bound/observable tests pass |
| M4 | Local SYK reference | LOP-03/04 | M2 | Majorana algebra + spectrum oracle + seeded sparse Hamiltonian + evolution error split |
| M5 | Result/contract integration | LOP-09 | M3,M4 | `cqhecs.quantum_gravity` module + `cqhecs.qg.experiment.v1` envelope; existing schemas unchanged |
| M6 | Open Quantum adapter + runner | LOP-05/06 | M5 + B-1 | `doctor/discover/generate/validate/quote/submit/collect/analyse/report` separable; quote spends nothing |
| M7 | QPU campaign | LOP-06/07 | M6 + live QPU | ≤25 Spark; Public/Standard only; ledger reconciles; raw evidence immutable |
| M8 | Studio API + MCP | LOP-10 | M5 | versioned routes + MCP tools, spend guard shared, secret-safe, typed errors |
| M9 | Web/Studio QG Lab UI | LOP-11 | M8 | every route reachable, axe/Playwright, provenance-first run cards, honest empty states |
| M10 | CPU/Vulkan native split | LOP-12 | — | `-DCQ_ENABLE_VULKAN=OFF` configures/builds/tests; CPU binary has no Vulkan loader dep |
| M11 | WebGPU f32 path + probes | LOP-12 | M9 | primitive differential vs WASM f64, explicit fallback, no exactness claim |
| M12 | Packaging | LOP-13 | M10,M11 | CPU+Vulkan EXEs, wheels install in clean venv, SBOM + SHA-256 manifest |
| M13 | Hardening & release audit | LOP-14 | all | no unexplained skips; secret scan clean; claims match evidence ledger |
| M14 | Handoff | LOP-15 | M13 | `FINAL_REPORT.md` + exact reproduction commands; clean worktree |

## 3. Execution order chosen (highest information per unit risk)

1. M0 → M1 → M2 (this session, credential-free).
2. M3 + M4 + M5 together: the "smallest scientifically meaningful vertical slice"
   required by `QGRAVITY.md` §17 (BMV effective-phase + null controls, and a small keyed
   SYK reference with Majorana-algebra tests), with independent dense oracles.
3. M6 runner skeleton with `doctor/discover/validate` runnable read-only once B-1 is
   resolved; `quote/submit` implemented but gated.
4. M8/M9 integration and UI.
5. M10–M12 native/packaging.
6. M13/M14 audit and report.

## 4. Non-negotiables carried from QGRAVITY.md

- Physics before correctness before evidence before polish.
- Separate `CLASSICAL_REFERENCE / CQ_HECS_CPU / CQ_HECS_VULKAN / WEB_WASM_F64 /
  WEBGPU_F32 / OPENQUANTUM_SIMULATOR / OPENQUANTUM_QPU / MODEL_PREDICTION /
  SYNTHETIC_OR_FIXTURE` everywhere.
- No `error_bound=0` default; uncertainty classes stay separate and nullable.
- Historical `research/v3` `r-io-7` evidence is immutable.
- ≤25 Spark credits, Public/Standard only, never Full credits, never auto-approve a quote.
- No secret in any tracked file, log, EXE, wheel or browser bundle.

## 5. Status legend

`DONE` · `IN_PROGRESS` · `BLOCKED` · `NOT_RUN` · `DEFERRED` · `REJECTED`.
See `STATUS.md` for the live roll-up.
