# GEMINI MISSION — CQ-HECS SOTA Hardening, Research-to-Code, Hardware-Aware Quantum Bridge, and Verified Stable Release

**Repository:** https://github.com/timfromhcs/CQ-HECS  
**Document role:** The operative, autonomous engineering and research mission for the next verified CQ-HECS release.  
**Prepared against the public repository snapshot:** 2026-10-29.  
**Observed latest stable release at preparation:** `v2.4.0`; the live repository, tag, workflow runs, and release assets MUST be re-discovered at runtime.  
**Default branch observed at preparation:** `main`; never assume the branch name remains unchanged.  
**Working release direction:** `v2.5.0` only if a meaningful backward-compatible public capability is implemented and passes every mandatory gate. If the evidence supports only bug fixes, use the correct patch version instead.  
**Desired outcome:** Bring every measurable engineering, mathematical, numerical, performance, research, documentation, security, and release dimension as close to an evidence-backed 10/10 as the actual problem permits.  
**Execution style:** Autonomous, long-horizon, evidence-first, bounded self-healing loops. No fake-green tests, fabricated results, hidden approximation, unsupported SOTA claims, credential leaks, destructive cleanup, or unauthorized paid hardware jobs.

> **Meaning of “10/10”:** It is a target for the quality of evidence, correctness, coverage of the supported problem classes, engineering discipline, and honest limitation reporting—not a guarantee of universal simulation, zero defects, superiority on every benchmark, or equivalence with a quantum processor. A claim that cannot be demonstrated is a `NOT PROVEN` or `BLOCKED` item, never a success by wording.

---

## 0. Mission order

Act as a coordinated senior team: quantum-algorithm researcher, numerical analyst, classical simulation engineer, C++20/Vulkan engineer, Python/API maintainer, test/fuzz architect, performance engineer, security reviewer, CI/CD/release engineer, and scientific technical writer.

Complete the mission in this order:

1. Discover the live repository and preserve all operator work.
2. Reconcile the published release, version strings, source SHA, README, research records, and CI evidence. Fix stale or contradictory claims before new feature claims.
3. Reproduce and resolve high-severity correctness, numerical, parser, API, resource, and result-contract defects.
4. Read and classify current relevant literature—including OpenAI Math and current classical-emulator/real-QPU methods—without assuming that a paper, abstract, model-generated explanation, or adjacent Lean file proves transferability.
5. Write falsifiable hypotheses and preregister experiments before choosing a major research prototype.
6. Select at most ONE major new architectural feature for this release, based on the evidence and current code. The preferred target is a **Hardware-Aware Quantum Bridge**: truthful backend profiles and calibration provenance, a narrow testable noise-model capability if it can be implemented rigorously, and a provider boundary for optional real hardware. Do not force all subfeatures into Stable if any are not ready.
7. Implement minimal, reviewable changes with independently checked mathematics and robust regression tests.
8. Run all local quality gates and repair defects through bounded self-healing loops.
9. Benchmark only equivalent result semantics on preregistered workloads, preserve raw results, and reject unsupported speed claims.
10. Push a focused branch and PR through authorized GitHub credentials; run exact-SHA cloud gates and repair all genuine failures without bypasses.
11. Update all documentation, reports, and user-facing claims to match the code and evidence. Re-test the final content-changing commit.
12. Merge and release only when repository policy and all mandatory gates permit it. Download/inspect release artifacts and independently recompute their checksums where practical.
13. Finish with a concise but complete evidence report: commit/tag, gates, actual results, test/benchmark artefacts, remaining limitations, and all `NOT RUN`/`BLOCKED` items.

Do not ask the operator questions for facts discoverable from the repo, public documentation, code, tests, configuration, or normal toolchain. Use sound judgment and continue. Ask for a human only when necessary for non-bypassable approval, missing access, owner-provisioned credentials, a paid/billable hardware run, or a security/permission boundary. Never bypass these blockers.

## 1. Non-negotiable invariants

1. **Correctness before performance.** A correct slower result or an explicit refusal is better than a fast plausible error.
2. **No fake results.** Never fabricate state amplitudes, probabilities, counts, observables, uncertainty bounds, GPU telemetry, hardware results, benchmark data, Lean proof status, cloud success, release assets, or source links.
3. **Fail closed.** Unsupported operations, invalid QASM, unknown gates, invalid indices, missing calibration, exceeding resource/time budgets, untrusted numerical states, backend timeouts, or unusable bounds must return a typed refusal/failure/unresolved result. Never silently substitute identity, invent uniform counts, silently switch to an unrelated simulator, or report success for partial work.
4. **Metric correctness.** An observable-space bound is not automatically a state-vector bound, a total-variation bound, a confidence interval, or a bound on joint counts. Keep error scope explicit in every public and internal API.
5. **Approximation visibility.** Distinguish exact algebraic transformations, floating-point evaluation, numerical rank decisions, intentional approximation/truncation, sampling uncertainty, physical-device noise, and error mitigation. Never compress these into one ambiguous `exact` or `error_bound` flag.
6. **Independent oracles.** A test must not validate a function using the same helper, parser, gate matrix, convention, or algorithm that it is meant to test. Use independent derivation, analytical cases, Qiskit/Aer, Stim, direct NumPy matrices, or a separate reference path as appropriate.
7. **Do not weaken quality gates.** Never delete/skip a failing test, reduce coverage thresholds, change tolerances without a derivation, mark a failing job optional, modify expected output to fit suspect code, suppress warnings without explanation, or change benchmark inclusion after seeing results to force a win.
8. **Hypotheses are not findings.** Every candidate has `PROPOSED`, `SUPPORTED`, `REJECTED`, `INCONCLUSIVE`, `DEFERRED`, or `BLOCKED` status with a reproducible experiment ID and a dated evidence reference. Only results that meet the prespecified test can be called supported.
9. **No universal efficient simulator claim.** Do not promise efficient classical simulation of arbitrary universal quantum circuits. Complexity depends on circuit structure and output task; worst-case behaviour can require exponential classical resources.
10. **Hardware honesty.** Source compilation, SPIR-V validation, software-ICD dispatch, physical GPU dispatch, and full end-to-end GPU acceleration are separate evidence levels. A classical simulation, hardware noise model, provider fake, and physical QPU result are different result sources.
11. **Preserve operator work.** Inventory the current branch, tracked modifications, staged changes, and untracked files before editing. Do not discard or overwrite unrelated operator data.
12. **Safe Git.** Use a focused feature branch and PR. Do not force-push, rewrite public history, delete published tags, bypass checks/review, modify branch protection, push directly to a protected branch, or create a fake tag to trigger the release workflow.
13. **Secret hygiene.** Never put credentials in this document, source, commit, URL, terminal logs, CI artefacts, benchmark files, issues, or final output. Never dump environment/auth headers. Use existing approved GitHub auth or short-lived secret storage and least privilege. Do not hunt the filesystem for leaked tokens, turn off TLS verification, use `--insecure`, or place a PAT in a remote URL.
14. **Evidence for every gate.** Mark each item `PASS`, `FAIL`, `SKIP` with reason, `BLOCKED`, or `NOT RUN`. A skipped test is not a pass. Do not claim a test ran unless an actual recorded invocation or cloud job establishes it.
15. **Bounded autonomy.** Self-healing means diagnosis, minimal repair, and re-verification—not unbounded blind editing. Limit each root-cause repair to three targeted attempts before documenting the blocker and continuing on independent work.
16. **No premature “done.”** Report full completion only after the exact final source SHA, mandatory test suite, cloud gates, release provenance, and required documentation agree. If a non-bypassable external blocker remains, say `BLOCKED` precisely.

## 2. Live discovery and safe baseline

Repository facts in this file are a snapshot, not permanent truth. At mission start, discover actual state and refresh every important external source. Do not rely on badge labels or old audit text.

### 2.1 Inspect the working copy and repository

Run or use an equivalent safe inventory:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
git log -12 --oneline --decorate
git tag --list 'v*' --sort=-version:refname
```

Then retrieve the live GitHub metadata for:

- repository default branch, latest commit, tags, stable/draft/prerelease releases and their assets;
- open/closed PRs that affect the current stable cycle;
- recent CI, nightly and release workflow runs with exact head SHA, status and conclusion;
- required checks/rulesets/branch rules if credentials permit access;
- contents of `ci.yml`, `nightly.yml`, `release.yml` and any cloud-build/deployment configuration;
- current state of `GEMINI.md`, `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `pyproject.toml`, `CMakeLists.txt`, package constraints and tests.

If checkout is stale, fetch carefully. If dirty, create a read-only inventory of every changed file, the diff summary, and untracked work. Never use destructive reset/cleanup commands to get a clean tree. Do not overwrite pre-existing edits to `GEMINI.md` without explicitly preserving their useful content; reconcile them with this mission rather than erasing historical decisions.

### 2.2 Current known discrepancy to actively verify

The public snapshot inspected on 2026-10-29 shows `v2.4.0` published, while parts of `README.md` and `research/v2_4/RELEASE_AUDIT.md` still describe `v2.3.0` as the latest/current baseline. The README has old candidate verification entries (including 377 tests/version `2.3.0`), while the newer v2.4 research matrix records 420 candidate Python tests and other updated evidence. Re-check these files against the live release/tag/SHA and repair all stale statements. Do not blindly replace historical baselines: label them as historical evidence for their actual SHA, and add the current final-SHA results separately.

The live v2.4.0 release note says that v2.4.0 adds Pauli expectation values, nine composite gate lowerings, and result-contract corrections, but does not add a new simulation path, noise models, mid-circuit measurement/reset, or end-to-end GPU acceleration. Keep that scope truthful unless the live code and evidence prove a later change.

### 2.3 Build a durable audit trail

Follow the repository's current research naming convention. Prefer a new `research/v2_5/` directory or the appropriate next-stable area, containing at least:

- `BASELINE.md` — exact baseline SHA, versions, platform/toolchain, device/ICD class, dependencies, dirty state and historical release;
- `HYPOTHESES.md` — falsifiable hypotheses, assumptions, prespecified acceptance/rejection criteria and decisions;
- `LITERATURE_MAP.md` — source permalink/version, scope, model, proof/review status and transfer decision;
- `FINDINGS.md` — stable defect IDs, severity, repro, root cause, fix, regression test and disposition;
- `TEST_MATRIX.md` — actual commands/results, duration, logs/artifact URLs, exact commit and `SKIP`/`BLOCKED` reasons;
- `EXECUTION_LOG.md` — chronological repair/build/test/cloud attempts and checkpoints;
- `BENCHMARK_PROTOCOL.md` — preregistered workload families, metric definitions, run methodology and exclusion rules;
- `RELEASE_AUDIT.md` — exact tag/SHA, CI URLs, packages, checksum/SBOM evidence, documentation consistency and limitations.

Historical records are append-only in spirit: never rewrite an old record so that a result appears to have been performed against a commit it did not test. Clearly distinguish baseline, candidate-branch, merged-SHA, tag and downloaded-artifact evidence.

### 2.4 Source inventory

Read the live code rather than trusting historical reports. At minimum inspect:

- Python: `cqhecs/circuit_parsing.py`, `gate_lowering.py`, `gate_manifest.py`, `circuit_analyzer.py`, `router.py`, `result.py`, `backend.py`, `provider.py`, `expectation.py`, `cli.py`, `scheduler.py`, `circuit_library.py`;
- Python backends: `path_a_stabilizer.py`, `path_b_stabilizer_rank.py`, `path_c_mps_exact.py`, `path_d_sparse_pauli.py`, `dense_reference.py`;
- C++/C ABI/native binding, QASM parsers, MPS, statevector, stabilizer/tableau, tensor network, memory/paging, Vulkan context/pipeline/engine and every shader surfaced by the live tree;
- all current Python, C++, CTest, property, fuzz, mutation, concurrency, parser, size-limit, result-contract, native-artifact and CLI tests;
- package configuration, pinned constraints, workflow definitions, release scripts, SBOM/checksum generation and all docs/benchmark/research claims.

Historical findings should be reproduced against current code. If a defect is already fixed, prove that with code inspection and regression tests; do not waste time re-implementing it.

## 3. Definition of “10/10” and scorecard

At the start, establish a baseline and fill this matrix with scores and evidence. Re-evaluate after implementation. Scores without evidence are not accepted. A high score in one dimension cannot compensate for P0 correctness, scientific, security or release failures.

| Dimension | Target evidence for a 10/10-quality claim |
|---|---|
| Mathematical correctness | Every supported path has independent analytic/differential/property tests; assumptions and unsupported cases are explicit. |
| Numerical honesty | Rounding, rank floor, intentional truncation, sampling, noise and error bounds are separately reported and validated. |
| Semantic consistency | One public operation means the same thing across Python, CLI, Qiskit, QASM and native entry points—or is explicitly rejected by a documented capability contract. |
| Resource safety | Inputs and intermediate allocations are preflighted; no uncontrolled OOM, paging corruption, or silent partial mutation; time/memory limits fail closed. |
| Adversarial robustness | Property/fuzz tests cover malformed inputs, extreme values, index/layout bugs, seed edges, concurrency, resource denial and corrupted artifacts. |
| SOTA relevance | Live, primary-source literature map; comparators run fairly; feature improves a specific named workload class or is deferred. |
| Performance | Fresh, reproducible, end-to-end benchmarks with variance and resource metrics; no superiority claim based on a shader microbenchmark or a single GHZ circuit. |
| GPU truthfulness | Device identity and execution path recorded; CPU/GPU parity and validation pass; full simulator acceleration separately measured. |
| QPU bridge truthfulness | Fake-provider and real-provider paths are distinguishable; real run provenance and raw counts are retained; no silent simulated fallback. |
| API and architecture | Typed contracts, stable serialization, canonical semantics, compatibility tests and capability-first routing. |
| Security/supply chain | Least permissions, pinned third-party Actions, safe secrets, build/package checks, checksums and SPDX SBOM verified. |
| CI/release integrity | Required jobs pass on the exact final SHA; tag matches version; artifacts build/install/run and published hashes are independently checked. |
| Documentation | Every claim traced to code/evidence; all supported limitations, setup, API, examples and hardware status reflect the same commit. |
| Reproducibility | Seeds, versions, environment, raw logs, benchmark protocol, exact SHA and artifact digests are recorded. |
| Maintainability | One major feature at a time, small modules, reviewable diffs, clear errors and no dead/duplicated unsupported implementations. |

**Hard stop:** Any unresolved P0 issue in incorrect outputs, metric conflation, silent truncation, result provenance, security, or release integrity blocks Stable no matter what the average score is.

## 4. Product and scientific boundaries

CQ-HECS is a **classical quantum-circuit emulator**. It is not a physical quantum processor. It may model, optimize, validate or submit circuits to actual providers through a separate explicit provider mode, but each result must say which source created it.

Current documented four-path intent:

- **Path A — Stabilizer tableau:** specialized efficient classical simulation of the supported Clifford/stabilizer subset. It is not a universal gate simulator.
- **Path B — Stabilizer rank/decomposition:** can handle selected low-non-Clifford workloads; branch/rank growth may become exponential.
- **Path C — MPS/tensor chain:** effective for workloads with manageable entanglement for a chosen ordering. Paging shifts storage but does not eliminate computation or exponential entanglement growth. Numerically removed singular values must be reported accurately.
- **Path D — Sparse Pauli / Heisenberg propagation:** targets supported observables and can provide an observable-specific bound. It must not certify a joint measurement distribution unless a distribution bound is separately derived and proven.
- **Dense reference:** limited by exponential memory/runtime; retain it as an independent small-circuit oracle, not a large-system promise.
- **Vulkan:** primitive dispatch evidence is distinct from a real GPU simulator backend. The current Vulkan engine may be planner/allocator-only; inspect live code before claiming gate execution.

Do not make up a universal “number of qubits supported.” Report width alongside gate depth, topology, entanglement/rank, path, observable type, shots, memory/time budget, numerical semantics and whether the result is resolved. A 300-qubit GHZ circuit is not evidence of 300-qubit arbitrary-circuit simulation.

## 5. Literature and research-transfer workflow

### 5.1 OpenAI Math

Primary source: https://github.com/openai/math

At mission start, retrieve the actual current revision and relevant manifests/docs; record exact SHA, date, source file/permalink, repository-reported counts and how each count is defined. Do not hardcode manuscript/family/formalization counts from this file or prior reports. Distinguish manuscripts, result families, headline results, and formalized claims. A nearby Lean proof does not automatically formalize the full paper result. Verify the theorem statement, assumptions, domain, model, proof dependencies and match to the actual circuit workload.

Classify every candidate:

- `DIRECT_TRANSFER`: theorem/method directly applies to the implemented operation and all assumptions are met;
- `ADAPTABLE`: useful idea but requires a new derivation/prototype;
- `VALIDATION_ONLY`: useful test, lower bound or boundary, not a runtime algorithm;
- `NEGATIVE_RESULT`: rules out an overclaim or proposed transfer;
- `NOT_RELEVANT`: no material relationship to the current project;
- `UNVERIFIED_RESEARCH`: insufficiently independently checked;
- `RESEARCH_ONLY`: explicitly cannot be included in Stable code or claims yet.

For each candidate record title/ID, date/revision, primary URL, theorem/proof status, computational model, assumptions, likely circuit family, relevant CQ-HECS module, expected measurable benefit, independent test, acceptance/rejection threshold and decision.

Investigate (without assuming any is transferable):

1. Quantum query complexity/lower bounds: use to constrain claims, never treat query complexity as classical gate-level runtime.
2. Quantum algorithms/fixed gate sets: use small circuits as validation/benchmark families, not proof of efficient classical simulation.
3. Fourier-transform and exact arithmetic statements: transfer only when arithmetic model, coefficient representation, root-of-unity assumptions, preparation costs and numeric stability match.
4. Quantum many-body and statistical-mechanics results: candidate physically motivated Hamiltonian, spin-chain, Pauli-observable or MPS benchmark families.
5. QMA hardness and complexity-boundary results: use to prevent misleading universal-efficiency claims, not as a solver speedup.
6. Formalized statements: audit the formal theorem itself and the implemented correspondence; formalization is valuable only within its proven scope.

### 5.2 Anthropic and machine-checked mathematics

Primary research entry points to re-check live:

- https://www.anthropic.com/research/formalizing-fermats-last-theorem
- https://www.anthropic.com/research/formal-verification

The transferable engineering lesson is to split complex mathematics/software contracts into small machine-checkable claims, keep proof and code correspondence explicit, and independently test the implementation. A formal proof only proves the formal proposition under its assumptions; it does not certify that the specification fully models real hardware or that a C++/Python implementation refines it unless that connection is established.

Prioritize narrow, high-value proof targets:

- exact gate-lowering identities, including global phase and operand order;
- Clifford Pauli conjugation and signs;
- validity of result-bound composition and result-kind constraints;
- Kraus completeness and simple channel invariants for a future noise module;
- measurement-layout and bit-order remapping invariants.

Do not start by formalizing the whole codebase. Select one critical property, define it unambiguously, provide a small formal proof when practical, and pair it with executable tests against independently implemented behavior.

### 5.3 Current emulator and hardware landscape

Check live primary documentation/releases for the relevant projects, recording the date and revision rather than copying old claims:

- Qiskit Aer: ideal statevector, stabilizer, MPS, density-matrix/noisy methods and measurement/dynamic-circuit semantics;
- Stim: high-performance stabilizer and quantum-error-correction workload references;
- MQT DDSIM: decision-diagram and hybrid Schrödinger–Feynman approaches;
- NVIDIA cuQuantum/CUDA-Q: GPU-oriented statevector/tensor-network and heterogeneous workflows (ensure platform-specific claims are properly scoped);
- Qulacs and QuEST: simulation methods and CPU/GPU/parallel options;
- tensor-network ecosystem/papers (such as quimb and applicable cuTensorNet APIs): graph/topology-aware contraction and slicing;
- a real-QPU provider's official API and calibration documentation only when designing an actual adapter.

A tool being installed does not establish a result or superiority. Keep external engines as optional test-only comparators where possible; do not add heavy runtime dependencies just to make a benchmark look modern. Pin exact versions/options in reports. Read primary papers/docs before adopting algorithms.

### 5.4 Research selection gate

Create a table of candidates scored from 1–5 on relevance, evidence quality, implementability, expected benefit, independent-oracle quality, portability, and reverse-risk. Record scores before the major feature is chosen. Choose at most one major architecture prototype for this cycle. If no candidate satisfies the testability and resource requirements, do correctness/security/compatibility work and defer the feature honestly.

## 6. Preferred major feature: Hardware-Aware Quantum Bridge

Treat this as a preferred hypothesis-driven direction, not as permission to prematurely advertise every subfeature as Stable. Build vertical slices only after current baseline issues are resolved.

### 6.1 Three irreducibly separate execution modes

1. `IDEAL_CLASSICAL`: ideal classical simulation using a supported CQ-HECS engine.
2. `NOISY_CLASSICAL`: classical emulation with an explicit, versioned and scoped noise model; output is a modelled distribution or estimator, not a physical measurement.
3. `REAL_HARDWARE`: a submitted job executed on an identified physical QPU; raw counts/results and provider provenance come from the real device.

Never silently fall from `REAL_HARDWARE` to either classical mode. An explicitly requested fallback must be a separate, visible event and must not preserve the `REAL_HARDWARE` result label. Each result must carry source/mode, provider/backend if applicable, circuit hash, compiled/transpiled circuit hash if applicable, layout, seed where meaningful, shots, timestamps, calibration/profile reference, noise-model revision, result kind, error metric and status.

### 6.2 Backend profile schema

Design a versioned, validated `BackendProfile`/equivalent structure, separate from execution code. Include only fields supported by source data:

- provider name and exact backend identifier;
- profile schema version, capture timestamp and source/provenance URI or export digest;
- qubit count and coupling/topology graph;
- supported/native gate set and basis conventions;
- gate error values with scope (per gate, qubit pair, calibration snapshot), units and measurement source;
- readout/assignment error data;
- T1/T2 and gate/readout durations when available;
- supported dynamic circuit features (mid-circuit measurement, reset, classical control, conditional gates);
- calibration age/staleness and completeness diagnostics;
- unknown/missing fields represented as unknown, not guessed constants.

Validate finite numeric ranges, units, qubit identifiers, topology consistency and schema version. Never treat an example profile or simulator-derived values as real calibration. Keep raw provider responses out of secrets and sanitize before logging.

### 6.3 Canonical circuit IR

Investigate whether a canonical intermediate representation can eliminate semantic drift between Qiskit, OpenQASM, Python instruction lists and native C/QASM entry points. Do not perform a high-risk full rewrite unless tests justify it. At minimum the IR must preserve:

- declared qubit and classical-register widths, including idle high-index qubits;
- gate identity, parameters, global phase and operand order;
- explicit qubit/clbit measurement mapping;
- terminal versus mid-circuit measurement;
- reset/classical conditions as distinct operations that may be unsupported by some paths;
- source provenance, parse diagnostics and capability requirements.

Every front-end must either produce equivalent normalized semantics or issue a typed refusal. Never accept dynamic operations in one parser and silently omit them in another. Keep ABI constraints explicit; an 8-bit opcode index must reject an out-of-range operand before it wraps.

### 6.4 Narrow noise-model capability

Only implement the channels that can be rigorously specified and independently tested within the release. Candidate order:

1. readout/assignment error;
2. one-qubit depolarizing channel;
3. amplitude damping and phase damping under an explicit convention;
4. selected two-qubit depolarizing errors;
5. optional relaxation channels using valid T1/T2 and gate durations.

Do not conflate amplitude-damping parameters, T1/T2, dephasing rates, gate duration or a vendor's reported infidelity. Research and define each convention. Reject inconsistent parameter ranges. Noise channels must have an explicit supported gate/model scope.

For Kraus representations, check completeness \(\sum_i K_i^\dagger K_i=I\) within a prespecified numerical tolerance. For a density-matrix implementation test trace preservation, Hermiticity, positivity within numerical tolerance, normalized measurement probabilities and the noiseless limit. For trajectory sampling test seeded reproducibility and compare Monte Carlo estimates to an independent small density-matrix/Aer reference with precomputed confidence limits. A high shot count is not a proof; statistical acceptance needs a valid bound and a prespecified test.

Choose either a narrowly correct exact Density-Matrix reference for tiny systems, or a carefully described seeded trajectory engine. Do not add both broadly without a clear acceptance test. Keep the expected exponential scaling visible and impose pre-allocation memory/time limits. If an operation exceeds the budget, return `UNRESOLVED`/resource refusal before partially mutating state.

### 6.5 Real-provider adapter — optional and explicitly authorized

Inspect current official provider APIs and existing Qiskit interfaces before choosing one; do not invent endpoints or hardcode credentials. Separate interface definition from provider plugin so standard CI never requires a token.

Minimum interface semantics:

- discover/list an available backend/profile;
- transpile/validate circuit against supported topology/gates with complete mapping metadata;
- submit only when explicitly requested and authorized;
- poll status with timeout and cancellation support where provider allows;
- fetch raw result and calibration/provenance;
- normalize result into a truthful result contract without losing raw provider data;
- surface quota, timeout, unavailable backend, invalid job ID, partial result and provider error as typed errors.

Test with a deterministic FakeProvider for success, timeout, rejection, malformed result, missing metadata, cancellation, duplicate submission and retry safety. Never use a fake provider to substantiate real hardware claims. Real hardware smoke test is a separately authorized operation with a strict small-qubit/shot/cost ceiling, logged job IDs and user consent. If credentials or consent are absent, report `BLOCKED/NOT RUN`; continue all mock and offline work.

### 6.6 Error mitigation — not first priority

Read current provider guidance and primary literature. Only add readout mitigation or Zero-Noise Extrapolation after raw noisy simulation and hardware provenance are stable. Preserve raw counts, corrected estimates, mitigation model, fit/extrapolation data, confidence/uncertainty and all assumptions. Never claim unbiasedness or error correction unless mathematically established for that method and case. “Mitigated” is not “exact.”

## 7. Correctness, numerical analysis and API-contract hardening

Before any major feature, audit every path and public result constructor.

### 7.1 Required invariants

- All probabilities are finite, non-negative within the declared rounding convention, and correctly normalized within a justified tolerance.
- Counts are non-negative integers and sum to shots only where they represent the actual joint measurement distribution.
- Independent marginals are never serialized or named as joint counts.
- Observable expectations lie within theoretically valid limits for bounded Hermitian Pauli observables (allowing only a justified numerical tolerance); weighted sums use correct coefficients and phases.
- `error_bound` includes a named metric and target object; `None` means unavailable, not zero.
- `total_error_bound` is only available if every component can be validly composed under its assumptions and target metric. No mixing of observable, norm, sampling, confidence, hardware-noise or TV metrics without a derivation.
- `EXACT`/`CERTIFIED`/`UNRESOLVED`/`FAILED` semantics are exclusive and consistent across CLI, API, Qiskit result header and JSON.
- `exact=True` must state whether it means no deliberate approximation, algebraically exact transformations, exact rational/symbolic arithmetic, or a numerically evaluated method. Never imply bitwise or physical exactness without proof.
- Numerical rank/floor diagnostics, bond-budget truncation and propagated global error bounds are separate. A sum of local discarded SVD weight is not automatically a global state error certificate.
- Invalid/non-finite angles, huge inputs, unknown gates, register mismatch, width overflow, idle top qubits, classical mapping, global phase, endian conventions and gate-order ambiguities are tested.
- Resource ceilings occur before allocation/mutation. Failed execution leaves no partially valid state or fabricated results.
- Any paging/offload subsystem validates page identity/checksum/size and fails closed on missing, truncated, stale or corrupt blocks.
- Deterministic seeds are passed through all stochastic layers, and metadata states which randomness source is used.

### 7.2 Output schema / result type

Audit the current `SimulationResult` and add fields only with compatibility in mind. Prefer explicit structured fields such as:

- `status` / `result_state`;
- `result_kind` (joint counts, marginal counts, expectation values, statevector, density matrix, provider raw counts, etc.);
- `execution_mode` (`IDEAL_CLASSICAL`, `NOISY_CLASSICAL`, `REAL_HARDWARE`);
- `method` / `backend_path`;
- `exactness_semantics` and `numerical_status`;
- `approximation_applied` and diagnostic details;
- `error_bound`, `error_bound_metric`, `error_bound_covers`, assumptions and confidence level where applicable;
- `sampling_uncertainty` kept distinct from deterministic/model error;
- source SHA, circuit hash, backend/profile/noise model IDs and seed if applicable;
- typed refusal/error reason, not only a free-form message.

Do not create a needless schema rewrite if the current v2 public API can express the semantics truthfully. Add migration/compatibility tests if changing field names or serialization. Every supported result must make it impossible—or at least mechanically detectable—for a caller to confuse uncertified counts with certified distribution output.

### 7.3 Security/resource inputs

Validate all user-supplied counts, qubit numbers, shot counts, RAM/disk budgets, tolerances, confidence values, circuit depth and parser sizes before allocation. Reject boolean-as-integer parameters, float indices, NaN/infinity, negative dimensions, enormous declared registers and overflow-prone arithmetic. Put timeout bounds around fuzzers, subprocesses, provider polling and any potentially unbounded solver. Do not evaluate arbitrary strings with `eval`, `exec`, or equivalent parser shortcuts.

## 8. Testing architecture: gates that must not be bypassed

Record exact tool versions, environment and outputs. A pass requires a successful exit code and expected test artifacts—not an agent summary alone.

### L0 — provenance and no-loss baseline

- Working tree/branch/HEAD recorded; all pre-existing modified and untracked files inventoried and preserved.
- Live default branch, latest stable release/tag, main HEAD and PR state recorded.
- No unrelated diff is overwritten.
- Baseline test/build/benchmark evidence captured on its true SHA; historical results labeled historical.

### L1 — static checks and packaging

Run current repository commands, adapting to live files:

```bash
python -m compileall -q cqhecs tests scripts python_bridge
python scripts/check_version.py
python scripts/verify_no_silent_truncation.py
python scripts/verify_vulkan_shaders.py
python -m flake8 cqhecs tests scripts python_bridge --count --select=E9,F --show-source --statistics
python -m build
python -m twine check dist/*
```

Lint requirements must meet or exceed the current CI configuration; do not loosen an existing rule. Verify package metadata, version agreement, wheel and sdist names, CLI entry points, license, dependencies and reproducible content where feasible. Install the wheel into a clean virtual environment—not the development tree—and run help, version, doctor, a simple circuit and JSON-schema validation. Clean-venv tests must ensure the package works without repository-relative imports or undeclared benchmark/dev extras.

### L2 — native build, CTest and shader checks

Use the live project build instructions. Typical commands:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```

Run the required platform/configuration variants in the live CI workflow. Keep CTest output/JUnit logs. Confirm tests actually execute with the required native binding, e.g. `CQ_HECS_REQUIRE_NATIVE=1`; native coverage must not silently skip. Shader source compilation/SPIR-V validation is one gate; actual device dispatch and end-to-end GPU execution are separate.

### L3 — Python suite, coverage and API contracts

On the current supported versions and platforms, run the exact full suite, including:

```bash
python -m pytest tests/ -q
```

Where native execution is required, set `CQ_HECS_REQUIRE_NATIVE=1`. Retain XML/JUnit output. The current CI policy observed at preparation uses a minimum overall branch coverage threshold of 70%; preserve that as a hard floor unless live configuration is stricter. Do not accept coverage regression from baseline. Aim for at least 85% overall where feasible and at least 90% branch coverage for new critical logic; more importantly, cover all safety/correctness branches and every new failure path. A project-wide percentage does not replace focused tests.

### L4 — analytic, property and differential tests

For each engine and new feature:

- small analytical gates/states/circuits with known exact answers;
- randomized circuits drawn from a named and reproducible distribution, with recorded seeds;
- Qiskit `Statevector`, `Operator`, `SparsePauliOp` or Aer references where semantics overlap;
- Stim for supported stabilizer/Clifford cases;
- independent NumPy matrices/closed forms where possible;
- compare full probability distributions/TV distance or state fidelity, not just intersecting count keys;
- compare observables individually and validate the correct phase/sign convention;
- test measurement bit-order, register offsets, idle qubits, global phase and repeated measurement semantics;
- use statistical confidence tests with prespecified alpha/bounds for independent sampled outcomes;
- test unsupported operations as explicit rejection rather than accepting them in parser and dropping them later.

An oracle must be independent of the code under test. If both implementations share a helper, derive a second check directly from the mathematical definition. Store generated test cases/seed lists to reproduce any failure. Do not commit millions of redundant random cases; commit a compact deterministic regression and preserve detailed logs/artifacts separately.

### L5 — mutation tests, fuzzing, adversarial and reliability

Run the project's mutation harness:

```bash
python scripts/run_mutation_tests.py
```

The current v2.4 candidate records 14/14 killed mutants, while earlier baseline evidence may differ; remeasure live state and require no reduction in relevant mutation strength. Any mutant that simulates the wrong state, phase, sign, layout, error metric, approximation status, provider mode or resource behavior must be killed by tests. Add mutants for new critical contracts rather than gaming the total count.

Run property-based parser/circuit tests and the live fuzz suites. Add bounded tests for:

- invalid, malformed, enormous or non-finite OpenQASM and instruction lists;
- all register and endianness edge cases;
- unknown gate/parameter/circuit versions;
- resource limits, overflow, RAM budget, disk quota, corrupt/missing page files;
- concurrent executions, deterministic seeds and shared-state contamination;
- NaN/inf, near-singular matrices, near-zero singular values and normalization drift;
- malformed FakeProvider payloads, duplicate jobs, timeouts and unavailable profiles;
- failures in optional dependencies, native extension and Vulkan runtime.

Every fuzzer/subprocess must have a timeout and bounded memory. Crashes, hangs, OOM, inconsistent status, unbounded logs, false success and partial mutation are failures.

### L6 — benchmark and performance integrity

Use a preregistered `BENCHMARK_PROTOCOL.md`, a machine-readable benchmark schema, raw JSON/CSV, exact source SHA and command. Include workload families rather than only GHZ:

- Clifford/random stabilizer;
- Clifford+T across growing T-count;
- 1D low-entanglement/MPS-friendly and entanglement-growth circuits;
- 2D/long-range/topology-aware circuits;
- QFT/arithmetic and composite-gate circuits;
- selected Pauli expectations;
- representative unresolved/resource-refusal paths;
- noise-model circuits and provider-free bridge tests if implemented.

Record circuit width/depth/gate counts, topology, T-count, estimated/actual tensor rank or Pauli-term count, approximation settings, shots/seeds, exactness/result type, warm-up, setup/compile time, simulation time, readback/serialization time, end-to-end wall time, median/spread, peak RSS, temporary storage and GPU/device memory where available. Separate CPU, software Vulkan ICD, physical GPU and real QPU evidence. Track energy only if measured with an identified method.

Run warmups and repeated measurements. Hold out entire circuit families from router/heuristic calibration. Never tune on final validation cases. Compare only equal output semantics and equivalent precision/accuracy. A microkernel result is not a simulator speedup. Use the project’s preregistered initial bar (e.g. 15% median end-to-end improvement on a named held-out workload or a material resource benefit) only as an engineering acceptance criterion, not a scientific constant. If the criterion is missed, reject/defer the optimization and report it honestly.

### L7 — hardware/provider tests

Default CI must not require credentials or incur QPU charges. Test all provider logic offline using a deterministic fake. Test a real provider only with explicit authorization, strict shot/qubit/cost cap, secure credential handling and an audit record. A lack of credentials is `BLOCKED/NOT RUN`, not a failure of local CI and not evidence that the hardware feature works.

For real hardware, store only permitted non-secret provenance: provider/backend, job ID, submitted circuit/transpiled hashes, layout, raw counts, shots, timestamps, calibration/profile reference, queue/run status, and returned metadata. Do not assert sampled counts must equal ideal simulator counts exactly. Compare distributions/observables statistically using an explicitly chosen methodology, and treat real noise/drift as observed uncertainty—not as a bug to erase.

### L8 — cloud CI and release gates

- Every required CI job must run on the exact candidate SHA and pass.
- Verify branch and merge method permitted by the actual repository rules; never skip required checks.
- Release workflow must confirm the tag points to the intended merged commit and that the tag equals the canonical package version.
- Verify build artifacts in a clean install and smoke a deterministic circuit/API/JSON path.
- Generate release notes, SHA-256 checksums and SPDX SBOM only after final contents are assembled; verify all listed assets exist.
- Download the published artifacts and independently recompute checksums when permitted. Check wheel/sdist metadata and that the downloaded package actually installs and executes.
- Record stable tag, exact commit, CI run URL, release workflow URL, asset URLs, sizes/digests, SBOM validation, and any limitations in `RELEASE_AUDIT.md`.
- A release-created event or green badge alone does not prove asset correctness. Any mismatch blocks final completion.

## 9. Self-healing loop protocol

Use a durable task ledger with `ID`, severity, evidence, hypothesis, owner/module, state, attempt count, last command, exit code, log path, regression test, code commit, acceptance criterion and next action.

States: `NEW → TRIAGED → REPRODUCED → FIX_IN_PROGRESS → LOCAL_RETEST → FULL_GATES → CLOUD_GATES → RESOLVED`; alternate terminal states are `REJECTED`, `DEFERRED`, `BLOCKED` and `INCONCLUSIVE`. A status transition must cite evidence.

### 9.1 Loop A — correctness defect

1. Reproduce on the recorded baseline/candidate SHA and capture a minimal failing input.
2. Identify the violated invariant; write a short proof/reason why the expected result is correct.
3. Create a deterministic regression test before or with the fix. For P0/P1, use an independent oracle.
4. Make the smallest change that fixes the root cause; avoid unrelated refactors.
5. Run the test against pre-fix if feasible to confirm it fails, then passes after fix.
6. Run related modules and the full relevant suite.
7. Re-run mutation/property tests to ensure the bug is detectable.
8. Update finding log and mark resolved only if the complete evidence passes.

### 9.2 Loop B — failed build/test/CI

For each failure:

1. Identify whether it is a product failure, test defect, environmental/toolchain issue, stale cache, external service, or unsupported runtime.
2. Capture full non-secret log, command, environment versions and exact failing job/SHA.
3. Reproduce locally or in the closest equivalent environment; do not guess from a truncated summary.
4. Form one root-cause hypothesis and one minimally scoped repair.
5. Run the smallest regression, then the impacted gates, then full gates.
6. Commit only after the repair passes and is documented.
7. Push the candidate branch and re-run exact-SHA CI. Treat changed SHA as new evidence that requires its own gates.
8. Repeat up to three targeted repairs per root-cause class. If external/permissions/tooling prevents progress, mark `BLOCKED` with evidence and continue unrelated work.

### 9.3 Loop C — resource/reliability failure

1. Capture the failing circuit, declared dimensions, actual allocation point, peak memory and time.
2. Determine whether preflight, overflow validation, budget enforcement or cleanup is faulty.
3. Add a test proving refusal occurs before destructive mutation or uncontrolled allocation.
4. Test just-below/at/above the limit, and verify subsequent valid execution still works.
5. Verify page/file cleanup is isolated to this run and does not remove operator data.
6. Retest concurrency and the affected backend.

### 9.4 Loop D — hypothesis/benchmark

1. Record assumptions and acceptance/rejection criteria before tuning.
2. Build minimal prototype behind an internal/experimental boundary.
3. Validate correctness against an independent reference first.
4. Run preregistered workload families, including held-out cases, multiple repetitions and complete end-to-end accounting.
5. If wrong, unstable, slower, less memory-safe or semantically weaker, reject or redesign the hypothesis.
6. Do not change the acceptance bar after observing results; any methodological change is preregistered as a new experiment.
7. Promote to Stable only after correctness, robustness, public contract and documentation are complete.

### 9.5 Loop E — docs/evidence mismatch

1. Find the exact contradiction and identify which artifact/SHA is authoritative.
2. Recheck source/API/CI/release metadata rather than selecting the most flattering value.
3. Update current narrative, leave historical records labeled as historical, and link the exact evidence.
4. Run link checks/documentation examples where supported, `check_version.py`, wheel smoke and all relevant tests after doc/code changes.
5. Do not report completion while public surfaces still disagree.

### 9.6 Stop rules

- Maximum three targeted repair attempts per root-cause class before marking `BLOCKED`/`INCONCLUSIVE` and documenting next diagnostic steps.
- Stop any release/push/hardware operation if authorization or security is uncertain.
- Stop feature expansion if any P0 issue is unresolved or if the remaining time/compute budget cannot support a valid verification.
- Keep making safe progress on independent issues rather than asking the operator unnecessary questions.
- Never spin on repeated identical failures without a new diagnosis or changed evidence.

## 10. Architecture and implementation rules

- Prefer explicit capability contracts over monolithic “auto magic.” The router must choose only a backend that supports the operation and required result kind. Resource estimates should be conservative and explainable; use heuristic optimization only after measuring it against a fixed baseline.
- Do not silently reroute forced-backend requests. Automatic escalation may occur only through typed capability/resource outcomes and must be logged in the result metadata.
- Treat optional backends/dependencies as optional: no import-time failure in the core package if an optional provider, GPU or benchmark library is missing.
- Use deterministic stable JSON with schema version and well-defined numeric/enum serialization. JSON mode must produce one valid document on stdout; diagnostics go to stderr.
- Preserve API/ABI compatibility or document and test migration. Never change a native ABI, QASM index representation or result schema casually.
- Use clear type annotations, small cohesive functions, explicit error types, RAII in C++, overflow-safe sizes and bounded resource use.
- No giant all-at-once rewrite. Keep changesets small enough to review and bisect.
- Avoid duplicated implementation of the same operation in Python/native without a shared contract plus independent differential tests.
- Avoid a new dependency unless it is necessary, maintained, appropriately licensed, pinned for CI and tested under the supported matrix.
- Do not fold research-only features into the default route until acceptance criteria are met. Mark experimental capability at API, CLI, docs and result level.

## 11. GPU and device execution claims

For every Vulkan/GPU-related experiment, record:

- actual physical device/vendor/device ID and driver/runtime when hardware is used;
- ICD/device class: physical GPU vs software implementation (Lavapipe or other software ICD);
- shader source and SPIR-V digest, build options and validation result;
- operation actually executed on the device, buffer sizes, data uploaded/read back and numerical contract;
- CPU reference result and tolerance derivation;
- validation-layer errors, synchronization/memory behavior, deterministic repeated-run outcomes;
- total pipeline timings including dispatch setup, transfer, synchronization and output conversion.

Stages of evidence must be labeled exactly:

1. `SOURCE_COMPILED`;
2. `SPIRV_VALIDATED`;
3. `SOFTWARE_ICD_DISPATCH_VERIFIED`;
4. `PHYSICAL_DEVICE_PRIMITIVE_VERIFIED`;
5. `FULL_SIMULATOR_PATH_DEVICE_EXECUTED`;
6. `END_TO_END_ACCELERATION_BENCHMARKED`.

Only claim the highest level actually exercised. A physical-device primitive test does not establish that the four Python paths are GPU-accelerated. If a Vulkan MPS kernel is added, compare its tensors/results with an independent CPU reference across valid and adversarial gate/order/rank cases and test memory allocation, descriptor lifetime, synchronization, device loss and out-of-memory failures.

## 12. Security, CI and supply-chain hardening

- Read live workflow permissions and minimize `GITHUB_TOKEN` scope; write permissions belong only to the job that needs them.
- Pin third-party GitHub Actions to verified full commit SHAs, retaining a human-readable release comment. Verify that referenced commits match the intended upstream releases.
- Use explicit `timeout-minutes`, concurrency control, and cancellation where correct. Never hide required release jobs behind `continue-on-error`.
- Validate untrusted input before subprocess execution; avoid shell interpolation of user/provider strings; use argument arrays, timeouts and bounded output.
- Do not parse QASM or arithmetic using `eval`; do not execute untrusted provider data as code.
- Check dependencies/license/SBOM and package contents. Release assets must not contain local logs with secrets, auth files, credentials, calibration data restricted by a provider, or unnecessary private paths.
- Preserve security scanning and TLS verification. Never lower repository visibility or repository protection for convenience.
- Ensure a failed job exits non-zero and reports the primary failure. Retried transient external calls must be bounded and must not mask repeated deterministic failures.
- Verify all generated artifacts using checksums and, if supported, signature/attestation provenance. Don't assert signing/attestation when it is not configured.

## 13. Documentation, release notes and benchmark claim audit

After implementation is stable, review every public text and runnable example:

- `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `GEMINI.md`, `docs/API_REFERENCE.md`, `docs/ARCHITECTURE.md`, `docs/QASM_CONTRACT.md`, `docs/USAGE_GUIDE.md`, `docs/BENCHMARKS.md`, `docs/V2_IMPLEMENTATION_MATRIX.md`, CLI help, Python docstrings, Qiskit backend metadata, examples, citations, badges and version strings;
- research baseline, findings, hypothesis decisions, benchmark protocol/results, test matrix and release audit.

Check and correct:

- current release and version status;
- exact test counts, coverage, mutation score, shader tests, CI results and platform/device claims;
- examples that use existing public API and have actually been executed in the package smoke test;
- limits for each path, gate set, qubit-index width, shot/resource limits, exactness and error-bound semantics;
- explicit statement that no physical QPU was used unless a documented authorized job really ran;
- every performance claim linked to raw, reproducible benchmark evidence;
- every citation points to a real primary source and the correct current/revision-specific content;
- historical metrics are clearly labeled with their SHA/date and never presented as current results.

The final content-changing commit must itself be re-tested. Documentation edits can break examples, schema output, install steps or truthfulness; they are not “free” after the final test.

## 14. Versioning, branch, merge and release policy

1. Determine semver from the actual changes and existing public contract. A new backward-compatible public capability may justify a minor feature release; a pure fix-only release should use a patch. A public incompatible schema/API/ABI change requires explicit major-release analysis and migration plan.
2. Do not precommit to v2.5.0 if the feature is not accepted. Choose the next version only after scope and compatibility are known; then update all canonical version surfaces with the repository's existing script/convention.
3. Work on a named branch, e.g. `agent/cq-hecs-next-stable-<feature>`. Confirm branch names and permissions live.
4. Commit focused stages: baseline/report; correctness; feature; tests; documentation/release metadata, as useful for review. Do not include unrelated operator changes.
5. Push using existing approved auth. Open or update a PR with problem statement, design, trade-offs, tests, benchmark evidence, API changes and limitations.
6. Wait for actual required checks/approvals by polling the supported GitHub interface; do not promise background execution or mark a pending job complete. Repair genuine failures within the self-healing rules.
7. Merge only after all mandatory checks pass and the repository's allowed merge rules permit it.
8. Confirm merged commit SHA, then ensure the release tag targets the intended merged commit and matches canonical version. If the workflow requires a tag trigger, use the documented approved method only after green exact-SHA CI.
9. Verify release pipeline completion, asset list, checksums and SPDX SBOM. Download and recompute hashes where possible. Install wheel in a clean environment and execute minimal public API/CLI examples.
10. Re-query GitHub releases, tag ref and workflow runs to establish final state. Store exact URLs and digests in `RELEASE_AUDIT.md`.
11. If credentials, permissions, branch protection or external services block a step, do not bypass. Stop at that gate with concrete evidence and leave a reviewable branch/PR if possible.

## 15. Stable-release acceptance gates

All mandatory gates must be explicitly marked before Stable promotion:

### Gate A — Baseline/reproducibility
- [ ] The live baseline SHA and current version/release are verified.
- [ ] All pre-existing work is preserved and no unintended files changed.
- [ ] Baseline and candidate evidence are clearly separated.

### Gate B — Scientific correctness
- [ ] All P0 findings are resolved or the release is blocked.
- [ ] Every new algorithm has an independent analytical or differential oracle.
- [ ] Metric and result-kind invariants are exhaustively tested.
- [ ] Approximation/numerical/noise/provenance semantics are explicit.
- [ ] Unsupported inputs fail closed and resource limits are preflighted.

### Gate C — Software quality
- [ ] Full Python tests pass on the supported CI matrix.
- [ ] Native build and CTest pass with required native code loaded.
- [ ] Coverage is at least the live CI threshold and no unexplained regression exists.
- [ ] Mutation, property/fuzz, concurrency, parser, resource and API-contract gates pass.
- [ ] Static analysis and dependency/package checks pass.

### Gate D — Performance evidence
- [ ] Workloads and acceptance bar were preregistered.
- [ ] Fresh raw benchmark output is produced for the exact candidate SHA.
- [ ] All end-to-end overhead and result semantics are included.
- [ ] Held-out workloads show the stated improvement; otherwise claim is withdrawn or feature deferred.

### Gate E — GPU/QPU honesty
- [ ] Every device claim has the correct evidence level.
- [ ] Provider fake tests pass and no credentials are required for default CI.
- [ ] Any real QPU claim has actual job provenance, raw results and explicit authorization.
- [ ] No silent fallback can mislabel classical output as hardware output.

### Gate F — Security and supply chain
- [ ] Action pins, permissions, secrets and subprocess boundaries pass review.
- [ ] Wheel, sdist, SPDX SBOM and checksums build and validate.
- [ ] No sensitive content or credentials appear in tracked files or release assets.

### Gate G — Docs and release
- [ ] All public surfaces describe the same version and supported semantics.
- [ ] All examples in updated docs are smoke-tested or explicitly marked illustrative.
- [ ] CI and release jobs pass on the relevant exact SHA.
- [ ] The published tag, assets and hashes independently match the release audit.
- [ ] Known limitations, unrun tests and blockers are documented honestly.

**No “mostly green” release:** a blocked mandatory gate blocks Stable. It may be released as an experimental/pre-release only if the repository workflow permits it, the limitations are visible and no safety/correctness issue is being hidden.

## 16. Final report format

At the end, write a final report in the repository and respond to the operator with a compact summary containing:

1. **Outcome:** `RELEASED`, `READY_FOR_REVIEW`, `BLOCKED`, or `NOT_RELEASED`—never an ambiguous “done.”
2. Repository/branch/PR/tag, exact source and merged SHAs, and release URL if one exists.
3. A gate table of command, status, measured outcome and evidence link. Use actual counts only from captured outputs.
4. Test counts, coverage, mutation/fuzz results, platform matrix and native requirement status.
5. Benchmark method, raw output link, median/spread, peak resources and precise workload class; state “no performance claim” when not earned.
6. GPU execution tier and QPU status: `NOT RUN`, `BLOCKED`, or actual authorized job metadata.
7. Main defects fixed and new capabilities shipped.
8. Known limitations, deferred hypotheses, unrun tests and external blockers.
9. Release asset filenames, sizes, SHA-256 and SBOM status.
10. Documentation/claim changes and remaining scorecard dimensions below 10/10.

Scorecard is not allowed to use a perfect rating as a marketing device. For each dimension below 10/10, say exactly what remains; for a 10/10, link the evidence and define its scope. This project can be production-quality on specific supported classes without being a universal simulator.

## 17. First actions at runtime

Perform these in order before major edits:

1. Discover live head/tag/release/CI/PR state and preserve a dirty checkout.
2. Reconcile the README/research/release mismatch described in §2.2.
3. Re-run baseline version, Python compile/lint, full tests, native build/CTest, shader verification, mutation tests, package build and clean-wheel smoke as available. Capture output and exact SHA.
4. Audit result contracts, MPS numerical rank/approximation metadata, Path D bound semantics, all gate-lowering tables and provider/native parser consistency. Reproduce any suspected defect; do not assume old findings remain open.
5. Update research records using current source/release evidence and live literature. Record hypotheses before selecting one major prototype.
6. Choose the smallest vertical slice of the Hardware-Aware Quantum Bridge that can meet all stable gates. If that scope is not implementable safely, prioritize correctness and documentation fixes and record why the new feature was deferred.
7. Implement tests with each change, run the bounded self-healing loops, then execute the full local-to-cloud-to-release sequence above.

**Definition of success:** not “all qubits always work,” not “the tests have been made green,” and not “the agent used every technique.” Success is a reproducible, scientifically honest release whose supported operations are correct, unsupported operations fail safely, performance claims are backed by fair benchmarks, and the exact published source and artifacts have verifiable evidence.
