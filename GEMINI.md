# GEMINI.md — CQ-HECS v2.0.0 Autonomous Research & Engineering Mission

> **Mission:** Take the current `timfromhcs/CQ-HECS` repository from its actual audited state to a defensible, tested, reproducible **v2.0.0** release. Work autonomously in bounded self-healing loops. Research all relevant classical quantum-simulation methods, prove or test their limits, implement the methods that are correct and genuinely useful, document methods that are not viable, run local and cloud CI/CD, push authorized changes, create the release only after every release gate passes, and update `README.md` as the final source/documentation edit before the final validation run and release tag.
>
> **Never claim a mathematical theorem, hardware capability, benchmark result, or release success that has not been verified. Never trade correctness for a green CI badge.**

---

## 0. Identity, repository, target and audited baseline

- Repository: <https://github.com/timfromhcs/CQ-HECS>
- Main branch at the start of this mission: `dd59c0c4e60e0ba7b95194798dccba288786db53` (merge of PR #1, `fix: eliminate fabricated results, silent truncation and fail-open routing`). Re-fetch the latest `main` before changing anything; this SHA is a reference snapshot, not permission to overwrite later work.
- Latest audited CI run for that main commit: <https://github.com/timfromhcs/CQ-HECS/actions/runs/39242815214>. Both Ubuntu and Windows jobs completed successfully when checked on 2026-10-19. A green run proves that the configured checks passed at that commit; it does not prove all algorithms mathematically correct.
- Latest published GitHub release at audit time: `v0.2.0`; the Python package's canonical version is also `0.2.0`.
- The current project includes a C++20/Vulkan native core, a Python package, four Python simulation paths, Qiskit BackendV2 integration, CLI, SAT/ARX modules, CMake/CTest, Python tests, GitHub Actions, and release-artifact generation.
- PR #1 added substantial correctness fixes, a single CLI entry point, shared circuit parsing, version checks, result error fields, and regression tests. Preserve and build on that work; do not rewrite from scratch without evidence.
- There was **no `GEMINI.md` in the repository root** at the time of audit. Put this file at the repository root and use it as this mission's instruction source.

### Current known concerns to re-verify first

1. `cqhecs/result.py`: `hoeffding_total_variation_bound()` currently uses a dimension-free bound of the form `sqrt(log(2/delta)/(2*shots))` while naming it a rigorous total-variation bound for an arbitrary categorical measurement distribution. A dimension-free bound of this form is not valid for arbitrary high-cardinality outcomes. Replace it with a mathematically valid bound for the exact metric and support size, or provide per-observable concentration bounds with an explicit confidence level. Do not merely change the test to agree with an invalid formula.
2. `scripts/run_mutation_tests.py`: audit the mutation harness itself. In the current version, several functions return `True` when a pre-mutation baseline is already incorrect (for example baseline GHZ parity failure), which can count a broken baseline as a killed mutant. Its `main()` also returns success even when mutants survive. These are release-gate integrity defects. Baseline failures must fail the harness; survivors must return a non-zero status.
3. `cqhecs/backends/path_c_mps_exact.py`: the MPS path uses floating-point SVD and drops singular values below a relative roundoff threshold while accumulating a discarded spectral mass. Verify whether the reported value really bounds the error of the returned state, probabilities and observables. Do not call float64 SVD mathematically exact. If a rigorous bound is not available, label the field as a measured diagnostic rather than a theorem and keep the result's guarantee appropriately limited.
4. `cqhecs/backends/path_b_stabilizer_rank.py`: decomposition uses complex floating-point arithmetic and a dense statevector path limited to a small number of qubits. Verify the declared supported gate set, branch normalization, global phases, measurement semantics, numerical diagnostics and bounded behavior. Do not declare `exact=True` with `numerical_error_bound=0` unless that contract is genuinely justified.
5. `cqhecs/backends/path_d_sparse_pauli.py`: the certified Pauli truncation bound applies to the explicitly evaluated observables, not automatically to the complete bitstring distribution. Keep the default return value observable-specific. If uncertified marginal samples are offered, label them clearly and never represent them as a joint distribution.
6. `README.md` is stale relative to the recent correctness-hardening work. Its opening paragraphs and architecture tables still claim cross-vendor physical Vulkan support, under-5-MB GPU execution, exactness and zero error guarantees that do not agree with the current architecture notes and release-cycle findings. **Do not update README yet.** Finish the implementation and other documentation first; update README in the final documentation step after all capabilities, metrics, support levels and release artifacts are settled.
7. `RELEASE_NOTES.md` still describes `v0.1.0`, while the release workflow copies that file to the current version's name. Correct this before the v2 release.
8. `docs/USAGE_GUIDE.md` still contains legacy native CLI commands and historical hardware/telemetry claims that do not consistently match the current `cq-hecs` Python CLI. Update documentation outside README before the final README pass.
9. `docs/BENCHMARKS.md` correctly labels its old tables stale/historical. Keep that warning unless new benchmark runs replace every displayed claim with reproducible current data.
10. The Python paths run on CPU. Shader compilation and software-Vulkan CI do **not** prove that the native engine actually dispatches on a physical GPU. Keep platform status precise and separately verified.

These are audit leads, not a substitute for re-checking the live `main` branch, test logs, source and method contracts at mission start.

---

## 1. Autonomy, git operations, credentials and safety rails

Work end-to-end without stopping for ordinary design decisions. Make reasonable defaults and record them. Ask for user input only if an action genuinely requires unavailable credentials/permissions or an irreversible decision that cannot be safely inferred.

### Git/GitHub procedure

1. Start with `git status --short --branch`, `git log -n 20 --oneline --decorate`, `git remote -v`, `git tag --list`, `gh auth status` (if GitHub CLI is installed), and live GitHub repository/branch/Actions/release checks.
2. Preserve uncommitted user changes. Never reset, clean, force-push, rewrite remote history, delete tags, or overwrite a branch without establishing ownership and obtaining explicit authorization.
3. Create a mission branch from the latest `origin/main`, e.g. `agent/v2-research-simulation`, then push that branch. Make small, coherent commits with clear messages.
4. Open/update a PR against `main`; allow Actions to run. Review failures and fix the root cause. Merge only after all required CI checks are green, the diff is reviewed, and repo permissions/policies allow it. If direct authorized push is the established workflow, still prefer branch + PR where supported.
5. Check that the branch has not fallen behind. Rebase/merge safely; never force-push as an automated first resort.
6. At release time, verify latest `main` commit, version, release workflow, existing tags and assets again. Create the `v2.0.0` tag only on the exact commit that has passed final gates, then push it and observe the tag-triggered Release workflow to completion.
7. After release CI succeeds, inspect the actual GitHub Release, tag target SHA, wheel, sdist, native artifacts, checksums, SBOM and release notes. Do not report release success until the assets are present and validated.

### Credential rules

- Use already configured Git credentials, `gh auth`, SSH agent, or a securely provided environment token. Check authentication without printing tokens.
- Never request a token be committed to chat, source, logs, markdown, `.env`, CI artifacts, crash reports or shell history. Never place credentials in a URL.
- Never try to mint/recover credentials, bypass GitHub permissions, disable branch protections, disable required checks, or evade repository rules.
- If the connected GitHub app/tool lacks write permission but local Git credentials are authorized, use local Git. If no write credential exists, finish all feasible local work, leave a complete patch/branch if possible, and report the precise permission blocker. Do not invent success or claim a push occurred.

### Self-healing loop contract

For each failing gate:

1. Preserve the full failure output, commit SHA, platform, command, environment and reproduction steps.
2. Reproduce the failure locally or in an isolated regression test.
3. Identify a root cause before editing; do not patch only a symptom or suppress a check.
4. Add a test that fails before the fix and passes after it, wherever feasible.
5. Implement the smallest correct fix.
6. Rerun the targeted test, related tests, full relevant suite, then CI.
7. Inspect the diff for unrelated changes, weakened assertions, skipped tests, fake metrics or changes that conceal a failure.
8. Commit and push coherent fixes so the cloud loop continues.
9. If the same gate fails three times with no new information, change strategy: inspect logs/source/toolchain, minimize the reproducer, or isolate the subsystem. Do not repeat the same failed command/fix indefinitely.

Never make a failing test pass by deleting it, marking it skipped, reducing assertions, swallowing exceptions, loosening numerical thresholds without mathematical justification, inserting placeholder output, or marking a CI job `continue-on-error`.

---

## 2. Definition of done for v2.0.0

v2.0.0 is a product release, not a promise that a universal classical simulator for all quantum circuits exists. The v2 scope is to:

- expose a stable, self-consistent simulation/result contract;
- correctly implement and test all relevant methods that are realistically implementable and useful within this repository;
- evaluate other credible methods and explicitly document why each is implemented, deferred, unsuitable or only experimental;
- report errors for the correct output metric with valid mathematical assumptions;
- refuse unsupported operations instead of returning invented or silently wrong outputs;
- provide an honest CPU/native-Vulkan/hardware support matrix;
- have reproducible tests, release builds, clean-install smoke tests, security checks, benchmark provenance and GitHub release assets;
- update public docs and **README last** so they describe the code that actually shipped;
- publish a tagged `v2.0.0` release only when every mandatory release gate passes.

Do not claim BPP = BQP, that all quantum advantage disappears, that every arbitrary circuit is efficiently simulable, or that a benchmark proves a general asymptotic speedup. Clearly distinguish query complexity, runtime, memory, output complexity, exact simulation, approximate simulation and hardware execution.

---

## 3. Phase 0 — Establish an evidence-based baseline

Before changing algorithms:

- Fetch the latest remote `main`, all open/closed PRs relevant to this repo, current tags/releases, Actions run histories, branch restrictions and release asset list.
- Record the exact start SHA and the initial dirty state in `research/v2/BASELINE.md`.
- Read `README.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `RELEASE_NOTES.md`, `SECURITY.md`, `docs/API_REFERENCE.md`, `docs/ARCHITECTURE.md`, `docs/USAGE_GUIDE.md`, `docs/BENCHMARKS.md`, `pyproject.toml`, `setup.py`, `CMakeLists.txt`, both CI/release workflows, the four backends, router, analyzer, shared parser, result schema, native core, tests, release scripts and `.gitignore`.
- Create an inventory of every public API, CLI command, backend, gate, result field, native target, shader, optional dependency and documentation command.
- Run the existing checks *without edits*: environment doctor, `python scripts/version.py`, `python scripts/check_version.py`, `python scripts/verify_no_silent_truncation.py`, shader validation, `pytest -ra`, mutation harness, clean CMake build, CTest, clean wheel/sdist build and the installed-wheel smoke commands from `release.yml`.
- Distinguish **passed**, **failed**, **skipped**, **not run**, **CI software Vulkan verified**, **loader verified** and **physical hardware verified**. A skipped native test does not count as a native pass.
- Save exact commands, package versions, logs and summaries in `research/v2/BASELINE.md`; do not dump huge logs into README.
- Verify that a fresh clone and out-of-tree build do not rely on stale artifacts in `bin/`, `build/`, local Python paths or environment-specific files.

If the current baseline fails, open a baseline defect record and repair it before adding research methods. Keep existing behavior changes documented; do not quietly accept previously passing tests becoming skipped.

---

## 4. Phase 1 — Correctness, numerical contracts and result semantics

Treat this as the first hard gate. No new simulator path should be added before the existing public behavior is trustworthy.

### 4.1 One result contract; no conflated error types

Audit `cqhecs/result.py` and the data exposed through the CLI/Qiskit API. Define separate concepts:

- **Execution state:** `SUCCESS`, `UNRESOLVED`, `FAILED` (or an equivalently clear, documented enum).
- **Method class:** exact symbolic/algebraic, exact combinatorial, floating-point numerical, certified approximation, heuristic/uncertified output.
- **Output kind:** joint counts/distribution, marginal counts, probabilities, expectation values, parity/correlations, statevector, density matrix.
- **Deliberate approximation error:** only for an approximation that was applied and whose bound applies to the returned output.
- **Numerical error/roundoff:** quantified only when it is actually estimated or bounded by a justified method; do not label a heuristic estimate as a rigorous bound.
- **Sampling error:** a confidence bound with explicit confidence/failure probability, number of samples and a clearly stated metric and support assumptions.
- **Unresolved reason:** unsupported gate, resource ceiling, numerical tolerance, method limit, cancellation or other specific cause.
- **Provenance:** CQ-HECS version, commit, backend, options, random seed, gate set, system/backend information and relevant diagnostic metrics.

Do not blindly sum unlike quantities into `total_error_bound`. Sum them only if the same metric, assumptions and triangle-inequality interpretation justify the composition. Otherwise expose separately named bounds on their own outputs and document the interpretation.

### 4.2 Fix the finite-shot confidence bound mathematically

The current `hoeffding_total_variation_bound(shots, delta)` must not retain an invalid dimension-free guarantee for arbitrary joint distributions. For a categorical distribution with `K` outcomes, a standard Weissman-style L1 concentration inequality has a support-size-dependent factor; in total variation, a form of the bound scales like `sqrt((K*ln(2) + ln(1/delta))/(2*shots))` under its stated assumptions (verify the exact theorem, constants, and `K` convention from a primary source before coding). This can become trivial for very large support, and that is an honest outcome.

Alternative where appropriate: report concentration bounds per observable whose samples are bounded (e.g. ±1 Pauli observable), with the number of observables and confidence budget explicitly represented. Do not call a bound on individual expectation values a bound on the complete bitstring distribution.

Tests must validate the theorem and assumptions, not just repeat the implementation's formula. Include high-cardinality counterexamples showing why a dimension-free joint-TV claim cannot hold.

### 4.3 Path A — stabilizer tableau

- Enumerate the actual supported Clifford operations and measurements.
- Verify phase bookkeeping, H/S/Sdg/X/Y/Z/CX/CZ/SWAP, reset if supported, repeated/non-terminal measurements, qubit indices, barriers/identities and classical-bit mapping.
- Any unsupported operation or unsupported dynamic circuit condition must raise a typed support error before partial execution.
- Test against Stim for large stabilizer circuits and Qiskit Statevector/Aer where suitable.
- Ensure sampling really uses the requested shot count, and report actual shots if method constraints limit them. Never expand a smaller sample to look like the requested count.

### 4.4 Path B — stabilizer-rank decomposition

- Document supported gates and branch-budget limits accurately. Check that every supported decomposition is mathematically valid for the gate convention/global phase.
- Test branch weights, normalization, interference, complex phases, RX/RY/RZ/P/U1 cases and fail-closed handling of unsupported rotations.
- Audit the current dense-statevector limit (`MAX_STATEVECTOR_QUBITS`) and high-width behavior: errors should be typed and routable, never replace the answer with a uniform or deterministic placeholder.
- Distinguish algebraically exact decompositions from their `complex128` implementation. Track numerical diagnostics or call the result numerically simulated; do not claim zero numerical error solely because an approximation cutoff was not deliberately applied.
- Test shot counts and confidence semantics separately from state-evolution correctness.

### 4.5 Path C — MPS/tensor chain

- Audit every gate dispatch branch. Unknown gates must raise, never fall through as identity.
- Verify two-qubit contraction index order, reversed qubit operands, non-adjacent SWAP networks, controlled phases, reset/measurement semantics and Qiskit bit order.
- Verify the roundoff/rank-selection criterion. Test tiny-but-meaningful singular values, normalization, statevector equivalence, accumulated truncation/roundoff estimates and behavior when a budget is reached.
- A sum of discarded singular values is not automatically a rigorous bound on every returned probability or expectation. Establish and test the actual error theorem; otherwise rename it to `estimated_*` and do not call it certified.
- Audit RAM accounting, temporary-file lifecycle, disk paging, cleanup on exceptions/cancellation, simultaneous jobs, filesystem-full conditions, file permissions, disk quotas, stale swap files and memory accounting before/after offload. `NVMe-offload` must mean real persisted tensor paging, not just a label.
- Dense sampling must have an explicit width limit. If a result cannot be sampled, return no fabricated counts and explain the supported alternative output.
- Ensure the backend does not mutate a state partially and then return a normal-looking success after memory exhaustion.

### 4.6 Path D — Sparse-Pauli / Heisenberg observable propagation

- Keep the claimed guarantee scoped to the actual requested observables.
- Test single-qubit Z observables, parity `Z_q Z_r`, and any added Pauli products against statevector/Aer on circuits small enough to enumerate exactly.
- Add tests for coefficient phases, unsupported gates, sparse-term merges, pruning at every layer, cumulative error accounting, tolerance equality boundaries, zero coefficients, non-finite input and invalid observable masks.
- Do not emit joint counts by default based only on independently sampled marginals. If optional marginal sampling remains, set unambiguous metadata such as `counts_are_joint_distribution: false`, and do not attach an observable bound as if it certified those samples.
- Verify that all supported two-qubit gates are mathematically conjugated; a missing rule must raise `UnsupportedPathDOperation`.

### 4.7 Router, parser, analyzer and Qiskit contract

- One shared parser/IR for all Python backends; no unsafe `eval`, no silent ignored instructions, no unparsed inputs defaulting to Path A.
- Capability checks must consider gate, gate parameters, qubit/clbit layout, measurement, reset, circuit width and method-specific limits.
- A user-forced backend must never silently reroute. Automatic routing may transition only on typed, expected capability/resource exceptions, not arbitrary `Exception`.
- Validate shots, seed, tolerances, resource limits and circuit inputs before execution.
- Audit `CQHecsBackend.run()` against Qiskit BackendV2 job/result contracts, multi-circuit input, options, target/transpilation, register layout and result metadata. A hand-written object with only a subset of job methods is not automatically a conformant Qiskit job.
- Test bit order and `measure_all()` extra classical-register behavior against Aer and Qiskit conventions.

### 4.8 Mutation test integrity is part of correctness

- Fix `scripts/run_mutation_tests.py` so baseline preconditions are asserted independently and baseline failure raises/fails the test; baseline failures must never count as a killed mutant.
- A mutation is killed only if a valid, independently verified baseline passes and the intentionally altered behavior is detected by the specific assertion.
- The mutation command exits non-zero when any mutant survives, the baseline is broken, or the harness itself errors.
- Prefer a real mutation framework for Python/C++ where it materially improves coverage. If mutations are manually injected, describe them accurately; do not claim a conventional mutation score for invariant probes that never mutate the target implementation.
- Add tests that deliberately make a mutant survive and deliberately break the baseline to prove the harness fails closed.

**Exit criteria for Phase 1:** all correctness-contract tests pass; every former fabricated-result/truncation/fail-open defect class is guarded by behavior-based regression tests; result semantics do not overclaim; all baseline CI jobs still pass.

---

## 5. Phase 2 — Complete method inventory and research review

Create and maintain:

- `research/v2/METHOD_CATALOG.md`
- `research/v2/LITERATURE_MAP.md`
- `research/v2/HYPOTHESES.md`
- `research/v2/EXPERIMENT_LOG.md`
- `research/v2/FORMALIZATION_STATUS.md`
- `docs/V2_IMPLEMENTATION_MATRIX.md`

For each candidate method, record: primary references, exact problem it solves, assumptions, supported outputs, complexity/known hard cases, existing implementation/dependency, estimated effort, licenses, reference oracle, tests, benchmark families, correctness status, decision (implement / integrate / experimental / defer / reject), and reason. “Investigated” does not mean “implemented,” and “implemented” does not mean “verified.”

### Methods to evaluate systematically

#### A. Exact or combinatorially exact methods

1. **Dense statevector / Schrödinger simulation** — implement or preserve as a small-circuit reference backend, with a hard memory estimate and fail-fast width guard.
2. **Stabilizer tableau / Gottesman–Knill** — preserve Path A and broaden tested Clifford coverage only where mathematically valid.
3. **Clifford+T stabilizer decompositions** — stabilizer rank, extent, rank reduction and branch strategies; exact symbolic versus floating-point versions must be distinguished.
4. **Matrix Product States / tensor trains** — current Path C, with accurate numerical contracts, MPS ordering/layout and optional controlled truncation.
5. **General tensor-network contraction** — contraction-order heuristics, graph/hypergraph representations, treewidth-like structural measures and output-specific contraction. Evaluate whether a practical general-TN backend expands useful coverage beyond MPS.
6. **Schrödinger–Feynman / circuit partitioning** — split circuits along cuts and trade RAM for contraction/summation work; account for cut overhead and exponential worst cases.
7. **Decision diagrams** — QMDD/QuIDD and related amplitude/quantum-function decision diagrams. Investigate licensing, maintenance, support and real performance before integrating third-party code.
8. **Feynman path-sum methods** — evaluate for circuits with favorable path structure, low non-Clifford count or repeated substructure.
9. **Graph-state / ZX-calculus reductions** — consider graph rewrite, stabilizer simplification and measurement-based/graph-structured workloads; implement only if a validated implementation and benchmark demonstrate value.
10. **Symmetry and subspace reduction** — conserved parity, particle-number sectors, permutation symmetry and other verified invariants. Require a sound detection/proof of the symmetry before reducing the state space.
11. **Exact arithmetic for restricted gate families** — use the Giles–Selinger ring or other algebraic representation only where the supported gates really belong to it; test exactness rather than rebranding complex floating-point arithmetic.
12. **Heisenberg / Pauli propagation** — Path D and possible extensions to user-selected local/multi-qubit observables. Bounds belong to each observable/output and must be mathematically proved.

#### B. Approximate, stochastic and noise-focused methods

13. **Explicit MPS/TN truncation** with a genuine error estimate/certificate and user-controlled tolerance; no silent approximation.
14. **Monte Carlo stabilizer decompositions / quasiprobability methods**; quantify variance, sample complexity and confidence intervals.
15. **Quantum trajectories** for noisy channels when applicable; distinguish stochastic estimator error from approximation error.
16. **Density-matrix / MPO simulation** for noisy or mixed-state circuits within explicit width limits; quantify the quadratic/exponential memory cost.
17. **Pauli propagation with term pruning** and observable-specific certified bounds.
18. **Circuit cutting** / wire cuts / gate cuts, where the overhead remains tractable and outputs can be combined correctly.
19. **Low-rank and structure-specific approximations** only if the algorithm explains the conditions for efficacy and supplies a validated error metric.
20. **Sampling/observable-first execution** where computing the requested marginal/observable is cheaper than computing the full distribution. Make the output contract explicit.

#### C. Performance and implementation techniques

21. Parallel CPU execution, BLAS threading and controlled thread pools.
22. SIMD/AVX2 as an optional target-scoped optimization with runtime/support expectations; portable CPU baseline must continue to work.
23. GPU acceleration in the native Vulkan engine only where that code actually dispatches the relevant kernels and results are verified against a CPU oracle.
24. Memory-mapped/disk-backed tensor storage only with real accounting, cleanup and I/O benchmarks; paging does not make exponential work disappear.
25. Cached contraction paths, gate fusion, circuit simplification and resource estimation.
26. Hybrid routing across methods, but only with explicit conversion costs, assumptions and error propagation.
27. Noisy circuit, Clifford-noise and restricted hardware-noise simulation if it is a meaningful user need.

### Research with OpenAI Math

- Inspect the official public catalogue at <https://github.com/openai/math> and its live `README.md`, `CONTENTS.md`, `overview` and Lean formalization catalogue. The catalogue has changed over time (about 719–722 manuscripts in recent snapshots); never hardcode the count.
- Treat it as a mathematical manuscript archive, not as a turnkey quantum simulator or a set of automatically proven theorems. Not every result is formally verified; check each paper's current status.
- Search the catalogue for quantum/query/circuit complexity, Boolean functions, probabilistic methods, matrix/operator algebra, graph/tensor structures, optimization, formal proof methods and algorithmic lower bounds. Classify papers by relevance rather than forcing unrelated results into this project.
- Where a theorem could guide CQ-HECS, extract its precise statement, assumptions, model of computation, complexity metric, proof status and implications. Compare against independent primary sources and counterexamples.
- If there is an accompanying Lean formalization, run its documented build/tests in an isolated environment. A passing Lean proof proves only the formal statement as encoded; verify that it actually states the property needed by our implementation.
- Do not download or vendor hundreds of PDFs unnecessarily. Use a pinned snapshot/metadata index or a script that records upstream commit SHA, paper URL, title, family/discipline and access date. Respect repository license and individual manuscript terms before redistributing full text.
- Never claim a result proves BQP = BPP, eliminates all quantum advantage, or solves arbitrary circuit simulation unless an independently verified theorem genuinely says so.

### Required hypothesis discipline

For every proposed improvement, write a falsifiable hypothesis with:

- exact circuit/task class;
- formal assumptions and input/output model;
- baseline method and quality/precision;
- predicted asymptotic and measured resource change;
- adversarial cases likely to falsify it;
- oracle/reference comparison;
- stop/reject criteria;
- proof status: conjecture, experimentally supported, formally verified under assumptions.

Potential first hypotheses:

- A router using gate structure, layout/treewidth estimates, non-Clifford resources and requested observables can reduce median and tail resource use compared with current fixed thresholds.
- Observable-only simulation can handle selected circuits larger than the full-state limit while preserving a mathematically valid observable-specific error bound.
- Combining stabilizer chunks with MPS/TN contraction or circuit cutting expands tractable workload classes beyond each method alone, after conversion/cut overhead is included.
- Symmetry-aware reduction lowers effective dimension for circuits that have a machine-checkable invariant.
- Decision diagrams are worthwhile only for circuit families with repeat/substructure that produce lower memory/time than the existing baselines.

Each research result must include negative results and regimes where the method loses. A benchmark win on a single toy circuit is not a general claim.

---

## 6. Phase 3 — Benchmark suite and reference oracles

Build a versioned, deterministic benchmark matrix. Preserve the historical benchmark report, clearly marked historical; do not mix old metrics with current numbers.

### Circuit families

- Bell pair and GHZ states at small widths and, for stabilizer-only operations, larger widths.
- Random Clifford circuits with fixed seeds and Stim comparison.
- Clifford+T circuits sweeping T-count, depth and qubit count.
- Low-T circuits beyond the dense statevector limit to test refusal/routing semantics.
- QFT and controlled-phase circuits at sizes that allow an exact oracle.
- 1D cluster/brickwork circuits; 2D/grid circuits; random sparse and dense connectivity.
- Circuits with low bond dimension and circuits engineered to exhibit growing/volume-law entanglement.
- Circuit families with repeated blocks, symmetries, low treewidth and poor treewidth.
- Selected noisy circuits for any density-matrix/trajectory method actually implemented.
- Invalid QASM, unsupported gates, extreme parameters, malformed registers and unsupported dynamic conditions.

### Oracles and statistical tests

- Small exact statevector: Qiskit `Statevector` as the main oracle; compare amplitudes up to allowed global phase where appropriate, probability vectors, expectation values and observables.
- Stabilizer cases: Stim plus independent known invariants.
- Probability sampling: compare distributions with mathematically valid support-aware/statistical tests and stated confidence; never demand identical random sample counts from unrelated seeds.
- Observable propagation: compare each requested expectation against the exact oracle and validate the advertised bound against observed error on many generated small circuits.
- Routing: verify the chosen path supports the circuit; intentionally forced unsupported paths must fail with typed and useful diagnostics.
- Fuzzing/property tests: generate circuits from each backend's supported gate set, shrinking failures to minimal examples. Invalid operations must be rejected deterministically.

### Resource/benchmark output

Each record includes commit SHA, version, OS, CPU, GPU/device/driver, Vulkan loader/device/queue status, compiler and flags, Python/Qiskit/NumPy versions, method, circuit family/seed, qubits, gates, shots, tolerance, elapsed wall and CPU time, peak RSS, GPU allocation/usage if genuinely measured, disk I/O if relevant, returned output type, error/confidence fields and status. Store raw JSON plus a short readable report.

A benchmark must not label estimated allocation as measured VRAM. Do not claim `HARDWARE_VERIFIED` from Lavapipe/software Vulkan or loader enumeration alone.

---

## 7. Phase 4 — v2 architecture and implementation policy

Implement the fewest layers needed for maintainable extensibility; do not perform a wholesale rewrite without measured benefit.

### Shared IR and capability system

- Define a normalized internal circuit representation shared by parser, router, backends, tests and CLI.
- Explicitly model gate name, validated parameters, qubits, measurement-to-classical-bit mapping and supported classical/dynamic behavior.
- Record the supported gate set per method; no implicit identity fallthrough.
- A capability query must return supported/not supported plus a reason before execution.
- Router decisions are deterministic and explainable; estimates include resource costs, not just a single heuristic such as T-count or cut-width.
- Typed resource/capability errors are routable; bugs and internal exceptions are not automatically converted into a different backend choice.

### Backend interface

Use a stable protocol with methods equivalent to:

- `supports(circuit) -> CapabilityReport`
- `estimate_resources(circuit, options) -> ResourceEstimate`
- `run(circuit, options) -> SimulationResult`

Do not preserve duplicated or conflicting parser logic between backends. Legacy APIs should either delegate to the new implementation or be deprecated with tests and documentation.

### Candidate backends for v2

Keep the four current methods as named strategies after their contracts are corrected. Add the dense statevector as a bounded reference/production backend if it is not already a clean, public strategy. Investigate generic tensor network contraction, symmetry reduction and either decision diagrams or circuit cutting as candidates. Implement only those which pass correctness, practical-resource and comparative benchmark gates. If a method is not useful/credible within this release, document it as investigated but deferred; do not add a nonfunctional stub to make a list look complete.

### CPU/native/Vulkan separation

- CPU Python distribution must work without Vulkan SDK if that remains the declared supported use case.
- The native Vulkan core must be a separately testable build/runtime capability with explicit availability and typed failure.
- Confirm that the native path actually executes the relevant simulation computation, not merely a utility or shader initialization.
- Make Vulkan an optional CMake feature if the stated product needs a CPU-only native build; ensure `find_package(Vulkan REQUIRED)` is conditional when Vulkan is disabled.
- Record discovered device, requested compute feature/queue, actual dispatched kernel and completion/error status. Software Vulkan is a separate CI tier.
- Test CPU-only builds, software-Vulkan CI, physical GPU runs only where available, and cross-vendor compatibility only after actual dispatch/results are verified on each claimed platform.
- Keep SIMD optimizations target-scoped; portable baseline must not require AVX2.

### Error and status invariants

- `FAILED`, `UNRESOLVED`, unsupported input and timeout are not normal successful simulations.
- `exact=True` means no deliberate approximation, not that floating-point arithmetic is mathematically exact. Include an exactness/numerical classification to disambiguate.
- A finite-shot `counts` result is a sample; do not call the empirical histogram the exact probability distribution.
- Error bounds must identify the target metric and confidence level. A local observable bound is not a global distribution bound.
- No result can be both failed/unresolved and presented as a normal completed result without unmistakable status metadata.
- Validate invariants inside `SimulationResult` constructors where possible; make contradictory combinations impossible or fail fast.

---

## 8. Phase 5 — CLI, API and developer experience

The `cq-hecs` command should be the one documented public Python CLI. Check the current CLI before changing it; preserve compatible useful commands.

Expected CLI contract (adapt names only with reason):

```text
cq-hecs version
cq-hecs doctor
cq-hecs backend list
cq-hecs analyze <file.qasm|name:bell>
cq-hecs run <file.qasm|name:bell> --backend auto --shots 1000 --seed 42
cq-hecs verify <circuit> --reference aer
cq-hecs benchmark smoke
cq-hecs benchmark matrix --output artifacts/benchmark-results.json
```

Requirements:

- `--help` works at every subcommand; invalid inputs return documented stable exit codes.
- `--format json` writes exactly one valid JSON document to stdout; all human logs/progress go to stderr. Use a versioned result schema.
- Paths are quoted/handled safely on Windows, Linux and paths with spaces/Unicode.
- `doctor` distinguishes Python CPU paths, native library, Vulkan loader, software device and physical hardware, with actionable advice.
- `analyze` explains selected method, supported gates, estimated resources, risks and reasons for unsupported output.
- `run` reports requested versus actual shots and output kind; do not fabricate counts for unsupported widths.
- `verify` can fail closed and identifies the metric compared, oracle, tolerances, statistical significance and pass/fail reason.
- Add CLI contract tests for JSON purity, exit codes, missing files, invalid options, invalid circuits, unresolved cases, logging and subprocess invocation.

The C++ CLI and the Python `cq-hecs` CLI may coexist, but label them unambiguously (`cq-hecs` for Python package, native binary for C++ engine), publish their support/output contracts separately, and avoid duplicate commands whose behavior differs silently.

---

## 9. Phase 6 — C++ core, Vulkan, native packaging and cross-platform work

- Audit `CMakeLists.txt` targets, output directories, shader embedding, C-ABI, nanobind/pybind extension, AVX2 flags, shared objects and tests.
- Clean builds must work out-of-tree on Windows/MSVC and Ubuntu/GCC/Clang with documented versions. Use separate build directories per generator/configuration.
- Run compiler warnings; sanitize where supported (ASan/UBSan, and TSan for concurrency-sensitive code). Investigate each new warning rather than hiding warnings globally.
- Validate SPIR-V with `glslangValidator` and, where installable, `spirv-val`; run native shader/pipeline tests on software Vulkan, then actual physical GPU execution where hardware access exists.
- Correctly distinguish `CI_VERIFIED`, `LOADER_VERIFIED`, `SOFTWARE_VULKAN_VERIFIED`, and `PHYSICAL_DEVICE_VERIFIED`. State which exact method/kernel is verified.
- Test native C-ABI lifecycle, invalid input, ownership, memory bounds, concurrency, errors and bitstring/measurement semantics.
- Do not advertise native Python acceleration unless the wheel actually contains a compatible extension and a clean-install smoke test confirms it is loaded and used.
- Decide the v2 deliverables based on what can be built and tested: pure-Python wheel/sdist plus optional Windows/Linux native archives. If native archives are advertised, build each in CI, test it on a clean runner, include licenses/dependencies and checksums. Do not pretend the Python wheel contains native binaries when it does not.

---

## 10. Phase 7 — Performance and method selection

- Baseline all methods on identical circuits, shot counts, output types and accuracy goals.
- Optimize only after correctness; keep reference paths for differential tests.
- Track peak RAM/VRAM, wall time, scaling trends and failure thresholds. Do not use one GHZ timing to generalize to all circuits.
- Evaluate contraction ordering, gate fusion, state/circuit simplification, symmetry checks, caching, vectorization, controlled CPU threading and optional GPU dispatch.
- Include startup/compilation costs and CPU↔GPU transfer costs in benchmarks; do not hide them unless the benchmark explicitly measures steady-state throughput.
- Make the automatic router benchmark-informed but deterministic and explainable. If two methods cannot be reliably compared from estimates, choose the safer supported method or expose the uncertainty.
- Never allow a performance optimization to turn unsupported operations into identities, drop small terms silently, alter bit order or bypass error tracking.

---

## 11. Phase 8 — Tests, reliability and security gates

### Mandatory gates on every PR

1. Python syntax/import/compile checks and lint.
2. Version checker and safe-truncation/fabricated-result audit.
3. Unit and contract tests for all changed modules.
4. Full pytest suite with explicit skip reporting.
5. CMake Release build and CTest on Ubuntu and Windows.
6. Shader validation and software-Vulkan checks where configured.
7. Behavior-valid mutation tests; survivors fail the job.
8. Qiskit Aer and Stim differential tests for supported domains.
9. Property-based/fuzz tests for circuit/QASM parsing and supported operations; keep corpus seeds for discovered bugs.
10. Clean install of the built wheel and sdist smoke test with `cq-hecs --help`, `version`, `doctor`, a small run and pure-JSON validation.
11. Security/dependency/license checks and secret scan.
12. Benchmark schema validation, not speed thresholds on shared virtualized runners unless variance is controlled.

### Coverage standards

- Focus on decision branches and contracts, not a vanity global 100% number.
- Set enforced coverage goals for critical packages only after measuring the baseline (target at least 90% statement coverage in core router/result/parser/backends as a starting point, with explicit branch coverage for safety-critical decisions). Raise coverage only with meaningful tests.
- Every bug discovered during this mission gets a focused regression test.
- A test marked skip must have an explicit environment requirement; CI must show when native components were skipped and must have at least one job where they are built and exercised.
- Report test count, pass, fail, skip, mutation survivors and coverage from actual logs, not hardcoded docs.

### Security and stability

- Validate parsers and resource options against huge/malicious input, path traversal, malformed JSON/QASM/CNF and resource-exhaustion cases.
- Ensure subprocess invocations use argument arrays rather than interpolated shell strings where possible.
- Audit temporary files, memory budgets, concurrency state and cleanup.
- Scan dependencies, licenses, secrets and packaged files.
- Fix outdated security support versions/response language to match the new version and practical maintainer capacity. Do not publish an untrue SLA.

---

## 12. Phase 9 — Packaging, versioning and release engineering

Do not set the canonical version to `2.0.0` just to make the job appear close to done. Keep release versioning coherent and make the version bump part of the actual release candidate once the implementation is frozen.

### Single version source

- Keep `scripts/version.py` as the canonical source or replace it with a true metadata source; do not duplicate independent hardcoded versions throughout the repo.
- Verify `cqhecs/__init__.py`, `pyproject.toml`, `setup.py` if retained, `CMakeLists.txt`, `CITATION.cff`, generated SBOM, release workflow, package filenames, `SECURITY.md`, changelog/release notes, CLI output and README after the final README edit.
- Remove or consolidate `setup.py` if modern `pyproject.toml` supports the complete package build; any legacy file retained must not disagree.
- Extend the version checker to validate release-note/version references and public version-bearing files, without blocking the intentional `[Unreleased]` section during development.

### Artifact generator issues to address

- Make the release generator clean or create an isolated fresh `dist/` so stale packages cannot be accidentally published.
- Avoid redundant competing build paths if `python -m build` already built wheel/sdist; or have one canonical builder and validate its outputs.
- Build the SPDX SBOM from actual selected runtime and native dependencies, accurate versions and correct license identifiers; no hand-written mismatches like an older NumPy minimum or Qiskit version.
- Include SHA256 hashes for every published release asset except the checksum file itself (including the SBOM and release notes if they are assets). Recompute after the asset set is finalized.
- Ensure `audit/release_tracking.json` records the exact released commit and hashes and is generated deterministically apart from permitted timestamp fields.
- Generate release notes for v2.0.0 that actually describe v2.0.0. Never copy stale `v0.1.0` notes into a correctly named v2 file.
- If the workflow advertises signing/attestation, implement and test actual signing/attestation; otherwise label it “build and publish,” not “sign.”
- Verify every asset exists and opens; install wheel from an empty virtual environment; extract/run native archives on supported platforms; validate SBOM/checksum content.
- Release workflow tag validation must require `v2.0.0` when canonical version is `2.0.0`, and reject mismatched tags.
- Consider provenance attestations and minimal GitHub permissions. Secrets must not be exposed to untrusted PR code.

### Expected v2 release assets

At minimum, only publish assets that are actually built and tested:

- `cqhecs-2.0.0-py3-none-any.whl` if it remains pure Python;
- `cqhecs-2.0.0.tar.gz` source distribution;
- `sha256sums.txt` listing all assets;
- `cqhecs-sbom.spdx.json` for the actual packaged components;
- `RELEASE_NOTES_v2.0.0.md` based on complete current release notes;
- current benchmark JSON and human report if regenerated and accurately labeled;
- platform-native archives only if Windows/Linux builds and clean-install/execution tests pass.

Do not invent asset names or upload historical benchmark data as current.

---

## 13. Final documentation order — README MUST be last edit

The user explicitly requires README to be the final content update. Follow this exact order:

1. Finish code, method research, tests, CI, packaging, SBOM/checksum/release workflow and all documentation other than README.
2. Update `CHANGELOG.md`, `RELEASE_NOTES.md`, `SECURITY.md`, `docs/API_REFERENCE.md`, `docs/ARCHITECTURE.md`, `docs/USAGE_GUIDE.md`, `docs/BENCHMARKS.md`, relevant LLMS documents and examples to reflect tested v2 behavior. Mark unverified or historical benchmarks clearly.
3. Freeze the feature set; choose the methods that passed their gates; document deferred/rejected methods and why. Do not allow the README to claim features still in progress.
4. Set canonical version `2.0.0`, align versioned metadata, run package/release dry-run checks and verify the changelog/release notes. Prepare release commit contents.
5. **Only now update `README.md` as the final file edit**: provide an accurate overview, honest capabilities/limitations table, install methods, tested commands, examples, output/error semantics, current CI state, hardware verification matrix, benchmark provenance, links to research/design docs, and release/download links that exist (or correct links templated for the release process). Remove unsupported cross-vendor/exactness/VRAM claims.
6. After README is updated, run the complete final validation matrix again (the README has changed, so it must not escape validation), inspect the complete diff, run documentation link/command checks and validate README examples against the v2 CLI.
7. Commit the release-candidate changes. Wait for local/cloud checks to complete in the same work session. Fix failures and rerun the final gates. If README has to change to reflect a real correction, repeat the final validation after its new last edit.
8. Only if everything is green, push the final commit, tag exactly `v2.0.0` on it and push the tag. Observe the release workflow, check all assets, verify checksums and run a download/install smoke test.
9. If a mandatory gate remains failing or a key capability is not genuinely implemented, do not tag/release. Keep working or report the specific blocker. Never publish a broken build because the user asked for a release.

---

## 14. Release acceptance checklist

Before tag/publish, every item must be checked from actual evidence:

- [ ] Latest `main` and PR history reconciled; no user changes lost.
- [ ] All relevant classical methods inventoried, tried/benchmarked where feasible, and an implement/defer decision with evidence documented.
- [ ] No critical correctness issues known in supported gates/results; previous fabrication/truncation/routing failures have regression tests.
- [ ] Probability/counts/observable outputs have correct and distinct semantics.
- [ ] Finite-shot statistical bounds are valid for the stated metric/support/confidence.
- [ ] Path C's numeric/truncation claims are correct and bounded or clearly labeled estimates.
- [ ] Backend support matrix and router are fail-closed.
- [ ] Mutation harness fails on broken baselines and surviving mutants.
- [ ] CPU/Python package tests pass; native components build and run in CI; all skips are explained.
- [ ] Ubuntu and Windows CI are green on the release commit; extra platform claims have genuine supporting runs.
- [ ] CMake/CTest, Python tests, fuzz/property tests, exact oracle tests, security checks and clean install pass.
- [ ] Native Vulkan claims match actual dispatch evidence; no unsupported physical-GPU claim remains.
- [ ] CLI commands/JSON/exit codes are stable and documented.
- [ ] Release version is `2.0.0`; `v2.0.0` tag will point to the tested commit.
- [ ] Wheel/sdist/native archives are built, installed/executed where applicable, and correctly named.
- [ ] SBOM, checksums, provenance and release notes refer to the exact release and assets.
- [ ] Other docs updated; README edited last; final CI rerun after README.
- [ ] GitHub Release is published and its live assets/downloads are verified.

---

## 15. Final report to the user

At completion, report:

- release URL and exact tag/commit SHA;
- which assets exist and which clean-install tests passed;
- latest Ubuntu/Windows CI run links and conclusions;
- actual pass/fail/skip counts, mutation score and measured coverage;
- methods implemented versus investigated/deferred, with links to the method matrix and experiments;
- verified hardware tiers, stating explicitly if physical GPU execution was not available;
- remaining limitations or blockers (never bury them under a “100% done” claim).

If unable to publish because the environment lacks write permissions or credentials, say so plainly and provide the tested branch/PR/patch links. Do not claim a push or release that has not occurred.
