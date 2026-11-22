# CQ-HECS Release Notes (DRAFT for 7.0.0)

**Status:** draft, not a release. The version is `7.0.0` (release candidate, 2026-11-22). Nothing in this file is published,
tagged or deployed. `RELEASE_NOTES.md` stays the notes of the last published release until
this draft replaces it.

Every statement below is tied to a file in `research/v7/evidence/` or to a test, and is
placed under exactly one of five headings. A statement that is not backed is not here. Items
that were not run are listed under **Not run** instead of being implied.

Migration steps for every caller-visible change: [`MIGRATION_V7.md`](MIGRATION_V7.md).

---

## Implemented

Code exists, is tested, and behaves as described. This is not a performance or physical claim.

* **Shared service layer and four-surface plan parity.** `cqhecs/service.py` builds the
  `ExecutionPlan` for Python, `cq-hecs plan`, MCP `cqhecs_plan` and Studio `/api/plan`; one
  test asserts identical documents on six circuits. Evidence: `waveA_A1.md`.
* **OpenAPI 3.1 and `/api/v1`** for the Studio API (generated, drift tested).
* **MCP protocol negotiation** (2025-06-18, 2025-03-26, 2024-11-05; legacy shape
  unchanged), worker-thread execution, typed `CANCELLED`, a concurrency cap of 8, bounded
  numeric inputs.
* **Studio request guard** (per-launch bearer token, Host and Origin lists, JSON-only POST,
  bounded drains).
* **Typed MaxSAT** `hcs.sat.maxsat.v1` and **unified-solver certification fields**
  (`certified`, `proof_level`, `require_certified`).
* **Isolated CaDiCaL solve** with parent-side re-verification of the model and the DRAT proof.
* **Separator width preflight** (`UNKNOWN` before any table is allocated).
* **Path A shot contract**: every requested shot is drawn or a typed refusal is raised.
* **Paths B and C error-story metadata** (dropped-branch mass, Born-norm sum, SVD
  instrumentation, `numerical_error_bound_reason`).
* **Uncovered-gate policy** for noisy hardware-profile runs (`warn`, `refuse`, `ideal`) and
  **calibration schema v3** with a provenance label, freshness and channel checks.
* **Native hardening**: ABI 1.1 on both libraries, argument validation, fault-injectable
  `VkResult` handling, device-loss latch, CPU-only build, sanitizer lane.
* **Web**: WebGPU device-loss fallback to WASM (labelled), keyboard and touch composer,
  mobile projects, one shared noise predicate, run-card `error_scope`.
* **Quantum Gravity Lab** (BMV competing models, SYK Trotter compiler and mirror circuit,
  Z2 gauge leakage, QG plan wrapper, offline replay) with web and Studio screens, and a QG plan
  envelope that is identical on Python, `cq-hecs qg plan`, MCP and Studio
  (`tests/test_qg_surface_parity.py`, 49 tests passed when this draft was written).

## Experimental

Present in the tree, opt-in or unrouted, and not part of the supported contract.

* **OMNIWAVE** (unchanged status): experimental; no CDCL; slower than CaDiCaL in the
  recorded suite.
* **Research Paths E, F and G** (2D tensor-network contraction order, MPS quantum
  trajectories, matrix product evolution): prototypes under `research/v7/prototypes/`, not
  imported by `cqhecs`, not routable. All three ended `RESEARCH_ONLY` against preregistered
  criteria, with negative results recorded (`research/v7/QUANTUM_SIMULATION_RESEARCH.md`).
* **Noise models** remain models: `M-FIT-2` is `EXPLORATORY_POST_HOC`; circuits are not
  transpiled into a profile basis.
* **Quantum Gravity Lab** values are finite-model quantities, never measurements of gravity.

## Measured

Finite, machine-specific numbers. None is an asymptotic or universal claim.

| Measurement | Value | Evidence |
| :--- | :--- | :--- |
| Full Python suite, Windows, re-run at `f880d0a` + wave F working tree | 4314 passed, 133 skipped, 0 failed | `waveE_E2.md` (integrator record) |
| Skip budget | skips are environmental (native build directory not set, optional extras absent), not failures | `SKIP_BUDGET.json` |
| Mutation suite, in place at the freeze | 95/95 killed (an earlier pre-Wave-A baseline was 64/64) | `waveE_E2.md`, `BASELINE_V7.md` |
| Native CTest, Vulkan ON, one AMD Radeon iGPU, MSVC | 26/26 | `waveE_E2.md`, `waveA_A2.md` |
| Native CTest, CPU-only build | 15/15 | `waveE_E2.md`, `waveA_A2.md` |
| CPU versus Vulkan BCP differential | 1,052,908 cells, 0 mismatches (correctness only, no timing claim) | `waveA_A2.md` |
| Web unit tests at the freeze | 167/167 | `waveE_E2.md` |
| Playwright at the freeze | 128 passed, 1 skipped (WebGPU, NOT_RUN: no adapter); Studio plan UI: 6 | `waveE_E2.md` |
| Release artifacts | built from `38e799b`; not published, no tag exists | `waveE_E2.md` |
| Path B versus a plain dense statevector | Path B slower on every measured case | `PATHB_DOMINANCE.json` |
| Separator table bound `2^(w+1)` | 31 rows, 0 violations of observed <= predicted | `waveA_A4_separator_calibration.json` |
| DRAT tamper matrix | 125 of 235 single-lemma deletions rejected (others are redundant) | `waveA_A4.md` |
| Path E (held-out seeds) | greedy order saves 6 to 12 bits of largest tensor versus a time-ordered baseline on 3 families; geometry sweep alone saves 1 bit on one family and loses 2 on another | `QUANTUM_SIMULATION_RESEARCH.md` |
| Path F versus exact density matrix, n <= 6 | trajectories 100 to 1000 times slower; normal interval under-covers | `QUANTUM_SIMULATION_RESEARCH.md` |
| Path G versus standard MPS at equal bond dimension | MPE met the target in 0% of truncation cells | `QUANTUM_SIMULATION_RESEARCH.md` |

The Python suite number is for one commit and one interpreter; later commits added tests and
have not been re-counted in a full run. A green run on an older commit is not evidence for a
later one.

## Formally checked

* Lean 4 specification lemmas in `formal/`, built with a pinned toolchain and Mathlib, with
  only the standard axioms: Path D truncation bound, Pauli multiplication and commutation,
  single-qubit sign rules for the Path A gate set, Path A tableau symplectic invariant
  (bit part). Trust label: `FORMALIZED_LEMMA`. These are statements about the specification,
  not a refinement proof of the Python or C++ code. Evidence: `waveA_A5.md`, `formal/README.md`.
* SAT trust labels in use: `MODEL_VERIFIED`, `TREE_RESOLUTION_CHECKED`, `DRAT_CHECKED`. No
  `FORMALLY_VERIFIED` component exists.

## Not supported

* Arbitrary-circuit simulation in polynomial time; any claim about `P` versus `NP`, ETH or
  SETH.
* A certified numerical error bound for Path B or Path C (`numerical_error_bound` is `None`).
* An optimality certificate for MaxSAT, more than 20 variables for exact MaxSAT, LRAT replay
  with the in-repository checker, a CDCL engine.
* Calibration-aware transpilation, a VALIDATION split for the noise models, CLI or Studio
  display of calibration schema v3.
* Real hardware from the package. `RealHardwareBackend` fails closed; no surface submits a
  QPU job, calls Open Quantum or spends credits.
* Any Open Quantum action from the package: the quote, submit, status and results routes and
  MCP tools exist only to return the typed refusal `QG_PAID_PATH_UNAVAILABLE`. Quote and submit
  stay manual steps in `scripts/run_qg_openquantum_campaign.py` under its 25-Spark ledger.
* An end-to-end GPU simulator or any GPU speedup; WebGPU is f32 and was not run on hardware
  in this cycle.
* Studio use over a network: it is a loopback tool.

## Not run

Listed so that absence is not read as success.

* GCC and Clang sanitizers, UBSan, Linux builds and software-ICD (lavapipe) conformance for
  the new native tests; only MSVC AddressSanitizer and one AMD device ran.
* The `cq_solve_sat` timeout fix was found by reading the code; it was not reproduced
  dynamically.
* `drat-trim`, `cake_lpr`, `lrat-check`; `python-sat` under Python 3.14.
* `openapi_spec_validator` (not installed); protocol revisions of MCP newer than 2025-06-18.
* WebGPU on hardware; a committed Playwright spec for Studio.
* The full mutation suite, native build and web suite after the last Wave B commits; the
  numbers in **Measured** are the last recorded ones.
* Anything under W10, W14, W16, W17 and W18 of `research/v7/PLAN_COVERAGE.md`: provider
  runs, executable signing, cross-surface freeze, independent audit, release.
