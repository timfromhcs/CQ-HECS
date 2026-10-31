# CQ-HECS V3 STABLE — Autonomous Research, Engineering, Verification and Release Mission

> **HISTORICAL DOCUMENT (archived 2026-10-31).** Everything below describes an
> earlier state: the v3.0.0 mission and the v3.2.0 handoff. v3.2.0, v3.3.0 and v3.4.0 have
> shipped since. For the current state, read [`research/v5/BASELINE.md`](research/v5/BASELINE.md),
> [`research/v5/TASKS.md`](research/v5/TASKS.md) and [`PLAN.md`](PLAN.md). Do not act on the
> tasks below.

**Repository:** https://github.com/timfromhcs/CQ-HECS  
**Mission target:** Deliver the next genuinely stable major release, `v3.0.0`, only when the evidence supports a major-version release.  
**Prepared against the public repository state observed on:** 2026-10-30 (Europe/Berlin).  
**Observed stable baseline:** `v2.5.1`, tag `v2.5.1`, source commit `1be682a20ca3ccc9079893e0b150217a568a23e6`.  
**Canonical project version at baseline:** `2.5.1` (`scripts/version.py`).  
**Primary branch observed:** `main`.  
**Purpose:** A long-horizon, agentic, evidence-first engineering and research plan for an Opus 5.5 high-effort coding/research agent.  
**Execution rule:** Inspect first, preserve work, make a measured plan from the live tree, implement in small auditable slices, prove each slice, then publish only a verified release.

> **Mission honesty:** “V3 Stable”, “SOTA”, “exact”, “GPU accelerated”, “real hardware”, “subexponential”, “polynomial”, and “verified” are technical claims, not marketing words. They must be supported by code, primary sources, formal statements, reproducible experiments, and/or exact-SHA CI evidence. A hypothesis is not a feature. A simulation is not a QPU run. A Vulkan shader dispatch is not automatically a GPU-accelerated quantum simulator. An ETH refutation is not a proof that P = NP.

> **Evidence update, 2026-10-30 — the first real QPU data exists.** The
> preregistered `r-io-7` suite ran to completion on
> `rigetti:cepheus-1-108q` via Open Quantum: 25 of 25 jobs (5/5 FIT, 20/20
> EVAL), 1000 shots each, 1 credit per job, 25 credits. Verdict
> **`SUPPORTED`** — median ΔTV = −0.071905, 95 % CI [−0.135899, −0.006703],
> 14/20 EVAL circuits closer to the measurement than the ideal distribution.
> This changes what the next agent must assume:
>
> - **A QPU run now exists, but not from this package.** `cqhecs` still has no
>   provider adapter; `RealHardwareBackend` remains a fail-closed boundary.
>   The counts are external reference data, submitted by a separate runner.
> - **Readout error, not gate error, is the dominant measured effect.**
>   P(0|1) spans 0.059–0.531 per qubit (mean 0.164); P(1|0) spans 0.003–0.070
>   (mean 0.033). The fitted CX depolarizing parameter is 0.00125.
> - **`M-FIT` is structurally too weak and stays frozen anyway.** It is
>   preregistered; the per-qubit readout it computes is replaced by the device
>   mean in `noise_model()`. Its own fit quality says so: mean TV `0.229` on
>   the five jobs it was tuned on. Any repair is `M-FIT-2`, post-hoc,
>   exploratory, and needs a fresh suite on another backend to be confirmed.
> - **The work packages are written down, not implemented:**
>   [`research/v3/EMULATOR_BUILD_PLAN.md`](research/v3/EMULATOR_BUILD_PLAN.md).
> - **Still missing:** any calibration snapshot (the provider returned none),
>   any second backend, and any second day. No drift, T1/T2, or cross-device
>   claim is available from this data. `OQ-25` repeats `OQ-09` and moved
>   ΔTV from −0.0442 to −0.0321, which is inside shot noise, not a drift
>   measurement.
>
> **Follow-up, same day:** the per-qubit model (`M-FIT-2`, `cq-hecs
> noise-fit`) was built and scored post-hoc. It does **not** beat the frozen
> device mean (median ΔTV +0.055, CI [−0.007, +0.092]); the qubit-0 readout
> defect exists only in the gate-free probes, so readout does not transfer
> between jobs without a layout (H-V3-9, rejected). See
> `research/v3/EMULATOR_BUILD_PLAN.md` §7.
>
> Treat every "no real hardware" statement below as scoped to *this package's
> execution modes*, not to the existence of measured QPU data in `research/`.

---

# 0. Mission order and completion contract

Act as a coordinated senior team consisting of:

- quantum-algorithm and quantum-information researcher;
- classical quantum-circuit simulation researcher;
- tensor-network / factor-graph / FAQ algorithm engineer;
- complexity-theory researcher (SAT, #SAT, ETH, circuit complexity, proof complexity);
- exact-arithmetic and numerical-analysis engineer;
- C++20 / Vulkan / GPU systems engineer;
- Python / Qiskit / API maintainer;
- hardware-provider integration engineer;
- SAT / DIMACS correctness engineer;
- test, fuzz, differential-oracle and mutation-testing architect;
- UI/UX and terminal-interface designer;
- security, supply-chain, CI/CD and release engineer;
- scientific technical writer and documentation auditor.

The mission is to take the actual current repository from its latest stable state to a materially better v3 release. Do not assume that all proposed features are feasible or stable. Determine what is already implemented, what is incomplete, what is inaccurate, and what can be proven within the cycle.

## 0.1 Required execution order

1. Rediscover the live GitHub state and the local working copy. The snapshot in this document is a starting reference, not a permanent fact.
2. Preserve every user change, branch, untracked file, release tag and prior research artefact.
3. Reconstruct an exact baseline: repository SHA, tag, package version, release assets, CI runs, source-tree structure, test inventory, dependency/toolchain versions, supported execution modes and current claims.
4. Audit the existing `GEMINI.md`, README, architecture docs, release notes, UI code, C++ core, Python backends, SAT tools, Vulkan code and hardware bridge. Reuse valid work; do not rewrite blindly.
5. Reproduce P0/P1 correctness and scientific-integrity risks before adding major features.
6. Build a versioned evidence ledger and falsifiable research hypotheses.
7. Re-read the OpenAI and Anthropic ETH artifacts and current quantum-simulation research from primary sources. Record exact revisions, statements, assumptions, proof scope and limitations.
8. Select a bounded set of V3 deliverables. A research prototype may remain experimental; it must not silently become a stable production backend.
9. Implement a coherent V3 architecture with stable contracts, exact/fail-closed semantics, clear capability routing and measured UI.
10. Run the local build/test/benchmark loops on the current platform, then run the full cross-platform/cloud gates on the exact candidate SHA.
11. Perform visual QA of every user-facing terminal/UI surface and README rendering.
12. Update documentation only after the implementation and evidence are stable; then rerun the relevant checks on the docs-changing commit.
13. Build clean packages, install them in clean environments, inspect the actual artifacts, independently verify checksums and SBOM, and confirm that release notes describe the exact artifact commit.
14. Merge and publish only through repository policy and authorized credentials. Never bypass checks, reviews, branch protection, provider consent, or required secrets.
15. Finish with a compact but complete report containing exact SHAs, tags, CI links, artifacts, benchmark data, supported limits, unresolved issues and all blocked/not-run items.

## 0.2 Definition of done

V3 is complete only when all of the following hold:

- every supported execution path has an explicit capability contract and truthful result metadata;
- all confirmed P0 and P1 defects are fixed or the affected functionality is disabled/refused with an explicit documented reason;
- no fabricated solver output, quantum state, probability, error bound, hardware result, device metric or performance number can be surfaced as real;
- exact arithmetic is exact within explicitly bounded representation limits and overflow is detected before undefined behavior;
- approximation, finite precision, sampling uncertainty, modeled noise and physical-device uncertainty are separately represented;
- SAT/UNSAT/#SAT statuses are logically sound, including timeouts and resource exhaustion;
- any research algorithm is labelled `EXPERIMENTAL` until its mathematical scope and implementation are independently verified;
- the TUI/CLI reports actual telemetry or explicitly labels a demo; no simulation of live metrics is presented as a live reading;
- Vulkan claims match the actual tested device, dispatch path and end-to-end integration level;
- real quantum-provider execution is a separate opt-in mode and never falls back invisibly to classical simulation;
- independent differential, property, fuzz, mutation, negative, and regression tests cover the changed contracts;
- Linux and Windows native builds, supported Python compatibility lanes, sanitizers, packaging and exact-SHA cloud CI pass;
- README, architecture, usage, API, benchmark, citation and release files agree with the same final source SHA;
- the final report does not claim a universal quantum simulator, P = NP, a real QPU run, or SOTA superiority without a valid proof or benchmark.

A blocker is not a reason to fake completion. Mark `BLOCKED`, document the exact missing permission/credential/device, and finish all independent offline work.

---

# 1. Live baseline discovery and repository safety

## 1.1 Re-discover the repository before changing anything

Use GitHub and the actual local checkout. Verify:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
git log -15 --oneline --decorate
git tag --list 'v*' --sort=-version:refname
```

Also query the live GitHub API (or the connected GitHub integration) for:

- default branch and latest commit SHA;
- latest release, stable/prerelease/draft tags and target commits;
- all open PRs and recent closed/merged PRs relevant to the V3 baseline;
- the exact `ci.yml`, `nightly.yml`, `release.yml` runs for the latest stable SHA;
- all release assets, sizes, digests/checksum files and release body;
- branch protection/rulesets and required checks, when the API exposes them;
- recent workflow failure history and the latest nightly result.

Never assume `main`, `v2.5.1`, a clean tree or any SHA is still current. If the live version changed since this plan was prepared, rebase the plan on the actual release and rename the research directory accordingly.

## 1.2 Baseline facts observed on 2026-10-30

These facts were observed from the public repository and must be rechecked before use:

- latest published release: `v2.5.1`;
- source SHA: `1be682a20ca3ccc9079893e0b150217a568a23e6`;
- release date: 2026-10-30;
- package wheel: `cqhecs-2.5.1-py3-none-any.whl`;
- package sdist: `cqhecs-2.5.1.tar.gz`;
- SBOM: `cqhecs-sbom.spdx.json`;
- published SHA-256 assets are recorded in the GitHub release body;
- exact-SHA CI run observed: `40984668303`, with seven successful jobs (static/package, Linux native, Windows native, ASan/UBSan, Python 3.12, 3.13 and 3.14 compatibility);
- release run observed: `40984668504`, successful;
- no open PRs were returned in the live query at that time;
- `main` pointed at `1be682a20ca3ccc9079893e0b150217a568a23e6`;
- canonical version lived in `scripts/version.py` and was `2.5.1`.

Do not copy any of the above into new release notes as though V3 had already been tested. Treat these as historical baseline metadata only.

## 1.3 Working tree preservation

Before editing:

- record staged changes, unstaged changes and untracked files;
- save a patch or immutable snapshot of operator changes outside the repository working tree;
- identify generated build files and tracked binary assets;
- inspect `.gitignore`, submodules and LFS status;
- do not run `git reset --hard`, `git clean -fdx`, force-push, history rewrite or tag deletion;
- do not overwrite the existing root `GEMINI.md` without first preserving its contents and decisions;
- do not remove historical `research/v2_*` files merely because they are old;
- create a dedicated branch using the current repository conventions, for example `agent/cq-hecs-v3-stable`, unless a conflicting branch already exists.

If the current tree is dirty, distinguish the user's edits from agent edits in the execution log. Do not commit unrelated operator changes.

## 1.4 Build an immutable baseline dossier

Create a new research folder, preferably:

```text
research/v3/
    BASELINE.md
    SOURCE_INVENTORY.md
    DEFECT_REGISTER.md
    HYPOTHESES.md
    LITERATURE_MAP.md
    RESEARCH_TRANSFER_AUDIT.md
    ARCHITECTURE_DECISIONS.md
    BENCHMARK_PROTOCOL.md
    TEST_MATRIX.md
    EXECUTION_LOG.md
    UI_UX_AUDIT.md
    RELEASE_AUDIT.md
    LIMITATIONS.md
    evidence/
```

If another V3/V3.0 research folder exists, extend it rather than creating duplicate competing records.

Every report must state:

- exact source SHA;
- date/time and timezone;
- OS, CPU, RAM, GPU, Vulkan driver/ICD and whether the GPU is physical or software;
- compiler/CMake/Python/Qiskit/Aer/Stim/Lean versions where applicable;
- command line, exit code and captured log path;
- whether the evidence is baseline, candidate, merge commit, tag or downloaded release artifact;
- which results were local versus cloud;
- all `NOT RUN`, `SKIP`, `BLOCKED`, `INCONCLUSIVE` states.

Historical evidence must remain attached to the SHA that actually produced it. Never edit a prior test matrix to imply an old commit passed tests that were only run later.

---

# 2. Actual V2.5.1 architecture: preserve and extend

The current project is not a blank slate. Read the live files; the following is the observed architecture inventory and a starting map only.

## 2.1 Python quantum-simulation surface

Core modules include:

```text
cqhecs/
  backend.py
  circuit_analyzer.py
  circuit_library.py
  circuit_parsing.py
  cli.py
  expectation.py
  gate_lowering.py
  gate_manifest.py
  hardware_bridge.py
  provider.py
  result.py
  router.py
  scheduler.py
  backends/
    dense_reference.py
    noisy_density_matrix.py
    path_a_stabilizer.py
    path_b_stabilizer_rank.py
    path_c_mps_exact.py
    path_d_sparse_pauli.py
```

Existing high-level capabilities recorded in the V2.5.1 release notes:

- four-path router/backends;
- Path A stabilizer-tableau path;
- Path B stabilizer-rank/decomposition path;
- Path C MPS/tensor-chain path;
- Path D sparse-Pauli observable path;
- Pauli expectation API;
- composite gate lowering;
- independent dense reference for small cases;
- hardware-aware noise/profile bridge;
- noisy density-matrix reference path with a 10-qubit documented ceiling.

The exact capabilities, gate support and numerical semantics must be revalidated from source and tests. Do not infer that “Path C exact” means symbolic exactness if the implementation uses float64, Q1.31 or numerical-rank thresholds.

## 2.2 Native C++20 and Vulkan surface

The repository contains:

```text
include/
  cq/
    exact_cyclotomic.hpp
  cq_hecs/
    core/
    tensor_network.hpp
    transpiler/
    vulkan/
    constraint_solver.hpp
    residual_engine.hpp
  cqhecs/
    algebra/ring.hpp
    stabilizer/tableau.hpp
    vulkan/

src/
  algebra/ring.cpp
  constraint_solver.cpp
  hybrid_engine.cpp
  sat_solver.cpp
  stabilizer/
  tensor_network.cpp
  vulkan/
  terminal_ui.cpp
  terminal_ui.hpp
  tiered_storage.cpp
  ...

shaders/
  compute/
  ...
```

The codebase includes exact cyclotomic/dyadic-ring representations for Clifford+T-related values, stabilizer/tableau code, MPS code, sparse/tensor-related components, Vulkan buffers/context/pipelines, embedded shaders, QASM parsing and native SAT tooling.

There are currently duplicate/parallel exact-ring surfaces (`cq::Cyclotomic8` and `cqhecs::algebra::ExactRingElement`). Audit their invariants and usage before choosing whether to consolidate. Avoid an ABI-breaking rewrite merely for aesthetic consistency.

## 2.3 Hardware bridge status at baseline

The `v2.5.1` release notes describe:

- `IDEAL_CLASSICAL`, `NOISY_CLASSICAL`, `REAL_HARDWARE` as separate modes;
- synthetic built-in profiles;
- Kraus noise channels and a noisy density-matrix backend;
- a fake provider for offline emulation only;
- a fail-closed `RealHardwareProvider` boundary, with no provider connected;
- no mid-circuit measurement, reset or classical control in the stated scope;
- no basis transpilation to a profile's native gates in the current fake-noise bridge;
- no real hardware result used to justify a release claim; the measured
  `r-io-7` counts are research evidence and evaluation data, not a package
  feature (see the evidence update at the top of this document).

The V3 agent must inspect the actual implementation and tests. Do not state that a real provider exists just because a class named `RealHardwareProvider` exists. A fail-closed placeholder is a security boundary, not a connected hardware integration.

## 2.4 Vulkan status must be split into levels

The repository has real Vulkan infrastructure and compute shader dispatch tests, but this does not by itself mean the complete CQ-HECS simulator executes its quantum state evolution on the GPU.

The current `cqhecs::vulkan::VulkanEngine` source describes/implements a planner or memory-allocation facade whose gate methods fail closed rather than evolving a state. Separately, `VulkanContext` has device/queue/pipeline and dispatch methods for selected compute primitives (including reset, CORDIC and tensor contraction), and `test_vulkan_compute_contract.cpp` validates real dispatch/readback. The CI lane permits a software ICD for dispatch testing. The V2.5.1 release note records a Vulkan primitive-dispatch verification on one AMD iGPU, but explicitly says that this is **not end-to-end GPU acceleration**.

V3 must retain these distinctions:

| Evidence level | What it proves | What it does not prove |
|---|---|---|
| Shader source compiles | GLSL/shader source is syntactically/build valid | Device execution |
| SPIR-V validates | Compiled SPIR-V passes the selected validator | Dispatch or correct output |
| Software ICD dispatch | Vulkan commands and readback work on a software implementation | Physical GPU performance |
| Physical GPU primitive dispatch | A named physical device executed named primitives correctly | Full simulator acceleration |
| End-to-end GPU simulation | An actual supported simulator path performs state evolution on GPU and is correct | Universal GPU speedup or all-circuit scalability |
| Reproducible comparative benchmark | A named workload on named hardware showed measured improvement | General SOTA superiority |

All future GPU status fields and README badges must use one of these levels, not a generic `GPU supported` label.

---

# 3. Priority audit findings from the inspected source

These are **audit leads**, not all independently reproduced bugs. The agent must reproduce each against the live baseline, record a minimal failing test, determine severity, and fix only confirmed problems. If a concern is disproven, record the proof and close it as `NOT A DEFECT`.

## 3.1 P0/P1: Python DPLL timeout and false UNSAT risk

File to inspect:

- `python_bridge/sat_engine.py`

Observed source pattern:

- `CQSATSolver.solve()` calls `_dpll()` and creates `SATSolverResult` with `satisfiable`, `assignment`, counters and `verified`;
- `_dpll()` returns `(False, None)` when wall-clock budget is exceeded;
- the result-building code can then set `verified=True` for any non-SAT outcome because it treats `not sat` as an UNSAT proof;
- the result model has no explicit `timed_out`/`unknown`/`status` field in the inspected file.

This is a serious semantic hazard: timeout is not an UNSAT proof. Verify the current revision and add an explicit tri-state or richer status:

```text
SAT_VERIFIED
UNSAT_PROVEN
TIMEOUT_UNKNOWN
RESOURCE_LIMIT_UNKNOWN
INVALID_INPUT
INTERNAL_ERROR
```

Never encode timeout as `satisfiable=False, verified=True`. A SAT assignment must be checked independently against the original clauses. An UNSAT status requires a sound exhaustive proof process; a timeout or heuristic pruning event must never become proof.

Apply the same contract audit to `src/sat_solver.cpp`, CLI JSON, C API and every wrapper. The native path already attempts to distinguish timeout (`timed_out=true`, `verified=false`), but its branch-pruning soundness still requires audit.

## 3.2 P0/P1: Hash-based Cuckoo pruning is not an UNSAT proof by itself

Files:

- `src/sat_solver.cpp`
- `python_bridge/sat_engine.py`
- `python_bridge/cq_hecs.py` / `JSpaceGamma` implementation

The native solver hashes assignments into a finite table and may prune when a stored 64-bit hash matches. The Python solver hashes only the first 32 sorted assigned variables in its current inspected implementation and may prune when the cuckoo table reports a match.

A hash collision is not proof that two search states are identical. A finite/replacement hash table can also evict entries, and a heuristic cache cannot establish logical unsatisfiability unless a collision-safe equality check validates the canonical state.

Required action:

1. Trace whether any hash collision/duplicate detection can remove an otherwise necessary branch.
2. If yes, classify as P0 correctness if it can yield false UNSAT.
3. Replace the proof-critical use with collision-safe canonical state keys (full immutable assignment plus any formula/propagation state necessary to identify the node), or make the hash table advisory only and never allow it to close a branch as a proof.
4. If the design is a transposition table, compare full canonical keys after hash lookup.
5. Add adversarial collision tests by injecting a deliberately constant hash function.
6. Compare SAT/UNSAT with brute force for small random CNFs and an independent solver (for example, PySAT if available as a test extra, or a transparent brute-force oracle for small n).
7. Add formulas where branches differ only in variables above bit 32 and formulas whose partial assignments differ in exactly one bit.
8. Confirm timeout, collision, table saturation and eviction never yield false UNSAT.

Do not retain “cycle pruning” language if no actual cycle exists in the search graph. A DPLL recursion tree is not automatically a cyclic state machine.

## 3.3 P1: DIMACS parser contract and Python/native parity

Files:

- `python_bridge/sat_engine.py` (`DIMACSParser`)
- `src/sat_solver.cpp` and parser header
- `tests/test_fuzz_sat.py`, `tests/cpp/test_sat_parser.cpp`

Audit:

- declared variable/clause counts;
- clauses spanning multiple lines (valid DIMACS commonly permits clause continuation);
- multiple clauses on one line;
- empty clauses;
- unterminated final clause;
- zero terminators;
- literals outside the declared variable range;
- duplicate and tautological literals;
- malformed/missing problem line;
- comments and whitespace;
- integer overflow, huge files and resource ceilings;
- file path/stdin errors;
- consistent Python/C++ parsing semantics.

The Python parser inspected at baseline initializes a clause accumulator per raw line and appears to accept more permissive syntax than the strict native parser. Verify this with a reference DIMACS grammar and differential tests. Do not “fix” valid continuation syntax by rejecting it. Compare parsed clause multisets after canonical normalization.

## 3.4 P1: Exact ring arithmetic overflow and undefined behavior

Files:

- `include/cq/exact_cyclotomic.hpp`
- `include/cqhecs/algebra/ring.hpp`
- `src/algebra/ring.cpp`
- `tests/cpp/test_exact_ring.cpp`

Observed risk:

- coefficients use signed `int64_t`;
- multiplication/addition expressions can overflow signed integers;
- scaling and shifts need checked bounds;
- denominator exponent addition (`k + other.k`) can overflow `uint32_t`;
- `noexcept` arithmetic that cannot report overflow may force undefined behavior or silent corruption;
- conversion using `pow(sqrt(2), k)` can overflow/underflow numerically even when the symbolic value is representable;
- exactness claims need to state coefficient/exponent bounds.

Required action:

1. Re-derive the arithmetic formulas from the represented ring definition.
2. Check all intermediate operations, not just the final value. `__int128` can help on supported compilers but itself has limits; implement checked arithmetic or use a proven arbitrary-precision backend where appropriate.
3. Decide whether to expose checked operations returning an error/expected type or throw typed overflow exceptions. Do not hide failure in `noexcept` arithmetic.
4. Guard shifts, multiplication, addition, subtraction, negation of `INT64_MIN`, and exponent sums.
5. Add exact boundary tests at and around overflow, including negative coefficients and `k` boundaries.
6. Add differential tests against Python big integers / SymPy exact algebra for randomized bounded cases.
7. Verify canonicalization uniqueness, addition/multiplication associativity within representable bounds, conjugation, norm, field identities and gate unitarity.
8. Avoid converting exact values to `double` for equality or correctness decisions.
9. Separate exact symbolic representation from approximate numerical export.
10. Audit both ring implementations and either unify them safely or document why two are intentionally retained.

## 3.5 P1: C++ exact-ring test may be disabled in Release

`tests/cpp/test_exact_ring.cpp` uses `assert(...)`. The native CI configures a Release CMake build. Many Release toolchains define `NDEBUG`, which compiles assertions out.

Verify whether `test_exact_ring` is currently meaningful under the actual CI compiler flags. Replace correctness-critical `assert` calls with an always-active test/check macro or a test framework that fails in Release. Alternatively, explicitly undefine `NDEBUG` for test targets, but prefer explicit checks with clear diagnostics.

Add a meta-test demonstrating that a deliberately false condition fails the test executable even under Release configuration. Never report `500,000` assertions as executed if the compiler removed them.

## 3.6 P1: Demo telemetry presented as live metrics

Files:

- `python_bridge/tui_dashboard.py`
- `src/terminal_ui.cpp`
- `src/terminal_ui.hpp`

The Python dashboard currently constructs telemetry-like values through formula-driven updates and preset constants. The C++ terminal UI updates VRAM, jitter, nudge state and attention weights using `sin`, cycle counters and synthetic patterns. It labels the engine `ACTIVE`, displays performance-like values and uses phrases such as `PHYSICAL HARVEST`.

Unless every reading is sourced from a real measured counter, these values are not live telemetry. This conflicts with the project's anti-fabrication invariant.

Required action:

- replace fabricated readings with a metrics-provider interface that reports actual measured values;
- use `UNKNOWN`, `NOT AVAILABLE`, or `DEMO DATA` when no valid source exists;
- if synthetic mode is retained, require explicit `--demo` and place a persistent `SIMULATED DATA` label in every frame;
- never call a CPU timing surrogate “GPU jitter” or “physical entropy”;
- remove hard-coded current version strings from UI code;
- never report VRAM utilization unless a supported device query actually returns it;
- do not infer an MPS bond dimension or tensor residual from a preset;
- do not present generated attention weights as a real optimizer's decisions;
- ensure `--cycles`/`--rate` and interactive quit work on Windows, Linux, redirected output and non-TTY sessions;
- ensure dashboard collection does not mutate the simulation under observation.

This is a P1 trust/UI issue and must block Stable if misleading data remains.

## 3.7 P1: Vulkan device selection and GPU provenance

`src/vulkan/vulkan_context.cpp` selects a “best” device using device type and name heuristics and has special scoring for Lavapipe/llvmpipe/SwiftShader. This may be acceptable for CI, but V3 must make selection policy observable and testable.

Required action:

- identify software versus physical devices using robust Vulkan properties and explicit user selection/override;
- do not equate `VK_PHYSICAL_DEVICE_TYPE_CPU` with a particular software ICD without recording evidence;
- report device name, vendor ID, device ID, driver version, API version, queue family and required feature support;
- support `--device auto|index|name` or an equivalent stable selection API;
- expose why a requested device was rejected;
- add tests for no device, multiple devices, software ICD, integrated GPU, discrete GPU and missing `shaderInt64`;
- never silently fall back from a requested physical GPU to a software ICD or CPU.

## 3.8 P1/P2: C++ UI and package/UI version drift

`src/terminal_ui.cpp` and `python_bridge/tui_dashboard.py` have older version strings and target descriptions. Use the canonical version surface or build metadata. Ensure no hard-coded v0.2.0/v2.4.0 labels survive in a current v3 UI.

## 3.9 P2: Baseline benchmark artefacts are historical

Files under `benchmarks/` include v0.2.0-era Vulkan/MPS benchmark reports and single-run smoke JSON from v2.2.0. Keep them for provenance, but mark them historical and remove their appearance of current V3 evidence. Never overwrite historical raw outputs with newer numbers.

## 3.10 P2: README and research scope consistency

Read every root and `docs/` document. The V3 README must not accidentally inherit old claims such as generic cross-vendor GPU acceleration, unlimited exact MPS, a universal 300-qubit capability, “bit-exact” floating-point behavior, actual QPU connectivity, or SOTA claims unsupported by current tests.

---

# 4. Scientific boundaries and vocabulary

## 4.1 Three separate quantum execution modes

Use the current three-mode model, but audit and strengthen it:

1. `IDEAL_CLASSICAL`: a classical computer simulates an ideal circuit using a named CQ-HECS path.
2. `NOISY_CLASSICAL`: a classical computer evaluates a specified noise model/profile; output is a modeled distribution or estimator.
3. `REAL_HARDWARE`: a job is submitted to and returned by an identified physical QPU.

No mode may silently masquerade as another. A result record must contain execution mode, result source, implementation/method, device/provider/backend, circuit hash, compiled/transpiled circuit hash where applicable, qubit and classical-bit mappings, shots, seed (when meaningful), timestamps, calibration/profile provenance, noise-model version, result kind, numerical status, error scope, and job ID when real hardware was used.

A fake provider always returns `NOISY_CLASSICAL` or an explicitly named emulator source, never `REAL_HARDWARE`.

## 4.2 Result semantics are not one boolean

Retain/extend the current `SimulationState` but audit every field and constructor. A truthful result may need:

- execution state: `EXACT`, `CERTIFIED`, `UNRESOLVED`, `FAILED`;
- result kind: joint counts, marginal counts, expectation values, amplitudes, statevector, density matrix, unitary, raw QPU counts, sampled estimate;
- exactness mode: symbolic/exact-ring, exact stabilizer algebra, exact combinatorial result, floating-point evaluation without deliberate truncation, or approximate/truncated;
- approximation metadata: what was truncated, when, by what policy and what diagnostic was computed;
- error bound: value or null, metric, target object, assumptions, proof/certificate reference;
- sampling uncertainty: confidence, failure probability, support size, method;
- model uncertainty: profile age, calibration provenance and omitted channels;
- source of result: local path, simulator package, hardware provider or external oracle.

`None` means “not available / not derived”, never “zero”.

`error_bound = 0.0` must not be used to suggest physical correctness, zero floating-point roundoff, a perfect hardware match or a certified bound on a different metric. A zero bound can only be stated for the metric and object actually proved.

## 4.3 Do not claim arbitrary efficient classical quantum simulation

Classical simulation can be efficient for restricted families: stabilizer circuits, bounded-entanglement MPS families, some low-width tensor networks, circuits with compatible algebraic phase structure, and task-specific observables. Universal worst-case circuits can require exponential resources under widely studied complexity assumptions.

CQ-HECS must report the workload structure and output task, not merely qubit count.

A statement such as “300+ qubits supported” must include the circuit family, backend path, depth, topology, bond/rank, measured output type, memory/time budget and exactness status. A GHZ or 1D cluster state result is not evidence for arbitrary 300-qubit universal circuits.

---

# 5. ETH / P vs NP / OpenAI Math / Anthropic research protocol

This work is a research-input stream, not a license to advertise a P = NP result or blindly port a SAT paper into the quantum simulator.

## 5.1 Logical boundaries that every agent must preserve

Definitions:

- `P`: decision problems solvable deterministically in polynomial time.
- `NP`: decision problems whose proposed witnesses can be verified in polynomial time.
- `P ⊆ NP` is known.
- `P = NP` is open.
- 3-SAT is NP-complete.
- ETH asserts, in one standard formulation, that 3-SAT has no deterministic `2^{o(n)}`-time algorithm in the number `n` of variables (with the relevant input-size conventions).
- #3-SAT counts satisfying assignments and is a #P-complete counting problem.

The implication is:

```text
P = NP  =>  ETH is false
ETH is false  -/->  P = NP
```

A subexponential algorithm such as `2^{O(n / sqrt(log n))}` is not a polynomial-time algorithm. It remains asymptotically superpolynomial. The new papers do not prove that `P = NP`.

Do not claim that subexponential SAT automatically gives subexponential time for all NP problems: the OpenAI manuscript explicitly notes that a `2^{o(n)}` bound does not necessarily transfer under arbitrary polynomial-time reductions. Inspect the size blow-up of each reduction.

## 5.2 OpenAI ETH manuscript — exact current artifact to review

Primary source:

- https://github.com/openai/math/tree/main/preprints/The-Exponential-Time-Hypothesis-is-False-October-25-2026
- https://github.com/openai/math/blob/main/lean/docs/378.md

The October 25, 2026 manuscript claims a deterministic algorithm for exactly counting satisfying assignments of arbitrary fixed-width `k`-CNF formulas (for every fixed `k ≥ 2`) in subexponential time and polynomial space. The headline expression in the manuscript is of the form:

```text
(n + m) ^ O_k(1) * 2 ^ (O_k(n log log n / sqrt(log n)))
```

For fixed clause density (`m ≤ Dn` for fixed `D`), the manuscript gives a stronger sparse-formula expression of the form:

```text
(n + m) ^ O_(k,D)(1) * 2 ^ (O_(k,D)(n / sqrt(log n)))
```

The core paper combines algebraic interpolation/grouping with exact tensor-network contraction and a 2-adic/modular algebraic structure. Read the complete paper and the proof roadmap; do not rely only on a summary.

Important formalization discrepancy to preserve:

- the current public `lean/docs/378.md` scope note describes a Lean-verified bound with an extra `(log log n)` factor compared with the sharper headline manuscript form;
- the weaker expression is still subexponential, so it still suffices for the claimed ETH refutation if all formal statements and encodings match;
- do not say the Lean files formalize the exact sharpest paper theorem unless the live scope note and comparator prove that exact match.

The manuscript has additional consequences (including selected counting results and a circuit lower bound for a language in `E^NP`) that need to be read and checked individually. Do not generalize them to all NP languages or to P vs NP.

## 5.3 Anthropic ETH artifact — exact current artifact to review

Primary sources:

- https://github.com/anthropics/formal-math/tree/main/eth
- https://github.com/anthropics/formal-math/blob/main/eth/README.md
- https://github.com/anthropics/formal-math/blob/main/eth/MainResults.lean

Anthropic's public README describes a deterministic subexponential algorithm for 3-SAT that in fact solves the harder #3-SAT counting task, with headline running time:

```text
2 ^ O(n log log n / sqrt(log n))
```

The condensed technical idea is a tensor-network contraction recurrence, with a SWAP/singlet decomposition. In the README the recurrence is presented as:

```text
e(9 K^16) <= 0.9 e(K) + O(1/K)
```

The SWAP operator is decomposed as identity minus twice a singlet projector; terms are grouped by the number of singlet components, followed by a choice of row/column contraction and balanced regrouping. This is a high-level roadmap, not a full implementation specification. Read the paper and source proof for exact definitions, constants, domains and assumptions.

The Anthropic README explicitly states that the result is purely asymptotic and says nothing about solving formulas in practice. Preserve that caveat in all CQ-HECS documents.

The README also explains formalization boundaries:

- `MainResults.lean` states key theorems and the proof is in separate files;
- the repository's Comparator workflow checks statement correspondence against challenge statements and also checks proofs with the independent `nanoda` kernel;
- the README documents how the Lean statements differ from printed paper statements;
- `Challenge.lean` contains two challenge statements that intentionally use `sorry`; do not mistake those statement placeholders for proved results or quote the build warnings without context;
- the paper-to-Lean correspondence must be manually audited via the paper index/appendix and current proof files.

The Anthropic paper is a research artifact. Its publication/formalization status is not the same thing as broad independent community acceptance. Record the current status and date; do not say “universally accepted” or “refereed” unless verified.

## 5.4 Formal proof policy for AI-derived mathematics

For each imported theorem or algorithm, keep these separate:

1. prose statement in the paper;
2. formal theorem statement;
3. proof term accepted by Lean;
4. dependency/axiom report;
5. paper-to-formal-statement correspondence;
6. extracted or handwritten executable implementation;
7. implementation-to-formal-specification correspondence;
8. experimental evidence and performance.

Lean acceptance proves the formal proposition under its assumptions and axioms. It does not automatically prove that the proposition fully captures the paper's intended statement or that an unrelated C++/Python implementation is a refinement of that formal model.

For every research import, record:

- source URL and immutable commit/revision;
- paper version/date;
- exact theorem identifiers;
- full assumptions and computational model;
- exact formal statement and proof target;
- axioms and trusted dependencies;
- independent checker status;
- limitations and known statement discrepancies;
- exact CQ-HECS module that could use the idea;
- transformation proof needed for transfer;
- negative/edge-case examples;
- benchmark workload and oracle;
- transfer classification.

Allowed classifications:

- `DIRECT_TRANSFER`: the published theorem directly applies and all assumptions match;
- `ADAPTABLE`: the technique suggests a new construction, but a new proof is needed;
- `VALIDATION_ONLY`: useful comparator/test family/boundary only;
- `NEGATIVE_RESULT`: prevents an unsafe or false claim;
- `RESEARCH_ONLY`: a prototype may be explored but is not release code;
- `NOT_RELEVANT`: no material application found;
- `UNVERIFIED`: insufficient proof or source correspondence.

## 5.5 What the ETH results may and may not contribute to CQ-HECS

Do not copy the OpenAI/Anthropic SAT algorithm into the quantum simulator as a generic quantum speedup. The algorithms solve a very specific classical Boolean counting problem. They do not compute arbitrary complex quantum amplitudes by themselves, do not run a QPU and do not prove universal quantum simulation tractability.

Potential research adaptations, all `RESEARCH_ONLY` until proved:

### A. Boolean factor-graph / #SAT representation

Represent a CNF formula as a sum-product network:

```text
#SAT(F) = sum_{x in {0,1}^n} product_{clause c} 1[c(x) is satisfied]
```

Implement a small independent Boolean tensor-network prototype to understand factor arity, variable elimination, contraction order, rank, sparsity, and exact integer arithmetic. The first implementation is a reference/research tool, not an assumption that the OpenAI algorithm has been reproduced.

### B. Weighted tensor contraction

A quantum amplitude is also a sum over internal wire assignments, but with complex-valued tensor factors and interference:

```text
A(y | x) = sum_{z} product_g T_g(z, x, y)
```

The algebraic domain differs from Boolean counting. Quantum circuits can contain complex phases and cancellations. The OpenAI 2-adic divisibility structure or Anthropic SWAP/singlet rank recurrence does not transfer automatically.

The candidate research question is:

> Under which exact coefficient domains, representations, valuations, rank conditions, and graph structures can a Boolean contraction theorem be generalized to a weighted complex tensor network without losing exactness or the proved complexity bound?

Potential domains to investigate:

- integers/rationals for simple exact factor graphs;
- cyclotomic/dyadic rings for Clifford+T amplitudes;
- finite fields/modular rings only where reconstruction is mathematically justified;
- exact algebraic number fields for appropriate root-of-unity gates;
- arbitrary-precision complex balls/intervals for certified approximate results;
- standard complex floating point only for explicitly non-certified numerical experiments.

For each domain, prove that addition/multiplication, zero testing, equality, conjugation and coefficient growth are controlled. Do not assume a valuation or divisibility property that has not been shown for every tensor operation.

### C. SWAP/singlet decomposition

Prototype the identity for two-qubit operators and test basis conventions, normalization, ordering and global phase. Generalize only after deriving the tensor form for the exact network object. The optimization is relevant only when SWAP tensors are part of the contracted network and the rank decomposition is cheaper than simply permuting tensor indices.

For networks where a SWAP is only a wire relabeling, explicit decomposition may add more work rather than reduce it. Require an operation-count model and benchmark it.

### D. FAQ / InsideOut / tensor-layout symmetry

Use the current 2026 work:

- https://arxiv.org/abs/2610.00547

The paper presents functional aggregate queries (FAQs) as a unified language for exact classical quantum-circuit simulation. It relates representation-aware InsideOut evaluation to treewidth bounds, fractional-edge-cover/sparsity bounds, rank-width-based simulation for suitable phase structures, and a tensor-layout-symmetry-width tractability criterion. The authors also report polynomial-size representations for Clifford-circuit affine-quadratic factors under their stated model.

This is a promising architecture inspiration:

- make the requested computation explicit (amplitude, probability, expectation, sample, partition function);
- make the algebra/semiring explicit;
- make the factor representation explicit;
- make the evaluation plan explicit;
- estimate graph/representation parameters before execution;
- choose a provably valid plan based on the task and supported factor algebra.

Do not rebrand the CQ-HECS router as an FAQ implementation unless the data model and InsideOut evaluation are genuinely implemented and independently tested.

## 5.6 No P = NP roadmap claims

The project may contain a research sandbox named `complexity_lab`, but its UI and README must state:

- P vs NP remains open;
- ETH subexponential results are not polynomial-time algorithms;
- practical SAT solver speed on a dataset does not prove a worst-case asymptotic bound;
- empirical scaling does not prove P = NP or P ≠ NP;
- heuristics, hash pruning, SAT witness verification and exact UNSAT proof are separate;
- #SAT counting is strictly more informative than SAT decision, but a solver for a restricted representation is not a universal #SAT solver.

A P = NP claim may only be made if an independently reviewed, mathematically valid polynomial-time algorithm for an NP-complete problem is provided with a complete proof of worst-case running time and correctness. That is not an expected V3 outcome.

---

# 6. Quantum simulation research and SOTA benchmarking

V3 should improve a specific workload class or an interface/verification guarantee. It must not claim “best simulator” based on a list of modern paper titles.

## 6.1 Define the computational task first

Distinguish:

- strong simulation: compute exact amplitudes/probabilities or a full state representation;
- weak simulation: sample from a measurement distribution;
- observable estimation: compute expectation values for named observables;
- noisy simulation: apply a stated noise model;
- circuit compilation/transpilation: map gates and topology to a device basis;
- physical execution: submit to actual hardware;
- error mitigation: transform measured/noisy estimates under explicit assumptions.

A benchmark comparing different tasks, result semantics or approximation policies is invalid.

## 6.2 Current CQ-HECS paths to preserve and improve

### Path A — stabilizer tableau

- Scope: supported Clifford/stabilizer operations.
- Preserve symplectic/GF(2) correctness, Pauli phases/signs, measurement and seeded sampling.
- Differential-test against Stim and Qiskit Aer stabilizer for overlapping supported semantics.
- Verify reset, measurement ordering, global phase irrelevance for counts, qubit indexing and partial measurement.
- No claim for general non-Clifford gates unless the exact path explicitly supports them.

### Path B — stabilizer-rank/decomposition

- Audit actual branch/rank growth and cutoff behavior.
- Separate exact algebraic decomposition from floating-point evaluation of branch amplitudes.
- Confirm the branch ceiling fails closed and is reported.
- Compare small circuits against dense statevector and Aer extended-stabilizer where semantics overlap.
- Measure scaling against T-count and entangling structure, not only qubit width.
- If the state representation is float64, do not call all arithmetic “bit-exact”.

### Path C — MPS/tensor chain

- Test all gate layouts and operand order, adjacent and non-adjacent routing, SWAP restoration, measurement and sampling.
- Preserve no-silent-truncation behavior.
- Distinguish no configured truncation from mathematical exactness: floating-point roundoff, fixed-point quantization, numerical rank thresholds and storage precision still matter.
- Keep per-update discarded spectral mass separate from a propagated global state/observable bound.
- Report bond-dimension history, maximum bond, RAM, disk, paging, temporary workspace and numerical rank floor.
- Make memory preflight happen before allocations or partial state mutation.
- Differential-test supported small cases against Aer untruncated MPS and dense statevector.
- Stress area-law, low-entanglement, 1D cluster, QFT-like, random brickwork and volume-law/high-entanglement families.
- For impossible volume-law cases, return `UNRESOLVED` rather than fabricate or silently truncate.

### Path D — sparse Pauli / Heisenberg propagation

- Treat this as a task-specific observable engine, not a full state simulator.
- Verify conjugation identities and phases for every supported gate.
- Independently derive the observable bound for every pruning/truncation rule.
- Report the exact observable(s), norm/metric and omitted-term proof.
- Never relabel an observable-specific error bound as a joint distribution or statevector bound.
- Compare with dense exact expectations on small random circuits.

### Noisy density-matrix path

- Current documented ceiling is 10 qubits; the dense density matrix has quadratic statevector dimension in memory.
- Preserve explicit memory preflight and strict ceiling.
- Verify Kraus completeness, trace preservation, Hermiticity, positivity within justified numerical tolerance, normalization and readout map.
- Test asymmetric qubit-specific noise, non-mirror-symmetric circuits, partial measurement and all supported gate parameters.
- Ensure noise attaches to the original source gate semantics, not accidentally to lowered constituent gates unless that is the documented model.
- No unknown gate is treated as identity.

## 6.3 External state-of-practice comparators

At mission start, re-check current official versions and supported options. Relevant comparators include:

- Qiskit Aer: https://qiskit.github.io/qiskit-aer/ — current docs describe statevector, density matrix, stabilizer, extended stabilizer, MPS, unitary, superoperator and GPU-enabled methods with backend-specific restrictions;
- Stim: https://github.com/quantumlib/Stim — stabilizer and quantum-error-correction circuit simulation; verify exact release, semantics and output type;
- MQT DDSIM: https://github.com/cda-tum/ddsim — decision-diagram / hybrid circuit simulation; inspect current branch, build and supported tasks;
- NVIDIA cuQuantum: https://developer.nvidia.com/cuquantum-sdk — GPU-oriented statevector/tensor-network APIs with vendor/platform constraints;
- MQT Bench: https://github.com/cda-tum/mqt-bench — benchmark families/circuit workloads, not itself a universal correctness oracle;
- quimb: https://github.com/jcmgray/quimb — tensor-network construction/contraction ecosystem;
- Qiskit transpiler/IBM Runtime docs when a real provider adapter is considered.

No runtime dependency should be added merely to create an SOTA-looking dependency list. Prefer optional test-only extras for differential oracles and pin exact versions in test reports.

## 6.4 Benchmark families

Build a reproducible benchmark suite with at least:

- GHZ and GHZ-like stabilizer;
- 1D cluster states;
- random Clifford circuits;
- Clifford+T circuits with controlled T-count;
- nearest-neighbour brickwork at controlled depth;
- QFT/QFT-like structures;
- random universal circuits;
- low-entanglement and area-law states;
- volume-law/high-entanglement states;
- sparse-observable and Pauli-heavy workloads;
- noisy circuits with asymmetric per-qubit/per-gate parameters;
- topology-constrained hardware circuits;
- large-narrow and small-dense workloads.

For each benchmark record input circuit hash, exact circuit generator version, n-qubits, depth, gate counts, T-count, two-qubit gate count, topology, estimated/observed entanglement proxy, max bond/rank, output task, path, shots, precision mode, truncation settings, memory budget, runtime, peak RSS/VRAM if measured, device identity, error and correctness oracle.

Use warmups, repeated runs, median and spread (and confidence intervals where suitable). Separate build/compile time from execution. Do not compare a CPU result from one task with a GPU result from another task or different numerical accuracy.

---

# 7. V3 architecture proposal

Do not rebuild everything into a monolith. Keep the current four-path architecture and progressively introduce explicit abstractions where they reduce semantic drift or enable measurable research.

## 7.1 Proposed layers

```text
┌──────────────────────────────────────────────────────────────┐
│ User surfaces: CLI / Python API / Qiskit adapter / TUI         │
├──────────────────────────────────────────────────────────────┤
│ Canonical Circuit IR + Result Contract + Capability Registry   │
├──────────────────────────────────────────────────────────────┤
│ Planner: task-aware path selection + resource preflight        │
├──────────────────────────────────────────────────────────────┤
│ Simulation backends                                            │
│  A stabilizer | B stabilizer-rank | C MPS | D sparse Pauli     │
│  dense reference | noisy density-matrix | experimental FAQ     │
├──────────────────────────────────────────────────────────────┤
│ Algebra / tensor / graph engines                               │
│  exact cyclotomic | checked integer | tensor factors           │
│  variable elimination | contraction plans | rank/symmetry      │
├──────────────────────────────────────────────────────────────┤
│ Execution devices                                              │
│  CPU | Vulkan primitive backend | experimental Vulkan path     │
│  provider adapters (explicit REAL_HARDWARE only)               │
├──────────────────────────────────────────────────────────────┤
│ Evidence / observability / provenance / testing                │
└──────────────────────────────────────────────────────────────┘
```

Do not force every module into the proposed shape if the existing architecture is already clearer. Record architecture decisions and their evidence.

## 7.2 Canonical Circuit IR

Audit whether the current `Instruction` model preserves:

- declared qubit count including unused high-index qubits;
- quantum and classical register widths;
- global phase;
- gate identity and exact source parameters;
- operand/control order;
- measurement `(qubit, clbit)` mapping;
- terminal versus mid-circuit measurement;
- reset, barriers, delay and classical conditional metadata;
- source frontend and parse diagnostics;
- device layout/transpilation mapping.

Do not normalize away semantics required by another backend. A frontend must either produce a semantically equivalent canonical IR or a typed refusal. Add a round-trip serialization format with explicit schema version.

A full IR rewrite is not mandatory if small compatible additions solve the observed mismatch. Avoid ABI-breaking index-width changes without a migration plan.

## 7.3 Capability registry and planner

Every backend should declare capabilities as data, not rely on scattered gate-name conditions. Capabilities should include:

- supported gate set and parameter arity;
- supported measurements and classical control;
- output/result kinds;
- exactness/numerical mode;
- max width and resource ceilings;
- noise support;
- topology constraints;
- supported arithmetic domain;
- device requirements;
- known unsupported/experimental semantics.

The planner should select only a backend whose declared capability supports the requested task. Resource preflight must run before allocation. If no path can return the requested result within limits, return `UNRESOLVED` with a useful explanation.

Do not silently route from a requested GPU/QPU path to CPU or from a requested real device to an emulator.

## 7.4 Provenance and result schema

Add only the metadata that is required and can be populated accurately. Consider a stable run manifest containing:

- schema version;
- CQ-HECS version and source SHA;
- normalized circuit hash;
- original source hash if available;
- frontend and parser version;
- selected backend and planner decision trace;
- device identity and actual execution path;
- numerical settings and approximation details;
- random seed(s);
- output type;
- time/memory metrics and where they were measured;
- calibration/noise provenance;
- error certificate and exact scope;
- warnings/refusals.

Do not break v2 clients casually. Add compatibility tests and a schema migration note for any versioned result change.

---

# 8. V3 research implementation workstreams

The agent should build the highest-value workstreams in the order below. A workstream may be deferred if the evidence or time/resource budget is insufficient. A failed hypothesis is a valid research outcome; do not keep forcing it into code.

## Workstream A — Correctness, contract and exact arithmetic foundation (mandatory)

Deliverables:

1. Fix confirmed SAT timeout/UNSAT status issues.
2. Make proof-critical hash/transposition logic collision-safe or remove proof authority from probabilistic hash pruning.
3. Harmonize Python/native DIMACS parsing.
4. Fix confirmed integer overflow/undefined behavior in both exact-ring surfaces.
5. Make exact-ring tests active in Release builds.
6. Audit all result constructors and remove ambiguous `exact`/zero-bound semantics.
7. Confirm Qubit/clbit, endian, partial measurement, global phase and operand-order parity across QASM, Qiskit, instruction lists, Python and native ABI.
8. Add regression tests for every confirmed issue.

Acceptance:

- no timeout can be represented as UNSAT;
- no collision can prune a branch as a proof;
- all successful SAT assignments are independently verified;
- UNSAT status has a sound exhaustive method and explicit proof provenance (or is clearly an untrusted decision status if a proof artifact is not generated);
- exact-ring overflow is caught deterministically;
- all Release tests execute meaningful checks;
- cross-frontend semantics match on the supported subset.

## Workstream B — Representation-aware tensor/FAQ research engine (one main research feature)

Build a contained research package first, for example:

```text
cqhecs/research_tensor/
    domains.py
    factors.py
    factor_graph.py
    elimination.py
    contraction_plan.py
    metrics.py
    boolean_counting.py
    weighted_networks.py
    faq.py
    experimental_backends.py
```

The exact package layout may follow the current repository style.

### B1. Minimal reference model

Implement a small, transparent factor graph/TensorNetwork model:

- typed indices with dimensions;
- factors with named variables/indices;
- explicit coefficient domain;
- declared free/bound indices;
- stable circuit/formula normalization;
- deterministic contraction plans;
- intermediate-size and operation-count estimation;
- resource-budget preflight;
- exact brute-force evaluator for tiny networks as oracle.

The first domains should be narrowly chosen and mathematically simple:

- Boolean/0-1 factors for SAT decision and count;
- arbitrary-precision integers for exact #SAT counts;
- exact dyadic/cyclotomic coefficients only when the implementation's ring is checked and the operation set is supported;
- floating complex domain for non-certified experiments, with explicit tolerance/precision metadata.

Do not implement a universal semiring abstraction before there is a concrete use case. But keep the coefficient operations behind a typed interface so future domains can be added.

### B2. Variable elimination / InsideOut baseline

Implement an exact, deterministic baseline:

- choose elimination orders (min-fill, min-degree or a documented heuristic);
- estimate induced width;
- track factor support/entry counts;
- execute with exact small arithmetic;
- compare against brute force on small instances;
- store the order and intermediate-size trace.

This is a reference point for FAQ-style evaluation. Do not describe it as the new OpenAI algorithm.

### B3. FAQ-style task specification

Represent the requested computation separately from the evaluation algorithm:

- SAT decision;
- #SAT counting;
- amplitude `A(y|x)`;
- probability;
- named expectation value;
- partition/sum-product function.

The output contract must state whether variables are summed, fixed or free. For a quantum circuit, boundary indices represent input/output basis values and internal wire indices are aggregated. Validate the mapping by enumerating all amplitudes for tiny circuits and comparing to dense matrix/statevector references.

### B4. Treewidth, fractional cover, rank-width and symmetry descriptors

Implement estimators separately and label approximate estimates as such:

- primal/line/incidence graph extraction;
- min-fill/min-degree induced width estimates;
- fractional edge-cover lower/upper estimators where available;
- phase-graph rank computations for compatible quadratic phase forms;
- separator symmetry descriptors;
- tensor-layout symmetry candidates.

A heuristic structural score must not be used as a correctness proof. Store estimator provenance and limitations.

### B5. Weighted complex extension experiment

Prototype only after the Boolean/integer model is proven:

- exact Clifford+T gate tensors over the verified cyclotomic ring;
- independent basis ordering and endian tests;
- exact contraction of tiny circuits;
- exact comparison to symbolic/direct matrix multiplication;
- explicit coefficient growth and overflow behavior;
- no generic irrational-angle gates in the exact ring unless represented by a separate algebraic/transcendental model.

Explore whether the OpenAI valuation/modular compression can be generalized to these coefficients. Before coding the optimization, write a theorem statement with every needed assumption. If no valid proof is found, keep a benchmarked exploratory prototype and label it `RESEARCH_ONLY`.

### B6. Anthropic SWAP/singlet experiment

- implement the two-qubit identity in a tiny algebra test;
- build tensor-form tests under both wire-order conventions;
- verify normalization and projector idempotence;
- generate small grid/complete-graph tensor networks;
- compare direct contraction with decomposed contraction;
- count rank/term growth and runtime;
- verify the recurrence's variables/normalization exactly before attempting to reproduce it.

Do not use the recurrence from the README as a black-box production complexity estimate. Re-derive the definitions and hidden constants from the paper.

### B7. Research acceptance

A new optimization can graduate only if:

- the mathematical operation is specified;
- correctness is proved or independently established within a clearly bounded domain;
- all assumptions match real inputs;
- exact small cases match an independent oracle;
- resource use is bounded and fail-closed;
- the same task/accuracy baseline is used in benchmarks;
- worst-case behavior and known limitations are documented;
- it beats an existing plan on a preregistered family or unlocks a family previously unsupported.

If it does not meet this, retain it as an experiment, not Stable routing.

## Workstream C — Quantum simulation quality and backend planner (mandatory)

- Audit A-D contracts and add explicit backend capability declarations.
- Add planner decision traces: why backend A/B/C/D/dense/noisy was selected, what alternatives were considered, and why they were rejected.
- Make resource estimates visible before execution.
- Make backend failure typed; no silent fallback except when the user explicitly asks for an allowed fallback.
- Add exact small-circuit oracle parity across all supported backend pairs.
- Add workload-based benchmarks with independent external comparators.
- Ensure all experimental new algorithms are opt-in.

A planner should choose by task and capability, not blindly by the largest qubit count or a single entropy heuristic.

## Workstream D — Hardware-aware noise and real-QPU bridge (bounded)

Keep classical noise modeling and physical provider execution distinct.

### D1. Noise model and profile hardening

Audit:

- parameter validation for finite values and correct physical ranges;
- Kraus completeness `Σ K_i† K_i = I`;
- trace preservation and positivity within numerical tolerance;
- qubit/gate targeting and ordered two-qubit pairs;
- profile schema version and provenance;
- age/staleness and unknown fields;
- basis-gate mapping and whether errors attach before/after gate lowering;
- whether uncalibrated gates are refused, modeled as noiseless by explicit policy, or unknown.

Never invent T1/T2, gate error, readout error, calibration timestamp or provider URI. The two built-in baseline profiles are synthetic and must stay labelled synthetic.

### D2. Basis transpilation / topology map

This is a useful V3 capability if it can be built correctly:

- canonical gate-to-native-basis lowering;
- coupling graph validation;
- directed versus undirected two-qubit gate semantics;
- routing SWAP insertions;
- complete logical-to-physical qubit map;
- classical-bit map preservation;
- gate duration/error propagation where provider metadata supports it;
- explicit refusal when no valid mapping exists.

Prove/validate each rewrite against independent matrix semantics for small circuits. Record original and transpiled circuit hashes.

### D3. Real provider adapter boundary

Do not invent a backend endpoint. Inspect current official providers, SDKs and auth contracts at runtime. Prefer an isolated optional plugin to avoid making offline CI require credentials.

Minimum provider interface:

```text
list_backends()
get_backend_metadata(name)
validate_and_transpile(circuit, backend)
submit(circuit, shots, explicit_authorization)
get_job_status(job_id)
cancel(job_id)  # only where provider supports it
fetch_result(job_id)
fetch_calibration_snapshot(backend)
```

Design typed statuses for queued/running/done/cancelled/failed/expired/unknown and preserve provider-native job IDs and raw result references.

Real submission requires all of:

- explicit user/operator authorization for this run;
- valid provider credentials from an approved secret mechanism;
- named backend and cost/qubit/shot ceilings;
- displayed circuit and shot count;
- no hidden retry that duplicates billable jobs;
- idempotency support where provider semantics permit it;
- job timeout/cancellation behavior;
- raw result and calibration provenance.

If no provider credentials and approval exist, implement and test the adapter boundary offline and report `REAL_HARDWARE: BLOCKED/NOT RUN`. Do not create a fake “real QPU” run.

### D4. Fake provider tests

Test success, rejection, malformed payload, job timeout, partial result, duplicate submission, cancellation, stale calibration, backend unavailable, unsupported gate, missing metadata and provider outage. The fake provider must remain `NOISY_CLASSICAL` or `FAKE_PROVIDER`, never `REAL_HARDWARE`.

## Workstream E — Vulkan GPU execution (prove the path before claiming acceleration)

The current repository has compute primitives and dispatch tests. V3 may extend them, but it must not advertise an end-to-end GPU simulator until the complete path is integrated and benchmarked.

### E1. Device and capability inventory

- enumerate device name/vendor/device/driver/API;
- detect compute queues and required features/extensions;
- expose physical versus software ICD;
- identify actual memory heap sizes and supported host/device memory;
- make selection observable and overrideable;
- distinguish no device from unsupported feature from software-only device.

### E2. Primitive correctness

For each shader pipeline:

- source and SPIR-V hash/version;
- compile and validate;
- bounds-check all dispatch dimensions and buffer sizes;
- validate alignment, descriptor limits, integer overflow and synchronization;
- run known-value host-to-device-to-host test;
- compare output against independent CPU reference;
- test boundary sizes and incomplete workgroups;
- test device-loss/dispatch failure handling;
- run validation layers in a dedicated CI lane where available.

### E3. End-to-end simulator integration criteria

Only implement an end-to-end GPU simulation slice if a clearly bounded workload supports it. It must:

- receive a canonical circuit/operation plan;
- allocate and evolve a valid state/tensor on device memory;
- support a declared gate/measurement subset;
- perform all required tensor operations on GPU rather than dispatching a decorative primitive and doing the actual simulation on CPU;
- return outputs in the same result contract;
- compare to a CPU reference on all supported small workloads;
- report transfers, sync, compilation/JIT, and kernel execution separately;
- fail closed for unsupported circuits;
- avoid vendor-specific assumptions unless selected device reports them.

### E4. Performance requirement

Run same-device CPU versus GPU end-to-end comparisons where possible, plus at least one named physical AMD or other device if available. Record software ICD results separately. No claim based on microbenchmark-only acceleration.

If the GPU path is slower for a workload, report it; use dispatch only when the measured/capability decision justifies it. A good V3 outcome may be a more truthful status display and a reliable primitive library, not a forced GPU feature.

## Workstream F — UI/UX, CLI and live observability (mandatory)

### F1. Current state

The repository has a CLI, a Rich-based Python terminal dashboard and a native C++ terminal UI. The inspected UI code contains formula-driven telemetry and static/default values. The V3 UX must eliminate the appearance of fake runtime readings.

### F2. Product UX goals

- make the first run understandable in under a minute;
- make the active backend/mode/result status obvious;
- show what the simulator can and cannot do for the submitted circuit;
- explain why a path was selected;
- present resource estimate before expensive work;
- show progress only if progress is actually measured;
- surface unsupported operations with actionable wording;
- make exactness/approximation/noise/hardware provenance understandable;
- support keyboard navigation and clean non-interactive CLI output;
- render well on Windows Terminal, PowerShell, CMD, common Linux terminals and redirected CI logs;
- keep compact mode and plain text/JSON output;
- respect terminal width, Unicode fallback, high contrast and screen-reader/plain-text usability.

### F3. Replace synthetic telemetry

Create a `MetricsProvider` abstraction. Candidate sources:

- process RSS / peak RSS through OS-supported APIs;
- memory budget usage counted by the backend's own allocator;
- Vulkan device name and memory heap properties from Vulkan, clearly labelled as capacity/heap info, not current utilization unless measured;
- actual timing from `steady_clock`/`perf_counter` for completed stages;
- actual MPS bond dimensions from the active `ExactMPSTensorChain`;
- actual circuit width/depth/gate/T-count from `CircuitAnalyzer`;
- actual path selection and unresolved reason from the router;
- actual provider job status from the provider adapter.

Unavailable metrics must render as `N/A` or `UNKNOWN`. A `--demo` mode may use deterministic generated values but the UI must persistently show `DEMO / SIMULATED VALUES`. Do not show “physical entropy”, “VRAM active” or “GPU load” without a genuine measurement.

### F4. Recommended dashboard layout

The TUI should have meaningful panels:

1. **Run overview:** version, source SHA, run ID, execution mode, current status.
2. **Circuit:** qubits, classical bits, depth, gate count, two-qubit gate count, T-count, unsupported operations.
3. **Planner:** selected path, capability fit, resource estimate, reason for selection/rejection of alternatives.
4. **Execution metrics:** elapsed time, measured RSS, allocator memory, device/ICD identity, actual kernel count/stages.
5. **Numerics:** exactness semantics, arithmetic domain, truncation policy, discarded spectral diagnostics, result-kind-specific error bound.
6. **Hardware bridge:** synthetic/real profile provenance, provider/backend, calibration age, topology and job status; hidden if irrelevant.
7. **Evidence:** circuit hash, seed, test/reference validation flag and warnings.

### F5. CLI improvements

Audit and refine the existing CLI commands rather than creating a second command hierarchy. Candidate UX:

```bash
cq-hecs doctor --format text|json
cq-hecs analyze circuit.qasm --explain
cq-hecs run circuit.qasm --explain --format json
cq-hecs profile list
cq-hecs backend list
cq-hecs benchmark run --suite smoke|full --output results/
cq-hecs monitor [--demo]
cq-hecs research status
```

Only expose commands that are implemented. Every subcommand needs help text, stable exit codes, JSON schema tests, invalid argument tests and a clean-venv smoke test.

### F6. UI visual QA

For every UI change:

- capture screenshots of representative terminal widths (80, 100, 120, 160 columns) using a real terminal emulator where possible;
- test Windows Terminal and at least one Linux terminal/CI pseudo-terminal;
- test narrow width, no color, no Unicode, redirected output and long backend/device names;
- check panel overflow, table truncation, alignment, color contrast and stale state;
- verify every displayed number originates from a named metrics source;
- compare screenshot and data source in a review artefact;
- ensure no placeholder/inert keybinding is displayed.

Do not claim visual QA passed if only a code review was performed. If screenshot capture is unavailable, mark that gate `NOT RUN` and provide a reproducible command for the operator.

## Workstream G — Documentation and developer experience (mandatory)

Refresh:

- `README.md`;
- `ARCHITECTURE.md` and `docs/ARCHITECTURE.md`;
- `docs/API_REFERENCE.md`;
- `docs/USAGE_GUIDE.md`;
- `docs/QASM_CONTRACT.md`;
- `docs/BENCHMARKS.md`;
- `docs/V2_IMPLEMENTATION_MATRIX.md` (rename/replace with a version-neutral or V3 matrix; preserve V2 history);
- `CHANGELOG.md`;
- `RELEASE_NOTES.md`;
- `CITATION.cff`;
- `llms.txt`, `llms-full.txt`;
- example programs and screenshots;
- GitHub templates and project metadata.

The README should include:

1. Clear product definition: classical quantum circuit emulator and optional bridge boundary, not a quantum computer.
2. Current stable status and tested platforms.
3. A capability matrix by backend, circuit family, output type, precision and limits.
4. Realistic quick start for pure-Python package and native C++ build.
5. CLI examples for analyze, run, expectation, noise profiles and optional monitor.
6. Clear explanation of `EXACT`, `CERTIFIED`, `UNRESOLVED`, `FAILED` and execution modes.
7. A “What CQ-HECS does not claim” section.
8. Current benchmark methodology, source SHA and result links.
9. Architecture diagram with correct CPU/GPU/QPU boundaries.
10. Roadmap and research-only experiments with status labels.
11. Citation/reproducibility instructions.
12. License and contribution guide.

Avoid giant badge walls, claims without links and outdated performance tables. Badges must point to real workflows and release metadata.

---

# 9. Test architecture — gates are non-negotiable

The current CI already provides a strong base: static/package checks, Linux C++20/Vulkan and Python suite, Windows native suite, Python 3.12–3.14 compatibility, and Linux ASan/UBSan native tests. Preserve and improve these lanes. Do not weaken thresholds to get green.

## 9.1 L0 — Provenance and repository safety

- exact branch/HEAD/tag/release recorded;
- dirty tree and operator changes preserved;
- no uncommitted or untracked source unexpectedly omitted;
- all artifacts tied to true SHA;
- release metadata reconciled.

## 9.2 L1 — Static and package checks

Run the current repository checks, adapting names only if the live project changed:

```bash
python -m compileall -q cqhecs tests scripts python_bridge
python scripts/check_version.py
python scripts/verify_no_silent_truncation.py
python scripts/verify_vulkan_shaders.py
python -m flake8 cqhecs tests scripts python_bridge --count --select=E9,F --show-source --statistics
python -m build
python -m twine check dist/*
```

Also validate:

- `pyproject.toml` metadata and supported Python range;
- exact dependency pins in CI constraints;
- wheel/sdist contain expected packages and no test-only modules;
- license files and package entry points;
- clean-venv install without repo-root imports;
- `cq-hecs --help`, `version`, `doctor`, profile list and a deterministic Bell/GHZ JSON smoke run;
- all JSON outputs parse and conform to a versioned schema;
- `pip check` in a clean environment;
- wheel import and command execution from outside the repository.

## 9.3 L2 — C++20 native build and sanitizers

Linux and Windows release builds:

```bash
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```

Also run sanitizer builds where supported:

```bash
cmake -B build-asan -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCQ_BUILD_TESTS=ON -DCQ_ENABLE_SANITIZERS=ON
cmake --build build-asan --parallel
ctest --test-dir build-asan --output-on-failure
```

Required validation:

- ASan and UBSan reach the relevant production and test translation units;
- test binaries contain real active assertions/checks in all build types;
- parser, solver, exact arithmetic, tensor update and memory-budget tests run under sanitizers;
- `ctest` logs and JUnit XML are retained;
- no test is silently skipped due missing native extension in mandatory Linux/Windows lanes.

## 9.4 L3 — Full Python suite and coverage

Keep `CQ_HECS_REQUIRE_NATIVE=1` in mandatory native lanes. Confirm that native-only tests cannot silently skip. Retain the existing branch coverage threshold (currently observed at 70% in CI) or raise it only when justified; never lower it for convenience.

Target increased coverage in:

- result serialization and status mapping;
- timeout/error/refusal paths;
- parser branches and malformed DIMACS/QASM;
- hardware profile validation;
- noisy density matrix;
- circuit analysis and route decisions;
- API compatibility;
- CLI JSON and exit codes.

Line/branch coverage is not proof of correctness; use semantic oracles too.

## 9.5 L4 — Independent mathematical and differential tests

### Quantum

- compare small statevectors to dense reference, Qiskit Aer and/or direct matrix products;
- compare stabilizer circuits to Stim and Aer stabilizer;
- compare MPS to Aer untruncated MPS on overlapping gates;
- compare expectation values to direct dense calculations;
- compare noisy density matrices to Aer density matrix/noise models;
- test every gate with asymmetric/non-palindromic circuits to reveal order/endian errors;
- include qubit `0`, highest valid qubit, non-adjacent pair, reversed operand order and partial measurement.

### Exact algebra

- Python arbitrary-precision reference;
- random ring identities within a checked representable range;
- overflow boundaries;
- exact gate matrix identities and unitarity;
- exact Clifford+T circuits versus direct exact products;
- float export checked separately from exact equality.

### SAT / #SAT

- exhaustive brute-force oracle for small `n`;
- random CNFs and structured formulas;
- solver witness validation;
- known SAT/UNSAT instances;
- collision-injected hash functions;
- table capacity and eviction stress;
- timeout under tiny budget returns UNKNOWN, never UNSAT;
- DIMACS parser cross-front-end differential tests;
- #SAT count against exhaustive truth-table enumeration.

### Tensor / FAQ prototype

- random small factor graphs checked against brute-force sum-product;
- random elimination orders preserve exact answers;
- index rename/permutation invariants;
- free/bound variable semantics;
- Boolean and integer domains;
- small Clifford amplitudes checked against direct statevector;
- exact coefficient and phase order tests.

## 9.6 L5 — Property, fuzz, mutation and adversarial testing

- Hypothesis tests for parsers, circuits, result contracts, gate lowering and ring normalization;
- bounded libFuzzer/AFL-style fuzzing where supported;
- deterministic seed and corpus recording;
- fuzz timeout and memory caps;
- source-level mutation harness (preserve current mutations and add new ones for each P0/P1 fix);
- parser truncation/overflow mutants;
- gate operand swap/phase sign mutants;
- false-UNSAT/hash-collision mutants;
- remove timeout detection mutant;
- zero/NaN/Inf error-bound mutants;
- change bit order and measurement map mutants;
- remove Kraus validation mutant;
- alter Vulkan buffer bounds mutant.

Every important mutant should be killed by a specific test. Mutation count is not a correctness proof; explain survivors and equivalent mutants explicitly.

## 9.7 L6 — Numerical and statistical validation

- probabilities finite and normalized within justified precision;
- density matrices Hermitian and trace-preserving within tolerance;
- positive semidefinite checks where meaningful (with scale-aware tolerance);
- error bounds checked against adversarial reference examples;
- sampling confidence statements use correct support size and failure probability;
- distinguish `TV`, norm, expectation, amplitude, per-outcome and state error metrics;
- seeds reproducible and passed through every stochastic layer;
- no test relies on a statistical pass with no prespecified tolerance or sample-size derivation.

## 9.8 L7 — GPU/Vulkan gates

Separate these jobs:

1. shader source compile;
2. SPIR-V validation;
3. software ICD primitive dispatch/readback;
4. physical GPU primitive dispatch;
5. end-to-end simulator integration;
6. end-to-end CPU/GPU parity and performance benchmark.

A software ICD pass is valuable CI evidence but cannot be presented as physical GPU performance. If a physical device is unavailable in cloud CI, mark the physical GPU lane not run and retain local evidence only if it was actually captured.

## 9.9 L8 — provider bridge tests

- FakeProvider contract tests run offline in all CI;
- no provider credential needed in standard CI;
- real hardware test lane is manually approved, optional and cost-capped;
- no credential printing in logs;
- no retries that cause duplicate billable jobs;
- raw job provenance checked;
- real test output is not copied from fake-provider fixtures.

## 9.10 L9 — security/supply chain

- pin GitHub Actions by full immutable SHA;
- least-privilege workflow permissions;
- no secrets in source/URLs/logs/artifacts;
- validate dependency lock/constraints;
- audit pip packages and native build inputs;
- validate SPDX SBOM and checksum generation;
- check archive paths against traversal;
- verify artifact hashes after download;
- use TLS verification; never use `--insecure`;
- do not scan the filesystem for credentials;
- run secret scanners using approved GitHub facilities where available.

## 9.11 L10 — Documentation and visual QA

- README render preview and link check;
- CLI help snapshots;
- TUI screenshot matrix;
- terminal width/non-TTY/no-color tests;
- every data value in UI tied to a telemetry source;
- current version and feature labels verified;
- all claims cross-linked to code/tests/research evidence;
- old benchmarks clearly marked historical.

## 9.12 L11 — Exact-SHA cloud verification

Run CI on the exact proposed merge/release SHA. A previous branch SHA or a docs-only ancestor passing is not enough if later source/docs changes affect the artifact. Capture all workflow IDs/URLs and job conclusions in `research/v3/TEST_MATRIX.md`.

---

# 10. Benchmark protocol and claim discipline

## 10.1 Preregister before running

For every performance experiment record:

- hypothesis and expected benefit;
- workload family and generation version;
- input hashes and seeds;
- included/excluded workloads and reasons;
- baseline revision and new revision;
- hardware/software environment;
- comparable result semantics;
- measurement start/end points;
- warmup and repetition count;
- aggregation statistic and spread;
- correctness/error gate;
- memory/time ceiling;
- stopping condition.

Do not change benchmark inclusion after viewing results to manufacture a win.

## 10.2 Comparison policy

- compare equal circuit and output task;
- compare equal noise model and sampling shots;
- compare equal accuracy/error requirements;
- separate preprocessing and runtime;
- include compilation and device transfer when claiming user-visible GPU improvement;
- use identical hardware and thermal/driver context where possible;
- avoid benchmarking against a baseline version that has different correctness semantics;
- include raw data and scripts;
- report failures, timeouts and unresolved circuits, not just successes.

## 10.3 Performance language

Allowed:

- “2.3× faster on the listed benchmark suite on device X, with the following result semantics.”
- “Lower peak RSS on workload family Y under settings Z.”
- “The experimental FAQ planner reduced estimated intermediate tensor entries on the tested family; correctness matched brute force for these sizes.”

Not allowed:

- “SOTA quantum simulator” without broad, fair and current comparator evidence;
- “10× GPU acceleration” from shader dispatch alone;
- “supports arbitrary 300-qubit circuits” based on GHZ/MPS examples;
- “P = NP progress” based on solver speed on a finite corpus;
- “exact” when the implementation uses undocumented rounding/truncation;
- “real quantum result” from a fake provider or simulator.

---

# 11. Bounded self-healing and long-horizon agent loop

The agent should act autonomously on safe, reversible engineering work. Self-healing is not random code mutation or repeated blind retries.

## 11.1 Global loop

```text
DISCOVER
  -> BASELINE
  -> AUDIT
  -> HYPOTHESIS
  -> DESIGN
  -> IMPLEMENT ONE SLICE
  -> BUILD
  -> TEST
  -> DIFFERENTIAL / MUTATION / FUZZ
  -> REVIEW CLAIMS
  -> RECORD EVIDENCE
  -> NEXT SLICE
  -> FINAL LOCAL GATE
  -> CLOUD GATE
  -> DOCS/RELEASE GATE
  -> REPORT
```

At each stage, checkpoint the current branch, exact diff and latest green commands. Use small commits or well-defined checkpoints so a failed experiment can be reverted without losing unrelated work.

## 11.2 Repair loop A — correctness defect

1. Reproduce on the baseline SHA or an isolated fixture.
2. Capture expected and actual outputs.
3. Build the smallest counterexample.
4. Identify whether the defect is specification, code, test oracle or documentation.
5. Derive the invariant independently.
6. Implement the smallest correction.
7. Add a regression test that fails on the old code.
8. Run focused tests.
9. Run adjacent module tests.
10. Run the full suite.
11. Run mutation tests against the defect.
12. Record root cause and evidence.

Maximum: three targeted repair attempts per root cause. After three unsuccessful attempts, stop changing that surface, document the blocker and continue with independent work.

## 11.3 Repair loop B — build / CI failure

1. Capture exact command, toolchain and log.
2. Classify source failure, environment issue, dependency issue, test failure or infrastructure flake.
3. Reproduce locally where feasible.
4. Do not delete/skip the test or suppress compiler warnings to get green.
5. Fix the root cause or pin the correct dependency/toolchain.
6. rerun failed job, then full local gates.
7. rerun cloud exact-SHA CI.

If external CI infrastructure is genuinely flaky, retain all attempts and mark the infrastructure diagnosis. A flaky pass is not proof that the source is always correct.

## 11.4 Repair loop C — resource/reliability failure

1. Identify preflight versus actual allocation behavior.
2. Capture peak RSS/device heap and intermediate sizes.
3. Reproduce with a bounded input.
4. Ensure no partial state or stale temporary pages remain after failure.
5. Add a deterministic budget test.
6. Confirm a resource refusal is explicit and machine-readable.

## 11.5 Research loop D — hypothesis testing

For each hypothesis:

1. State the exact claim.
2. List mathematical assumptions.
3. Derive the needed intermediate lemmas.
4. Select a minimal experiment.
5. Specify independent oracle and expected acceptance/rejection criterion.
6. Implement a reference version first.
7. Run experiment with recorded seeds/hashes.
8. Analyze positive and negative results.
9. Formalize critical identities/lemmas where practical.
10. Decide `SUPPORTED`, `REJECTED`, `INCONCLUSIVE`, `DEFERRED` or `BLOCKED`.

Do not rewrite the hypothesis after seeing results without creating a new version and preserving the original outcome.

## 11.6 Repair loop E — docs/UI claim mismatch

1. Extract the claim from README/UI/release note.
2. Find the source implementation.
3. Find test or benchmark evidence.
4. If evidence is missing, downgrade the claim or add a test.
5. update every duplicated claim source.
6. render/preview and check links.
7. re-run version/docs checks.

## 11.7 Stop and escalation rules

Stop and request operator authorization only for:

- a real billable QPU submission;
- a hardware test with external cost or provider terms;
- missing owner-only credentials/permissions;
- merge to protected branch if policy requires human review;
- deletion/destructive action or rewriting release history;
- security-sensitive change requiring owner decision.

Do not ask for information already available from the repo. Do not stop the entire V3 mission because real hardware is not available; finish offline adapter tests and mark real QPU as blocked/not run.

Never send a message that says the work will happen later. Perform all permitted work in the current execution.

---

# 12. Milestone plan: v2.5.1 -> v3.0.0

Milestones are ordered gates, not calendar estimates. A later milestone may start on an independent branch only if it does not obscure a correctness blocker.

## M0 — Snapshot and baseline audit

**Deliverables:** `BASELINE.md`, `SOURCE_INVENTORY.md`, initial `DEFECT_REGISTER.md`, exact test matrix and claim map.  
**Gate:** the team can answer exactly what exists, what works, what is experimental and what is only a placeholder.

## M1 — Correctness and trust hardening

**Priority:** P0/P1.  
Fix or explicitly disable confirmed:

- Python SAT timeout status;
- collision-prone SAT pruning if proof-critical;
- Python/native DIMACS mismatch;
- exact-ring overflow/shift/exponent hazards;
- Release-disabled assertions;
- fabricated UI telemetry;
- result-metadata semantic mismatches;
- any confirmed QASM/Qiskit bit-order/operand/measurement regression.

**Gate:** focused regression, independent differential and full local test suite pass.

## M2 — Contracts and planner consistency

Implement or improve:

- canonical circuit semantics (incremental, compatibility-preserving);
- central capability descriptions;
- result-kind/execution-mode provenance;
- resource preflight and refusal codes;
- planner explain mode;
- stable JSON schema and CLI exits.

**Gate:** all frontends behave identically for the supported subset and explicitly refuse unsupported semantics.

## M3 — Mathematical research engine (bounded, experimental)

Implement Boolean factor-graph reference, exact #SAT brute-force comparator for small cases, variable elimination/InsideOut, structural estimators and a transparent FAQ-style task model. Then explore a weighted Clifford+T tensor prototype and one SWAP/singlet reproduction experiment.

**Gate:** exact reference results match independent brute force/dense quantum outputs for small instances; research-only labels and limitations are correct. No requirement to reproduce the full OpenAI/Anthropic asymptotic result unless the proof and implementation scope are realistically achievable.

## M4 — Quantum path and benchmark improvement

Harden A-D, run current external comparators, improve route explanations and implement at most one evidence-backed planner/backend improvement. Keep experimental backends out of default stable routing until proven.

**Gate:** preregistered workload family shows a measured benefit or a previously unsupported task becomes correctly supported; no regressions elsewhere.

## M5 — Noise model and real-provider bridge

Improve provenance and optional device-aware lowering. Implement one real provider adapter only if current official SDK/API access and test infrastructure are available. The fake provider remains offline and explicitly synthetic.

**Gate:** all fake-provider tests pass; no invisible fallback; real QPU mode remains blocked/not run unless an authorized real job is actually completed and recorded.

## M6 — Vulkan/device layer

Improve device selection, telemetry and dispatch safety. Implement an end-to-end GPU simulator slice only if a specific workload and supported shader pipeline can be completed and differentially verified.

**Gate:** clearly identified device class, host/device parity, correct end-to-end pipeline, and fair benchmark. Otherwise retain primitive-only status and document it correctly.

## M7 — UI/UX and developer workflow

Replace synthetic dashboards with real metrics, redesign the TUI around actual run data, improve CLI `--explain`, resource preflight and JSON, and add screenshots/visual regression artefacts.

**Gate:** all displayed values trace to metrics sources or are clearly demo-marked; keyboard and non-TTY flows work.

## M8 — Docs, packaging and release preparation

Update README, API docs, architecture, research reports, benchmarks, release notes and citation metadata. Rebuild wheel/sdist and install cleanly. Check every published claim against the code.

**Gate:** docs, version and artifacts align on the same candidate SHA.

## M9 — Cloud, release and final audit

Run Linux/Windows CI, sanitizers, Python compatibility, shader checks, mutation, fuzz and package tests. Verify exact-SHA CI. Merge/release through policy, download all assets, independently hash them and record the final release audit.

**Gate:** no mandatory failure, no unresolved P0/P1, no false claim, all artifact digests verified.

---

# 13. Proposed V3 Stable feature set and deferral rules

The agent must decide final V3 contents from evidence; this table is a target, not a guarantee.

| Area | V3 Stable target | Experimental / defer if not proven |
|---|---|---|
| Core contracts | robust result schema, explicit status, capability registry | breaking result model rewrite |
| Quantum paths | A-D correctness, explainable routing, better benchmarks | unsupported universal path |
| Exact arithmetic | checked operations and bounded guarantees | arbitrary precision backend if not completed/benchmarked |
| Tensor research | Boolean factor graphs, exact reference, FAQ evaluation model if correct | claimed OpenAI/Anthropic port; universal weighted compression |
| Circuit simulation | measured workload-specific improvements | SOTA superiority language |
| Noise | corrected density matrix, validated Kraus channels, provenance | unvalidated complex noise model |
| QPU bridge | clean provider boundary, robust fake tests, optional adapter | real hardware claim without actual authorized job |
| Vulkan | honest device detection and primitive dispatch, possibly one end-to-end slice | generic cross-vendor full GPU acceleration |
| UI | measured TUI/CLI, demo explicitly marked | fake active metrics or speculative GUI overhaul |
| SAT | sound status/UNSAT handling, collision-safe search, #SAT reference | P = NP or general NP polynomial claims |
| Documentation | current, cited, reproducible | badges/claims without proof |

A major version requires a real user-visible capability, interface/semantic milestone, or architecture upgrade with migration notes. If V3 only fixes defects and delivers no meaningful stable capability, choose a justified minor/patch release instead of manufacturing a `3.0.0` release.

---

# 14. GitHub, CI, release and supply-chain workflow

## 14.1 Branch and PR policy

- Work on a focused branch.
- Commit in coherent checkpoints (baseline audit, correctness fixes, research prototype, UI, docs, release).
- Keep commits reviewable; avoid one massive unreviewable commit.
- Do not force-push or rewrite shared history.
- Do not push directly to protected `main` if the repository policy requires PR.
- Create a PR with problem statement, design, test evidence, benchmark protocol and limitations.
- Wait for exact-SHA required CI, then merge only if policy permits.

## 14.2 CI requirements

Maintain or improve:

- static checks/package smoke;
- Linux C++20/Vulkan/Python full suite;
- Windows C++20/Vulkan/Python full suite;
- Python supported-version matrix;
- ASan/UBSan;
- shader compilation/validation;
- software Vulkan dispatch test;
- nightly stress/fuzz/mutation/performance smoke;
- optional hardware provider tests (offline fake by default).

Check action references are immutable full SHAs, permissions are job-scoped and minimal, concurrency does not cancel release workflows, and artifacts upload on failures when useful.

## 14.3 Release integrity

Before tag:

- canonical version in `scripts/version.py`;
- `cqhecs.__version__`, `pyproject.toml`, CMake/package metadata and docs consistent;
- changelog/release notes correct and dated;
- release source SHA exact;
- required CI green on exact SHA;
- wheel and sdist clean-venv tested;
- CLI smoke JSON valid;
- SPDX SBOM generated and schema validated;
- SHA-256 checksums generated after final release notes/assets;
- artifact file list matches release workflow expectations;
- each asset downloaded and digest independently checked after publication.

Never edit an already published release asset to make old documentation look current. Publish an erratum or a new release instead.

---

# 15. Required documentation formats and research reporting

## 15.1 `research/v3/HYPOTHESES.md`

Each hypothesis must have:

```text
ID:
Title:
Status: PROPOSED | SUPPORTED | REJECTED | INCONCLUSIVE | DEFERRED | BLOCKED
Claim:
Formal statement:
Assumptions:
Scope:
Related theorem/paper:
Transfer classification:
Required lemmas:
Prototype:
Independent oracle:
Benchmark family:
Pre-registered acceptance criteria:
Observed result:
Decision:
Evidence files:
Exact source SHA:
Reviewer notes:
```

## 15.2 `research/v3/RESEARCH_TRANSFER_AUDIT.md`

For each OpenAI/Anthropic/FAQ idea:

- theorem name and source revision;
- paper statement and Lean statement side by side;
- assumptions and domains;
- proof checker status;
- exact code-to-theorem mapping;
- candidate CQ-HECS module;
- gap analysis;
- prototype design;
- independent tests;
- reason for adoption/rejection/deferral.

## 15.3 `research/v3/TEST_MATRIX.md`

Each row includes exact command, source SHA, OS/toolchain, result, duration, log, artefact URL and status. Do not put `PASS` if the command did not run. Use explicit `SKIP`, `NOT RUN`, `BLOCKED` and `INCONCLUSIVE`.

## 15.4 `research/v3/LIMITATIONS.md`

List the limitations users could otherwise misunderstand:

- gate/circuit subset per path;
- max qubits and why it exists;
- dense memory scaling;
- MPS entanglement/bond growth;
- finite precision and truncation;
- exact ring coefficient limits;
- noisy model assumptions and size ceiling;
- Vulkan primitive vs full simulator status;
- QPU provider status;
- unsupported dynamic-circuit features;
- SAT solver timeout/UNSAT proof model;
- research prototypes not shipped/stable.

---

# 16. Stable acceptance gates — hard go/no-go

Every gate is recorded as `PASS`, `FAIL`, `NOT RUN`, `SKIP (reason)`, `BLOCKED (reason)` or `INCONCLUSIVE`.

## Gate A — Repository/release truth

- live baseline, branch, release, tag and SHA reconciled;
- no unpreserved user changes;
- canonical version verified;
- all current claims sourced.

## Gate B — Scientific correctness

- ETH/P-vs-NP boundaries accurate;
- no claim that P = NP was solved;
- all imported research claims map to primary sources;
- formal verification scope and implementation scope separated;
- exact arithmetic overflow guarded;
- no fabricated SAT/UNSAT/#SAT or quantum outputs.

## Gate C — Quantum correctness

- A-D and density-matrix path differentially validated within declared scope;
- measurement/classical map and endian semantics consistent;
- approximation/error metadata scoped correctly;
- unsupported operations refuse before partial output;
- all new research tensor algorithms exact on testable tiny cases.

## Gate D — SAT correctness

- timeout never treated as UNSAT;
- hash collisions cannot prune proof-critical branches;
- SAT witnesses independently verified;
- UNSAT proof path sound and documented;
- DIMACS parsing follows the declared grammar;
- #SAT brute-force reference agrees for small instances.

## Gate E — Hardware and GPU truth

- fake and physical provider results distinct;
- no fallback masquerades as real hardware;
- synthetic profiles labelled synthetic;
- Vulkan device and ICD identity visible;
- end-to-end GPU claim only if actual integrated path is measured;
- real QPU job recorded only if explicitly authorized and completed.

## Gate F — UX and observability

- no fake live telemetry;
- all metrics sourced or demo-marked;
- CLI/TUI cross-platform and readable;
- screenshots/visual QA evidence included where supported;
- all controls/commands work as advertised.

## Gate G — Software quality

- static/package checks pass;
- Linux/Windows native tests pass;
- Python full suite with native required passes;
- supported Python compatibility passes;
- sanitizers pass;
- mutation and fuzz gates pass;
- no tests silently skipped in required lanes;
- no weakened thresholds or deleted tests.

## Gate H — Performance evidence

- benchmark protocol preregistered;
- same-task comparisons;
- raw results and scripts retained;
- no regressions beyond agreed tolerance without explanation;
- no ungrounded SOTA claims.

## Gate I — Security/supply chain

- least-privilege permissions;
- immutable action pins;
- no credentials in code/logs;
- SBOM valid;
- checksums independently verified;
- archive/package contents sane.

## Gate J — Docs/release

- README, API, architecture, changelog, release notes, citations, llms files agree;
- clean package install/CLI smoke pass;
- exact source SHA CI green;
- published tag equals canonical version;
- downloaded release assets match recorded hashes.

**Hard stop:** Any unresolved P0 correctness defect, false UNSAT possibility, false hardware provenance, fake live telemetry, unguarded exact arithmetic overflow, hidden approximation, broken release provenance or failed mandatory CI blocks Stable.

---

# 17. Final report contract

When complete, return a concise executive summary followed by detailed evidence. Include:

1. final version, tag and exact source SHA;
2. PR/merge URL and exact-SHA CI URLs;
3. actual features implemented and file paths;
4. confirmed defects and fixes with regression tests;
5. research hypotheses and status, including rejected hypotheses;
6. formalized theorem/proof status and exact scope;
7. quantum simulation capabilities by backend and tested circuit family;
8. Vulkan device/dispatch/end-to-end status;
9. real QPU provider status and whether any authorized real job ran;
10. UI screenshots/visual QA evidence;
11. benchmarks with exact hardware, workload, baseline and result;
12. test counts, coverage, CTest, sanitizer, fuzz and mutation results;
13. package/release asset names and SHA-256 verification;
14. limitations and known risks;
15. items `NOT RUN`, `SKIP`, `BLOCKED` or `INCONCLUSIVE`;
16. explicit statement that P vs NP remains open unless a genuinely valid proof is delivered and independently checked (expected V3 status: open).

Do not say “perfect”, “bug-free”, “SOTA” or “10/10” as an absolute. Say what was tested and what the evidence supports.

---

# 18. First actions for the agent

Start immediately with the following sequence:

1. Fetch live repository metadata, latest release, branch, main SHA, open PRs and recent workflow runs.
2. Inspect the local checkout status and preserve user work.
3. Read current `GEMINI.md`, README, architecture, version, all active CI workflows and V2.5.1 research reports.
4. Build a complete source inventory from the live tree.
5. Reproduce the Python DPLL timeout result contract issue and test hash collision behavior in both SAT implementations.
6. Reproduce DIMACS parser differences with a grammar-compliant multiline CNF fixture.
7. Audit both exact-ring implementations for overflow and check CMake Release flags for `NDEBUG`.
8. Verify whether the exact-ring test assertions execute in Release.
9. Trace every live TUI metric to its data source; replace fabricated values or label demo mode explicitly.
10. Reconcile Vulkan primitive dispatch and AMD iGPU evidence with the actual test logs and release documentation.
11. Read the full OpenAI ETH manuscript, `lean/docs/378.md`, Anthropic ETH README/paper/MainResults/PaperIndex and the 2026 FAQ quantum simulation paper.
12. Create the V3 research dossier and defect register.
13. Implement the highest-severity confirmed correctness fixes before any new research backend.
14. Proceed milestone by milestone, preserving exact evidence and refusing unsupported claims.

**End condition:** The agent must stop only after V3 passes the mandatory gates and the final report is evidence-complete, or after it has exhausted the bounded repair cycles and documented a precise external blocker. A partial but truthful result is better than a fabricated Stable release.

---

# 19. Primary research and technical references

The following are seed sources, not a closed bibliography. At runtime, fetch current versions, record immutable revisions and add or remove sources based on relevance.

## OpenAI / ETH / formal mathematics

- OpenAI, *The Exponential Time Hypothesis is False* (25 October 2026):  
  https://github.com/openai/math/tree/main/preprints/The-Exponential-Time-Hypothesis-is-False-October-25-2026
- OpenAI Lean formalization scope note:  
  https://github.com/openai/math/blob/main/lean/docs/378.md
- OpenAI Math repository:  
  https://github.com/openai/math

## Anthropic / ETH / formal mathematics

- Anthropic, *A 2^{o(n)} Time Algorithm for 3-SAT* artefact:  
  https://github.com/anthropics/formal-math/tree/main/eth
- Anthropic ETH README and formalization caveats:  
  https://github.com/anthropics/formal-math/blob/main/eth/README.md
- Anthropic formal-math repository:  
  https://github.com/anthropics/formal-math

## Quantum-circuit simulation / tensor networks

- Geerts et al., *Unifying and Extending Strong Simulation of Quantum Circuits* (30 September 2026):  
  https://arxiv.org/abs/2610.00547
- Qiskit Aer simulator API:  
  https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html
- Qiskit Aer simulator methods tutorial:  
  https://qiskit.github.io/qiskit-aer/tutorials/1_aersimulator.html
- Stim:  
  https://github.com/quantumlib/Stim
- MQT DDSIM:  
  https://github.com/cda-tum/ddsim
- NVIDIA cuQuantum:  
  https://developer.nvidia.com/cuquantum-sdk
- MQT Bench:  
  https://github.com/cda-tum/mqt-bench
- quimb:  
  https://github.com/jcmgray/quimb

## Formal verification and proof checking

- Lean 4: https://github.com/leanprover/lean4
- Mathlib: https://github.com/leanprover-community/mathlib4
- Anthropic comparator/nanoda details: inspect the live Anthropic ETH repository and pinned CI scripts.

## Existing CQ-HECS references

- Repository: https://github.com/timfromhcs/CQ-HECS
- Current baseline release (re-discover at runtime): https://github.com/timfromhcs/CQ-HECS/releases
- Current architecture: `ARCHITECTURE.md`, `docs/ARCHITECTURE.md`
- V2.5.1 correction findings and test matrix: `research/v2_5_1/`
- OpenAI Math transfer history: `research/v2_1/openai_math/`, `research/v2_4/evidence/`, `research/v2_5/`
- Existing simulator benchmark history: `benchmarks/`, `docs/BENCHMARKS.md`

---

**Mission motto:** Build the strongest CQ-HECS that the mathematics, code and evidence actually justify. Preserve the ambition; remove the exaggeration. Make every result reproducible, every limitation visible and every success independently checkable.
