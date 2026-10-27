# GEMINI MISSION — CQ-HECS Stable Correctness, Hardening, CI, and Release

**Repository:** `https://github.com/timfromhcs/CQ-HECS`
**Primary target:** `v2.2.2` Stable, unless live repository metadata proves that the version or release plan has changed.
**Mission type:** Full-source audit, reproducible defect confirmation, mathematical/correctness fixes, stress testing, documentation alignment, secure CI, Git push/PR/merge, and release verification.
**Execution style:** Evidence-first, iterative, no false-success paths, no hand-waved tests.
**Status date for the initial external audit:** 2026-10-27. Re-check live GitHub state before acting; never assume this document's starting commit is still current.

---

## 0. The mission in one sentence

Inspect the live repository and its current Git state; reproduce or explicitly refute every high-priority audit finding; fix root causes; add regression, differential, property-based, boundary, stress, and failure-path tests; run local gates; push a focused branch; open/update a PR; fix every CI failure in a repeatable loop; merge only when the actual repository rules and all required checks permit it; then, only if every release gate is satisfied, publish `v2.2.2` from the exact verified commit and report the proof.

**Do not send a completion message just because code was written, a local test passed, a PR was opened, a badge is green, or a job was skipped. Report completion only when the final commit/release criteria in Section 18 are supported by observable evidence.** If an external permission, unavailable physical device, missing secret, required human review, or platform outage makes a gate impossible, do not fake it or bypass a rule. Exhaust reasonable alternatives, record the blocker and evidence, and report that the mission is blocked rather than complete.

## 1. Highest-priority values

1. **Correctness before performance.** A slower correct result or explicit `UNRESOLVED`/unsupported error is preferable to a fast fabricated result.
2. **Truth over green-looking output.** No fake counts, fake GPU telemetry, false `exact=True`, ignored gates, mislabeled error bounds, silent truncation, or false `completed=True`.
3. **Fail closed.** An unsupported gate, invalid register, unknown semantic, exceeded resource budget, failed reference comparison, missing native module, or failed verification must not silently turn into an identity operation, a guessed answer, a different path, or a successful exit code.
4. **Tests must prove the user-visible contract.** “It did not crash” is not a correctness test. Test state/output, probability distribution, observables/error bound, memory behavior, failure semantics, bit order, and exit/status schema as appropriate.
5. **Do not weaken gates to get green.** Never delete/skip a failing test, loosen a tolerance without a derivation, hide a warning, downgrade a contract, or alter a test to match a broken implementation. A specification change needs a reason, documentation, independent reasoning, and review.
6. **Preserve the repository and operator work.** Do not reset, clean away, overwrite, or reformat unrelated changes. Inspect the existing `GEMINI.md` and `git status` before editing. If existing operator-specific instructions or an uncommitted `GEMINI.md` differ from this mission, preserve them in a separate backup/merge commit or merge their still-valid requirements into the final guide. Never destroy operator changes just to replace this document.
7. **No unsafe Git shortcuts.** Never force-push, rewrite public history, delete tags, push directly to protected `main`, bypass required reviews, or disable branch protection. Use a feature branch and PR. If the host disallows the requested merge, leave a truthful, reviewable PR and report the exact blocker.
8. **No secrets in code or logs.** Never print tokens, copy credentials to URLs, commit credentials, store them in the mission log, or echo sensitive environment variables. Use the Git credential helper / `gh auth` / host-provided secure credentials.
9. **No unsupported hardware claims.** Compiling a GLSL shader to SPIR-V does not prove execution on a physical GPU. Planner output is not GPU telemetry. Only claim Vulkan acceleration if a real queue submission, synchronization, device execution, and result readback were exercised on a documented environment.
10. **Evidence is durable.** Each discovered defect, test command, exact exit status, relevant output, final SHA, CI URL, and limitation belongs in audit/release evidence, not only in a transient terminal scrollback.

## 2. Scope and what must be delivered

Work within the existing project's architecture unless evidence demonstrates a design problem. Deliver all of the following:

- A live-state baseline: repository URL, default branch, base SHA, tags/releases, worktree status, branch and permissions observed.
- A current audit log listing each reviewed finding as `CONFIRMED`, `FIXED`, `NOT REPRODUCED`, `BLOCKED`, or `FOLLOW-UP`, with code paths, tests, results, and rationale.
- Regression tests for every confirmed defect and nearby edge cases.
- Correctness fixes in Python, C++, parser/router/result contracts, packaging, documentation, workflows, or test harnesses where justified.
- Stronger independent differential checks, including a real MPS-vs-reference check rather than checking only that two outputs share one key.
- Reproducible resource/timeout tests that cannot take down the runner through an uncontrolled allocation.
- A test matrix and final release notes whose claims match the actual implementation.
- Green local static, Python, native C++, CTest, mutation, packaging, smoke, and available sanitizer gates.
- Green GitHub Actions for the actual source SHA that will be merged/tagged; green Windows/Linux and Python compatibility lanes that the current workflow defines.
- A feature branch pushed and a PR merged only after all required checks pass and the repository's branch/review rules are satisfied.
- A release tag and GitHub release only after the merged commit meets every stable gate, with artifact checksums/SBOM and exact source provenance validated.
- A concise final report only after proof is collected. Include actual results, not expected ones.

Do not expand scope to an entirely new simulator/backend, novel quantum algorithm, or real GPU engine unless the critical fixes require it. A Stable release should make current claims true, not increase the claim surface.

## 3. Repository facts that must be re-checked, not assumed

The initial audit observed the following on 2026-10-27, but these are only starting clues. Verify them live before touching code:

- `main` was at `812da806d9b4528f1c4f8ccd3cbb7b37b6f009ce`.
- `scripts/version.py`, `pyproject.toml`, and `CMakeLists.txt` were already declaring `2.2.2`.
- The public Releases/Tags list showed `v2.2.1` as latest published stable; no `v2.2.2` tag/release was visible then.
- CI for the current main SHA was green across Linux, Windows, Python 3.12–3.14, package smoke, and the configured Linux ASan/UBSan job.
- The current Nightly Extended Validation run was green, with 311 Python tests and 11/11 source-level mutants killed; two Qiskit-QFT deprecation warnings were visible.
- The code already uses a shared gate manifest, capability-first routing, structured `EXACT`/`CERTIFIED`/`UNRESOLVED`/`FAILED` result states, a conservative observable-only Path D contract, and a source-level mutation harness.
- The repo makes a point of stating that the Vulkan scheduler is planner-only and physical GPU dispatch is unverified. Preserve that honesty.

At mission start, query live GitHub API / `gh` / `git` for:

```text
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
git log -8 --oneline --decorate
git tag --list 'v*' --sort=-version:refname
```

Also inspect live `main`, releases, tags, open PRs, branch protection/rulesets if permitted, recent Actions runs and the current project version. Save the outputs needed for audit **without saving credentials or private environment details**. If local `main` is stale, fetch first. Do not use this document's SHA in place of a current base SHA.

## 4. Git, branch, and preservation protocol

### 4.1 Before any file edit

1. Read `GEMINI.md`, `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CQ-HECS-V2-ROADMAP.md`, `docs/`, `research/next_stable/`, `research/v2_2/`, relevant tests, `pyproject.toml`, `constraints/ci-py311.txt`, `CMakeLists.txt`, `cloudbuild.yaml`, and every relevant workflow under `.github/workflows/`.
2. Read the existing worktree state and all local commits. List modified, staged, untracked, ignored-but-relevant, and generated files. Do not assume a dirty file belongs to the agent.
3. Create an immutable baseline record such as `research/next_stable/EXECUTION_LOG.md` or `audit/v2.2.2_execution.json`, including base SHA, timestamp, Python/compiler/OS/CMake/Vulkan versions, release state, and known pre-existing changes.
4. If the worktree is dirty, inspect each changed file and preserve its content. Never run `git reset --hard`, `git clean -fdx`, `git checkout -- .`, or any command that would discard user changes.
5. Create a new focused branch from the latest default branch, preferably `agent/cq-hecs-v2.2.2-stable-hardening` or a unique mission branch if that name exists. Do not work directly on `main`.
6. Keep commits logically grouped: correctness fix + regression test, resource-hardening + stress test, parser/input contract, test quality, CI/supply chain, docs/release notes. Do not create an empty commit just to retrigger CI.
7. Before every commit: `git diff --check`, inspect `git diff`, inspect status, run relevant tests, and ensure no generated binary/cache/secret is being unintentionally committed.
8. After a push: record pushed branch SHA and URL; use `git fetch` and compare remote SHA. Never assume a `git push` succeeded just because the command was attempted.

### 4.2 Existing `GEMINI.md`

The checked-in guide was observed to carry an older Stable mission target (`v2.2.0`) and useful operator instructions. Do not simply overwrite it without reading it. Preserve relevant security, release, and operator constraints; update stale version references only after checking live metadata. Avoid a self-referential loop where the agent repeatedly rewrites `GEMINI.md` to describe itself. The final mission document should be precise and stable, and any modifications to it must be covered by the final CI run.

### 4.3 Never use force push

Use regular `git push -u origin <branch>`. If remote history has advanced, fetch and reconcile with a normal merge or a safe rebase of the *unpublished feature branch only*, after ensuring no operator changes are lost. Never force-push. Never delete or retarget published tags.

## 5. Iterative loop design: how to continue until green without looping blindly

The mission is deliberately a loop, not a one-shot code-generation exercise. Repeat the following cycle until the release gates pass:

### Loop A — Inspect → reproduce → record

1. Read the implementation and existing tests for the current finding.
2. Write the smallest black-box regression test that expresses the external contract and fails on the unmodified implementation if the defect is present.
3. Run that specific test alone and capture exact command, exit code, failing assertion, and relevant output.
4. If it does **not** fail, do not claim the defect was reproduced. Expand the test to cover intended edge conditions. If still not reproduced, label it `NOT REPRODUCED`, explain what the test ruled out and why, and keep a permanent test where it still adds value.
5. A test that fails for an unrelated import error, missing dependency, absent native binary, flaky timeout, wrong setup, or pre-existing environment problem is **not** a reproduction. Fix the harness/environment or run it in the supported CI environment.

### Loop B — Hypothesis → fix → regression

1. State the root cause as a precise invariant/formula/data-flow problem before changing code.
2. Implement the smallest correct fix. Keep the result semantics and API compatibility in view.
3. Run the new regression test: it must now pass.
4. Run nearby tests and independent reference comparisons. A fix is not acceptable if it only makes the new assertion pass by hardcoding its expected result.
5. Add positive, negative, boundary, reversed-order, non-adjacent, invalid-input, and failure-path tests as relevant.
6. Perform code review of the change itself: shape/order correctness, ownership/lifetime, arithmetic overflow, resource ceilings, error paths, cleanup, concurrency, platform behavior, and any behavior contract the code advertises.

### Loop C — Broader validation

Run all targeted component tests, then full Python, native, coverage, mutations, package smoke and formatting/static checks. If any gate fails, inspect the actual failing log and fix the root cause. Never retry the same failed command unchanged more than once unless the failure is demonstrably transient and the transient nature is documented.

### Loop D — Commit → push → CI → inspect

1. Commit only the validated change(s).
2. Push the feature branch and open or update a PR to the current default branch.
3. Wait for the actual Actions runs for the exact head SHA, then inspect all jobs and logs, not only the check summary.
4. For every failing check: identify failing job, step, test, root cause, reproduce locally or with a focused remote rerun, fix, test, commit, push, then wait for new checks.
5. A `skipped`, `cancelled`, `neutral`, `timed_out`, `action_required`, `stale`, or “not run” result does not satisfy a required green gate. Do not confuse a successful PR-merge-queue SHA with the release tag SHA.
6. Repeat until all checks for the current PR head are green. If a protected branch requires a review, wait for the real review; never bypass it with admin flags or altered rules.

### Loop E — Merge → exact-SHA verification → release

1. Confirm the base branch has not moved unexpectedly; refresh the PR and rebase/merge the latest default branch safely if necessary.
2. Ensure required checks refer to the latest PR head and include the actual code change. Confirm there is no unresolved review comment or unresolved merge conflict.
3. Merge using the repository's allowed method and only when all rules permit. Record merge commit SHA and compare it to GitHub.
4. Fetch updated default branch; rerun all essential local gates on the merged code. Check the Actions CI for the exact merged SHA.
5. Update version/release notes/CHANGELOG/CITATION/security/docs only if not already accurate. Re-run `scripts/check_version.py` and the release gates **after** these changes. Documentation is part of the release source and must not be changed after the final verification without rerunning CI.
6. If and only if every stable criterion passes, create or trigger the version tag from the exact intended merged SHA, using `v2.2.2` when live metadata confirms that is the correct next version. The release workflow must then show green CI for the exact tag SHA before publication. Do not manually bypass a failed workflow or create an alternative release artifact outside the documented process.
7. Verify release assets, source provenance, checksums, SBOM, tag SHA and release notes from the public page. Download at least the wheel and source archive, verify SHA-256 independently, and test-install the exact published wheel in a fresh environment.
8. Only now prepare final report.

### 5.1 Anti-infinite-loop rules

Continue until all actionable code/repository gates are green, but **do not** loop blindly forever:

- If the same failure recurs twice, stop repeating commands and perform a deeper root-cause analysis (instrumentation, reduced repro, source trace, toolchain check, independent reference).
- If a gate is externally blocked (permissions/review/runner outage/physical hardware not available), finish all work that can be proven locally, record the exact blocker, and do not falsely declare completion.
- If fixing one issue reveals another, add it to the ledger and continue.
- If a requested algorithmic enhancement would expand scope or lacks a trustworthy correctness oracle, defer it rather than risking a false Stable claim.
- No arbitrary “max 3 loops, stop even though bug remains” behavior. Use a reasoned escalation and a truthful blocked state, not a fake completion.

## 6. Initial audit: files and surfaces to inspect deeply

### Python logic and public API

- `cqhecs/circuit_parsing.py`: Qiskit normalization, QASM parser, angle expression parser, register offsets, measurements, tuple input coercion and malformed input.
- `cqhecs/gate_manifest.py`: gate arity, parameter count, path capabilities and non-unitary semantics.
- `cqhecs/circuit_analyzer.py`: T-count, Clifford detection, entanglement/cut estimates, measurements and supported-path derivation.
- `cqhecs/router.py`: capability-first routing, forced path behavior, error propagation, auto routing and no silent fallback.
- `cqhecs/backends/path_a_stabilizer.py`: stabilizer update formulas, native fallback criteria, qubit bit ordering, Clifford-only correctness.
- `cqhecs/backends/path_b_stabilizer_rank.py`: stabilizer rank coefficients/branch aggregation, T and Tdg, Clifford-angle reductions, statevector limits, random sampling and normalization.
- `cqhecs/backends/path_c_mps_exact.py`: tensor index order, two-site contraction, SVD/rank handling, SWAP routing, page-out/page-in, budget enforcement, sequential conditional sampling, terminal measurements and cleanup.
- `cqhecs/backends/path_d_sparse_pauli.py`: Pauli conjugation signs, masks, strict observable parser, term truncation, discarded coefficient bounds, per-observable error bounds, `UNRESOLVED` behavior, no fictitious joint counts.
- `cqhecs/result.py`: `EXACT`/`CERTIFIED`/`UNRESOLVED`/`FAILED`, numeric/sampling/approximation bounds, total-bound metric compatibility, serialization and exit status.
- `cqhecs/backend.py`: Qiskit BackendV2 Target vs executable gate manifest, measurement maps, multiple circuits, result semantics.
- `cqhecs/cli.py`: stdout/stderr purity, JSON schema, status/exit codes, input validation, exceptions and stable CLI contract.
- `cqhecs/scheduler.py`: must remain honestly planner-only; timing jitter is not cryptographic entropy.

### Native/C++ / ABI / Vulkan

- `include/cq_hecs/core/mps_simulator.hpp`, `include/cq_hecs/core/statevector_simulator.hpp`, `include/cq_hecs/core/types.hpp`, `include/cq_hecs/core/qpu_engine.hpp`.
- `include/cq_hecs/transpiler/qasm3_parser.hpp`, `src/cq_qasm_parser.cpp`, `src/qasm_parser.cpp`, `src/qasm_angle.hpp`, `src/cq_c_api.cpp`, `src/cq_hecs_api.cpp` and Python binding sources.
- `src/vulkan/vulkan_engine.cpp`, `include/cq_hecs/vulkan/vulkan_engine.hpp`, `src/hybrid_engine.cpp`, `src/stabilizer_tableau.cpp`, compute shaders and SPIR-V build flow.
- CMake target definitions, test targets, AVX2 compile flags, Vulkan SDK requirements, sanitizer options, platform-specific paths and shared-library ABI.
- Ensure native C ABI validates pointers, lengths, enum/gate IDs, integer overflow, output buffer sizes and error reporting. No UB or exception may cross an unsafe C boundary without being translated.

### Test, release, docs and security surfaces

- `tests/test_correctness_contracts.py`, `tests/test_adversarial_aer_and_stim.py`, `tests/test_200q_sampling_acceptance.py`, `tests/test_qiskit_and_transpiler.py`, `tests/test_mps_300qbits.py`, parser/SAT/fuzz tests, native C++ tests and mutation harness.
- `tests/native_artifacts.py`: verify that native tests do not silently pass/skip when required native artifacts are missing.
- `scripts/run_mutation_tests.py`: verify it mutates real production source, runs isolated subprocesses, detects baseline issues and restores source byte-for-byte.
- `scripts/verify_no_silent_truncation.py`: static heuristic only; never treat it as a proof. Add dynamic tests for defect classes.
- `scripts/verify_vulkan_shaders.py`: compilation/valid SPIR-V only, not physical device execution. It rewrites `.spv` outputs; inspect resulting diffs and don't commit unrelated compiler drift.
- `scripts/check_version.py`, `scripts/generate_sbom_and_checksums.py`, `scripts/package_release.ps1`, `scripts/smoke_test.ps1`, version surfaces and release workflow.
- `README.md`, `ARCHITECTURE.md`, `docs/USAGE_GUIDE.md`, `docs/API_REFERENCE.md`, `docs/QASM_CONTRACT.md`, `docs/BENCHMARKS.md`, `docs/V2_IMPLEMENTATION_MATRIX.md`, `research/next_stable/*`, release records and changelog.

## 7. Prioritized findings and required actions

The prior audit identifies a handful of high-priority risks by reading live source. Some were not locally executed by the auditor, so **confirm each before declaring it a reproduced bug**. The agent must update the ledger when an item has been reproduced, fixed, not reproduced, or blocked. The source line numbers may move; use symbols and current code, not line-number assumptions.

### CQ-01 — Python Path C MPS: reversed two-qubit operand order (`q1 > q2`)

**Priority:** P1 until reproduced or convincingly refuted.
**Likely file:** `cqhecs/backends/path_c_mps_exact.py`, `ExactMPSTensorChain.apply_two_qubit_gate`.

The audit noticed that the `q1 > q2` `einsum` branch appears to associate the physical input axes in the wrong order. For a two-site tensor, the chain is ordered low-index site then high-index site; the supplied two-qubit gate matrix is ordered by the operation's original operand order. When operand order reverses, *both input and output axis mapping must be derived carefully*. A superficially plausible axis swap is not enough.

**Reproduce first** with the path forced directly, not via auto-router (otherwise another backend can mask the bug):

```python
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend

cases = []
# Control/target order and input state intentionally distinguish directions.
qc = QuantumCircuit(2); qc.x(0); qc.cx(0, 1); cases.append(("cx_q0_to_q1_from_01", qc))
qc = QuantumCircuit(2); qc.x(0); qc.cx(1, 0); cases.append(("cx_q1_to_q0_from_01", qc))
qc = QuantumCircuit(2); qc.x(1); qc.cx(1, 0); cases.append(("cx_q1_to_q0_from_10", qc))
qc = QuantumCircuit(2); qc.x(1); qc.cx(0, 1); cases.append(("cx_q0_to_q1_from_10", qc))

for name, qc in cases:
    expected = Statevector(qc).data
    result = PathCMPSExactBackend(ram_budget_mb=64).execute(qc, shots=4096, seed=7)
    assert not result.unresolved, (name, result.to_dict())
    assert sum(result.counts.values()) == 4096, (name, result.counts)
    probs = np.zeros(1 << qc.num_qubits)
    for bitstring, count in result.counts.items():
        probs[int(bitstring, 2)] = count / 4096
    # Distribution check; add a separate state-level gate/contraction check below.
    target_probs = np.abs(expected) ** 2
    tv = 0.5 * np.abs(probs - target_probs).sum()
    assert tv < 0.06, (name, tv, result.counts)
```

The above probabilistic test is a first smoke check, not sufficient to test phases or extremely rare outcomes. Add a deterministic, small-state differential test for the MPS tensor/statevector contraction: compare vectors up to a global phase, verify norms, and compare probabilities at `atol`/`rtol` suitable for complex128. If `to_statevector()` is capped at the size under test, use it; otherwise compare amplitudes/observables by another independent exact method.

For state preparation, include explicit checks that (Qiskit bitstring convention, `q0` rightmost):

- `x(0); cx(0,1)` yields only `11`.
- `x(0); cx(1,0)` leaves only `01` because the control `q1` is zero.
- `x(1); cx(1,0)` yields only `11`.
- `x(1); cx(0,1)` leaves only `10` because the control `q0` is zero.

**Fix requirements:** derive the contraction using named tensor dimensions (write the equation in the comment); ensure the operation preserves ordered gate operands; preserve the original chain state if memory refusal occurs. Do not merely reverse the output bitstring to get counts to match.

**Expand regression coverage** to every supported two-qubit gate in Path C (`cx`/`cnot`, `cz`, `swap`, `cp`, `crx`, `cry`, `crz`, `cu1`) in both operand orders, including asymmetry-sensitive input states and one or more random small circuits. Include adjacent and non-adjacent pairs in a three-/four-qubit chain. Compare against `qiskit.quantum_info.Statevector` or Aer with an exact/no-truncation setting. For complex gates, compare statevectors up to global phase, not only counts.

**Completion rule:** close this finding only after (a) a minimal test fails on the prior code and passes after the fix, or (b) the hypothesis is refuted by convincing independent comparisons covering both orientations; in either case keep a regression that protects the invariant.

### CQ-02 — Path C: pre-allocation RAM/storage budgets and sampling paging

**Priority:** P1.
**Likely file:** `cqhecs/backends/path_c_mps_exact.py`.

The current shape of the implementation creates intermediate contraction arrays and calls `np.linalg.svd` before checking the projected retained tensor storage. SVD can allocate large internal temporaries. The sampler calls `_ensure_site_in_ram()` over all sites before building right environments and batched shot state; paging pages may then be rehydrated all at once. Consequently, a limit that looks like a strict RAM budget may only measure retained tensor bytes, not true process peak RSS. A QASM declaration may also create a very large number of site arrays before any resource limit is applied.

**Do not make a fake “hard RAM limit” claim.** Separate these concepts in code, result metadata, and docs:

- retained MPS tensor bytes;
- projected temporary tensor/SVD working-set bytes (an estimate, if the library cannot expose allocator internals);
- swap/on-disk bytes;
- process RSS / peak RSS, measured opportunistically and possibly unavailable;
- user-configured budget and whether it is a hard cap or a conservative preflight estimate.

**Required changes and tests:**

1. Add validated constructor budgets: finite, positive, and within a documented maximum; reject NaN, infinity, zero, negative, bool-as-number, and unreasonable values.
2. Before each expensive contraction, estimate shapes and bytes using overflow-safe arithmetic. Include old tensors, temporary two-site tensor, evolved tensor, SVD input, and worst-case `U/S/Vt` output. Apply a conservative multiplier for SVD/library workspace, document it, and refuse *before* allocating if projected requirements exceed the relevant budget.
3. Keep refused operations atomic: the old valid MPS must be unchanged. Test this before and after the preflight failure, including non-adjacent SWAP routing where one intermediate swap may succeed before a later operation is refused. If partial multi-gate routing is allowed to remain a coherent partial state internally, the overall circuit result must still be `UNRESOLVED` and must not sample/return that partial state as a successful circuit answer.
4. Avoid rehydrating every paged tensor merely to sample. Either implement bounded-memory environment paging/streaming with tests or fail closed before rehydration when it cannot satisfy the RAM contract. Never report success with a budget violation.
5. Estimate initial per-site allocation before creating an `n`-element list of NumPy arrays. Reject huge circuits before allocating objects. Preserve the documented 200–300 qubit structured workload capability; don't add a limit so low that the accepted GHZ/MPS tests fail.
6. Guard `shots` and temporary arrays against invalid, huge or overflowing values. Large-shot requests must fail before the allocation can OOM the test host.
7. Add tests with deliberately tiny RAM/storage budgets to force early refusal. Add an optional child-process RSS test with a timeout; do not assert a brittle exact RSS number across OSes. Assert the configured resource contract, stable state on refusal, and no fabricated output.
8. Inject swap-file failures (missing file, truncated file, `np.load` exception, out-of-disk/full disk if safely mockable) and verify cleanup and an explicit error state, not a false successful result. Ensure every temporary directory/page is cleaned on all exit paths.
9. Verify `cleanup()` is idempotent and does not mask the original exception. Test multiple concurrent chains for unique swap paths and absence of data cross-contamination.
10. Measure test workload resource usage; don't equate `active_tensor_bytes` with RSS. Preserve `None` for unavailable metrics rather than inventing values.

### CQ-03 — Qiskit measurement-to-classical-bit mappings

**Priority:** P1 for unsupported layouts; high confidence from the normalized data model.
**Likely file:** `cqhecs/circuit_parsing.py`, especially `_parse_qiskit`; also router, path backends, Qiskit BackendV2 and result formatting.

The normalized instruction triple `(name, qubits, params)` discards the destination classical bit(s) carried by a Qiskit measurement instruction. That cannot fully represent measurement semantics for circuits with custom bit mappings, unmeasured classical bits, repeated measurement or nontrivial classical-register layouts. The QASM parser explicitly rejects mismatched qubit/classical indices instead of silently remapping them; the Qiskit parser must have an equivalent truth contract.

Choose one coherent implementation strategy and document it:

- **Minimal Safe Stable:** reject nontrivial measurement mappings that are not representable by the current contract, with a specific `UnsupportedCircuitInputError` before simulation; OR
- **Full support:** extend the IR to carry `classical_bits`/measurement mapping and preserve that information through routing, sampling, result keys and all relevant adapters.

Do not add a partial patch that only sorts terminal measurements and still loses mapping semantics. Don't make Qiskit and QASM paths disagree silently.

**Regression matrix:**

- `QuantumCircuit(2, 3)` with only `q0 -> c2` and unmeasured `c0/c1`;
- `q0 -> c1` and `q1 -> c0`;
- measurements inserted in reverse order (`q1 -> c1` before `q0 -> c0`);
- multi-register Qiskit circuits with nonzero global offsets;
- repeated measurement to same/different classical bits;
- missing/extra clbits, non-contiguous classical targets and `measure_all()` layout;
- measurement before later gate (must be rejected if mid-circuit measurement isn't supported);
- equivalent QASM 2.0/3.0 cases and error category consistency.

Every test should assert either the *exact expected classical output mapping* or the exact, documented rejection. Tests must run through direct backends/router **and** the public `CQHecsBackend` provider where appropriate; provider-only tests do not cover the direct `parse_circuit()` API.

### CQ-04 — Parser coerces invalid qubit indices (`int(q)`)

**Priority:** P2; confirm all public input contracts.

`_parse_instruction_list()` used `int(q)`, which may silently convert a floating index such as `1.7` to `1`, and bool values are integer subclasses. A strict quantum input parser should reject invalid indices instead of normalizing them into another circuit.

- Accept genuine integer index types, including NumPy integer types if they meet the API contract.
- Reject booleans, non-integral floats, strings (`"2"`), NaN/inf, negative values, repeated/invalid arity, and excessively large indices unless the public contract explicitly declares a conversion rule.
- Validate `qubits`/`params` are finite iterables of expected shape; don't leak confusing Python exceptions for malformed nested input.
- Use structured errors consistently in native and Python parsers where feasible.
- Add property/fuzz tests for empty lists, generators, huge integers, invalid nesting, weird scalar types and valid boundary values.

Do not reject a legitimate API use only because a type differs from built-in `int`; define and test the exact accepted integral abstraction.

### CQ-05 — Path-C-vs-Aer differential test under-proves correctness

**Priority:** P2, but mandatory because test claims should match assertions.
**Likely file:** `tests/test_adversarial_aer_and_stim.py`, test `test_path_c_vs_qiskit_aer_mps`.

The old test's decisive assertion checks only that at least one key overlaps between the CQ-HECS and Aer count dictionaries. That does not prove matching distributions; many incorrect distributions share support keys.

Upgrade to:

1. For small circuits, compare Path C statevectors (global phase ignored) and/or exact probabilities against `qiskit.quantum_info.Statevector`.
2. Compare measurement support and normalization exactly where appropriate.
3. For sampled counts, compute total variation distance or a statistically justified coordinate-wise confidence envelope with an explicit seed and enough shots. Do not compare raw RNG streams across different libraries.
4. Test asymmetric/nonuniform states, phase-sensitive evolutions, both CNOT directions, CZ, SWAP, parameterized rotations, nonadjacent gates, terminal/partial measurement, and random bounded circuits.
5. On Aer MPS, explicitly use documented no-truncation options for an exact small-circuit reference, or set/report any truncation options. Never compare an untruncated implementation to an undocumented/default approximate reference without saying so.
6. Add a mutation that alters one tensor axis or one supported matrix entry and show that the differential test fails. The existing mutation harness's 11/11 result only covers its current 11 defect classes; add tests/mutants when a new class is discovered.

### CQ-06 — No timeout in the native SAT subprocess fuzz helper

**Priority:** P2.
**Likely file:** `tests/test_fuzz_sat.py`.

The QASM subprocess helper already uses a timeout, but the SAT helper as inspected did not. Add a conservative timeout and a clear failure message containing sanitized input size/test ID, not the entire arbitrary hostile input if huge. Keep solver exit codes explicit (for example, SAT and verified UNSAT are different normal outcomes under the documented CLI contract). Add stress/adversarial DIMACS cases for huge declared variable counts, clause counts, malformed terminators, duplicate literals, tautologies, empty clauses and contradictory units. Prevent malformed test cases from consuming unbounded CPU/RAM.

### CQ-07 — Path B “exact” vs “bit-exact” wording

**Priority:** P2 documentation/contract correctness.

Path B performs floating-point amplitude/branch arithmetic. It may avoid *deliberate approximation* when under budget, but that does not mean symbolic exact arithmetic or universal bitwise arithmetic identity. Audit all public claims including docstrings, README, architecture diagrams, metadata and research notes. Define `exact` consistently as the code intends, document the floating-point mode, and report approximation/numerical uncertainty honestly. Do not rewrite results to say “certified” unless a mathematically valid bound applies to the returned quantity.

### CQ-08 — Path C numerical-rank cutoff and “untruncated” claims

**Priority:** P1/P2 depending on reproducible error case.

The Python implementation uses a relative singular-value floor to decide numerical rank. Small but nonzero singular values can matter for ill-conditioned states; a cutoff described as a roundoff convention is not automatically a proof that the dropped contribution is physically irrelevant. The current code correctly records discarded spectral mass as a diagnostic and avoids advertising it as a certified global bound. Preserve that distinction and re-test it.

- Construct controlled matrices/states with singular values above and below the chosen threshold, including near-cancellation and very small rotation parameters.
- Compare against higher-precision or dense reference results where feasible.
- Ensure diagnostic mass is measured correctly and not hidden.
- If the algorithm deliberately discards a nonzero component, either change the numerical-rank rule/implementation, classify the result/contract with adequate caution, or derive a valid conservative error bound. Do not simultaneously call the operation mathematically exact and hide the discarded component.
- Keep `numerical_error_bound=None` if no defensible bound is derived; do not manufacture a number from the sum of local SVD residuals without proving propagation.
- Explain difference between `error_bound` (deliberate approximation), `numerical_error_bound` (defensible roundoff/error bound, or null), `sampling_error_bound` (finite shots) and diagnostic metrics.

### CQ-09 — Vulkan / native status claims

**Priority:** P1 for release truthfulness, P2 implementation work.

Existing code/docs correctly describe the Python scheduler as a planner and physical Vulkan dispatch as unverified. Preserve these labels.

- `scripts/verify_vulkan_shaders.py` demonstrates that GLSL sources compile and that resulting SPIR-V has expected magic; it does not test a physical GPU, queue submission, synchronization or readback.
- C++ CPU fallback or facade execution is not GPU acceleration, regardless of a Vulkan dependency or name.
- Keep `PLANNER_ONLY`, `CPU_REFERENCE`, `LEGACY_DIAGNOSTIC`, `EXPERIMENTAL`, and `PHYSICAL_GPU_UNVERIFIED` semantics precise where needed.
- Do not implement a token “dispatch” path that records a command buffer but returns CPU output as if GPU output.
- If and only if a real GPU backend is deliberately added, add an integration lane on an identified Vulkan device/driver; validate shader reflection/bindings, descriptor layouts, device limits, dispatch dimensions, barriers, queue family, staging/copy/readback, timeouts/device loss and numeric agreement with CPU reference. Capture device/driver/API details. Otherwise keep GPU acceleration explicitly unclaimed.

### CQ-10 — Large-register and API validation

**Priority:** P1/P2 based on measured allocations.

The QASM maximum register constant may be much larger than a physical simulator can safely initialize. A syntactically legal register size does not imply it is safe to materialize as hundreds of thousands/millions of Python tensors or native per-qubit objects.

- Add a configured, documented per-backend/per-entrypoint circuit-size budget with safe integer arithmetic.
- Preflight `n`, shot count, tensor sizes, statevector exponent/shift values, C-API buffer sizes and allocation byte calculations before allocating or shifting.
- Ensure `1 << n` occurs only after width checks and cannot overflow/allocate accidentally.
- A legal huge input may be parsed only if parsing is bounded; execution should refuse with a structured `UNRESOLVED`/input error before large allocation.
- Do not confuse a “number of qubits accepted by the parser” with “number of qubits efficiently simulable”.

### CQ-11 — Version/docs/release metadata consistency

**Priority:** P2; mandatory Stable gate.

Check these surfaces and all release-related scripts/workflows: `scripts/version.py`, `cqhecs/__init__.py`, `pyproject.toml`, `CMakeLists.txt`, `CITATION.cff`, `CHANGELOG.md`, `RELEASE_NOTES.md`, security support policy, docs, wheel/sdist metadata, SBOM package version, tag and release title/assets. `python scripts/check_version.py` must pass.

Fix contradictions about sampling vs dense-statevector limits, path capabilities, 300-qubit workload semantics, CPU vs GPU execution, exactness and “bit-exact” wording. If a guide says Path C has a 20-qubit count cap while current sampling has a separate wider limit, make clear which function/representation each limit belongs to and verify against constants/tests. Avoid copying the same hard-coded version number into new scripts.

### CQ-12 — CI actions need current Node-24 runtime and stronger pinning

**Priority:** P2 security/maintenance; mandatory for clean CI on current GitHub-hosted runners.

As of 2026-09-23, GitHub Actions runners no longer provide Node 20 for JavaScript actions. Existing audit logs showed warnings for `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/upload-artifact@v4`. Check current upstream supported releases live rather than guessing a version.

- Upgrade to reviewed action releases that use Node 24 and are compatible with current runner versions. Do not blindly change every `@v4` to `@v6`/`@v7` without reading release notes and assessing breaking changes, OS support and inputs.
- Pin third-party actions to full 40-character commit SHAs where practical; verify the SHA belongs to the intended reviewed upstream release. Keep a short adjacent comment identifying the version for maintainers.
- Prefer a supported dependency-lock mechanism if the repo/org adopts one; otherwise full commit SHA pinning is GitHub's documented strongest general recommendation short of a managed lockfile.
- Set least-privilege `permissions:` at workflow/job scope. `contents: write` should be limited to the release job; verification/build/PR CI should ordinarily be read-only.
- Keep `pull_request_target` out of untrusted-code execution paths. Avoid checking out an untrusted PR and then exposing write tokens/secrets.
- Audit shell interpolations, artifact paths, cache keys, permissions, release asset globs and `GITHUB_OUTPUT`/`GITHUB_ENV` handling for injection.
- Ensure PR CI and tag-release CI run on the exact SHA being merged/published. Fail closed if a matching successful CI run is absent.
- Avoid relying on movable tags for the action code being executed; document action versions and review upgrades.
- Don't update an action solely by string replacement. Run every workflow and inspect logs for deprecation/incompatibility warnings after upgrade.

### CQ-13 — Qiskit QFT deprecation warnings

**Priority:** P2.

The latest successful test log showed `QFT` / `BlueprintCircuit` deprecation warnings. Update the test to the documented current replacement (e.g. `QFTGate` or `synth_qft_full`, after checking current Qiskit behavior) and ensure the test still tests the same circuit transformation/execution contract. Do not simply filter the warning or remove QFT coverage. Add a compatibility decision if the minimum supported Qiskit floor requires conditional behavior.

### CQ-14 — Property/fuzz coverage and mutation range

**Priority:** P2.

Use property-based testing for strict parsers, arithmetic edge cases and small random circuits where safe. Hypothesis is a suitable tool, but add it as a declared/test dependency and keep deterministic seeds/settings where needed for CI repeatability. Every discovered minimal failure should become a fixed regression test. Do not use stochastic fuzz tests that can randomly destroy CI without storing the failing example.

Mutation testing currently covers 11 known source mutants. Keep the baseline/restore invariants and increase coverage when a meaningful new defect class is discovered. Report the mutation score only for the listed mutant set; it is not a proof of correctness.

## 8. Quantum correctness contract: reference-led verification

### 8.1 Independent references

Use the most appropriate oracle for the circuit class:

- `qiskit.quantum_info.Statevector` for small pure-state unitary circuits and exact probability/state comparisons.
- Qiskit Aer `statevector` for independent state evolution where useful.
- Qiskit Aer `matrix_product_state` for cross-checking MPS, with `matrix_product_state_max_bond_dimension=None` and documented truncation settings when comparing an untruncated case. Verify live library defaults.
- Stim for Clifford/stabilizer circuit comparisons, matching measurement and bit conventions carefully.
- Small exact hand-calculated circuits (X, H, Bell, GHZ, controlled rotations) for sanity and independently understandable outcomes.

A reference library isn't a magical oracle: check its options, transpilation, measurement semantics, bit order and whether it applies any truncation/noise. Record the reference method and tolerances in each test's docstring.

### 8.2 Deterministic versus stochastic checks

**Deterministic checks** should cover statevector up to a global phase, state normalization, exact zero probabilities/support, exact expectation values within floating tolerance, matrix/unitarity properties, gate identities, parser normalization, error state/exit code and memory accounting.

**Stochastic checks** should cover seeded sampling, shot sum, allowed support, empirical frequencies, probability/TV deviation within a derived bound, and seed determinism where the API promises it. Never require identical streams from two unrelated random number generators. Use enough shots for the chosen error threshold and document why the threshold is statistically defensible.

For a returned `counts`, always test `sum(counts.values()) == shots` when the result is supposed to contain counts. Do not test for presence of a key that could legitimately be absent due to a finite sample unless the exact probability and shot/sample guarantee justify it. For symmetric distributions and random outcomes, use a seed and statistical tolerance, not exactly 50/50.

### 8.3 Gate matrices and conventions

- Establish one documented basis and bit convention across Python, C++, Qiskit provider, QASM, C ABI and CLI.
- Qiskit count strings typically display `q0` at the rightmost bit; tests must assert this with an asymmetric circuit, not GHZ alone.
- For every supported gate, verify the matrix convention `U[output_bits, input_bits]`, control/target operand order and physical tensor axis mapping.
- Check two-qubit gates under `(q0,q1)` and `(q1,q0)` on asymmetric states, and for non-adjacent qubit pairs where the implementation routes through SWAPs.
- Apply gate inverse tests and known identities (e.g., `T†T=I`, `H²=I`, `CX²=I`, `SWAP²=I`; valid angle identities within precision).
- Check output normalization and norm conservation for unitary evolution.
- Test both control target orientation and operand indexing; don't rely only on circuits in which both outcomes happen to be symmetric.

### 8.4 Path-specific correctness

**Path A — Stabilizer tableau**

- Test only supported Clifford gates, each native and Python implementation as applicable.
- Validate tableau invariants, symplectic commutation/anticommutation and measurement collapse.
- Cross-check random small Clifford circuits against Stim and Statevector probabilities.
- Verify non-Clifford inputs are rejected by forced Path A; no silent route change under forced selection.
- Test native fallback gates explicitly; unsupported native gates should use the known correct Python path only if fallback is part of the documented behavior.

**Path B — Stabilizer-rank decomposition**

- Test exact branch coefficients for T/Tdg and non-Clifford rotations; test Clifford-angle rotations are handled through exact Clifford operation path where intended.
- Test `max_rank_branches` limits at below/equal/above boundary; no successful fabricated answer when exceeded.
- Test statevector width guard before `1 << n` or any dense allocation; test just below, at and above boundary.
- Compare small random circuits against Statevector probabilities and state vectors where API permits.
- Validate complex phase behavior, branch weight aggregation, normalization and seeded counts.
- Don't call floating-point amplitudes “bit-exact” or symbolic exactness.

**Path C — MPS**

- Test each supported single-qubit and two-qubit gate against dense statevector at small width.
- Include both two-qubit operand orders and non-adjacent gates; compare the *same logical unitary* regardless of internal chain routing.
- Test entanglement-induced rank growth and repeated nontrivial operations; test rank cap vs no-cap paths separately if both exist in native code.
- Verify SVD singular values and reconstruction residual with analytically known small matrices.
- Test numerical rank threshold on near-zero and tiny-but-nonzero singular values; don't conceal them as a certified zero without evidence.
- Test generic MPS sampling on non-GHZ bond-dimension-two states and asymmetric distributions; a GHZ heuristic must only apply after exact structural validation.
- Test measurements of selected qubits in arbitrary requested order, partial marginals, and the full classical map contract.
- Test `max_storage_mb`, `ram_budget_mb`, temp directory, swap files, cleanup, allocation refusal and exact state coherence after a refused operation.
- Test large structured GHZ/cluster cases (200–300 qubits) without claiming arbitrary 300-qubit simulation efficiency.

**Path D — Sparse Pauli dynamics**

- Confirm all supported gate conjugations and signs for X/Y/Z Pauli factors, control gates and rotations.
- Test user observable syntax fully consumed, masks nonnegative/in-range, repeated factor cancellation and invalid suffix rejection.
- For each observable, compare result with exact Statevector expectation and prove actual discrepancy `<=` reported bound (within floating epsilon), for retained and truncated cases.
- Confirm error bounds accumulate conservatively for every returned observable; tolerance exceedance yields `UNRESOLVED` with no values.
- Never attach an observable expectation bound to an invented joint bitstring distribution. If opt-in marginals are provided, label them as marginals/uncertified and don't call them a joint distribution.

### 8.5 Statistical thresholds

Avoid arbitrary thresholds that can fail randomly or accept wrong results. Use one of:

- exact equality for deterministic invariants;
- a tolerance justified by floating precision and circuit conditioning;
- explicit binomial / Hoeffding / TV confidence bounds with confidence `1-delta` and correct support size;
- repeated deterministic-seed regression plus a separate statistical property test.

Remember that a pointwise Hoeffding bound for one outcome isn't automatically a simultaneous bound for all outcomes unless the multiple-outcome correction is included. The result module already distinguishes distribution and observable metrics; maintain that distinction.

## 9. Parser, router, CLI and API contracts

### 9.1 Parser

- QASM 2.0/3.0 supported grammar must match docs. Unknown gates/constructs must be rejected, never ignored.
- Require complete statement consumption; enforce semicolons, register declarations, bounds and finite angle values.
- Preserve register offsets across multiple quantum/classical registers.
- Check parameter count, gate arity, finite float values, duplicated/invalid register declarations and malformed parentheses.
- Keep angle expression evaluation as a dedicated safe parser, never unrestricted Python `eval`.
- Add size limits for total source bytes, line bytes, angle length/depth, number of instructions and declared registers. Limits must prevent CPU/memory abuse before an oversized parse/execute path begins.
- Compare native and Python parser acceptance/rejection/error category for a shared corpus. Differences must be explicit documented compatibility gaps, not accidental behavior.
- Add malformed and property-based QASM inputs that never crash the process or hang. Run native parsers only via subprocess with timeout and capped input.

### 9.2 Router

- Check `gate_manifest` is the single authority for supported gate signatures where intended.
- A path is chosen only if it truly supports every operation's arity/parameters and measurement structure.
- Forced path selection never silently reroutes.
- Only expected capability errors may be considered for routing; programming errors must bubble up, not be swallowed by `except Exception` and silently retried.
- Unresolvable/resource-bound-exceeded circuits produce `UNRESOLVED`; technical failures are `FAILED`; neither should return success-shaped fabricated counts.
- Add router transition tests at each path boundary (T-count, qubit count, cut width, error tolerance, budget) to catch off-by-one routing mistakes.

### 9.3 CLI/JSON

- Under `--format json`, stdout is exactly one parseable JSON document; diagnostics go to stderr.
- Validate documented exit codes for success, usage error, unresolved/verification failure and environment unavailable.
- Test every subcommand's `--help`, invalid flags/values, bad paths and unsupported backend path.
- JSON schema version is present and stable. Check error responses also conform to the documented schema where applicable.
- Avoid catching every exception and turning it into a successful-looking payload. If a last-resort exception handler exists, it must return nonzero status and preserve diagnostic context while not leaking secrets.
- Test pip-installed `cq-hecs` entry point separately from running `python -m`/in-process CLI.

### 9.4 C ABI / C++ API

- Validate null pointers, sizes, indices, buffer lengths, invalid enum values, malformed QASM and exceptions at the ABI boundary.
- Ensure no C++ exception crosses C ABI unhandled. Return documented status/error and valid output length.
- Test caller output buffers canaries before/after expected area; test short buffers and overflows.
- Run sanitizers against parser/solver/hardening paths, and widen coverage if cheap.
- Test consistent API/ABI versioning and exported symbol names on Windows/Linux.

## 10. Resource and stress testing without destabilizing CI

Use three tiers:

1. **Fast contract tests (every PR):** small deterministic allocations and carefully mocked low budgets to force refusal before big allocation.
2. **Medium stress tests (CI/nightly):** structured 200–300 qubit GHZ/cluster workloads, moderate random circuits and bounded sampling. Add hard wall-clock timeout and memory limits where runner permits.
3. **Long/external profiling (nightly/manual):** repeated operations, page-in/page-out, high bond-dimension growth, heavy SAT formulas and benchmark scaling. Record hardware/software metadata; don't make all CI depend on noisy performance figures.

Every resource test should state which quantity is bounded: tensor bytes, projected working set, process RSS, virtual memory, swap/disk, shot workspace, wall time, or circuit width. Do not label a tensor-byte counter as RSS or VRAM. On Windows use appropriate process metrics; on Linux be clear whether a `resource` value is peak RSS KiB or bytes. If measurement isn't available, report `None` instead of an invented zero.

For subprocess tests, set timeouts and capture stdout/stderr. When using OS limits, make them generous and portable enough not to create unrelated flakes. Large-allocation test cases must test early refusal; do not deliberately attempt to allocate tens of GB and hope the runner survives.

## 11. Benchmarking and optimization rules

Correctness gates come first; only optimize after the reference tests are green.

- Use `benchmarks/run_vulkan_mps_benchmarks.py`, `benchmarks/generate_benchmarks.py` and existing JSON artifacts as starting points. Read their methodology before trusting results.
- Distinguish “benchmark generator output” from an actually executed benchmark. Do not fabricate benchmark result files or copy numbers from a different host.
- Establish baseline and candidate using the same runner, build type, circuit seed, shots, memory budget, thread count, warmup and repeated-run policy.
- Report median and dispersion or robust quantiles; avoid one-time fastest-run comparisons.
- Add size sweeps for bond dimension and qubit count. Capture time, peak RSS, allocated tensor bytes, swap bytes, gate count, max bond dimension, sample method and result status.
- Check performance does not worsen asymptotically or allocate dense state vectors unexpectedly for wide/low-entanglement cases.
- Do not “optimize” by truncating states silently, lowering fidelity, dropping gates or weakening tests. Any approximation must be opt-in, quantified and clearly labeled.
- For Pauli pruning, a better speed result is valid only if the bound covers the actually returned observable values and unresolved cases still fail closed.
- For SVD, use stable linear algebra and validate reconstruction/rank against independent NumPy/scientific references. Do not invent a new tensor network algorithm for Stable absent a reproducible workload and correctness oracle.

## 12. External research protocol

Research should answer a concrete question, not just collect fashionable terms. Prefer primary documentation, peer-reviewed papers and upstream implementation source. Use current sources; include access dates and links in `research/next_stable/RESEARCH_LEDGER.md`.

Required research areas:

1. **MPS/SVD:** mathematical MPS ordering, two-site contraction, canonicalization, QR/SVD updates, discarded singular values, truncation error propagation, conditional sampling and complexity in bond dimension.
2. **Reference behavior:** current Qiskit Statevector/Aer options, MPS no-truncation settings, sampling/output/bit-order semantics, and version migration notes.
3. **Parser:** OpenQASM version/measurement semantics, safe numeric expression parsing and input-size denial-of-service prevention.
4. **Property/differential testing:** Hypothesis, reduced random circuits, metamorphic identities, property shrinking and independent oracle selection.
5. **C++ reliability:** ASan/UBSan scope, allocation/overflow guards, exception boundaries and platform differences.
6. **GitHub Actions security:** latest Node-24-compatible first-party action releases; full SHA pinning; least privilege; release permissions isolation; CI exact-SHA guarantees; supply-chain provenance/SBOM verification.
7. **GPU truthfulness:** Vulkan queue submission, descriptor/buffer layouts, synchronization and readback required to claim compute acceleration. If hardware isn't available, preserve the “unverified” status.

For each researched idea record:

- source and publication/version date;
- problem it solves;
- assumptions and domain of validity;
- whether assumptions match CQ-HECS;
- proposed adaptation (if any);
- expected correctness/performance effect;
- how it will be tested;
- result: adopted, rejected, deferred, or blocked.

Do not claim that a paper proves CQ-HECS correct. Reproduce source examples independently where relevant. Do not add an approach such as a 2D tensor network, quantum-inspired heuristic, code symmetry compiler, new stabilizer decomposer or advanced GPU contraction merely because it is new. Adopt only when the problem is concrete, benefit plausible, assumptions match, and a trustworthy reference test can validate the implementation.

Useful reference starting points (check them live for current behavior):

- Qiskit Statevector: https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.quantum_info.Statevector
- Qiskit AerSimulator (methods and MPS options): https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html
- Qiskit Aer MPS implementation notes/source: https://github.com/Qiskit/qiskit-aer/blob/main/qiskit_aer/backends/aer_simulator.py
- Schollwöck, *The density-matrix renormalization group in the age of matrix product states* (Annals of Physics 326, 96–192, 2011): https://doi.org/10.1016/j.aop.2010.09.012
- Hypothesis property-based testing docs: https://hypothesis.readthedocs.io/en/latest/
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
- Node 20 removal on GitHub Actions (2026-09-23): https://github.blog/changelog/2026-09-23-node-20-is-no-longer-available-in-github-actions/
- OpenQASM language specification: https://openqasm.com/

## 13. Existing test inventory and exact local gates

Read current `pyproject.toml`, `constraints/ci-py311.txt`, CMake and workflow commands first. Do not assume test counts stay constant. The following commands correspond to the current observed repository layout and should be adjusted if the live code has intentionally changed.

### 13.1 Python setup — Windows PowerShell

From the repository root, in a clean worktree/virtual environment:

```powershell
py -3.11 -m venv .venv-stable
.\.venv-stable\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -c constraints/ci-py311.txt -e ".[dev,benchmark]"
```

If the environment cannot satisfy a pinned constraint, record the resolver output and inspect dependency compatibility. Do not delete constraints simply to make installs work. Use a fresh alternate venv for other Python versions; never share one venv between 3.11/3.12/3.13/3.14.

### 13.2 Python setup — Linux/macOS shell

```bash
python3.11 -m venv .venv-stable
source .venv-stable/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints/ci-py311.txt -e '.[dev,benchmark]'
```

For native-required suites, build the native binary first and set `CQ_HECS_REQUIRE_NATIVE=1` as CI does. If that environment variable is not supported by the current version, inspect `tests/native_artifacts.py` and use the actual project contract; never accept a run where required tests silently skipped.

### 13.3 Static, syntax and version gates

Run from repository root:

```bash
python -m compileall -q cqhecs tests scripts python_bridge
python scripts/check_version.py
python scripts/verify_no_silent_truncation.py
python -m flake8 cqhecs tests scripts --count --select=E9,F63,F7,F82 --show-source --statistics
```

Use the exact lint invocation in CI if the installed flake8 entry point differs. `verify_no_silent_truncation.py` is only a heuristic scan; a pass does not replace dynamic regression tests. Confirm `compileall` is not the only import check.

### 13.4 Python unit / integration suite

After native build where tests require it:

```bash
python -m pytest tests/ -q
```

For a timing profile:

```bash
python -m pytest tests/ -q --durations=25
```

For native-required CI-equivalent tests on Linux/macOS:

```bash
CQ_HECS_REQUIRE_NATIVE=1 PYTHONPATH=. python -m pytest tests/ -q
```

On PowerShell:

```powershell
$env:CQ_HECS_REQUIRE_NATIVE = "1"
$env:PYTHONPATH = "."
python -m pytest tests/ -q
```

Use the full public test suite, not only the new regression. Store JUnit XML when running CI-style validation. Confirm the test session shows all expected test classes; review skips and warnings.

### 13.5 Coverage gate

```bash
python -m coverage run --branch --source=cqhecs -m pytest tests/ -q
python -m coverage report -m --fail-under=70
python -m coverage xml -o coverage.xml
```

A minimum 70% branch-coverage gate is the current observed baseline. Coverage percentage doesn't prove correctness, and critical mathematical code needs tests even if line coverage is already high. Don't lower the threshold. Add branch coverage for new error/resource paths and verify the report includes the changed module.

### 13.6 Mutation gate

```bash
python scripts/run_mutation_tests.py
```

Expected general property: the unmutated baseline passes every embedded check, each mutation produces the targeted observable defect, every mutant is killed, subprocess timeouts are handled, all source files are restored byte-for-byte even if a check errors, and a clean Git diff remains except for intended edits. If the harness says a mutant survives, do not delete the mutant. Either fix the implementation/test or, with an explicit reason, repair the mutation anchor so it represents the real production defect. Verify the harness never counts setup errors as killed defects.

### 13.7 Native C++ configure/build — Windows PowerShell

Requires the current supported C++20 toolchain and Vulkan SDK according to the checked-in CMake/docs:

```powershell
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```

On a multi-config generator, configure-time `CMAKE_BUILD_TYPE` may not control the actual configuration; always pass `--config Release` to build and CTest. Confirm CMake actually found the Vulkan SDK and the intended compiler. Record `cmake --version`, compiler version, Vulkan SDK and architecture.

### 13.8 Native C++ configure/build — Linux

Use the exact CI toolchain where possible:

```bash
sudo apt-get update
sudo apt-get install -y cmake ninja-build g++-12 libvulkan-dev glslang-tools mesa-vulkan-drivers vulkan-tools
python -m pip install -c constraints/ci-py311.txt numpy qiskit qiskit-aer stim pytest psutil coverage flake8 nanobind setuptools wheel
python -m pip install -e . --no-deps
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON -DCQ_ENABLE_AVX2=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --config Release --parallel "$(nproc)"
ctest --test-dir build --output-on-failure --schedule-random -j"$(nproc)"
```

Use `sudo` only in a disposable/approved environment. Don't alter a user's global toolchain or package manager. If AVX2 is enabled, ensure the CI runner actually supports it; do not make binaries require AVX2 without a runtime/target policy.

### 13.9 Sanitizers

Use the project's configured sanitizer target/CI job and verify sanitizer flags are present in the effective build commands (the current CI already performs a flag-reachability check):

```bash
cmake -B build-sanitize -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCQ_BUILD_TESTS=ON -DCQ_ENABLE_SANITIZERS=ON
cmake --build build-sanitize --parallel
ctest --test-dir build-sanitize --output-on-failure
```

Run on a supported GCC/Clang platform; CMake says this option is not supported on MSVC. Run the same narrowed parser/solver/hardening set used in CI and broaden it when reasonable. Address sanitizer/UBSan reports at their root; don't add ignorelists or mark tests expected failures solely to get a green workflow.

### 13.10 Shader source validation

```bash
python scripts/verify_vulkan_shaders.py
```

Expected current inventory was 12 shader sources, but verify count from live tree. This command compiles sources and writes corresponding `.spv` files; inspect `git status` afterwards and decide whether generated binary changes are intentional/reproducible with the configured SDK. A pass means **shader compilation/SPIR-V validation only**, not device execution.

### 13.11 Package, wheel and source archive

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Inspect wheel/sdist contents and metadata, ensuring no secrets, local absolute paths, unintentional research dumps, test caches, stale files or missing runtime packages. Verify package version matches the canonical version. Keep build tooling deterministic where compatible with project policy; record any build dependency update.

### 13.12 Fresh virtual environment install and CLI smoke test

Linux/macOS:

```bash
python -m venv /tmp/cqhecs-release-smoke
/tmp/cqhecs-release-smoke/bin/python -m pip install --upgrade pip
/tmp/cqhecs-release-smoke/bin/python -m pip install dist/cqhecs-2.2.2-py3-none-any.whl
/tmp/cqhecs-release-smoke/bin/cq-hecs --help
/tmp/cqhecs-release-smoke/bin/cq-hecs version
/tmp/cqhecs-release-smoke/bin/cq-hecs doctor
/tmp/cqhecs-release-smoke/bin/cq-hecs --format json run name:bell --shots 1000 --seed 42 > /tmp/cqhecs-bell.json
/tmp/cqhecs-release-smoke/bin/python -c "import json; p=json.load(open('/tmp/cqhecs-bell.json', encoding='utf-8')); assert p['schema_version']; assert p['result']['counts']; assert sum(p['result']['counts'].values()) == 1000; print(p['result']['path'], p['result']['state'])"
```

Replace the wheel filename based on the actual canonical version; don't hardcode `2.2.2` in automation when a canonical version helper can be used. On PowerShell, use a unique temp directory and `.venv` activation, parse JSON via `ConvertFrom-Json`, and check `$LASTEXITCODE` after every command. Confirm the installed console script works outside the repository directory; otherwise the source tree may be masking missing package files.

### 13.13 Release provenance / checksum

Run the current release generator in a clean, correctly versioned tree (read its side effects first):

```bash
python scripts/generate_sbom_and_checksums.py
```

Independently verify checksums; don't trust the script's printed values as their own verification. Ensure checksums cover every distributed asset except the checksum file itself. Validate SPDX JSON, the SBOM package version/name/namespace, license and dependency declarations. The CI-generated artifact and release-generated artifact must be traceable to the correct source SHA. Use trusted build provenance/attestation where supported; hashes alone prove byte identity, not who built the artifact or whether the build was trusted.

## 14. Required targeted regression recipes

Add these as automated tests (not merely manual notes) in the appropriate test file. Use the project's existing unittest/pytest style consistently.

### 14.1 Path C reversed-control regression

A minimal test should explicitly instantiate `PathCMPSExactBackend`, assert the result status and count support, and compare with Statevector. For deterministic basis inputs, assert exact support, not exact shot split. For arbitrary states, compare statevectors/probabilities at stated tolerances.

The following is a fully specified test pattern for `ExactMPSTensorChain`; adapt the imports only if the live public class/interface changes. It uses Qiskit's gate matrices as the input operations and Qiskit's independent `Statevector` as the reference. The dense MPS contraction is in site order (site 0 first), so explicitly reorder tensor axes before comparing it with Qiskit's little-endian statevector indexing (`q0` is the least-significant bit):

```python
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector
from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain


def _mps_vector_in_qiskit_order(mps, n):
    # to_statevector() flattens site axes in chain order [q0, q1, ..., q(n-1)].
    # Qiskit vector index uses q0 as the least-significant bit, so reverse axes.
    tensor = np.asarray(mps.to_statevector()).reshape((2,) * n)
    return tensor.transpose(tuple(reversed(range(n)))).reshape(-1)


def _run_small_unitary_circuit_on_mps(qc):
    mps = ExactMPSTensorChain(num_qubits=qc.num_qubits, ram_budget_mb=64.0)
    try:
        for inst in qc.data:
            op = inst.operation
            if op.name in {"barrier", "id"}:
                continue
            qubits = [qc.find_bit(q).index for q in inst.qubits]
            matrix = np.asarray(Operator(op).data, dtype=np.complex128)
            if len(qubits) == 1:
                mps.apply_single_qubit_gate(qubits[0], matrix)
            elif len(qubits) == 2:
                # Preserve the original operand order. This is the contract under test.
                mps.apply_two_qubit_gate(qubits[0], qubits[1], matrix)
            else:
                raise AssertionError(f"unexpected gate arity in test: {op.name}")
            assert not mps.memory_limit_exceeded, "small reference test unexpectedly exceeded budget"
        return _mps_vector_in_qiskit_order(mps, qc.num_qubits).copy()
    finally:
        mps.cleanup()


def test_mps_reversed_cx_matches_statevector():
    qc = QuantumCircuit(3)
    qc.h(2)
    qc.ry(0.37, 1)
    qc.cx(2, 0)  # non-adjacent; gate operand order differs from chain order
    qc.cp(0.41, 2, 1)
    qc.swap(1, 0)

    actual = _run_small_unitary_circuit_on_mps(qc)
    expected = np.asarray(Statevector(qc).data, dtype=np.complex128)
    actual_norm = np.linalg.norm(actual)
    expected_norm = np.linalg.norm(expected)
    assert np.isclose(actual_norm, 1.0, atol=1e-10)
    assert np.isclose(expected_norm, 1.0, atol=1e-10)
    actual /= actual_norm
    expected /= expected_norm
    fidelity = abs(np.vdot(expected, actual)) ** 2  # ignores global phase
    assert fidelity > 1 - 1e-9
```

This test exercises the MPS contraction with the requested operand order rather than relying on Path C's sampled counts alone. Check the `Operator` local basis/operand convention in the installed Qiskit version and pin it with an asymmetric two-qubit sanity test. If the chain's documented `to_statevector()` ordering differs from the observation above, correct the explicit conversion based on a minimal `x(0)`/`x(1)` test; never weaken the fidelity assertion to hide a bit-order problem. The public backend execution and shot-sampling path still require their own tests.

### 14.2 MPS differential test for every two-qubit gate

Build a parameterized test list containing `cx/cnot`, `cz`, `swap`, `cp`, `crx`, `cry`, `crz`, `cu1` with valid angle values. For each gate test operand order `(0,1)` and `(1,0)`, and at least one non-adjacent pair `(0,2)` / `(2,0)` in a 3- or 4-qubit circuit. Use initial states that make the target gate's control/target role observable, plus Hadamard/phase/rotation-prepared states that reveal phase mistakes. Compare against `Statevector`, not a hand-duplicated gate implementation. If some gate is no longer part of Path C's documented supported set, assert it is rejected explicitly and update manifest/docs consistently.

### 14.3 Probability and sampling comparison

For small `n`, compare deterministic probabilities to the reference. For returned samples compute:

```python
from collections import Counter
import numpy as np

def counts_to_probs(counts, num_qubits):
    total = sum(counts.values())
    assert total > 0
    out = np.zeros(1 << num_qubits, dtype=float)
    for bitstring, count in counts.items():
        out[int(bitstring, 2)] = count / total
    return out

def total_variation(p, q):
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())
```

Choose shots and an acceptance bound based on support size and confidence. Do not hard-code `TV < 0.01` for a wide, low-shot state. Also separately test exact support constraints for Bell/GHZ where those constraints are absolute.

### 14.4 Memory preflight test

Create an MPS with a tiny configured storage ceiling, capture a copy of the valid state and dimensions, and apply an entangling gate whose required working set exceeds the budget. Assert refusal occurs before `np.linalg.svd` (monkeypatch it to fail if called) or before any large temporary allocation, `memory_limit_exceeded`/status is set, the prior state remains coherent and no counts are returned as a successful full-circuit result. Ensure the test itself doesn't allocate large arrays.

### 14.5 Qiskit mapping test

Test the deliberate contract decision: unsupported remapping raises a clear typed error before execution, or full mapping is represented and produces the expected classical bitstring exactly. The test must prove unmeasured bits are padded/formatted as documented and that measurement insertion order does not silently change meaning.

### 14.6 Invalid instruction-list tests

Add invalid cases including `1.7`, `True`, `"1"`, `NaN`, infinity, negative index, huge index, wrong arity, non-finite gate angle, a gate with wrong parameter count and malformed iterable. Each must raise a clear parser/validation error and must never be silently converted to another valid circuit.

### 14.7 Fail-closed result contract tests

For every backend, force a circuit outside supported capabilities and a circuit beyond the configured resource budget. Assert:

- no fake counts/probabilities/expectation values are returned;
- `UNRESOLVED` is not `EXACT` or `FAILED` unless the semantics are explicitly documented;
- `error_bound`/`numerical_error_bound` are not inconsistent;
- no count total is claimed if counts are absent;
- CLI exit code and JSON schema match the public contract;
- the router did not silently switch away from a forced path.

## 15. CI design and secure workflow audit

Review all jobs in `.github/workflows/ci.yml`, `nightly.yml`, and `release.yml` in context. The current pipeline includes Linux, Windows, Python 3.12/3.13/3.14 compatibility, Python 3.11 deterministic lanes, native C++20, CTest, coverage, shader source checks, source mutation and a Linux sanitizer job. Preserve them unless current evidence proves a step redundant or broken.

### CI required conditions

- PR CI covers all modified code and all high-risk subsystem contracts.
- Python tests on current supported versions pass; native-only tests either run or produce an explicit expected skip in compatibility-only lanes. Native-required lanes must set the required environment flag and fail if a native artifact is absent.
- Linux and Windows native builds pass, not just Python tests.
- CTest runs all expected tests and does not silently omit registered tests.
- ASan/UBSan runs under a supported compiler and proves flags reach the actual core/test objects.
- Coverage and mutation thresholds remain enabled.
- Package smoke installs the built wheel in a fresh environment outside the source tree.
- The release workflow refuses a tag unless the exact tag SHA has a successful required CI run and tag version matches canonical code version.
- Upload/build actions do not grant unneeded write permissions. Release publishing permission is isolated to the release job.
- Workflow artifacts have clear names, retention, expected-file checks and no leaked secrets.
- All actions use reviewed Node-24-compatible upstream versions and ideally full commit SHA pins; exact SHA is looked up from upstream release metadata and checked, not guessed.
- After upgrades, run CI on a test branch and inspect deprecation/runtime warnings; a successful exit status is not enough if the Actions runtime is warning about imminent incompatibility.
- If workflow policy/settings cannot be changed because permissions are unavailable, document the exact settings that an owner must enable (required checks, PR approval, force-push restriction). Never claim branch protection was enabled from a repo commit if it required owner settings outside access.

## 16. Docs, cosmetics and user experience

After behavior stabilizes, sweep all docs and visible output for stale/misleading claims. Avoid editing public docs prematurely and then leaving them inaccurate after code changes.

Check:

- [ ] README and usage guide accurately distinguish Python CPU paths, native binary, planner-only scheduler and physical GPU status.
- [ ] Path A scope is Clifford; Path B scalability is governed by T-count/rank and dense statevector width; Path C by bond dimension/storage/numerical rank/sampling width; Path D returns observables under a certified bound, not a generic joint measurement distribution.
- [ ] “Exact” means what `SimulationResult` actually enforces; float arithmetic and finite-shot sampling are described separately.
- [ ] Error-bound terms use consistent metrics. No sum of observable and distribution bounds without a valid same-metric argument.
- [ ] Examples are copy-paste runnable and use the actual current API arguments.
- [ ] All paths, aliases, measurement behavior, supported gate sets and rejected operations agree with `gate_manifest.py`, router, Qiskit Target, QASM contract and C++ implementation.
- [ ] CLI help, error messages, JSON schema and exit codes are stable and clear.
- [ ] QFT deprecation warnings are fixed with current API, not merely suppressed.
- [ ] Markdown code fences, links, tables, diagrams and headings render properly; no broken internal anchors.
- [ ] `CHANGELOG.md` and `RELEASE_NOTES.md` describe actual changes, actual verification and material limitations.
- [ ] `GEMINI.md` references the correct target/version and doesn't contain stale “mission target v2.2.0” instructions if the release target is `v2.2.2`.
- [ ] Generated audit/research files identify source URLs, date/SHA and distinguish executed tests from planned commands.
- [ ] Remove no useful historical record just to make a report look clean.

Cosmetic cleanup must not camouflage a correctness defect. Keep formatting-only changes separate from math/resource fixes where feasible.

## 17. Release workflow: `v2.2.2`

The target version is conditional on the live release metadata. If `v2.2.2` is already released by the time this mission runs, **do not overwrite or retarget it**. Reassess the current code version and use the proper patch version only after reviewing the release history and user intent. Never create a second content set under a published tag.

If `v2.2.2` is indeed the next release:

1. Ensure version metadata is consistently `2.2.2` across all required files and scripts. Use `scripts/check_version.py` as a gate.
2. Add release notes that say what was fixed, how it was tested, what remains unsupported, and whether a behavior/API change occurred.
3. Do not claim physical Vulkan execution without a real hardware/device test. Clearly state if the native engine is CPU reference or planner-only.
4. Build wheel and sdist from the final intended source; inspect package contents; install in fresh venv; run smoke test from outside repository.
5. Generate/check SBOM and SHA256. Recompute checksums independently. Review SBOM completeness and license fields; don't claim a dependency-complete SBOM if only dependency floors are present.
6. Merge the PR after all rules/required checks are green. Record merge commit SHA; fetch it from `origin/main`.
7. Confirm `git rev-parse HEAD` and GitHub default branch SHA match the intended final source after merge. Check no uncommitted changes.
8. Ensure required CI passes for exact target SHA. The release workflow specifically waits for CI on the tag SHA; rely on that guard rather than bypassing it.
9. Create/push tag `v2.2.2` only from the exact final merged SHA. Do not sign a tag with an unavailable key or claim signature verified unless it was verified.
10. Wait for the actual release workflow to complete. A tag being present alone is not proof release artifacts published successfully.
11. Inspect the published GitHub release: title, prerelease/draft flag, notes, asset list, wheel, sdist, checksum list, SBOM and release notes.
12. Download the exact published assets and verify checksum plus clean-install smoke. Ensure artifact version metadata matches tag and source SHA in release notes.
13. If the release action fails, diagnose and repair workflow/build root cause. A green pre-tag main CI does not override failed tag CI.
14. If any release gate is blocked, do not publish an incomplete release or claim Stable. Leave an accurate PR/state and explain the precise remaining blocker.

## 18. Definition of “done” — no exceptions

The agent may send a final completion report only if all relevant items are evidenced. Every line below must be marked `PASS`, `NOT APPLICABLE WITH REASON`, or `BLOCKED WITH EVIDENCE`; **any P1 correctness/resource issue that remains confirmed and unfixed prevents Stable completion.** “Not tested” is never equivalent to “pass”.

### Code and correctness

- [ ] Every P1 audit finding reproduced or refuted with evidence; every confirmed P1 is fixed.
- [ ] Reversed-order Path-C gate differential/regression suite passes; phases/statevector and probabilities are checked for small states.
- [ ] Memory preflight, paging, huge input, cleanup and no-fabricated-output tests pass.
- [ ] Measurement mapping is correctly represented or explicitly rejected; Python/QASM/provider contracts agree.
- [ ] Strict input validation prevents silent coercion/truncation; fuzz tests are bounded.
- [ ] Differential MPS test compares meaningful results, not only overlapping key sets.
- [ ] Path D bound dominates actual observable discrepancy for exact reference cases, and unresolved behavior is fail-closed.
- [ ] Result schema cannot produce contradictory success/exact/unresolved combinations without being caught by tests.
- [ ] No tests or static checks were disabled/softened merely to get green.

### Local verification

- [ ] `compileall` passes.
- [ ] Version check passes.
- [ ] Silent-truncation heuristic scan passes, with known heuristic limitations understood.
- [ ] Full Python suite passes, and native-required tests actually execute in native CI.
- [ ] Branch coverage threshold passes; new critical branches are tested.
- [ ] Mutation harness baseline passes and all documented mutants are killed; no stale mutated files/bytecode remain.
- [ ] CMake Release build passes on supported native environment.
- [ ] All registered CTest tests pass; no unexpectedly missing target.
- [ ] Linux ASan/UBSan job passes and checks effective flags.
- [ ] Shader compilation validation passes if Vulkan SDK/source are in scope; its result is described only as compile validation.
- [ ] Package wheel/sdist build and `twine check` pass.
- [ ] Fresh-environment CLI smoke passes, including one valid JSON document, correct counts sum and expected state.
- [ ] `git diff --check` passes; no unrelated generated artifacts, secrets or local paths are committed.

### CI / PR / merge

- [ ] All current required GitHub checks pass on the latest PR head SHA.
- [ ] Linux and Windows build/test jobs pass.
- [ ] Python compatibility matrix passes across all versions currently declared supported.
- [ ] CI action runtime warnings have been resolved or documented as non-blocking by explicit upstream evidence; Node-20-incompatible actions are not left in the workflow.
- [ ] PR is merged only after required reviews/rules are fulfilled; no rules were bypassed.
- [ ] The final merged SHA is recorded and its CI passes.
- [ ] The default branch is clean and has no uncommitted release edits.

### Stable release

- [ ] Live version/tag/release metadata agrees; no existing published tag was moved.
- [ ] Release notes, changelog, docs and SBOM match the actual implementation.
- [ ] Tag points to the final verified merged SHA.
- [ ] Release workflow for that exact tag SHA succeeds.
- [ ] Expected assets exist and are downloadable.
- [ ] SHA256s independently verify; SBOM JSON parses and accurately states version/license/scope.
- [ ] Published wheel installs in a clean environment and the CLI smoke test succeeds from outside the source checkout.
- [ ] Release notes clearly disclose limits such as physical GPU execution being unverified if that is still the truth.
- [ ] Final report cites commit, tag, PR, CI run, release URL, exact test counts and any remaining limitations.

## 19. Required evidence ledger

Maintain a durable record such as `research/next_stable/EXECUTION_LOG.md` and update it in the same branch. Keep it concise enough to be useful but detailed enough to audit. Suggested format:

```markdown
# Execution log — CQ-HECS next Stable

- Started: ISO timestamp / timezone
- Base SHA: <actual>
- Feature branch: <actual>
- Target version: <live-verified version>
- OS/compiler/Python/CMake/Vulkan: <actual>

## Finding: CQ-01
- Status: CONFIRMED / FIXED / NOT REPRODUCED / BLOCKED
- Source: path + symbol
- Reproduction command/test: <exact>
- Before: exit code + concise failing assertion/log
- Root cause: <actual reasoning>
- Fix commit: <sha>
- Regression result: exit code + result
- Broader reference test: <command + outcome>
- External references: <URL, version/date>

## Gate evidence
| Gate | Exact command/workflow | SHA | Result | Evidence URL / artifact | Notes |
|---|---|---|---|---|---|
```

Rules:

- Record actual numeric test count, skipped count and warnings as emitted by the current run. Do not reuse the historical `311 passed` as if it were the new code result.
- Record each relevant run SHA and URL. A green run on the parent commit is not evidence for a feature commit.
- Include a brief reason when something is not applicable or unavailable.
- Do not include tokens, private URLs, personal host paths or unrelated environment secrets.
- Preserve failure evidence as useful context; don't edit the log to erase the fact that a fix required multiple attempts. Summarize final status separately.

## 20. Final report format

Only after all done criteria pass, send the user a final summary with:

1. **Outcome:** whether `v2.2.2` is truly Stable and published, or whether work is blocked (never label blocked as complete).
2. **Repository state:** final merge commit SHA, tag SHA, PR URL, release URL and exact feature branch if relevant.
3. **Critical fixes:** each verified root cause and regression test that demonstrates it is fixed. Explain if an audit hypothesis was not reproducible.
4. **Test evidence:** actual Python pass/fail/skip count, CTest count, coverage %, mutation score/current mutant count, sanitizer results, package smoke, and OS/Python matrix. Link the CI runs.
5. **Release artifact evidence:** wheel/sdist/SBOM/checksum results, exact SHA verification, fresh install and CLI result.
6. **Capability boundaries:** explicit remaining limitations such as physical GPU unverified, Path D observable-only certification, or no mid-circuit measurements if they remain.
7. **Remaining non-blocking work:** cosmetic/docs/performance improvements that do not invalidate Stable. Never bury a P1 or mark unresolved work as cosmetic.
8. **Evidence log path:** point to the committed audit log and test matrix.

Do not say “everything is proven” in a mathematical absolute sense. Say precisely what was tested and what evidence supports the release. A finite test suite cannot prove every possible quantum circuit correct; it can strongly establish the defined contract over targeted, randomized, boundary and independent-reference coverage.

---

## 21. Operational command sequence (default runbook)

Adapt to live repo state and OS, but follow this order. Do not blindly paste all steps before understanding the current checkout.

1. Inspect Git state and repository guide; save baseline.
2. Fetch current main, release/tag state, PR state, recent CI and action versions.
3. Create a feature branch; don't overwrite local changes.
4. Confirm the Path-C reversed gate hypothesis; commit a test-only reproduction if practical.
5. Reproduce each other P1 finding in isolation; update `FINDINGS.md`/execution log.
6. Fix Path C gate axis order, if confirmed; add complete differential matrix.
7. Fix preflight/resource budget and bounded sampling/page-out behavior; add resource tests.
8. Resolve Qiskit measurement-map contract; add direct/router/provider/QASM tests.
9. Tighten parser coercion and timeouts; add fuzz/property tests.
10. Strengthen Aer/Statevector/Stim reference assertions; validate Path D error-bound tests.
11. Audit exactness/error semantics, QFT deprecations, docs and public claims.
12. Upgrade/re-pin actions after inspecting current upstream release notes and SHA; tighten permissions without breaking release workflow.
13. Run focused tests for each change; then complete static/Python/native/CTest/coverage/mutation/package/smoke gates.
14. Update changelog/release notes/audit/test matrix based on actual results.
15. Run `git diff --check`, inspect full diff, ensure no unintentional `.spv`, `.pyc`, build, test-result or secret changes.
16. Commit coherent changes and push feature branch.
17. Open/update PR, inspect every check and log; fix failures in a root-cause loop until green.
18. Meet required review/branch rules, merge normally, and verify merged commit SHA.
19. Rerun/check exact merged SHA gates; tag correct version only when release criteria pass.
20. Verify tag-release workflow, published artifacts, checksums, SBOM and fresh install.
21. Update execution log with exact evidence and report once the final checks prove the stated status.

If the agent cannot perform a step because of permissions or missing tools, it must still implement and test what is safely possible, preserve changes, and report the exact blocked operation. It must not claim to have pushed, merged, released, used a physical GPU, or run a test if it has not done so.

## 22. Additional hardening checklist

### Memory and numerical stability

- [ ] All size products are overflow-safe before allocation.
- [ ] All gate angles, probabilities, singular values and normalization quantities are finite/valid at boundaries.
- [ ] Zero-norm and NaN/Inf states fail closed.
- [ ] Any normalization step is mathematically justified; it must not hide lost amplitude or wrong gate updates.
- [ ] Temporary tensor allocation is part of the documented resource model.
- [ ] SVD rank decisions are stress-tested against ill-conditioned matrices.
- [ ] Randomized tests can be reproduced from stored seed and shrunk failing sample.
- [ ] File paging is private per simulation, uses safe paths and cleans up on exceptions.
- [ ] No temp-file collisions across concurrent chains/processes.
- [ ] User-controlled file path and circuit filename are not used unsafely for temp names.

### Reliability / concurrency

- [ ] Same circuit + same seed yields documented reproducibility.
- [ ] Independent simulations do not share mutable global state unexpectedly.
- [ ] Backend instances can be used concurrently only if contract permits; otherwise guard and document it.
- [ ] Exceptions in worker/thread/process do not turn into partial successful result.
- [ ] Timeouts are present for arbitrary potentially expensive subprocess input.
- [ ] Cancellation/interrupts clean up temporary resources.

### Build / packaging

- [ ] Wheel contains `cqhecs` and needed `python_bridge` modules but excludes tests/research/binaries unless explicitly designed to include them.
- [ ] sdist contains all files needed to rebuild and source license/citation/readme.
- [ ] Native binary packaging clearly states compiler/runtime/Vulkan requirements and doesn't pretend the Python wheel contains GPU hardware implementation.
- [ ] Windows path separators, console output encoding, executable location and PowerShell exit codes are tested.
- [ ] Linux executable permissions and dynamic dependency checks are performed where applicable.
- [ ] Version is derived from canonical helper wherever possible.
- [ ] SBOM output doesn't include invented dependency versions.

### Security / supply chain

- [ ] No credential appears in `git diff`, logs, tests, docs, artifacts, release notes or remote URL.
- [ ] Actions are current Node 24-compatible releases and pinned/locked with a documented update method.
- [ ] `GITHUB_TOKEN` permissions are read-only by default; release write access is job-scoped.
- [ ] Artifact downloads use trusted sources; tar/zip extraction cannot overwrite arbitrary files in scripts.
- [ ] Any user-provided circuit/QASM path is validated and parser length limits are enforced.
- [ ] SAT/ARX input resource ceilings are explicit and tested; no unbounded denial-of-service behavior in CLI.
- [ ] Public claims about exactness, error bounds, hardware and cryptanalysis are accurate.

### Cosmetics and ergonomics

- [ ] No stale release target/version in mission docs.
- [ ] No misleading `GPU`, `Vulkan accelerated`, `exact`, `certified`, `bit-exact` wording without evidence/qualifier.
- [ ] No console status message says success while underlying result state is unresolved/failed.
- [ ] Clear error text names offending gate/index/limit and next step.
- [ ] No unnecessary warnings in the supported test path; legitimate warnings are understood and documented.
- [ ] Code remains maintainable; avoid duplicated gate implementations where a shared source-of-truth can safely be used.
- [ ] No overbroad refactor bundled with critical correctness change unless required; keep PR reviewable.

## 23. Release discipline — final reminder

The goal is not to make CQ-HECS look larger, faster, more quantum or more GPU-accelerated than it is. The goal is a trustworthy classical quantum-circuit simulation and analysis toolkit whose supported cases are correct, whose unsupported cases are honestly rejected, whose resource boundaries are explicit, whose error metrics mean what the docs say, and whose released artifacts can be independently checked.

**Continue the inspect → reproduce → fix → test → commit → push → CI → fix → merge → verify → release loop until each release-blocking condition is backed by evidence. Only then report.**
