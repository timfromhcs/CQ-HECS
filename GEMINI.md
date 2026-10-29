# GEMINI MISSION — CQ-HECS Next Stable, Research Transfer, Mathematical Correctness, SOTA Evaluation, CI/CD and Verified Release

**Repository:** <https://github.com/timfromhcs/CQ-HECS>  
**Mission document purpose:** Operative, evidence-first long-horizon build plan for the next CQ-HECS Stable release.  
**Last prepared:** 2026-10-29.  
**Observed release at preparation:** `v2.3.0`.  
**Observed default branch at preparation:** `main`.  
**Observed release merge SHA at preparation:** `ba27bd1e7d814c79b7982ba3a9739f264f054520`.  
**Working target:** `v2.4.0` (selected: the cycle landed a validated backward-compatible capability, Pauli expectation values) only if the final changes include at least one validated, compatible feature; otherwise select the correct patch version (e.g. `v2.3.1`) rather than making a cosmetic minor-version bump. **Re-discover all live facts at runtime.**  
**Run style:** autonomous, multi-phase, evidence-driven, self-healing loops with durable checkpoints; no unsupported claims, bypassed checks, data loss, credential leaks, or fake-green CI.  
**Authority:** This document is a mission plan. Repository state, applicable permissions, branch protection, release rules, current dependencies, and primary research sources always take precedence over stale assumptions in this document.

---

## 0. Mission definition

Operate as a senior quantum-simulation researcher, numerical analyst, systems/C++ engineer, Python maintainer, test architect, performance engineer, security-conscious release engineer, and technical writer. Inspect the live CQ-HECS repository and current upstream research; formulate explicit falsifiable hypotheses; identify what can be transferred from OpenAI Math and from state-of-the-art real-quantum and classical-emulation research; implement only ideas whose assumptions fit the code; create independent mathematical and differential tests; run all local build and quality gates; repair failures through bounded self-healing loops; push a focused branch using existing secure GitHub authentication; fix cloud CI failures until every applicable required gate passes; update documentation and reports in the final content-changing push; merge only through the repository's permitted workflow; publish and verify a release from the exact merged commit; and deliver a final evidence report with known limitations.

**The end state is not “code added.” The end state is “a specific source commit, its tests, its public API contract, benchmark evidence, release artifacts, release notes, checksums, and cloud verification all agree.”**

Do not ask the operator questions for details that are discoverable from the repository, GitHub metadata, project configuration, toolchain, or public research. Use reasonable engineering judgment and continue autonomously. Ask for human action only when genuinely required, such as required PR approval, inaccessible organization policy, missing authorized credentials, a billable real quantum hardware run, or a secret that must be provisioned by the owner. Do not bypass those blockers.

## 1. Core principles — non-negotiable

1. **Correctness before speed.** A correct, bounded, slower answer—or explicit `UNRESOLVED`/unsupported status—is preferable to a fast fabricated answer.
2. **Mathematical claims must be derived and scoped.** A theorem about one model, distribution, gate set, oracle model, physical system, or metric does not automatically prove a statement about another.
3. **Tests must independently check behavior.** “No exception,” “same support key,” “shader compiled,” “job completed,” or “two implementations share code” is not enough to prove mathematical correctness.
4. **No fake results.** Never fabricate counts, probabilities, expectation values, GPU telemetry, hardware access, error bars, benchmark records, cloud deployment success, release assets, or formal proof status.
5. **Fail closed.** Unknown gates, invalid QASM, invalid indices, unsupported control flow, exceeded memory/time budget, untrusted approximation, unavailable native extension, unverified result metrics, and failed references must result in an explicit error or unresolved result—not an identity operation, silent fallback, guessed output, or false success.
6. **Do not weaken a gate to make CI green.** Never delete or skip a failing test, loosen tolerance without a derivation, silently reduce test coverage, hide warnings, turn required checks into optional checks, or modify the expected result to match a suspect implementation.
7. **Hypotheses are not results.** Every research hypothesis must be marked `PROPOSED`, `SUPPORTED`, `REJECTED`, or `INCONCLUSIVE`, with experiment IDs, code revision, datasets, environment, results, and decision rationale. Do not describe a hypothesis as SOTA until evidence supports the exact scope of the claim.
8. **Hardware honesty.** Shader source compiles, SPIR-V validates, software Vulkan dispatch, physical GPU dispatch, and end-to-end GPU simulator acceleration are different evidence levels. Report each separately. Never infer a physical GPU run from CI on a software ICD.
9. **Evidence is durable.** Save commands, exact exit status, environment, baseline SHA, relevant output, benchmark JSON, artifacts, CI URLs, release SHA and checksum outputs into tracked audit records. Never save secrets, sensitive environment output, or raw auth headers.
10. **Preserve operator work.** Before editing, inspect `git status`. Do not run destructive cleanup commands, overwrite pre-existing modifications, or discard untracked work. Preserve the current historical research/audit ledger. If the existing `GEMINI.md` is still present, read it and reconcile valid operational details; do not destroy prior evidence merely to install this plan.
11. **Safe Git behavior.** Work on a focused feature branch. Do not force-push, rewrite public history, delete published tags, bypass reviews, disable branch protection, or push straight to a protected default branch. Use a PR and repository-authorized merge method.
12. **Secure credentials.** Do not paste tokens into this file, code, URLs, command output, issue text, commits, logs, artifacts, or final reports. Do not run `echo $GITHUB_TOKEN`, `set`, `env`, or analogous commands that dump secrets. Use existing `gh auth`, Git credential helper, host-managed `GITHUB_TOKEN`, or approved secret manager. Use least privilege and short-lived credentials where available. If auth is absent, report the blocker; never search the filesystem for leaked tokens or invent credentials.
13. **No secret-handling shortcuts.** Never disable TLS verification, use `--insecure`, embed a PAT in a remote URL, reduce repository visibility, turn off security scanning, or grant workflow-wide write permissions only to make a release work.
14. **Do not claim work that did not run.** Label every gate `PASS`, `FAIL`, `SKIP` with reason, `BLOCKED`, or `NOT RUN`. A skipped device test is not a pass. A green badge is not proof that all required jobs ran.
15. **No premature final message.** Report mission completion only after the exact final commit and release criteria below have evidence. If a real external blocker remains after reasonable attempts, report `BLOCKED` with evidence, not “perfect,” “done,” or an equivalent false claim.

## 2. Live discovery and baseline lock

The repository facts in this file are snapshots from 2026-10-29, not permanent truth. At mission start, refresh the default branch, current head, tags, releases, open PRs, current workflows, and current OpenAI Math and simulator research.

### 2.1 Safe repository inspection

Run or achieve the equivalent of:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
git log -10 --oneline --decorate
git tag --list 'v*' --sort=-version:refname
```

Then query the live GitHub repository for:

- default branch name, head SHA, last push time, tags, latest stable release and release assets;
- open/closed PRs relevant to the next stable release;
- recent CI, Nightly, and Release workflow runs and their exact SHA/conclusion;
- branch protection/rulesets and required checks, when the current credentials allow reading them;
- current workflows (`.github/workflows/ci.yml`, `nightly.yml`, `release.yml`), `cloudbuild.yaml`, `scripts/package_release.ps1`, `scripts/generate_sbom_and_checksums.py`, and `scripts/check_version.py`;
- actual state of `GEMINI.md`, `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `docs/`, `research/`, `audit/`, `pyproject.toml`, `CMakeLists.txt`, and current tests.

If the checkout is stale, fetch the remote. If the worktree is dirty, make a read-only inventory of each modified/staged/untracked file and preserve it. Never use `git reset --hard`, `git clean -fdx`, `git checkout -- .`, `git restore .`, or another destructive command to create a convenient baseline.

### 2.2 Baseline record

Create a new versioned audit area such as `research/v2_4/` (or the convention established by the live repository) with:

- `BASELINE.md`: exact source SHA, release baseline, platform/toolchain, Python/Qiskit/NumPy versions, build options, Vulkan ICD/device class, package versions, and known pre-existing changes;
- `HYPOTHESES.md`: falsifiable research hypotheses, priorities, predictions, success/failure criteria;
- `LITERATURE_MAP.md`: source, revision/date, claim scope, formalization/review status, transferability and implementation decision;
- `TEST_MATRIX.md`: all gates, actual commands, outcomes, durations, skipped/blocked reason, and evidence links;
- `EXECUTION_LOG.md`: chronological immutable-ish record of audit/fix/build/test/cloud iterations;
- `FINDINGS.md`: defect IDs, severity, root cause, minimal repro, regression test, fix commit, and current disposition;
- `BENCHMARK_PROTOCOL.md`: workload definitions, reference versions, statistics, hardware and performance rules;
- `RELEASE_AUDIT.md`: exact version/tag/SHA, assets, checksums, SBOM, CI run URLs, documentation state, known limits.

Use atomic, append-only logs where practical. Do not rewrite a historical audit in a way that erases how a defect was found or which earlier commit its result describes.

### 2.3 Inventory the current implementation

At minimum inspect the current versions and public contracts of:

- `cqhecs/circuit_parsing.py`, `gate_lowering.py`, `gate_manifest.py`, `circuit_analyzer.py`, `router.py`, `result.py`, `backend.py`, `provider.py`, `cli.py`, `scheduler.py`, `circuit_library.py`;
- `cqhecs/backends/path_a_stabilizer.py`, `path_b_stabilizer_rank.py`, `path_c_mps_exact.py`, `path_d_sparse_pauli.py`;
- native public APIs, C/C++ parser(s), MPS/statevector/stabilizer engines, Vulkan contexts/pipelines/engines, shaders, Python bindings, and CLI bridge;
- the full tests directory, CTest inventory, fuzzing/mutation harness, native-artifact checks, benchmark generators/runners and stored results;
- `GEMINI.md`, `README.md`, `ARCHITECTURE.md`, `CQ-HECS-V2-ROADMAP.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/*`, `research/next_stable/*`, `research/v2_1/*`, `research/v2_2/*`, and the latest relevant `audit/*` files.

Do not assume that historical audit findings are still defects. Reproduce them against live code or explain why they are already fixed/not reproducible. A previous green test run is not a substitute for running current code.

## 3. Mission scope and version policy

Primary mission:

1. protect and correct scientific/result contracts;
2. extend evidence and test depth;
3. use OpenAI Math and relevant real-quantum/classical-emulation research to formulate and test improvements;
4. deliver at least one meaningful, well-validated improvement if the evidence supports it;
5. build a reliable cost-aware path selection and benchmark story where feasible;
6. preserve clean architecture and isolate experimental modules;
7. finish local verification before GitHub push;
8. self-heal cloud CI failures without bypassing gates;
9. update public docs/reports as the final source-content change;
10. merge and publish a verified release only from the correct, green, exact source commit.

Versioning is evidence-based:

- Use `v2.4.0` if this cycle actually lands a backward-compatible new public capability or algorithm that has acceptance tests and proper docs.
- If the cycle only corrects bugs/contracts and adds no substantive new capability, use the correct patch version, e.g. `v2.3.1`.
- If compatibility breaks, stop and justify whether a major version is warranted; do not make a breaking change under a minor release merely to hit the target name.
- Do not pre-commit a version number before the scope is known. Record the decision and why it follows SemVer.

`main` was the observed default branch at preparation. The task wording may say “master,” but always discover the live default branch and use it. Never create or merge to a nonexistent `master` just because the mission text mentions it.

## 4. Scientific scope: definitions and boundaries

CQ-HECS is a **classical emulator of quantum circuits**, not a quantum processor. In this mission, “real quantum research” means using current quantum algorithms, physical-circuit models, quantum-hardware workflows and papers as relevant targets or validation references. Any actual hardware run is optional, separately authenticated and cost-controlled; it must never be faked in CI. Do not represent a classical simulator result as a physical quantum measurement.

The current four path classes have different contracts and limits:

- **Path A — Stabilizer tableau:** fast classical simulation of the supported Clifford subset; not a general universal-gate simulator.
- **Path B — Stabilizer-rank/decomposition:** useful for appropriate low-non-Clifford circuits; complexity grows rapidly as rank/term count rises.
- **Path C — MPS/tensor chain:** useful for circuits with manageable entanglement under the chosen chain ordering; numerical SVD and the current rank floor must be represented honestly.
- **Path D — sparse Pauli/Heisenberg propagation:** the current certificate applies to supported expectation values. It does not automatically certify the full measurement distribution. Optional independent-marginal samples must never be presented as the joint quantum output distribution.

New methods must supplement—not overstate or erase—these specializations. There is no credible goal of making arbitrary universal quantum circuit simulation polynomial-time by assertion. Worst-case classical simulation can require exponential resources; exploit structure, report costs and refuse unsupported guarantees.

### 4.1 A claim ledger for all public wording

For every claim such as “exact,” “certified,” “SOTA,” “GPU-accelerated,” “supports 500 qubits,” “uses X MB,” or “faster than Y,” record:

- precise claim;
- relevant code path and version;
- assumptions, workload class and input semantics;
- mathematical/numerical definition;
- reference method;
- test/benchmark evidence;
- hardware/software environment;
- conditions where it does not apply;
- source location in README/docs/RELEASE_NOTES.

If the evidence cannot support the wording, change the wording or add the missing evidence. Never change the underlying evidence merely to protect a marketing statement.

## 5. Current public research baseline to verify live

Refresh all URLs and revision dates at execution time. This is a starting map, not a frozen or exhaustive literature review.

### 5.1 OpenAI Math — treat as research data, not automatically verified truth

Primary upstream:

- Repository: <https://github.com/openai/math>
- README and verification caveats: <https://github.com/openai/math/blob/main/README.md>
- History: <https://github.com/openai/math/blob/main/history.md>
- Overview/results map: <https://github.com/openai/math/blob/main/overview.tex>
- Lean formalization catalogue: <https://github.com/openai/math/tree/main/lean>

As of the web check on 2026-10-29, upstream surfaces reported roughly 721 manuscripts across 373 result families, with approximately 42% of headline/top-line results formalized; different indexes may show different counts/definitions. **Never hardcode these counts as current truth.** Query upstream manifest/history at mission start, record exact commit SHA, date, schema, counts and method used to distinguish paper, family, headline result and formalization. OpenAI explicitly describes the repository as raw research data at differing verification stages; some manuscripts are not Lean-formalized and may contain issues. Do not treat “there is a related Lean file” as proof that a paper’s headline claim has been formally verified.

Required transfer classifications:

- `DIRECT_TRANSFER`: method/lemma is mathematically applicable to an implemented operation and preconditions are met;
- `ADAPTABLE`: promising, but assumptions, cost model, or domain require a new derivation/prototype;
- `VALIDATION_ONLY`: useful as a mathematical constraint, boundary, or test oracle but not a new algorithm;
- `NEGATIVE_RESULT`: narrows/blocks an invalid claim or algorithmic direction;
- `NOT_RELEVANT`: not materially relevant to quantum circuit simulation or project submodules;
- `UNVERIFIED_RESEARCH`: cannot be used as the basis of a stable claim until independently checked.

For each candidate, record paper ID/title, upstream permalink, revision/date, paper version, primary claim, computational model, assumptions, proof status, formalization file/claim (if any), relevance to the code, expected benefit, failure mode, exact experiment/test, and decision. Read the relevant primary source, not just its filename, abstract, or the project’s old summary.

#### OpenAI Math topic families to investigate

1. **Quantum complexity and oracle/query lower bounds.** Use them to ground what complexity claim is and is not justified. A query-complexity theorem does not provide a gate-level classical simulator; oracle truth tables may hide exponential work. Do not infer a universal simulator from a speedup/lower-bound theorem.
2. **Quantum information and unitary synthesis.** Useful for exact gate identities, circuit construction, and model semantics. A polynomial-size quantum circuit is not itself a classical simulation method.
3. **Mathematical physics / quantum many-body / spin systems.** Potentially relevant to Hamiltonian evolution, correlations, entropy, symmetry sectors, physically structured benchmark families, or observables. Derive the exact mapping to the implemented gates/state representation before adopting it.
4. **Tensor, graph, Fourier and combinatorial algorithms.** Potentially relevant to contraction planning, graph separators, structured tensor contractions, and workload preprocessing. A theorem about exact arithmetic or a special algebraic circuit model must not be silently applied to floating-point tensor contraction.
5. **Probability, concentration and sampling.** High relevance for statistical confidence statements, sampling error, random benchmarks, and confidence intervals. Verify the random-variable assumptions, support size, dependence assumptions, metric and confidence level.
6. **Formal proof and Lean artifacts.** Use to prove selected small algebraic invariants (e.g. gate decomposition, Pauli rewrite, Boolean/symplectic identities). Connect each formal theorem to a separately tested implementation. The theorem proves the formal model, not memory safety, parser correctness, or the compiled GPU kernel by itself.
7. **SAT/complexity/ETH claims.** Relevant only to the SAT/constraint modules or project complexity statements. Any extraordinary complexity claim is `UNVERIFIED_RESEARCH` until independently scrutinized. Do not transfer it to quantum circuit emulation without a rigorous reduction matching the actual input and output model.
8. **Pure number theory, geometry, PDE or unrelated mathematics.** Skip unless a concrete code path and mechanism are identified. “Mathematically impressive” is not a transfer criterion.

#### Specific OpenAI Math families to triage explicitly

The CQ-HECS repository's earlier audit identified several concrete families. Re-open their current upstream pages/papers and check that IDs/titles have not changed before drawing conclusions:

| Family / theme | Transfer hypothesis | Safe decision before verification | Required verification |
|---|---|---|---|
| **130 — faster structured Fourier-transform circuits** | Could inspire a fast path for a *matching structured transform* or a contraction subproblem if CQ-HECS encounters the same algebraic structure. | `ADAPTABLE`, not direct transfer. The published model may assume exact complex arithmetic, supplied roots of unity, unrestricted coefficients, or special indexing; these are not automatically equivalent to float64 tensor contraction. | Formalize the exact subproblem; compare operation counts and wall time against standard FFT/structured transform baselines; test floating-point stability and all input-size assumptions. Do not claim a general simulator speedup. |
| **273 — entropy photon-number inequality / bosonic information** | Potentially relevant only if a future scope adds bosonic modes, photonic circuits, Gaussian states or continuous-variable quantum simulation. | `RESEARCH_ONLY` for the current qubit-only stable core. | Determine whether the current state representation and gates can express the paper's physical model. If not, record as out of scope; do not force a qubit mapping without an explicit derivation. |
| **275 — QMA-hardness of continuum Coulomb energy** | Helps ground limitations and future chemistry/many-body use cases; can inform realistic benchmark discussion. | `VALIDATION_ONLY` / complexity boundary, not a simulator algorithm. | Check the theorem's input model and promise conditions. Use it to prevent overclaiming efficient generic ground-state simulation; do not infer new runtime guarantees for the existing circuit backends. |
| **279 — exact quantum factoring over a fixed gate set** | Could provide a high-value *benchmark circuit family* for exact gate-set semantics and resource scaling, once a reproducible circuit generator and exact circuit specification are available. | `VALIDATION_ONLY` for target workload construction, not a classical factorization/simulation shortcut. | Compare circuit construction, gate set, success semantics and end-to-end circuit simulation. An efficient quantum circuit family does not establish efficient classical simulation of its states. |
| **283 — unitary synthesis from a Boolean oracle** | Useful to test understanding of oracle models and gate/circuit representation. | `NEGATIVE_RESULT` for any claim that oracle-assisted synthesis yields a free classical simulator. | Account for the cost and representation of the target-dependent oracle, including potentially exponential truth-table information. Never hide oracle work outside a complexity ledger. |
| **284 — randomized versus quantum query complexity** | Can ground the project's statements about quantum/classical complexity and benchmark-model boundaries. | `VALIDATION_ONLY` / complexity boundary. | Keep query complexity, gate complexity, classical simulation time and output-sampling complexity separate. Do not treat a query lower bound as a constructive circuit simulator. |
| **Quantum many-body / spin-system families** | May provide benchmark Hamiltonians, correlation observables, symmetries, and geometry-sensitive workloads. | `ADAPTABLE` per individual manuscript. | Map a concrete Hamiltonian/Trotter circuit or observable to supported CQ-HECS instructions; verify physical parameters, approximation order, boundary conditions and reference values. |
| **Sampling / concentration / probabilistic families** | May improve sample confidence reporting and workload generation. | `ADAPTABLE` for the exact result only after derivation. | Prove the inequality under the actual independence/support assumptions; name the metric, delta/confidence, support size, and any clamping. Never substitute a theorem for a distribution with different assumptions. |

The earlier local audit has its own supporting notes under `research/v2_1/openai_math/`. Treat those as historical reasoning, not as a current upstream verification. Preserve them, re-check each primary source and add a fresh result for every new decision.

Do not implement manuscripts wholesale. Extract a small, auditable mathematical claim, define its assumptions, prove relevance, write a minimal prototype, test against trusted references, benchmark, and retain or reject it.

### 5.2 Real quantum and high-performance emulator references

Use these as evolving reference implementations and literature sources, not as a claim that CQ-HECS must beat every feature in them.

- **Stim:** <https://github.com/quantumlib/Stim> — high-performance stabilizer simulation and sampling, including vectorization and reference-frame sampling. Compare compatible Clifford workloads; do not compare incompatible output semantics.
- **qsim:** <https://github.com/quantumlib/qsim> — high-performance dense statevector emulator, gate fusion, CPU vectorization and multithreading. Use for small/medium exact differential tests and CPU performance baselines where the gate sets match.
- **Qiskit Aer Simulator:** <https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html> and <https://qiskit.github.io/qiskit-aer/tutorials/1_aersimulator.html> — statevector, density matrix, stabilizer, extended stabilizer, MPS and GPU tensor-network modes. Pin exact Aer version and options; make truncation/noise/precision explicit.
- **NVIDIA cuQuantum / cuTensorNet:** <https://docs.nvidia.com/cuda/cuquantum/latest/> and <https://docs.nvidia.com/cuda/cuquantum/latest/cutensornet/> — useful reference for contraction-path optimisation, memory-aware slicing, autotuning and tensor-network execution. This is CUDA/NVIDIA-oriented; it is not a drop-in AMD/Vulkan backend. Use it as a conceptual/reference comparator unless hardware/API compatibility is explicitly established.
- **2D tensor-network emulation research:** Rudolph & Tindall, “Simulating and sampling from quantum circuits with 2D tensor networks,” *npj Quantum Information* (published 2026-09-24), DOI <https://doi.org/10.1038/s41534-026-01372-2>. The paper describes a generalized boundary-MPS contraction method and controlled state/sample convergence for physically motivated 2D circuits, with GPU speedups in its evaluated setup. This is a strong research candidate, not a guarantee that a reimplementation will improve all circuits.
- **Qiskit / OpenQASM:** <https://qiskit.org/> and <https://openqasm.com/> — use their documented gate, measurement, classical-bit and transpilation semantics. Do not advertise OpenQASM 3 support merely because a native parser file exists; validate the actual public path end to end.

For every comparator, pin exact package/commit/version and options. Keep optional dependencies optional unless the project explicitly changes its support policy. Never let the reference implementation call the same buggy CQ-HECS helper that it is supposed to check.

## 6. Falsifiable research hypotheses

Create or update `research/v2_4/HYPOTHESES.md`. Give each hypothesis an ID, priority, assumptions, prediction, implementation cost, minimal test, benchmark, threshold, risks, and decision. Run low-cost falsification experiments first. Do not merge a new backend into auto-routing before it meets its own gates.

### H0 — Result-metric contract may permit misleading distribution-level composition

**Priority:** P0; investigate immediately.  
**Basis:** Current code structure separates observable and distribution metrics but has a `total_error_bound` property that composes fields conditionally. Path D’s optional marginal sampling is explicitly not a valid joint output distribution.  
**Hypothesis:** There exists a result combination in which an observable-space bound or an error bound excluded from samples is serialized as a total-variation bound for a distribution.  
**Experiment:** Test `SimulationResult.total_error_bound` and `to_dict()` for (a) expectation-only, (b) ordinary sampled counts, (c) Path-D marginal counts with `counts_are_joint_distribution=False`, (d) unresolved result, (e) zero/one support, (f) absent numerical bound, and (g) multiple confidence levels. Trace each field’s metric/source through the constructors.  
**Acceptance:** No composition unless all terms bound the same target quantity/metric and the combined confidence interpretation is valid. Invalid compositions return `None` or a specifically named metric-bound field, not a misleading TV bound. Preserve backwards compatibility only if the semantics remain truthful; otherwise version the schema and document migration.  
**Reject condition:** If full code audit demonstrates the suspected path cannot occur, save a minimal proof/negative test and classify `NOT REPRODUCED`; do not make an unnecessary API change merely because this plan suggests a risk.

### H1 — Path C's numerical rank floor may conflict with `exact=True` / `error_bound=0`

**Priority:** P0/P1.  
**Basis:** Current documentation describes a relative SVD rank floor near `1e-13` and says discarded spectral mass is a diagnostic rather than a globally propagated numerical error bound.  
**Hypothesis:** A nonzero singular value can be removed by the rank floor, while the result still appears exact in a way that a user could read as mathematical exactness.  
**Experiment:** Construct near-degenerate/ill-conditioned gate sequences where the exact small-system statevector is known; log singular spectrum, retained/discarded values, normalized-state fidelity, observable deviation and metadata. Include values near the threshold and multiple SVD steps.  
**Acceptance:** Either (a) the code uses an explicitly documented numerical-zero rule with defensible threshold analysis, or (b) all discarded nonzero spectral mass marks the output as numerically approximated and any valid propagated bound is derived, or (c) the discarded mass stays diagnostic-only and `exact` is defined narrowly as “no deliberate approximation beyond the documented algorithmic rank rule” with unambiguous separate numerical status. Do not label a spectral diagnostic a rigorous global bound without proof.  
**Required tests:** before/at/after floor, degenerate spectrum, repeated truncations, normalization, resource refusal, and differential reference checks.

### H2 — Cost-aware routing will improve workload selection versus fixed thresholds

**Priority:** P1.  
**Hypothesis:** A cost model calibrated on historical workloads can reduce total/geometric-mean runtime or memory failure rate versus the current fixed thresholds, without changing output contracts.  
**Features to evaluate:** qubit count, gate count, non-Clifford count/rank proxy, gate topology/interaction graph, estimated MPS bond growth, number of observables and term count, shots, required output form, memory budget, CPU/GPU capabilities, and confidence in each estimate.  
**Protocol:** First build a labelled workload set and collect actual time/RSS/peak memory/term counts per path. Use train/validation split by *circuit family* rather than random adjacent circuits to avoid leakage. Start with explainable cost heuristics; only consider learned prediction if a simpler model clearly underperforms and maintenance cost is justified.  
**Acceptance:** Show measurable improvement on held-out families while exactness/refusal contracts remain unchanged. Document cases where the prediction is wrong. Add deterministic fallback based on established capabilities/resources when estimates are unavailable.  
**No-go:** Do not claim “optimal router”; use “cost-aware heuristic” unless a formal guarantee exists.

### H3 — A graph-aware tensor-network contraction planner will cover some workloads Path C handles poorly

**Priority:** P1 research / P2 stable integration.  
**Hypothesis:** Converting supported unitary circuits to an explicit tensor network, estimating graph/treewidth structure, searching contraction orders and slicing selected indices may solve some 2D/local-topology or low-treewidth workloads within lower peak memory than fixed MPS ordering.  
**Research basis:** 2D tensor-network sampling paper by Rudolph & Tindall (2026-09-24) and cuTensorNet’s published contraction-path/slicing/tuning capabilities.  
**Prototype:** Add a separate `experimental_tensor_network` module or backend; do not refactor all existing paths at once. Support a deliberately narrow first set of unitary circuits and output modes. Implement a straightforward reference contraction for small systems before optimising. Then compare greedy/min-fill/search-based contraction ordering, graph separators and memory-bounded slicing.  
**Tests:** tensor-network identity against small dense statevectors, gate axis/permutation tests, complex conjugation conventions, global phase where applicable, contraction-order invariance, slicing invariance, probability normalization, observable agreement, output sampling accuracy, memory ceiling, deterministic plan seeds, refusal when estimated/actual resource budget exceeds limit.  
**Acceptance:** Exact small-system parity with reference within the declared floating-point tolerance; for approximate state/sample generation use a valid, correctly scoped error estimate or label it uncertified; at least one named workload class shows a reproducible improvement versus Path C under identical CPU/resources and against a reasonable independent baseline.  
**No-go:** Do not let a greedy plan that happens to work on GHZ be used as proof of broad 2D advantage.

### H4 — Adaptive MPS qubit ordering may lower bond growth on selected circuits

**Priority:** P1 research.  
**Hypothesis:** Graph-aware physical/logical qubit order or swap-routing heuristic can reduce peak bond dimension/working-set size for some structured circuits.  
**Experiment:** Compare natural order, interaction-graph ordering, min-cut/heuristic ordering, and baseline; record planning overhead, peak bonds, SVD time, total time and result correctness. Use same circuits and seeds across variants.  
**Acceptance:** Keep a heuristic only if it improves overall cost after including reordering/routing overhead on held-out workloads. The circuit permutation must preserve measurement/classical-bit ordering or correctly invert it in the result. Every permutation gets round-trip tests and asymmetric circuits.

### H5 — Path A can benchmark against a highly optimised stabilizer reference before custom low-level optimisation

**Priority:** P1.  
**Hypothesis:** The current tableau path leaves performance on the table on repeated high-shot Clifford workloads relative to vectorised/reference-frame techniques.  
**Experiment:** Compare CQ-HECS, Stim, and Aer stabilizer on compatible noiseless and supported noisy Clifford workloads. Separate circuit-compilation/setup time from steady-state shot generation; test 1, 100, 10,000 and larger safe shot counts.  
**Potential transfer:** vectorized bit-packed state, efficient tableau representation, reusable compiled sampler/reference sample, bulk shot generation, careful memory layout.  
**Acceptance:** Reproducible improvement or a clearly documented reason not to duplicate a mature external method. If a Stim adapter is added, keep it optional and preserve a self-contained implementation; test gate and result semantics against a separate path. Never route silently through an external dependency that is absent in a clean install.

### H6 — Path B can improve some low-non-Clifford circuits through decomposition/search improvements

**Priority:** P1/P2.  
**Hypothesis:** Canonical phase/branch merging, duplicate stabilizer-term aggregation, memoization and better decomposition planning reduce runtime for selected low-T circuits without changing values.  
**Experiment:** Compare term count, peak memory, elapsed time, branch cancellations and exact small-system output against dense statevector/Aer extended stabilizer. Use circuits with T-counts near the existing threshold and controlled scaling of qubit count/depth.  
**Acceptance:** A term-count reduction alone does not suffice; require end-to-end improvement and equal result semantics. If a pruning/sampling estimator is added, derive and test its own statistical/error guarantee; do not reuse a deterministic truncation bound as a distribution bound.

### H7 — Path D can be more expressive and efficient when observables are selected intentionally

**Priority:** P1.  
**Hypothesis:** Sparse Pauli propagation with explicit observable selection, commutation/cancellation rules, support-aware batching and term-growth diagnostics will handle some tasks faster than complete-state simulation.  
**Scope candidates:** arbitrary valid Pauli strings; supported Pauli Hamiltonian expectation values; correlation functions; explicit per-observable result bounds; reusable backwards-propagated terms for repeated queries where mathematically valid.  
**Tests:** all single/two-qubit conjugations against matrices; Pauli phases including `XZ` convention; random Clifford conjugation; sparse term merging/cancellation; output bound versus exact statevector; bound on every returned observable; early unresolved return; large support masks; repeated and identity factors; no accidental promotion to a joint distribution.  
**Acceptance:** Only advertise supported observables. If batching reports a combined bound, explicitly state whether it is (a) a bound for each observable, (b) a bound on a vector/max norm, or (c) a sum bound; do not conflate these. Avoid double-counting/loss of per-observable bounds unless the stated combined bound rigorously covers it.

### H8 — Probability/concentration methods can tighten and correct sampling contracts

**Priority:** P0/P1.  
**Hypothesis:** Some existing confidence-bound helper(s) may confuse per-outcome additive error with total-variation distance or fail to scale conservatively with support size.  
**Experiment:** Re-derive every inequality from a primary source; enumerate support size 1, 2, small K, K=2^n, large K, low/high shots and valid delta. Use small exactly known distributions and Monte Carlo as a sanity check, while understanding that simulation is not proof.  
**Acceptance:** Each bound names the target metric, support assumptions, dependence assumptions, confidence level, and clamping behavior. Tests validate edge cases, while documentation includes the formula and references. A distribution-free TV bound may become vacuous for large support; it must be reported as vacuous rather than quietly replaced with a stronger false bound.

### H9 — Genuine end-to-end Vulkan acceleration is possible only after the CPU/native semantics stabilize

**Priority:** P2 experimental; no mandatory stable claim.  
**Hypothesis:** Selected tensor contraction or state-update kernels can outperform the CPU reference on some AMD Vulkan devices after upload, dispatch, synchronization and readback overhead.  
**Plan:** Choose one complete workload and one GPU pipeline. Implement CPU/GPU equivalence tests first, then real-device smoke test and validation-layer run, then warm/cold benchmark protocol. Include transfer/compile time and kernel time separately and report end-to-end wall-clock time.  
**Acceptance:** On a documented physical device, the kernel genuinely executes on device; all output matches CPU reference within declared tolerance; no Vulkan validation errors or unhandled device-loss/resource failures; measured improvement exceeds noise on a declared workload. If no available physical device/runner exists, leave the full path `EXPERIMENTAL` or `PHYSICAL_GPU_UNVERIFIED`; do not invent result data.  
**Hardware portability:** Keep CPU path available. Feature-detect Vulkan capabilities. Do not hard-code assumptions about vendor, shaderInt64, subgroup width, memory heaps, or driver behavior.

### H10 — Real quantum hardware as an optional external validation adapter

**Priority:** P2 optional; never a release prerequisite unless authorized.  
**Hypothesis:** A provider adapter can give CQ-HECS a reproducible path to submit a small compatible circuit to real quantum hardware and compare observed counts to the ideal simulator and a declared noise-aware model.  
**Scope:** Use documented Qiskit BackendV2/provider interfaces or a separately maintained adapter. Hardware execution is a different mode from emulation. Require explicit user opt-in, bounded shots/cost, hardware backend name, calibration/noise snapshot time, job ID, transpiled circuit hash, seed/options where supported, and clear quantum-hardware provenance.  
**Testing:** unit tests use mocks/fakes for successful jobs, timeouts, provider errors, job failure, partial result, quota/credential absence, cancellation and invalid calibration snapshots. Real-device test is manual/explicit and must not run automatically in public CI. Keep API credentials in local secure keychain/CI secret store, never repository files.  
**Acceptance:** No credentials = clear `SKIPPED/BLOCKED` external check, not fake success. Simulator output is not relabelled as hardware output. A noisy hardware histogram should be compared via appropriate statistical/noise metrics, not required to equal ideal statevector counts.

### H11 — QASM/IR contract can be made more uniform without pretending unsupported dynamic semantics exist

**Priority:** P1.  
**Hypothesis:** A canonical IR that explicitly carries qubits, classical bits, parameters, global phase, register offsets and measurements will reduce divergence across Qiskit/OpenQASM/native paths.  
**Plan:** First define and test the current supported semantics. Then add required IR fields in a backward-compatible way or schema-version the IR. Keep `reset`, mid-circuit measurement, classical branches and noise unsupported until there is a correct execution model across all intended paths.  
**Acceptance:** Every format either maps to the same semantics or returns a structured refusal. Do not advertise broad OpenQASM 3 support based solely on the existence of a C++ parser source file.

### H12 — Formal methods can protect algebraic rewrites and data contracts

**Priority:** P2.  
**Hypothesis:** A small Lean/math proof set or symbolic verification pipeline can reduce regressions for a few high-risk identities.  
**Candidates:** composite-gate lowering identities; Pauli conjugation and sign/phase rules; symplectic Clifford updates; composition conditions for bounds; parser/index arithmetic invariants.  
**Plan:** Formalize one small, self-contained property; connect it to executable matrix/property tests; record exact theorem and implementation correspondence.  
**Acceptance:** Only claim a formal proof for exactly the theorem checked by the proof toolchain. Do not present Lean compilation as proof that the compiled Python/C++/GLSL implementation has no bugs.

### H13 — Circuit cutting/partitioning can be useful for some topology and memory regimes

**Priority:** P2 experimental.  
**Hypothesis:** Cutting selected circuit edges or partitioning a circuit into subcircuits may reduce per-task memory enough to solve some workloads that exceed Path C's memory envelope.  
**Research question:** Does the reduction in subcircuit size outweigh the number of fragments, quasiprobability/shot overhead, reconstruction work and combined statistical error?  
**Plan:** Implement only a tiny benchmark prototype; choose cuts from an interaction graph; quantify fragment count and predicted estimator variance before execution. Compare with whole-circuit MPS and an exact statevector for small instances.  
**Tests:** reconstruction matches exact probabilities/observables on tiny circuits; sample budget and confidence are explicit; cut reconstruction has no silent missing fragments; timeout/memory ceilings work; wrong or unsupported cut configurations refuse.  
**Acceptance:** Keep only if a named workload family improves the defined resource metric with a valid combined error/confidence statement. This is not a free exponential-speedup technique.

### H14 — Density-matrix, noisy trajectory or MPO simulation should be a separate capability, not an implicit extension

**Priority:** P2/future.  
**Hypothesis:** A future noise-aware backend can support a restricted subset of noise channels more efficiently than dense density matrices, using stochastic trajectories or matrix-product operators when the physical/circuit structure permits.  
**Scope guard:** This is not required for v2.4.0 unless a small, correct, well-tested feature fits the release. Do not let a unitary-only parser accept reset/noise/classical control just because one experimental backend implements a subset.  
**Tests if prototyped:** CPTP map constraints, trace preservation, positivity where the representation promises it, known channels, seeded ensemble statistics, density-matrix/statevector comparison in noiseless limit, noise-model provenance, and resource refusal.  
**Acceptance:** Exact noisy semantics and approximation status are clear; no implicit “unitary simulation” label for a noisy result.

### H15 — Symmetry/subspace reductions can reduce work when the invariant is proven

**Priority:** P2.  
**Hypothesis:** Circuit/Hamiltonian symmetries can identify an invariant subspace and reduce effective dimension for selected workloads.  
**Plan:** Start with a small number-conserving or parity-conserving circuit family. Verify the proposed symmetry operator commutes with every gate or preserved channel; check initial-state membership and mapping back to requested outputs.  
**Tests:** random circuits satisfying/failing the symmetry condition; compare reduced and dense exact outputs; inject one symmetry-breaking gate and verify that reduction is rejected; test degeneracy and measurement remapping.  
**Acceptance:** Automatic reduction only when preservation is mechanically established. A false symmetry detection is a correctness bug; otherwise keep it opt-in/experimental.

## 7. Research ranking and mandatory decision record

Rank candidates with a transparent score, not intuition alone. Suggested scale 1–5:

- direct relevance to CQ-HECS workload;
- strength/independence of evidence;
- potential correctness or performance benefit;
- implementability in this release;
- risk/complexity (reverse score);
- ability to create an independent test oracle;
- fit with portable CPU + AMD/Vulkan objectives.

P0 correctness tasks are not displaced by a high feature score. Among feature candidates, prototype at most one major architectural method in parallel with stable hardening unless the team/context can keep tests independent. For every non-selected method record `DEFER`, `REJECT`, or `RESEARCH_ONLY`, with rationale. Do not keep unbounded speculative branches alive.

## 8. Architecture requirements for any new implementation

1. **Small, reviewable modules.** Keep new experimental algorithm(s) in separately named modules. Do not mix unverified research code into mature Path A/B/C/D code before benchmarks and correctness gates pass.
2. **Canonical circuit/observable IR.** Define qubit order, bit order, angles, global phase, register mapping, measurements, classical bits, supported gates and parameter domains. Schema changes need compatibility tests.
3. **Capability manifest is source of truth.** Analyzer, router, backend, Qiskit Target and docs should derive from or be validated against one machine-readable contract. A route advertised as supported must either execute correctly or refuse before expensive state mutation.
4. **Cost estimate has uncertainty.** Report estimations as estimates, including whether a value is measured, derived, heuristic, or unavailable. A guessed peak memory number is not a hard cap.
5. **Atomic resource refusal.** Estimate large allocations before allocation where possible. If an operation fails after partial internal updates, prevent those partial states from being returned as successful circuit output; restore state or mark it invalid/unresolved.
6. **Error contracts are typed and metric-specific.** Define whether an error bound applies to state norm, fidelity, expectation-value absolute error, per-outcome probability, TV distance, energy, or another metric. Do not compare or sum unlike quantities.
7. **Determinism.** Explicit seeds; record seed and RNG/version in metadata when relevant. Do not demand identical random streams from independent libraries.
8. **No hidden fallback.** Auto routing may try another backend only on explicit, safe capability/resource failures if the circuit state is unchanged and the fallback supports the requested output contract. Programming errors must propagate.
9. **Correct global phase and endianness.** Preserve qubit/bit-order convention through parsing, transpilation, gate lowering, statevectors, counts and native adapters. Matrix equality may be up to global phase only when the public contract explicitly permits it; otherwise compare the full unitary.
10. **Resource budgets cover more than retained tensors.** Distinguish persistent tensor bytes, temporary contraction/SVD workspace estimates, disk-paged bytes, measured process RSS/peak RSS, and GPU memory. Explain whether the configured budget is a strict enforcement or a preflight estimate.
11. **Optional dependencies remain optional by default.** A clean CPU-only install must not require a GPU SDK or hardware credential. An optional research extra must be tested as optional and as installed.
12. **No dependencies with incompatible license or hidden network requirement.** Check license, maintenance status, platform support, transitive dependencies, reproducibility and offline test viability before incorporating outside code.

## 9. Required correctness and test programme

Build tests from mathematical contracts, not just current implementation. Tests must fail when a realistic defect is deliberately introduced.

### 9.1 Small-system independent references

For small circuits, use one or more appropriate external reference implementations:

- Qiskit `Statevector`/`Operator` for amplitudes, unitaries and expectation values where supported;
- Qiskit Aer statevector/MPS/stabilizer/extended-stabilizer only with options and precision explicitly recorded;
- Stim for compatible stabilizer circuits, not arbitrary non-Clifford circuits;
- an independent NumPy matrix reference for individual 1-/2-/3-qubit gate matrices where feasible;
- exact hand-derived circuit invariants for Bell/GHZ/parity/known arithmetic circuits.

Keep the reference independent: do not call CQ-HECS’s gate-lowering, parser, bit-order or gate-matrix implementation to generate the expected answer for a test of that same code.

### 9.2 Gate lowering

For every supported lowering rule, test:

- operator/unitary equivalence against the reference for randomly generated legal angles and edge angles;
- both two-qubit operand orders and non-adjacent operands;
- correct control/target ordering and Qiskit little-endian conventions;
- global phase handling, including multi-controlled gates where classical truth-table equality is not sufficient;
- invalid arity, repeated operands, wrong parameter count, NaN/infinity and out-of-domain values;
- actual execution through each compatible backend and Qiskit provider, not only the decomposition list;
- capability manifest, target/transpiler, direct parser and JSON result agree on support/refusal.

Mutation examples must include a sign/phase error, swapped axes, wrong control/target, missing rotation, wrong global-phase adjustment, and a gate wrongly advertised as supported.

### 9.3 Path A — stabilizer

Test random small Clifford circuits against Stim/Aer and exact known stabilizers; tableau invariants, commutation, symplectic checks, inverse circuit, repeated measurements, Bell/GHZ/cat and graph states; deterministic seeded samples; support/parity/correlation; bit ordering; thousands of qubits only within a declared safe benchmark scope. For performance, separate compilation/setup and sampling throughput, compare multiple shot counts, track memory, and never compare unsupported noise/gates.

### 9.4 Path B — stabilizer rank

Test known Clifford+T circuits and controlled T-count sweeps; branch/term merging; cancellation; global and relative phase; statevector fidelity/probabilities for small n; probability normalization; all terms retained in exact mode; explicit refusal/approximation semantics when resource ceilings are reached; compare against Aer extended-stabilizer only when that mode’s approximation settings are documented. Track peak branch count and memory, not only n/T count.

### 9.5 Path C — MPS

Test norm and normalization after every gate class; both operand orders; non-adjacent SWAP routing; random small circuits vs statevector; MPS sampling vs ideal probabilities by a statistically justified test; partial measurement mapping; seed determinism; bond-dimension tracking; orthogonality/canonicalization assumptions; near-zero and degenerate singular spectra; SVD residuals; paging integrity and cleanup; storage/RAM preflight before allocation; atomic refusal; corrupted/missing page; shot × qubit product guard; memory/OOM child-process tests with timeout. Test circuit ordering changes with measurement bit remapping.

If the SVD rank floor drops nonzero terms, report the actual semantics truthfully. A sum of discarded singular values is not automatically a rigorous end-to-end state-vector or TV-distribution bound without a valid propagation argument. Do not promote diagnostics to certificates.

### 9.6 Path D — sparse Pauli / Heisenberg

Test every supported 1-qubit conjugation against explicit unitary matrices in the exact internal basis; test CX/CZ/SWAP and phase signs on all 2-qubit Pauli combinations; random Clifford circuits against exact expectation values; all supported parameterized gates; strict observable parsing; repeated factors (`Z_i Z_i = I`); identity expectation; invalid mask/type/index; threshold and term-budget truncation; exact accumulated coefficient 1-norm bounds; per-observable versus combined error reporting; early-stop behavior; `unresolved=True` returns no certified values; and optional marginal samples are never mislabeled as the circuit joint distribution.

For bounds: prove the triangle inequality applies to the exact target; use magnitude of complex coefficients; explicitly include every discarded contribution; do not double-count or omit the truncation at any step. Test the bound against exact circuits but do not mistake finite testing for a proof.

### 9.7 Result schema and statistical guarantees

Every backend should conform to a versioned result schema with:

- result state: `EXACT`, `CERTIFIED`, `UNRESOLVED`, `FAILED` or a carefully documented numeric-approximation status;
- `output_kind` such as counts, probabilities, statevector, expectation values, density matrix or sample estimate;
- clear `exact` semantics and numerical mode;
- per-error component with metric, bound, confidence/probability level, source and assumptions;
- any combined bound’s metric and composition rationale;
- `counts_are_joint_distribution` or equivalent, whether counts represent the requested circuit semantics;
- qubit/classical-bit ordering and measurement mapping;
- resource estimates versus actual measurements;
- backend/path, seed, dependency/reference versions and relevant circuit/config hash;
- unresolved/failure reason.

Do not assume every backend returns every type of output. Validate allowed/required fields conditional on output kind and state. Invalid combinations should be impossible to serialize as plausible success.

### 9.8 Parser/API/bit ordering

Test Python instruction lists, Qiskit circuit, QASM 2, any actually supported QASM 3 surface, Python provider, CLI JSON, C API, native C++ parser and binding. Use paired equivalent circuits and assert identical semantics or explicitly defined refusal. Cover global register offsets, permuted/missing classical bits, repeated/mid-circuit measurements, unsupported classical control/reset/noise, invalid and huge indices, non-finite angles, malformed register declarations, unknown gates, wrong arity, missing semicolons, truncation, invalid UTF-8 where applicable, and resource ceilings. Test Qiskit’s qubit 0/rightmost count convention end to end.

### 9.9 Property tests, fuzzing, mutation and sanitizers

- Hypothesis properties must be deterministic/reproducible and have a reasonable CI profile; save discovered failures as explicit regressions.
- Fuzz parser and DIMACS/SAT input with corpus management, wall-time limits, output-size limits and exit-code assertions.
- Subprocesses must have timeouts and sanitized failure logs.
- Source-level mutation harness must prove the unmutated baseline passes *first*. A baseline failure is an infrastructure/test failure, not a “killed mutant.” A surviving mutant must make the harness exit nonzero. Restore source bytes exactly even after a crash/interruption; use a temp worktree/copy where safer.
- ASan/UBSan or platform equivalents on native code; validate no new data races if concurrency is changed. Run a reduced predictable sanitizer subset in regular CI and broader coverage in Nightly.
- Validate that failure tests themselves fail when their failure condition is removed or corrupted.

### 9.10 Resource, concurrency and chaos testing

Use configured safe ceilings, not uncontrolled host exhaustion. Test before/at/after each boundary; finite and positive budgets; bool vs numeric inputs; overflow-safe dimension products; allocation failure; disk full/missing page; file corruption; cancellation; timeout; repeated runs; concurrent independent simulations; concurrent CLI subprocesses; Vulkan device lost/timeout; exception cleanup; and atomic state refusal. Use isolated temp directories and child-process timeouts. No test should deliberately take down a shared runner.

### 9.11 Real quantum hardware tests are optional and separately gated

Default public CI must never require real-provider credentials or spend quota. Mock all provider/job lifecycle cases. A real hardware run requires explicit authorization and cost/shot bounds; record device/backend, date, calibration snapshot, transpiled circuit hash, transpiler settings, shots and job provenance. Mark unavailable real hardware as `NOT RUN`/`BLOCKED`, never as passing.

## 10. Benchmark programme and SOTA comparison rules

### 10.1 Workload matrix

Include families that stress different methods, not just the easiest high-qubit demos:

- Bell, GHZ, cat, repetition and cluster states;
- random Clifford circuits and QEC-like circuits (Stim-compatible subset);
- Clifford+T sweeps with T-count and number of qubits varied independently;
- 1D nearest-neighbour, long-range and 2D/geometry-matched circuits;
- shallow/deep brickwork circuits and entanglement-growth trajectories;
- QFT/controlled-phase and arithmetic/composite-gate circuits;
- Ising/Heisenberg-style Trotter circuits with documented topology/parameters;
- random universal circuits at small sizes for exact comparison;
- low-/high-entanglement and low-/high-treewidth families;
- selected observables versus full-distribution output requirements;
- memory-stress and near-budget cases;
- unsupported/noisy/dynamic-circuit cases to test refusal contracts;
- if a tensor-network prototype exists, graph families that distinguish chain MPS from 2D contraction/slicing.

Do not claim general superiority based only on GHZ or Clifford circuits. A circuit family that is easy for one path may be hard for another; the report must show per-family performance and limitations.

### 10.2 Comparator policy

For each comparison record exact reference version/commit, environment, compatible gates, measurement semantics, approximation settings, dtype/precision, bond dimension/truncation options, noise configuration, shots/seed, and whether setup/compile time is included. Separate exact, bounded approximation, and statistical sampling comparisons. Reference tools may have their own bugs; use at least two independent checks for the riskiest small-system identities where practical.

### 10.3 Metrics

Record:

- wall-clock end-to-end time and substage times;
- planning/setup/compilation versus execution time;
- throughput, e.g. shots/sec only when definitions match;
- peak process RSS, retained tensor bytes, temporary workspace estimate, disk bytes and GPU memory separately;
- peak bond dimension, stabilizer rank/term count, Pauli term count, contraction FLOPs/estimated tensor size;
- fidelity, state norm, probability normalization, selected expectation errors, TV distance or another metric **only when appropriate to the output**;
- error certificate, confidence delta/level and whether the stated guarantee is rigorous or empirical;
- repeat count, median and quantiles/dispersion, warmup and hardware state.

Use a stable benchmark runner and machine-readable JSON/CSV with schema version. Do not manually type new timing numbers into a report. Generate reports from raw result files and preserve raw evidence. Compare at least several repeated runs and report noisy results honestly. Use geometric mean only with clearly defined benchmark weights and separate per-workload tables.

### 10.4 Performance acceptance criteria

For a new performance feature, preregister the workload families and success threshold in the hypothesis record before tuning on the final set. Suggested initial threshold: a material improvement (for example 15% or more in a named workload family) without worse correctness, without exceeding memory budgets, and without a large regression in comparable workload families. The exact threshold can differ by experiment but must be fixed before final validation, include noise/confidence reasoning and be stated as a heuristic acceptance bar—not a universal scientific standard.

A benchmark that only improves a microkernel but makes the complete simulator slower is not an end-to-end win. A performance result that changes precision, bond dimension, shot semantics or output kind is not a fair comparison unless the trade-off is stated and the error/quality constraints match.

## 11. Local implementation and self-healing loops

Use small phases. After each root-cause fix, run focused tests; after a coherent group, run the full relevant suite; before push, run all mandatory local gates. Maintain a durable execution log after each phase and each recovery iteration.

### 11.1 Self-healing protocol

For every failure:

1. Capture the exact command, exit code, relevant test ID, log excerpt and environment. Redact secrets and unrelated personal paths where they do not help reproduce the defect.
2. Classify it: code defect, mathematical/specification defect, flaky test, test harness issue, dependency/environment drift, resource issue, external service issue, or unsupported hardware.
3. Reproduce locally with the smallest deterministic test/circuit/input possible.
4. Identify root cause; do not patch only the visible symptom if the abstraction or contract is wrong.
5. Add or improve a regression test **before or alongside** the fix. Confirm the test fails on the broken version when feasible.
6. Apply one minimal logical fix. Avoid bundling unrelated refactors with a correctness patch.
7. Run targeted tests, then affected suite, then cross-backend/differential tests as needed.
8. Rerun the previous reproducer, relevant regression suite and failure-path tests.
9. Write the outcome into `FINDINGS.md` and `EXECUTION_LOG.md`; note any follow-up risk.

Bounded retries: if the same failure signature survives three repair attempts, stop repeating the same strategy. Reassess the assumption, shrink the reproduction, inspect source/ABI/dependency versions, and create a new hypothesis. After five iterations with no principled progress, report a clear `BLOCKED`/`INCONCLUSIVE` item and continue unrelated work if safe. Do not use infinite loops to conceal lack of diagnosis. A self-healing loop may continue across distinct root causes, but every iteration must produce new evidence or a justified decision.

### 11.2 No test cheating

Prohibited actions include:

- deleting the failing test or adding it to an exclusion without technical proof;
- setting a CI job to `continue-on-error` to make release green;
- lowering coverage below policy to cover new code;
- turning hardware-required checks into allowed skips while still saying hardware passed;
- weakening a mathematical tolerance without deriving the correct value;
- changing public result semantics without tests/docs/schema versioning;
- catching broad exceptions and emitting empty success values;
- fabricating baseline data or copying stale benchmark JSON as current results;
- silently skipping optional test dependencies and reporting the resulting reduced suite as the full suite.

If a test is invalid, prove why, replace it with a stronger/accurate test, record the rationale and ensure the updated test still protects the contract.

### 11.3 Suggested local checkpoints

Use tracked logs with these checkpoints:

- `L0`: live state + exact baseline locked;
- `L1`: initial tests and reproducible failure inventory;
- `L2`: research hypotheses and transferability decisions written;
- `L3`: result/schema P0 issues resolved;
- `L4`: algorithm changes and targeted differential tests pass;
- `L5`: stress, fuzz, mutation, sanitizer gates pass;
- `L6`: benchmark results and no-regression analysis done;
- `L7`: complete local release candidate validation pass;
- `C0`: branch pushed and PR created/updated;
- `C1`: cloud checks on exact branch commit pass;
- `D0`: final documentation/reports content push complete;
- `C2`: all required CI after D0 pass on exact final source SHA;
- `M0`: merged commit verified on default branch;
- `R0`: tag/release assets/checksums/provenance verified;
- `F0`: final report assembled from evidence.

Never advance a checkpoint just because a command was started. Store command, exit, evidence and timestamp (UTC) as applicable.

## 12. Required local quality gates

Adapt exact commands to the current scripts, platform and dependency declarations; do not copy stale commands blindly. Verify each command exists before invoking it. Record all actual commands and outcomes.

### 12.1 Python correctness and static gates

Typical commands from the current project structure:

```bash
python -m compileall -q cqhecs tests scripts python_bridge
python scripts/check_version.py
python scripts/verify_no_silent_truncation.py
python scripts/run_mutation_tests.py
python -m pytest tests/ -q
python -m coverage run --branch --source=cqhecs -m pytest tests/ -q
python -m coverage report -m --fail-under=70
```

Use the repo’s pinned constraints for deterministic CI, including `constraints/ci-py311.txt` if it remains applicable. Make sure required test extras such as Hypothesis/Aer/Stim are installed in their intended test lanes. When native coverage is expected, set the currently documented native-required environment flag (e.g. `CQ_HECS_REQUIRE_NATIVE=1`) so missing native execution cannot masquerade as a pass. Do not assume the current number of tests is a permanent expected count; compare result files and explain any additions/removals.

Lint at least the currently required fatal/pyflakes rules across `cqhecs`, `tests`, `scripts`, and `python_bridge`. If adding a strict formatter/type checker, first make the whole repo pass without a mass blind rewrite. Treat mypy/pyright as a separate gate only after type expectations are configured accurately.

### 12.2 Native C++ / CTest

Linux-style baseline, adjusted for supported compiler:

```bash
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure --schedule-random
```

Windows/MSVC-style baseline:

```powershell
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```

Verify the actual CMake options/toolchain, do not report that a build uses GPU acceleration just because Vulkan was found. If MSVC does not support the chosen sanitizer configuration, use the documented Linux sanitizer lane and report platform scope explicitly. Run warnings/static analysis where current compiler settings support them; new high-severity warnings must be resolved or justified.

### 12.3 Vulkan gates

```bash
python scripts/verify_vulkan_shaders.py
```

Then run the current CTest Vulkan primitive dispatch test using the repo’s documented required-device/environment flags. Separate these outcomes:

- GLSL source and SPIR-V compilation/validation;
- loader/ICD is found;
- software ICD dispatch passed;
- physical AMD/NVIDIA/other device dispatch passed;
- validation-layer run passed;
- full simulator pipeline ran on device and matched CPU;
- end-to-end simulator performance improved.

Only claim levels actually evidenced. The current v2.3.0 release documents primitive Vulkan dispatch verification, not full end-to-end acceleration.

### 12.4 Package, installation, and release dry-run

Typical relevant gates:

```bash
python -m build
python -m twine check dist/*
python scripts/check_version.py
python scripts/generate_sbom_and_checksums.py
```

Check current script interfaces before use. Install the built wheel into a clean venv with no repository path on `PYTHONPATH`; run `cq-hecs --help`, `cq-hecs version`, `cq-hecs doctor`, and a known builtin with JSON output. Parse JSON with a separate process and assert schema version, status, output kind, expected nonempty/empty result and correct error fields. Confirm whether the wheel is pure Python and state explicitly if native C++/Vulkan artifacts are not bundled.

### 12.5 Benchmark smoke + reproducibility

- Validate benchmark schemas and required metadata.
- Run a small smoke benchmark on every PR, plus expanded benchmark families in Nightly/manual runs.
- Save raw outputs as CI artifacts and upload results even on failure where safe.
- Make the runner fail if required cases are silently omitted or a workload unexpectedly returns unresolved while marked successful.
- Never block stable CI on a noisy, unbounded full performance benchmark; use deterministic correctness smoke gates in PR and broader performance analysis in controlled jobs.

### 12.6 Docs/metadata consistency

Before the final content push, verify:

- one canonical version and consistent copies in `pyproject.toml`, `scripts/version.py`, CMake/project metadata, CLI and relevant native API;
- README support claims match actual capability manifest and result schemas;
- all benchmark tables state version/date/hardware/method and are generated from the corresponding raw artifacts;
- old reports are labelled historical, not passed off as current;
- no README badge is described as stronger proof than its underlying workflow;
- release notes accurately list added, changed, fixed, removed, limits and non-claims;
- API/QASM/usage/architecture docs have current entry points and exit codes;
- links to references and artifacts exist;
- secret-scan/license/SBOM/checksum checks pass under the current policy.

## 13. GitHub Cloud push and self-healing CI loop

Do all local correctness and required quality gates before the first push. A green cloud job is not permission to skip local checks.

### 13.1 Authentication and least privilege

1. Inspect whether `gh auth status` succeeds; do not print token values or dump environment variables.
2. Prefer existing Git credential-helper / authorized `gh` credentials for Git pushes; use host-managed `GITHUB_TOKEN` for Actions when the workflow’s permissions are sufficient.
3. Keep workflow default permission read-only and grant the minimal write scope only to the release job that needs it. Use pinned, reviewed action SHAs where established in this repository.
4. Never embed PATs in remote URLs, command strings, `.env`, `GEMINI.md`, scripts, workflow files, commit messages or CI artifacts.
5. Never disable branch protection, required checks, secret scanning, TLS validation or PR review to “make the release go through.”
6. If a fine-grained PAT or organization permission must be granted by the owner, request that action transparently and continue all local work that does not require the permission.

### 13.2 Branch and PR protocol

- Re-check default branch and existing mission branches/PRs.
- Create a unique branch from latest default branch, for example `agent/cq-hecs-v2.4.0-research-hardening`, unless an active branch for this mission already exists and is demonstrably the right one.
- Keep commits focused: result-contract fix; numeric/exactness contract; tests; new experimental method; performance/benchmark; final docs. If the repository prefers fewer commits, preserve logical separation in the PR body/changelog.
- Push the branch only after local gate L7 passes or after a deliberately small early PR whose incomplete status is clearly marked draft and cannot be merged/released.
- Open/update a PR containing scope, core changes, hypotheses evaluated, tests and exact results, performance tables, limitations, security impact, migration notes, release type and evidence paths.
- Avoid force-push unless the repo's policy and PR context explicitly require it and it is safe; prefer normal pushes. Never rewrite a published stable branch/tag.

### 13.3 CI failure self-healing loop

For each cloud workflow run:

1. Verify run head SHA matches the branch commit just pushed.
2. Fetch the failed job names, step names, full log excerpt and run URL.
3. Classify each failure as code/test, dependency/toolchain drift, workflow/permissions, unavailable hardware, external provider outage, flake, or resource timeout.
4. Compare against the local run on the same SHA. If a gate fails only in cloud, reproduce the environment/version/command locally where feasible; do not assume it is flaky.
5. Fix root cause in the branch; add regression tests for code failures; add workflow validation for workflow failures.
6. Run focused and required local tests, then push another normal commit.
7. Verify the new CI run is attached to the new SHA; repeat until all applicable required jobs pass.
8. If the same failure signature repeats three times, stop the identical repair attempt and use a fresh root-cause investigation. If it is an unavailable physical-device gate, classify correctly rather than pretending it passed. If the required service/runner is unavailable, record actual evidence and wait for a legitimate rerun only when authorized/available in the current session; do not promise asynchronous follow-up.
9. Use `workflow_dispatch`/rerun only through an authorized GitHub action and only to rerun a real job, not to conceal failure. Keep run URLs and exact SHA in `TEST_MATRIX.md` and `RELEASE_AUDIT.md`.
10. Do not merge while any required check is failing, pending, cancelled, skipped unexpectedly, or running against a different SHA.

Treat successful Linux CI and Windows CI independently. Treat software Vulkan and physical GPU gates independently. Cloud Build success is a separate gate from GitHub Actions if the current project actually configures Cloud Build; if credentials/project are not available, mark `BLOCKED/NOT VERIFIED` and do not report complete Cloud Build validation.

## 14. Documentation and research-report final pass — final content-changing push

Documentation should evolve with the implementation as needed for code review, but **the final authoritative documentation/report reconciliation is the last source-content change before final full CI and merge**. This satisfies the final-push requirement without releasing a version whose docs do not match its binaries.

On this final content pass:

1. Rebuild `README.md` support/claims/installation/quick start from verified public behavior. Keep it accurate, accessible and complete; do not add a performance slogan without a current benchmark artifact.
2. Update `ARCHITECTURE.md` and `docs/ARCHITECTURE.md` for actual path capability, exactness/numerical status, output contract and resource model.
3. Update API, QASM contract, embedding/usage guides, CLI and hardware support matrix to match current code, including unsupported semantics.
4. Update `CHANGELOG.md` and `RELEASE_NOTES.md` for the exact intended version and actual changes; include notable fixes, features, test evidence, migration notes and limits. Do not simply rename stale release notes.
5. Update `docs/BENCHMARKS.md`, `benchmarks/*`, `research/v2_4/*`, `audit/*` and tracking JSON from generated results. Keep historical benchmarks clearly labelled; do not overwrite history with current numbers.
6. Update the OpenAI Math snapshot, manifest diffs, relevance/transfer report and negative-result records with exact upstream SHA/date. Note which claims are formalized/reviewed and what remains unverified.
7. Update version references, citations, badges and links. Check that README/Release Notes do not call the product a real quantum computer, imply support for unsupported dynamic/noisy circuits, or imply full GPU execution when only primitives are verified.
8. Regenerate SBOM/checksums after the final packaged bits are stable. Keep artifacts and report provenance aligned.
9. Run Markdown link checks or a suitable link checker if permitted/network available; distinguish transient external network failures from dead repository paths.
10. Run a documentation consistency audit against the final code/capability manifest and the generated benchmark/CI evidence. Add test checks for version/support-matrix/report invariants where practical.

Commit the final content/report update as the last normal source commit before the final complete validation. Push it. Then rerun all required CI on that exact commit. If any subsequent source edit is required, it is no longer the final source commit: repeat the full final-doc check and required CI on the new commit. Do not change docs or test files after the versioned release artifacts have been generated unless you intentionally start a new candidate and regenerate/reverify everything.

## 15. Merge, tag, publish, and verify

### 15.1 Merge conditions

Merge only when:

- local L7 gates are all green;
- cloud C2 required checks on the exact final documentation/source commit are all green;
- all review requirements and branch rules are satisfied;
- there are no unresolved P0/P1 correctness/scientific-integrity findings;
- all research hypotheses implemented as features have their required acceptance evidence;
- the final docs/report content is in the PR;
- the target version and compatibility notes are approved by SemVer logic;
- the diff contains no secrets, accidental binary dumps, cache, temp files, unrelated changes, or stale benchmark result claims.

Use the repository’s actual allowed merge method. If an approval is required, stop and request it; do not bypass it. The default branch was `main` at preparation. Merge into the live default branch—not `master` unless live metadata really says `master`.

### 15.2 Release procedure

Inspect the current `.github/workflows/release.yml` and follow its real preconditions. The release must be created from the merged, verified default-branch commit or from the exact stable tag pointing to that commit, according to the workflow’s contract. The release tag must not point to an earlier pre-doc SHA.

- Check all version surfaces and clean packaging.
- Run the current release workflow via the authorized event/path.
- Confirm workflow was triggered for the intended tag and source SHA.
- Confirm the release is neither draft nor prerelease if stable is the intended target.
- Verify every release asset exists and downloads completely: wheel, source tarball, checksums, SBOM, release notes, and native artifacts only if the workflow actually builds/distributes them.
- Recompute SHA-256 locally from downloaded release assets and compare with published `sha256sums` and GitHub asset digests where available.
- Inspect wheel metadata and run a clean install from the actual uploaded wheel; verify `cq-hecs version`, `doctor` and a known deterministic builtin. Ensure the release artifact matches the source tree and docs.
- Validate SBOM syntax and expected contents, licence data and source commit provenance. If signing/attestation is configured, verify it; do not claim signatures that were not produced.
- Confirm the Release Notes state actual limitations, including whether native GPU code is bundled, whether physical GPU dispatch was tested, and which simulator modes are experimental.
- Verify a subsequent clean checkout of the published tag can run the documented install/smoke path.

If publishing succeeds but asset verification fails, do not call the release complete. Diagnose the artifact/workflow mismatch, create a corrected release only through the repository’s documented safe process, and avoid deleting/reusing immutable tags in violation of project policy. If an existing public release is wrong, transparently document it and use a new corrective version/tag rather than rewriting published history.

## 16. Security, supply chain and operational hardening

Audit the current release pipeline and workflows for:

- least-privilege permissions and write scopes confined to jobs that need them;
- pinned GitHub Actions to immutable reviewed commit SHAs where feasible;
- third-party action trust, tag/commit verification and update policy;
- no use of untrusted PR code with privileged secrets;
- no interpolation of untrusted title/branch/input text into shell without safe quoting;
- dependency pins/constraints and lock or constraints strategy that remains maintainable;
- `pip-audit`/OSV or equivalent dependency vulnerability scan if compatible with workflow policy;
- license/SBOM generation and checksums from final artifacts;
- secret scanning and prevention of credentials in logs/artifacts;
- native input ceilings, parser fuzzing, file handling and path traversal protections;
- subprocess timeouts, bounded output, safe temporary directories and cleanup;
- Vulkan validation/exception cleanup and safe device/queue resource lifetime;
- reproducible build/package metadata where practical.

Do not add a new security scanner only to create noise. Configure its policy, make false positives actionable, and never silently ignore a high-severity finding. A scanner outage is not the same as a clean scan.

## 17. Final public outputs and exact completion report

At mission completion, commit the final report data before the final source commit; after release, append only release verification results in a clearly defined audit-only commit if the project policy allows it. If an audit-only post-release commit is necessary, it must not change the source that the release claims to represent. If it changes shipped source/docs, produce a new release candidate and verify again.

Final response/report must include:

- target release/version and why SemVer fits;
- base SHA, final merged SHA, tag commit SHA, release URL;
- PR URL and merge status/method;
- CI/Nightly/Release workflow URLs and exact run conclusions/SHA;
- Python and CTest counts, coverage, mutation score and sanitizer results with environment;
- version/package/smoke/SBOM/hash outcomes;
- OpenAI Math source SHA/date/manuscript/family counts as observed and the transfer candidates accepted/rejected/deferred;
- each hypothesis decision with benchmark/test evidence;
- before/after metrics per benchmark family, hardware/runtime configuration, methodology, variance, correctness metric and artifact link;
- GPU evidence level explicitly: compile, software ICD dispatch, physical device primitive dispatch, or complete end-to-end simulation. Never conflate them;
- any real quantum hardware run provenance or explicit `NOT RUN` reason;
- all unresolved, deferred, unsupported and external-blocked items;
- links to reports and released assets.

Use a truthful status word: `VERIFIED COMPLETE` only if all required stable criteria are satisfied; `PARTIALLY COMPLETE` if optional research or external proof remains but the stable release is genuinely valid; `BLOCKED` if a required gate/permission/device/service is unavailable; `FAILED` if release criteria are not met. Do not describe the project as “perfect.” Describe precisely which tests and contracts were verified and which were not.

## 18. Release hard gates (checklist)

Use this as a blocking checklist. A unchecked item is not implicitly passed.

### Before the first push

- [ ] Live repo/default branch/release/PR/workflow facts rechecked.
- [ ] Worktree/user changes inventoried and preserved.
- [ ] Baseline saved with exact SHA and environment.
- [ ] Old findings reproduced or marked appropriately.
- [ ] Research snapshot SHA and new diff captured.
- [ ] Hypotheses written with falsifiable success/rejection criteria.
- [ ] No P0 finding left untriaged.
- [ ] Result-contract and exactness audits completed.
- [ ] Focused regression tests added and pass.
- [ ] Full Python suite passes in required mode.
- [ ] Native build and required CTest pass.
- [ ] Mutation harness baseline passes and all required mutants are killed.
- [ ] Shader/Vulkan tests classified accurately, including skipped hardware.
- [ ] Package/smoke/version/truncation and security checks pass.
- [ ] Benchmark smoke is reproducible and raw artifacts retained.
- [ ] Local test matrix has actual results, not expected results.

### Before merge

- [ ] New algorithm (if any) has correctness proof/derivation and independent differential/property tests.
- [ ] No false claim of exactness, certified TV error, hardware access or SOTA superiority.
- [ ] No unresolved P0/P1 correctness/scientific-integrity defect.
- [ ] Resource and failure contracts remain fail-closed.
- [ ] Final documentation/report content update is the last source-changing commit.
- [ ] Final local gates run on that exact commit.
- [ ] Branch is pushed with secure auth and PR exists.
- [ ] Required CI for the exact final SHA is all green; no unexpected skip/pending/cancel.
- [ ] Nightly/manual extended gates are run or the actual reason they are not a release gate is documented.
- [ ] Required reviews and branch protections satisfied.
- [ ] Merge destination matches live default branch (`main` at time of writing; recheck).

### Before reporting release complete

- [ ] Release tag points to the verified merged source commit according to the repository release contract.
- [ ] GitHub release is published with correct version/type.
- [ ] Every expected asset exists and downloads.
- [ ] SHA-256/checksum verification passes against downloaded files.
- [ ] SBOM and provenance validated.
- [ ] Clean-install wheel/package smoke passes.
- [ ] README, docs, release notes and hardware/feature claims match actual artifact/source.
- [ ] Final audit includes exact run URLs, SHAs, metrics and limitations.
- [ ] All skipped/blocked/unverified claims are plainly stated.

## 19. Immediate first actions for the agent

Do not start by implementing the new tensor-network backend. First:

1. Refresh live GitHub state, version, latest SHA/tag/release, current `GEMINI.md`, branch protection and current cloud runs.
2. Read the existing `GEMINI.md` fully and merge its still-valid historical CQ issue identifiers/operational requirements into this mission’s ledger. Preserve earlier finding history; mark old release targets as historical, not current.
3. Inspect `cqhecs/result.py`, all Path D result construction, and the latest tests to confirm or refute H0 from source and executable reproductions.
4. Inspect Path C SVD/rank selection and result metadata to confirm or refute H1.
5. Re-run the baseline result tests, Python suite, native/CTest, static/version/truncation/mutation/packaging gates. Capture the real baseline before code changes.
6. Refresh OpenAI Math’s exact upstream SHA, history, index and formalization catalogue; diff against the previous snapshot. Review only candidates with a plausible mechanism for CQ-HECS first.
7. Write the hypothesis catalogue and pick the highest-value tractable research candidate after the P0 result-contract fixes. Do not let feature work overtake correctness.
8. Proceed phase by phase, recording evidence. Keep the new tensor-network path experimental unless and until it passes the same core contract, differential and resource gates as the stable paths.

## 20. Source and literature links

Primary sources to refresh at runtime:

- OpenAI Math README: <https://github.com/openai/math/blob/main/README.md>
- OpenAI Math history: <https://github.com/openai/math/blob/main/history.md>
- OpenAI Math overview: <https://github.com/openai/math/blob/main/overview.tex>
- CQ-HECS repository: <https://github.com/timfromhcs/CQ-HECS>
- CQ-HECS releases: <https://github.com/timfromhcs/CQ-HECS/releases>
- CQ-HECS Actions: <https://github.com/timfromhcs/CQ-HECS/actions>
- Stim: <https://github.com/quantumlib/Stim>
- qsim: <https://github.com/quantumlib/qsim>
- Qiskit Aer simulator documentation: <https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html>
- Qiskit Aer simulator tutorial: <https://qiskit.github.io/qiskit-aer/tutorials/1_aersimulator.html>
- NVIDIA cuQuantum: <https://docs.nvidia.com/cuda/cuquantum/latest/>
- NVIDIA cuTensorNet: <https://docs.nvidia.com/cuda/cuquantum/latest/cutensornet/>
- Rudolph & Tindall, 2D tensor networks (2026): <https://doi.org/10.1038/s41534-026-01372-2>
- OpenQASM: <https://openqasm.com/>

Cite the exact source and version in the research log. Do not rely on these links alone; the live content may change, paper revisions may update, and a method must be understood at the level of its full assumptions and result contract.

---

## Closing instruction

Work autonomously for as long as each iteration is evidence-producing and safe. The target is not the largest diff, the most ambitious README, or an unconditional “SOTA” label. The target is a release that makes a small number of defensible improvements, proves the critical contracts through independent tests, reports performance honestly, survives local and cloud validation, and ships from an exact verified commit. If the highest-standard result requires rejecting a fashionable method, keeping a new backend experimental, declining an unsupported hardware claim, or reporting a genuine blocker, do that.

---

## 21. Execution status and handoff (updated 2026-10-29, second agent)

This section records what has actually been done against this mission so that the next agent does not redo or contradict it. Everything above remains the operative plan; statuses below override its "to do" wording.

### 21.1 Where the first agent stopped

Uncommitted on `main` at baseline `ba27bd1`: H0 (`SimulationResult.total_error_bound` metric scope) and H1 (Path C numerical-rank metadata) fixes in `cqhecs/result.py`, `cqhecs/backends/path_c_mps_exact.py`, `cqhecs/backend.py`, regression tests in `tests/test_correctness_contracts.py`, and the `research/v2_4/` ledger (baseline, hypotheses, literature map, test matrix, evidence logs). `backend.py` was left half-edited (unused `contract_metadata_keys`). All of it was preserved and completed.

### 21.2 Done in this cycle

| Item | Status | Evidence |
| :--- | :--- | :--- |
| H0 result-metric composition | FIXED | `research/v2_4/FINDINGS.md`, `tests/test_correctness_contracts.py` |
| H1 Path C numerical-rank semantics | FIXED | same |
| H8 confidence-bound wording | REVIEWED, docs fixed | `tests/test_confidence_bounds.py` |
| README error-handling example (`AttributeError`) | FIXED | `TestDocumentedErrorHandling` |
| Path D idle-top-qubit width through the new API | FIXED in the API (Path D itself unchanged) | `tests/test_expectation.py` |
| Nine more exact gate lowerings | SHIPPED | `tests/test_gate_lowering.py` |
| Pauli expectation values (`cq-hecs expect`, `cqhecs.expectation`, dense reference) | SHIPPED, H7 partial | `tests/test_expectation.py`, `tests/test_cli_expect.py` |
| Mutation gate | 14/14 killed | `scripts/run_mutation_tests.py` |
| Version | 2.4.0 on every surface | `scripts/check_version.py` |

### 21.3 Not done (do not claim)

- **Web research:** the web-search tool failed on every call (model error), so no paper or doc page was read this cycle. Landscape facts come from the GitHub API and prior knowledge and are labelled as such in `research/v2_4/LITERATURE_MAP.md`.
- No performance benchmark against Stim/Aer/qsim was run; no SOTA or speed claim is made. H2-H6, H9, H12-H15 are deferred, H10 not run, H14 research-only.
- No physical-GPU end-to-end validation; no real quantum hardware.
- Mid-circuit measurement, reset, noise and density matrices remain refused.

### 21.4 Suggested next cycle

1. Mid-circuit measurement/reset on Path A (tableau collapse already exists in `StabilizerTableauSimulator.measure`); needs an IR that carries classical-bit destinations.
2. A benchmark harness per `BENCHMARK_PROTOCOL.md` before any H2/H5 work.
3. Re-run the web research that was blocked, then update `LITERATURE_MAP.md`.
4. Extend Path D's gate set to controlled rotations (currently Path C only), which would let `sparse_pauli` serve more circuits.
