# GEMINI MISSION — CQ-HECS Next Stable Release

**Mission type:** Autonomous repository engineering, correctness audit, test hardening, CI/CD repair, and stable-release preparation  
**Repository:** `https://github.com/timfromhcs/CQ-HECS`  
**Proposed target:** `v2.2.0` Stable, subject to the SemVer decision gate below  
**Language:** Keep code, tests, commits, and public project documentation in the language and conventions already used by the relevant file. This mission document is German; source code and technical docs may remain English where the repository already uses English.  
**Execution mode:** Work directly in the checked-out repository. Do not merely give advice or generate a plan: inspect, implement, test, fix, commit, push, verify cloud CI, update documentation last, push again, and verify the final commit's CI.

---

## 0. Mission objective

Turn the current CQ-HECS repository into a **truthful, reproducible, tested, and release-ready Stable version**. Improve the implementation first, then strengthen tests and CI until they demonstrate that the code works. Push changes to GitHub using the provided credential securely. Continue the fix/test/push/CI loop until all required local and cloud gates are green. **Only after implementation, tests, GitHub CI, and available Cloud Build validation are green, rewrite the README to accurately describe the final implementation.** Push that documentation change and run the relevant gates again on the final commit.

The final result must be supported by actual commands, exit codes, logs, Git commit SHAs, and CI run links. Never claim a test, physical GPU run, cloud build, or release step succeeded unless evidence proves it.

### Core values

1. **Truth over appearances.** No fabricated counts, fake telemetry, misleading benchmark records, fake hardware support, unearned `exact` claims, or success status when a required test did not run.
2. **Fail closed.** Unsupported inputs, exceeded budgets, failed verification, missing native dependencies, and unresolved results must be surfaced explicitly. No silent identity gates, automatic unknown-gate acceptance, hidden truncation, invented results, or silent path changes.
3. **Tests prove contracts, not just absence of crashes.** Every meaningful feature needs positive, negative, boundary, and regression coverage appropriate to the risk.
4. **Preserve the repository.** Read the current `GEMINI.md`, contributor instructions, Git state, and workflows first. Preserve valid existing guidance and user changes. Do not wipe, reset, force-push, rewrite published tags, or remove tests just to make a build green.
5. **Never bypass failed gates.** Repair the root cause. Do not disable tests, loosen assertions without specification evidence, skip failing jobs silently, or conceal warnings to produce a green badge.
6. **No secrets in source or logs.** A GitHub token will be provided by the operator/agent environment. Use it only through secure credential mechanisms. Never print, commit, paste, echo, or embed it in a URL, script, test fixture, log, generated doc, or Git remote.

---

## 1. Initial reconnaissance and repository safety

Before editing any file:

1. Read the existing root `GEMINI.md`, `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `SECURITY.md`, `CQ-HECS-V2-ROADMAP.md`, `research/v2_1/`, `docs/`, `pyproject.toml`, `CMakeLists.txt`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, and `cloudbuild.yaml`.
2. Re-query the live GitHub repository, current default branch, latest commit, tags/releases, PRs, workflow status, and Cloud Build configuration. The repository may have changed since this instruction was authored.
3. Check `git status --short --branch`, `git remote -v`, current branch, current commit, tracked/untracked changes, and published tags. Record the starting SHA in a durable audit file such as `research/v2_2/BASELINE.md` or `docs/RELEASE_AUDIT_v2.2.md`.
4. Do not overwrite or discard pre-existing user work. If the worktree contains uncommitted changes, inspect and preserve them; separate mission edits from unrelated edits. Never use `git reset --hard`, `git clean -fd`, or an equivalent destructive operation.
5. Work on a dedicated branch, for example `agent/v2.2.0-stable-hardening`, unless repository policy or an existing active work branch requires a safer alternative. Never force-push. Never move or retag an already-published version tag.
6. Inspect current `main`, not stale audit documents, before deciding whether a reported issue remains present. Label each finding `CONFIRMED`, `ALREADY FIXED`, `NOT REPRODUCED`, or `BLOCKED` with evidence.

### SemVer decision gate

`v2.1.0` was the last known published release during the original audit. Confirm the live release first. The proposed target is `v2.2.0` if this work delivers compatible new capabilities such as explainable routing, improved diagnostics, or provenance metadata. If the final change set is only bug fixes and no additive capability, explicitly evaluate whether a patch release is more correct. Do not bump or tag a version merely to make it look new. Once the decision is made, keep all version surfaces consistent and immutable tags intact.

---

## 2. Baseline: prove the initial state before changing it

Run the applicable checks on the untouched checkout and record each as **PASS / FAIL / SKIP / NOT RUN / BLOCKED**. Include the exact command, platform, toolchain, dependency versions, duration where useful, exit code, and log/artifact location.

At minimum inspect and run where available:

- `python scripts/version.py`
- `python scripts/check_version.py`
- `python scripts/verify_no_silent_truncation.py`
- `python scripts/verify_vulkan_shaders.py`
- `python scripts/run_mutation_tests.py`
- `python -m compileall cqhecs tests`
- all Python tests with the project-supported invocation
- CMake configure/build and CTest
- native self-tests, if the built executable supports them
- packaging: wheel and source distribution build
- clean virtual-environment install of the actual built wheel
- CLI contract: `--help`, `version`, `doctor`, a valid tiny circuit, an invalid circuit, JSON parsing, and exit-code checks
- GitHub Actions on Ubuntu and Windows
- Cloud Build or other configured cloud build, if `cloudbuild.yaml` is connected to a live project/trigger and credentials permit verification

Do not call the baseline “green” if a required test did not run. A failed baseline is valuable evidence; fix it instead of hiding it.

Create/update a test evidence ledger, recommended path: `research/v2_2/TEST_MATRIX.md`. Do not put secrets, private environment data, API keys, or sensitive machine identifiers into that ledger.

---

## 3. Confirmed review targets from the prior audit

Re-verify every item against the live checkout before changing it. These are audit targets, not permission to make blind edits.

### 3.1 QASM parser tests and fail-closed input semantics

File previously reviewed: `tests/test_fuzz_qasm.py`.

Several existing tests appear to expect success for malformed floating-point parameters, unknown gates, out-of-range qubit indices, or syntax missing required punctuation. Verify the intended OpenQASM version and the documented parser contract. For each case, explicitly decide whether the input is valid, invalid, or accepted under a documented recovery rule.

Required work:

- Invalid numeric parameters such as malformed floats, `NaN`, infinity where prohibited, or malformed expressions must not silently become valid gate parameters.
- Unknown or unsupported gates must be rejected unless the specific parser/API contract documents a safe, semantically correct handling mode. Never silently treat them as identity operations.
- Out-of-range indices must not be silently rewritten or cause undocumented register expansion. If an extension is intended, document and test it separately.
- Missing semicolons and malformed syntax should follow one explicit grammar/recovery policy. Tests must assert that policy rather than assume that lenient parsing is always desirable.
- Empty/comment-only input must follow a documented policy (valid no-op or structured parse error); either can be defensible, but be consistent.
- Assert process return code, structured JSON schema, error category, stdout/stderr separation, and absence of fabricated successful circuit results.
- Use timeouts in subprocess tests. Bound maximum input size and runtime for fuzz targets.

Keep regression tests for every known parser bug after it is fixed.

### 3.2 Optional `psutil` and false-green resource tests

File previously reviewed: `tests/test_long_running_stress.py`.

The test optionally imports `psutil` and uses a fallback RAM delta of `0.0` if it is unavailable. That can make a memory assertion pass even though RAM was never measured.

Required work:

- A resource test must never equate “measurement unavailable” with “resource usage equals zero”.
- Either install a required measurement dependency in the specific test extra/CI job and fail if absent, or use an explicit `pytest.skip`/unavailable state with a clear reason. A skip must be visible in CI and release evidence.
- Distinguish host RSS, tracked simulator allocations, and real device-local/VRAM measurements. Do not label an internal memory-budget counter as actual GPU memory usage.
- Test the resource governor's arithmetic and budget decisions independently from real process/device measurements.
- Use repeatable sampling and tolerate normal OS RSS noise without masking unbounded growth.

### 3.3 Concurrency tests must match the promised contract

File previously reviewed: `tests/test_concurrency.py`.

The existing test creates independent solver/scheduler/MPS objects in worker threads. This validates concurrent independent workloads, not shared-instance thread safety.

Required work:

- Document which objects/APIs are thread-safe and which require per-thread instances.
- Test independent concurrent jobs separately from shared-instance access if shared use is supported.
- When testing shared state, synchronize starts, collect every future result, impose timeouts, verify output correctness (not just a boolean success), and check for corruption, deadlocks, race findings, and leaked resources.
- Do not promise race-free behaviour based only on a thread-pool test without sanitizers or shared-state coverage.

### 3.4 SVD precision test names and claims must match the test

File previously reviewed: `tests/test_svd_precision.py`.

Its name/docstring and code describe different cycle counts. Reconcile the test name, comments, loop counts, assertion semantics, and reported test matrix. Test reconstruction error, relative/absolute tolerances, near-zero and ill-conditioned matrices, complex tensors, degenerate singular spectra, and the distinction between a diagnostic residual and a mathematically certified simulation error bound.

Do not use a test that simply repeats an operation many times as proof of “zero drift” unless it measures and asserts the quantity actually claimed.

### 3.5 Mutation testing: test the harness and the production code honestly

Files previously reviewed: `scripts/run_mutation_tests.py`, `tests/test_mutation_harness_meta.py`.

The repository has meta-tests for baseline failure, surviving mutants, and harness errors. Preserve them. Inspect whether each listed “mutant” actually mutates or isolates the production implementation, or whether it only simulates a defective behaviour in a hand-written helper. Accurately name the mechanism.

Required work:

- A clean baseline is a prerequisite; broken baseline means the mutation gate fails.
- Every surviving mutant or harness error must yield a non-zero exit code.
- A mutant is killed only if an independent behavioural assertion detects the injected defect. Exceptions caused merely by a broken harness are not kills.
- Add mutations for the highest-risk historical defects: unknown gate treated as identity, wrong CZ conjugation sign, qubit/classical-bit ordering, fabricated wide-register counts, false `exact=True`, suppressed error bounds, swallowed resource failure, wrong T-count routing, missing JSON fields, and incorrect exit status.
- Where practical, add a maintained source mutation-testing tool for Python (evaluate tools such as `mutmut` or Cosmic Ray), or implement isolated source patches with deterministic restoration and explicit checks. Do not blindly add a new tool without confirming maintenance, supported Python versions, runtime, and compatibility.
- Do not advertise a “100% mutation score” as broad proof of correctness; state the mutant set, scope, exclusions, and actual score.

### 3.6 CI and coverage must create real gates

File previously reviewed: `.github/workflows/ci.yml`.

The workflow installs broad/unpinned latest dependencies, uses Python 3.11 as the main lane, reports coverage for `cqhecs`, but does not enforce a minimum threshold or explicitly enable branch coverage in the reported command.

Required work:

- Audit supported Python and dependency versions against current upstream support policies. The package metadata must not claim versions that are not tested. Avoid unneeded claims of support for end-of-life interpreters. Change metadata only after validating compatibility and documenting the policy.
- Use a deterministic pinned/constraints test lane for releases plus a separate compatibility lane for newest supported versions. Do not let every stable build silently float to arbitrary dependency versions.
- Add a supported-version matrix, with a fast required PR lane and broader scheduled/nightly lane.
- Add Python branch coverage. Establish a real baseline before selecting an enforceable threshold. Prefer meaningful coverage on the correctness-critical modules, not a vanity global percentage.
- Include maintained code that is part of the supported product in the coverage plan (for example `cqhecs/` and applicable `python_bridge/` modules). Explain exclusions explicitly.
- Make coverage failures fail CI; report the exact threshold and artifact.
- Verify CI does not silently omit test files, optional dependencies, build targets, or failing jobs.
- Give workflow jobs minimum required token permissions. Pin GitHub Actions to reviewed immutable commit SHAs where practical; never blindly update actions without testing.

### 3.7 C++ sanitizers exist but must be proven active

`CMakeLists.txt` previously exposed `CQ_ENABLE_SANITIZERS`, enabling AddressSanitizer and UndefinedBehaviorSanitizer for compatible GNU/Clang toolchains. The reviewed CI workflow did not enable it.

Required work:

- Add a separate Linux Clang or GCC sanitizer job with `-DCQ_ENABLE_SANITIZERS=ON`.
- Verify in actual compile/link command output or `compile_commands.json` that the relevant core objects, native executable, and test targets have the expected sanitizer flags. Merely setting a CMake option is not evidence.
- Run CTest and relevant native parser/solver tests under sanitizers; upload useful logs on failure.
- Use a separate ThreadSanitizer job if it matches the toolchain and concurrency contract. Do not combine incompatible sanitizer modes.
- Keep sanitizer jobs separate from physical-GPU verification when the driver/runtime combination is unsuitable.

### 3.8 Vulkan/GPU verification levels must remain separate

Shader compilation, software Vulkan, loader/device enumeration, and successful physical GPU compute dispatch are different verification levels.

Required work:

- Report each level independently: `SHADER_VALIDATED`, `SOFTWARE_VULKAN_VERIFIED`, `LOADER_VERIFIED`, `PHYSICAL_GPU_DISPATCH_VERIFIED`, and `NOT_VERIFIED` (or an equivalent existing schema).
- A shader compiler exit code cannot promote a physical GPU claim.
- On a suitable physical device, dispatch a known small operation, synchronize correctly, read back results, and compare against an independent CPU reference. Test invalid dispatch dimensions, limits, buffer bounds, device-loss/error paths, initialization and teardown.
- If the required physical device is unavailable, report `NOT_VERIFIED`/`SKIP` with reason and do not fail an unrelated CPU-only test. Do not claim all GPU paths are stable without the relevant hardware run.
- Inspect the actual implementations before assuming the Vulkan integration executes the advertised algorithm.

### 3.9 Scheduler and dashboard claims need functional tests

Files previously reviewed: `cqhecs/scheduler.py`, `src/terminal_ui.cpp`, `src/main.cpp`.

The Python `VulkanComputeScheduler` previously appeared to create submission metadata and mark it `completed=True` without an actual Vulkan queue dispatch. `harvest_hardware_entropy()` mixed timing values into a linear congruential generator, which does not prove unbiased or cryptographic entropy. The C++ TUI used synthetic values and advertised controls that were not all handled in the visible input loop.

Required work:

- Either implement real device operations and their verifiable completion semantics, or clearly rename/document the components as planners, simulators, or demos.
- Never label synthetic data as live telemetry; mark demo data visibly and programmatically.
- Make each advertised keyboard control work, or remove it from the UI/help.
- Unit-test workgroup arithmetic, overflow, limits, completion-state transitions, cancellation and errors independently from real GPU execution.
- If a job is marked completed, require evidence of the actual operation completing according to the API's stated contract.
- Do not call a PRNG result “hardware entropy” or claim unbiased/cryptographic entropy without an appropriate, separately verified entropy source and sound design.
- Source displayed version from the canonical release mechanism, not a stale hardcoded banner.

---

## 4. Required test architecture for the next Stable

Create a tiered test suite so quick feedback remains fast while deeper confidence tests run on scheduled or release jobs.

### Tier A — deterministic unit and contract tests (every PR)

- Input parsing, validation, all documented gate support, and explicit rejection of unknown gates.
- Result-schema contract, `exact`/approximation/unresolved states, every error field, and “no result while unresolved” invariants.
- CLI JSON purity: exactly one valid JSON value on stdout in JSON mode; diagnostics only on stderr; stable and documented exit codes.
- Qiskit BackendV2 operations, transpilation, measurements, multi-circuit behaviour, classical-register mapping, seed/options and unsupported-circuit outcomes.
- Each historically fixed bug has a named regression test.
- Fast small-circuit differential tests.

### Tier B — property-based and differential tests

Add Hypothesis to the dev/test extra and implement generated tests with bounded examples and deterministic settings where appropriate. Use a fixed seed or stored examples when reproducing a failure; retain Hypothesis's regression database in local workflows where appropriate without depending on it as the only record of a bug.

Generate **valid circuits from a deliberately limited grammar**, not arbitrary invalid Qiskit objects, for property tests. Maintain separate invalid-input generators for parser/error-contract properties.

Core properties:

- `sum(counts.values()) == sampled_shots` for results that promise counts.
- Every count is non-negative; keys have the documented width/bit mapping.
- Repeated runs with the same backend version, input, and seed are reproducible where determinism is a contract.
- A gate followed by its inverse restores the state within a justified tolerance.
- A circuit followed by its inverse returns to the initial state (check global phase appropriately).
- Normalized statevectors/probability distributions satisfy the correct norm conditions.
- Probabilities and physical Pauli expectations lie in their valid intervals, within justified numeric tolerance.
- Circuit analysis accurately reports gate count, T-count, qubit count and connectivity properties for generated circuits.
- A path runs only circuits within its capabilities; forced paths never silently reroute.
- Increasing memory constraints or changing explicit limits must follow documented outcomes; do not assert monotonic runtime unless the algorithm and measurement methodology justify it.

Differential comparisons:

- Path A: use Stim and/or Qiskit Statevector/Aer on supported stabilizer circuits. Check exact support/correlation and bit ordering; do not demand identical random samples from unrelated RNG implementations.
- Path B: compare small Clifford+T circuits to Qiskit Statevector/Aer probabilities/amplitudes, considering global phase and numerical tolerance.
- Path C: compare low-qubit MPS results to a dense Statevector reference; sweep bond dimensions, entanglement patterns, complex gates and ill-conditioned SVD cases. Ensure any truncation diagnostics are not misrepresented as a certified end-to-end bound.
- Path D: independently compute each requested observable using Qiskit `Statevector`/`SparsePauliOp`; verify the observed error is within the reported bound whenever the implementation claims such a bound. Ensure an observable bound is never presented as a whole-joint-distribution guarantee.
- Router: run the same small circuit directly through the selected backend and through the router; validate the results and reported path agree with the capability policy.

Use statistically sound assertions for stochastic results. Avoid brittle “exactly these counts” assertions except where deterministically guaranteed by the test setup. Do not use matching seed integers across libraries as evidence that the random streams are the same.

### Tier C — native fuzzing, malformed-input testing, sanitizers

- Keep fixed regression cases in `tests/`.
- Add property-based parser tests for OpenQASM and DIMACS.
- Add bounded coverage-guided native fuzz targets for the QASM parser, DIMACS parser, JSON/result formatter, critical gate/phase operations, and allocation/shape validation.
- Use AddressSanitizer + UndefinedBehaviorSanitizer in compatible native CI; evaluate ThreadSanitizer separately if needed.
- Fuzz targets must have limits/timeouts and must not accept “crashed or hung” as a successful test.
- Save every discovered crashing input as a minimized regression fixture.
- Test invalid sizes, integer boundaries, malformed floating point, empty/overlong inputs, duplicate declarations, unclosed constructs, invalid qubit indexes, buffer-size mismatches, and overflow-sensitive dimensions.

### Tier D — resource, concurrency and long-running tests

- Make required telemetry dependencies explicit or skip loudly and honestly if a measurement source is unavailable.
- Separate simulator-internal allocation accounting from actual OS RSS and actual GPU VRAM.
- Measure memory over repeated phases with baselines and checkpoints; prevent noisy single readings from causing false alarms without masking sustained growth.
- Use timeouts and diagnostics for every stress/concurrency job.
- Test independent parallel jobs and any officially supported shared-object concurrency separately.
- Ensure every worker exception reaches the test result and no executor/future is left unread.
- Add failure injection: allocation failure, resource budget reached, parser exception, device unavailable/device lost, output-file write failure, cancellation and partial-result handling.

### Tier E — benchmarks and performance regression evidence

Use small, deterministic smoke benchmarks on PRs and a broader benchmark suite in scheduled/release workflows. Use public/reference circuit families where license and generation terms allow. Evaluate MQT Bench as a source/inspiration, but do not imply it is already integrated unless it is.

Include representative cases:

- Bell/GHZ at several sizes;
- random Clifford circuits;
- Clifford+T with increasing T-count;
- low-entanglement 1D circuits and cluster states;
- higher-connectivity/dense-entanglement circuits that stress MPS;
- QFT/controlled-phase circuits;
- Path D single-qubit and selected pair observables;
- unsupported gates and boundary/resource failures.

Each performance record must include schema version, canonical CQ-HECS version, exact commit SHA, platform/CPU, runtime and dependency versions, compiler/build type, circuit fingerprint, seed, parameters, warm-up/repetition policy, elapsed-time distribution (not only one best sample), memory fields with their measurement source, selected path, result state, and raw output. Clearly label smoke timings as smoke timings. Keep historical records but never label them current.

Do not fail a PR based on noisy microsecond thresholds. Add performance regression thresholds only after stable baselines and variance analysis exist. Correctness must pass before a speed comparison counts as useful evidence.

---

## 5. Mathematical and simulator-specific release contracts

Review the documented mathematical claims with care. Tests do not replace proofs, and simulations of randomly generated examples do not prove a general theorem.

### Path A — stabilizer/tableau

- Exercise H, S, X/Y/Z, CX/CNOT, CZ, SWAP and all supported Clifford-equivalent rotations.
- Validate symplectic updates, phase/sign rules, inverse operations and commutation invariants.
- Compare many small generated Clifford circuits with Stim/Qiskit references.
- Test measurement support and correlations (Bell/GHZ, parity) at both small and large qubit counts.
- Test indexing/endianness independently from state correctness.

### Path B — stabilizer rank

- Test each supported non-Clifford gate and each Clifford-angle special case.
- Test decomposition normalization and branch recombination; no uniform-distribution fallback or placeholder counts.
- Test low T-count and exact implementation-limit boundaries, including one below, exactly at, and one above each limit.
- Compare against dense references for small circuits and report algebraic exactness separately from float64 numerical error.

### Path C — MPS

- Test single- and two-qubit gates, adjacent/non-adjacent gate handling, swaps/reordering if implemented, complex-valued states, SVD degeneracies, and canonicalization/environment contractions.
- Compare state fidelity/amplitudes/probabilities against dense references on small circuits.
- Check bond dimensions, tensor dimensions, finite values, normalization, allocation accounting, and budget behavior.
- Test 1D low-entanglement success cases and higher-entanglement/resource exhaustion cases separately.
- Test MPS-native sequential sampling on wide structures without dense `2**n` allocation; independently assert actual sampled-shot totals and output correlations.
- Never call the state mathematically exact solely because no configured bond-dimension cap was used if singular-value numerical cutoffs or floating-point operations remain. Report the implemented contract accurately.

### Path D — sparse Pauli/observable mode

- Verify the Heisenberg conjugation rule for all supported one- and two-qubit Clifford/non-Clifford cases against explicit matrices on small systems.
- Cover CZ sign/phase cases, rotations, SWAP and all gates in capability claims.
- For every truncation, independently compute the discarded-coefficient contribution and verify the returned observable-specific bound.
- When the bound exceeds tolerance, require `unresolved` with no uncertified expectation values.
- Reject unsupported gates/observable strings and invalid qubit indexes.
- Never report independent marginal samples as a joint measurement distribution.

### Result, error bounds, sampling and serialization

- Check validation for zero/negative shots, invalid delta/tolerance, invalid support sizes, large integers, non-finite values, and missing output fields.
- Test bound monotonicity where mathematically guaranteed (more shots should not enlarge the relevant concentration bound; a larger support should not make the same support-dependent bound falsely tighter).
- Verify each error bound corresponds to the output metric it claims to cover. Compose bounds only where the metrics and assumptions permit it.
- Test finite-shot bounds against the correct referenced formula with edge cases in the log domain. Statistical simulation tests are useful supporting tests, but do not replace a mathematical derivation.
- Reject invalid JSON output schemas and verify exactly one JSON document in JSON mode.
- Treat `None`/unavailable error bounds as meaningful, not as zero.

---

## 6. Test and CI implementation requirements

### CI architecture

Implement separate jobs or tiers with clear responsibilities:

1. **Fast PR checks:** syntax/static checks, version audit, small correctness/contract tests, CLI/package smoke.
2. **Cross-platform full tests:** Ubuntu and Windows C++ build, Python tests, CTest, backend contract, shader validation, package build.
3. **Sanitizer tests:** Linux compatible compiler + ASan/UBSan and applicable native parser tests.
4. **Quality reports:** branch coverage, lint/type checks if configured, and artifacts.
5. **Nightly/release extended suite:** property-based higher-case runs, fuzzing budget, long stress, performance suite.
6. **Hardware lane:** physical GPU tests only on a known suitable/self-hosted runner; mark unavailable hardware honestly.
7. **Cloud Build:** inspect `cloudbuild.yaml` and existing triggers/credentials, then actually run or trigger the configured cloud build. Confirm the expected source revision and final build status. If the project is not connected or credentials cannot access it, document that as BLOCKED and do not claim it passed.

Avoid concurrent duplicate deployments/releases. A normal branch push should only trigger the test/build workflows expected for a branch. Publish a Release only when all applicable gates are green and the version/tag/artifact policy has passed.

### Dependency strategy

- Keep a reproducible CI configuration for stable versions.
- Add a separate newest-supported-dependencies job to detect upcoming upstream incompatibility.
- Check the live Python/Qiskit/NumPy support policies before editing minimum versions.
- Verify the package really installs and runs under every declared supported combination; otherwise narrow the declared support.
- Prefer lockfiles/constraints for stable CI. Do not depend on “whatever pip installs today” as the only stable evidence.

### Code-quality signals

- Use targeted formatting/lint/type checking suitable for this repository; do not introduce a large tooling stack without a reason.
- Keep lint scope consistent with the actual supported code. Gradually expand; do not silently omit problematic modules.
- Enforce meaningful branch coverage after collecting baseline.
- Publish JUnit/test reports, coverage report, sanitizer logs, benchmark JSON and build artifacts for debugging where CI supports it.
- Ensure failed jobs keep enough logs for diagnosis, but redact secrets and sensitive environment variables.

---

## 7. Implementation order and do-not-skip phase gates

Follow this order. Fixes may be reorganized only if dependencies demand it; document the reason.

### Phase 0 — Audit and baseline

- Inspect current branch and state; preserve user edits.
- Confirm current version/tags, CI and Cloud Build.
- Run baseline and create `research/v2_2/BASELINE.md` and `research/v2_2/TEST_MATRIX.md`.
- Create a prioritized issue list classified P0/P1/P2 with filenames, evidence and acceptance criteria.

**Gate:** Every required test is classified PASS/FAIL/SKIP/NOT RUN/BLOCKED. No unsupported “all green” statement.

### Phase 1 — Correct false-green tests and wrong contracts

- Repair QASM invalid-input expectations according to the documented spec.
- Repair resource tests that treat absent measurement as zero.
- Fix cycle-count/documentation mismatches and concurrency claims.
- Make CLI JSON/exit-code/result-state contracts explicit.
- Keep regression tests for all reproduced defects.

**Gate:** Tests themselves fail when their required measurement/validation was not performed. No invalid input silently produces a clean successful simulation.

### Phase 2 — Correctness-critical implementation fixes

- Fix actual implementation defects discovered by the baseline/tests.
- Preserve fail-closed routing and unsupported-gate errors.
- Verify the result schema and all mathematical error/approximation claims.
- Remove fake telemetry or explicitly expose demo mode; do not falsely describe metadata-only scheduling as real dispatch.
- Separate software-Vulkan, loader and physical GPU status.

**Gate:** All previously reproduced regressions have independent failing-before/fixed-after tests or equivalent evidence.

### Phase 3 — Test amplification

- Add Hypothesis and property tests.
- Expand differential testing for A/B/C/D and routing.
- Add native fuzz targets and saved crash regressions.
- Activate sanitizer jobs and harden mutation testing.
- Add branch coverage and meaningful thresholds after baseline.
- Expand concurrency/resource failure tests.

**Gate:** New tests exercise the actual shipped modules, report their execution status, and are not merely additional synthetic demonstrations.

### Phase 4 — Local full verification

Run the full supported test/build matrix. Fix the root cause of every failure. After each fix, run the smallest targeted regression first, then all relevant tests. Repeat the full matrix after a sequence of related fixes and before each push.

**Gate:** No unexplained failures, no silent skips, and no weakened assertions introduced simply to achieve success.

### Phase 5 — Commit and cloud CI loop

- Commit coherent, reviewable units to the dedicated branch.
- Push using the secure credential mechanism described below.
- Monitor GitHub Actions for the exact pushed SHA and, if configured, Cloud Build for that same source revision.
- If any workflow fails: download/read logs, identify root cause, implement the fix, rerun the targeted tests locally, rerun full relevant checks, commit and push. Repeat until all required gates pass.
- A green run on an older SHA does not prove that the latest push is green.
- Do not bypass required branch protections, use `--no-verify`, force push, suppress failure status, or push secrets.

**Gate:** The latest code commit—not merely a prior commit—has green required GitHub CI and confirmed Cloud Build where configured.

### Phase 6 — Rewrite documentation LAST

Only after the implementation and all code/test/cloud gates are green:

- Rewrite the entire `README.md` to reflect the final code accurately.
- Preserve useful technical detail, but remove/repair stale release examples and unsupported claims.
- Document the actual four-path behaviour, precise limitations, true CPU/GPU status, install paths, examples, errors, validation commands, and only reproducible current benchmarks.
- Separate production/stable functions from experimental/legacy/research components.
- Update `CHANGELOG.md`, `RELEASE_NOTES.md`, relevant docs, test matrix, hardware support matrix and benchmark notes so all active files agree.
- Keep old historical information only when clearly labeled historical and not presented as current.
- Do not claim universal simulation, cryptographic breaking, physical GPU acceleration, exact arithmetic, zero leaks, or benchmark speed without the correct evidence.
- Run Markdown/link checks where available, copy/paste all quick-start commands into a clean environment, and verify command names/options against the actual CLI.

**Gate:** README and documentation are accurate against the final source code and contain no known stale active versions, commands or performance/hardware claims.

### Phase 7 — Final docs push and final Stable gate

The documentation commit changes repository contents and may trigger new workflows. Therefore:

- Commit and push the documentation update after it passes local docs/version checks.
- Rerun/verify CI on that final commit, including any Cloud Build trigger that should run.
- Verify version consistency across package metadata, central version, native C API, Qiskit backend version, CMake, CLI, changelog and release notes.
- Verify wheel and sdist clean installs, checksums/SBOM and release asset list.
- Review the final `git diff`, `git status`, commit history, action logs and release artefact names.
- Only create/publish a Stable tag/release if the user has authorized release publication and all applicable gates pass. The request to push source does not justify bypassing repository release policy.

**Gate:** Final source and documentation SHA has passing required CI and verified Cloud Build status. If any final-doc commit fails, fix and repeat the loop.

---

## 8. Secure GitHub authentication and push protocol

The operator will provide a token to the agent. **The token is a secret, never a source-code value.**

Preferred order:

1. Use the agent/runtime's approved secret store or the authenticated GitHub CLI/Git Credential Manager session, if already configured.
2. Otherwise, obtain the token through a secure environment variable supplied by the operator/runtime (for example `GH_TOKEN`/`GITHUB_TOKEN`) or a protected secret store. Use only the minimum repository permissions required.
3. If using GitHub CLI, authenticate without displaying the token and configure Git to use the secure credential helper (`gh auth setup-git`) as appropriate. Ensure the token is not embedded in `origin` or any Git config URL.
4. Never hardcode the token in shell scripts, command arguments containing its literal value, CI YAML, Markdown, `.env` files tracked by Git, test fixtures, commit messages, exception dumps, or logs. Do not use `set -x` around secret use. Never call `printenv`, dump the process environment, or log `gh auth status --show-token` or equivalent token-bearing output.
5. Before and after pushing, inspect `git remote -v` and recent diffs for credential-bearing URLs or accidental secrets. If a secret is accidentally written or exposed, stop, do not push it, remove it from the working changes/history safely, notify the operator, and rotate/revoke that credential through the approved process.
6. Do not weaken branch protections. Do not use force push. Do not rewrite published tags. Prefer normal commits and normal pushes on the task branch. Integrate to the default branch only through the repository's authorized process and permissions.
7. Do not print the token in the final report. Report only whether authentication/push succeeded and the branch/SHA/CI links.

If authentication lacks required permission, stop that action and report the precise non-secret permission problem. Do not attempt to obtain broader credentials or bypass organization policy.

---

## 9. Fix/test loop: mandatory behaviour

Operate in this loop rather than stopping after writing suggestions:

1. Reproduce the failure.
2. Identify the root cause from source, test output, and logs.
3. Add or improve a regression test that fails for the defect and passes for the correct contract.
4. Fix the implementation or test harness—never merely conceal the failure.
5. Run the targeted test and relevant suite.
6. Run the full local release gate when a coherent batch of changes is ready.
7. Commit and push to the authorized task branch.
8. Inspect cloud workflow results for the exact new SHA.
9. Fix cloud-only issues (platform paths, packaging, dependency drift, permissions, line endings, compiler/SDK differences) and repeat.
10. After code and cloud gates are green, update README/docs last, push that commit, and run the required gates on the final SHA again.

Keep a short progress/evidence ledger as the work proceeds so the operator can audit what happened. Avoid meaningless churn: do not create a commit per trivial line or keep pushing the same failure without changing the root cause.

If a true external blocker makes further progress impossible (for example, unavailable organization permissions, missing Cloud Build access, or no physical GPU runner), do not fake success or loop forever. Prove the blocker, finish all independent work, leave the affected requirement explicitly `BLOCKED`/`NOT VERIFIED`, and report the exact operator action needed. Continue until green whenever the failure is fixable within the repository and available credentials.

---

## 10. Definition of Done for Stable

Do not mark the mission complete until every applicable item below is supported by evidence:

- [ ] Current repository state, version, branch and starting SHA were recorded.
- [ ] No user changes were lost.
- [ ] All confirmed P0 defects were fixed and have regression tests.
- [ ] Invalid/unsupported input follows documented fail-closed semantics.
- [ ] No result is marked successful when required output, sampling, verification or resource measurement did not occur.
- [ ] All four simulation paths have suitable independent differential/property tests for their supported domains.
- [ ] Numerical, approximation and sampling error fields have explicit and correctly tested semantics.
- [ ] Qiskit BackendV2, CLI JSON/exit codes, native API, packaging and version consistency pass.
- [ ] Mutation harness fails closed; results accurately describe the actual mutation methodology.
- [ ] Branch coverage is reported and an established, meaningful gate is enforced.
- [ ] Supported Python/dependency combinations are tested; release installation is reproducible.
- [ ] C++ sanitizer job passes for applicable native targets.
- [ ] Parser fuzzing/property tests run, and discovered failures became regression tests.
- [ ] Stress, memory and concurrency tests do not silently replace missing telemetry with zero.
- [ ] GPU claims match the verification level actually achieved; physical GPU runs are not assumed.
- [ ] Benchmarks are reproducible, versioned and labeled with provenance; stale data are not presented as current.
- [ ] GitHub Actions are green for the latest source commit.
- [ ] Cloud Build is green for the latest source commit if configured and accessible; otherwise the exact external blocker is documented.
- [ ] README was revised only after code/test/cloud gates were green, and all other active docs were reconciled.
- [ ] The documentation commit was pushed and all required CI/cloud gates are green for the final commit.
- [ ] Release artifacts (wheel, sdist, checksums, SBOM and notes) match the canonical version and pass clean-install/smoke checks.
- [ ] No token, secret, credential URL, personal access data or sensitive machine detail appears in git diff, commits, artifacts, or logs.
- [ ] Final report states what changed, exact tests executed, PASS/FAIL/SKIP/BLOCKED details, commit SHAs, branch and links to GitHub Actions/Cloud Build logs. Do not claim “all green” when any required gate is blocked or not run.

### Final report format

At completion, report:

1. Final version and branch; final code and documentation commit SHAs.
2. A concise summary of implementation/test/CI/docs changes.
3. A table of local test gates and their exact outcomes.
4. Links and status for GitHub Actions and Cloud Build associated with the final SHA.
5. Which GPU/hardware levels were actually verified and which remain unverified.
6. Any remaining limitations, skipped checks, or external blockers.
7. Confirmation that no token was committed, printed, or embedded into a remote URL.

**Do not report completion until the definition of done has been checked against the final commit.**
