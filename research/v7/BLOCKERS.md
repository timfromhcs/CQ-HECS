# Blockers and open issues

## B-001 Stale native artifacts in the local `build/` directory
```
ID: B-001
Severity: Low (local environment only)
Category: INTEROP / RELEASE
Affected: working tree, not the repository
Minimal reproduction: pytest tests/ with the pre-existing ignored build/ directory
Expected: version tests see 4.0.0
Observed: test_c_api, test_cli_powershell (2) fail: cq_hecs.dll / cq_hecs.exe in build/ report 3.7.0
Root cause: build/ predates the version bump; tests/native_artifacts.py prefers it
Evidence: research/v7/evidence/final_pytest.txt
Fix attempted: rebuilt into build/v4 and set CQ_HECS_BUILD_DIR; 19 passed
Remaining risk: CI builds from scratch, so it is unaffected; developers with an old
  build/ must rebuild. The local build/ directory was not deleted (not mine).
Next safe action: none required
Status: FIXED (environment)
```

## B-002 Optional-dependency and external-checker coverage not exercised
```
ID: B-002
Severity: Medium (coverage gap, not a defect)
Category: RELEASE
Observed: python-sat, drat-trim, lrat-check, cake_lpr, Lean toolchain are not installed
  here; the corresponding tests are skipped. v4 does not change that code, but
  its certification claims therefore rest on v3.7.0 evidence only.
Next safe action: run the nightly workflow or install the extras and rerun.
Status: OPEN (documented as NOT RUN in TEST_MATRIX.md)
```

## B-003 No remote CI evidence yet
```
ID: B-003
Severity: High for release (not for development)
Category: RELEASE
Observed: remote CI and preview results exist only after the pull request is opened.
Status: IN_PROGRESS (see RELEASE_AUDIT.md)
```

## B-004 Equivalent mutant (resolved)
A "global literal sign flip" mutant of the separator counter survived; it is
semantically equivalent (the count is invariant under negating every literal). It
was replaced by a polarity-ignoring mutant that is killed. Recorded so the 60/60
score is not read as a harness tuned to pass.

## B-005 Total deadline does not yet cover proof checking (D3, W3-10)
```
ID: B-005
Severity: Medium (honesty) -> FIXED
Category: RESOURCE
Affected: cqhecs/sat_external.py, cqhecs/omniwave/engine.py
Fix: the external adapter's proof budget is now the remaining time within the stated
  deadline (_proof_budget: timeout - elapsed, unless an explicit override is given); the
  OMNIWAVE engine caps its proof check by the remaining time as well. A search that
  refutes the formula but has no time left for the proof returns UNKNOWN, not a false UNSAT.
Evidence: tests/test_unified_deadline.py (6 tests); tests/test_omniwave.py and
  tests/test_unified_solver.py still pass (472 passed).
Status: FIXED
```

## B-006 Path C "exact" label audit (D12, W3-03)
```
ID: B-006
Severity: None (audit)
Category: NUMERICAL
Observed: audited. The Python surfaces already qualify the label: error_bound=0.0 means
  no deliberate budget approximation; numerical_error_bound is None with a "not derived"
  reason; the discarded mass is metadata["discarded_spectral_mass_diagnostic"] only, and
  tests pin that it is never presented as a bound. CLI/Studio serialise metadata.
Fix attempted: none needed. Remaining: the Studio/Web UI copy that renders a result state
  should state the qualifier in plain language (Wave 7), not an overclaim.
Status: FIXED (audit complete: NOT REPRODUCED as a defect; see FINDINGS F-004)
```

## B-008 Oversized bridge POST aborted the client (FIXED)
```
ID: B-008
Severity: Low (test reliability) -> FIXED
Category: RESOURCE / INTEROP
Affected: cqhecs/hardware/bridge.py (`_Handler._body` 413 path); tests/test_sha_bridge.py::test_strict_json_validation
Minimal reproduction: POST /pair with a Content-Length of 5000. The 413 path replied without
  reading the declared body; closing the socket with unread data then surfaced to the client as
  ConnectionAbortedError [WinError 10053] (and, once, as a flaky full-suite failure under load).
Root cause: `_body()` wrote 413 for `n > MAX_BODY` without consuming the request body. `_reject()`
  already drained a rejected body for exactly this reason (its docstring records the limiter's 429
  arriving as RemoteDisconnected), but the oversized-body path was missed.
Fix: `_Handler._drain_declared()` consumes a plausible declared body (`0 < Content-Length <=
  DRAIN_CAP = 1 MiB`) under a monotonic deadline before `_body()`/`_reject()` reply, mirroring
  `cqhecs/studio/app.py::_discard` (`read1` + deadline, so a trickling client cannot extend the
  drain). An implausible length (non-digit or > DRAIN_CAP) is still rejected at once instead of
  waiting for bytes a hostile client may never send.
Evidence: `tests/test_sha_bridge.py::test_oversized_body_is_consumed_before_the_413` is red on the
  un-drained path and green with the fix; `test_sha_bridge.py` + `test_sha_bridge_adversarial.py`
  34 passed.
Remaining risk: a body larger than DRAIN_CAP is still not fully drained, so a >1 MiB request may
  still abort the client; that is bounded and no worse than before.
Status: FIXED
```

## B-007 python-sat / external proof checkers not exercised here
```
ID: B-007
Severity: Medium (coverage, not a defect)
Category: RELEASE
Observed: python-sat, drat-trim, lrat-check, cake_lpr, Lean are not installed; W3-11 (child-process isolation) and the external DRAT/LRAT lanes are NOT RUN. The D3 certification tests use a monkeypatched sat_external, so the code path is covered but the real solver is not.
Next safe action: run the nightly/`CQ_REQUIRE_EXTERNAL=1` lanes where the tools exist.
Status: OPEN (documented as NOT RUN)
```


---

# V7 blockers and open issues (E3, 2026-11-22)

Append-only. Candidate `38e799b`. IDs are `B-V7-NN` so they do not collide with `B-001..B-008` above. B-002 and
B-007 (optional-checker coverage) are superseded in detail by B-V7-01 and B-V7-06. Template per AGENTS.md section
14. Severity here: P1 blocks a stable release; P2 must be fixed or accepted by the maintainer; P3 is documented.

## B-V7-01 python-sat / CaDiCaL exits with 0xC0000409 after a complete result
```
ID: B-V7-01
Severity: P2 (external defect; mitigated in code)
Category: INTEROP / RESOURCE
Affected version/commit: python-sat 1.9.dev24 on Windows 11, CPython 3.13.13 and 3.14.6; cqhecs 7.0.0 at 38e799b
Minimal reproduction: Solver(name='cadical195', with_proof=True), solve, delete, exit the interpreter. A bare
  solve with with_proof=False exits 0. Every pytest process that ran the external CaDiCaL tests ended with exit
  code -1073740791 (0xC0000409) after all tests had passed (D5, A4).
Expected: exit code 0 after a passing run.
Observed: abnormal interpreter exit after the result is produced.
Root cause: not in cqhecs; reproduced with a plain script that does not import it. Not diagnosed in python-sat.
Evidence: research/v7/evidence/waveA_A4.md, waveD_D5.md
Fix attempted: cqhecs/sat_external.py runs the raw solve in an isolated child (solve_external_isolated); a
  complete result followed by an abnormal exit is re-verified by the parent and carries a warning. A crash with no
  result, a hard-deadline kill or garbage output gives UNKNOWN. The defect is not suppressed.
Remaining risk: CI running these tests in the main process on Windows can see a non-zero exit with every test
  green. The hosted CI lane has not been observed.
Next safe action: run the external tests in the isolated path only on Windows CI, or pin a python-sat build that
  does not abort; report upstream.
Status: OPEN
```

## B-V7-02 Clang and Windows sanitizer lanes NOT_RUN (GCC-12 ASan+UBSan passed on hosted CI)
```
ID: B-V7-02
Severity: P3 (was P2 before the hosted run)
Category: INTEROP / SECURITY
Affected: native C++ core at 38e799b
Observed: locally NOT_RUN (no g++, the clang shim is broken); only MSVC /fsanitize=address ran, on 9 test
  executables (A2). The hosted job "Linux ASan + UBSan native tests" on PR #55 at 38e799b succeeded: gcc-12 with
  -fsanitize=address,undefined, halt_on_error=1, 100% tests passed out of 9 (read by E3, evidence/waveE_E3.md).
Remaining risk: Clang and UBSan on Windows are not run; the hosted result is one green job on a SHA whose CI
  run is still in progress and fails elsewhere (B-V7-15), not a green release.
Next safe action: re-confirm on the final freeze SHA.
Status: OPEN (GCC-12 hosted PASS at 38e799b; Clang NOT_RUN)
```

## B-V7-03 WebGPU f32 on a real adapter: partial run only
```
ID: B-V7-03
Severity: P3 (was P2 before the partial run)
Category: HARDWARE / INTEROP
Observed: the Playwright Chromium run exposes no adapter, so the WebGPU conformance spec is skipped (1 skip in the
  128/1 result). Wave E5 then ran the page in an installed Chrome 157 on an AMD RDNA2 adapter with unsafe-WebGPU
  flags: status RUN_PARTIAL, 20 cases measured, worst max-abs probability difference 1.7e-8 and worst TV 7.8e-8
  against the declared 5e-6 and 1e-5. One case (mid-circuit measurement) is not supported by the WebGPU engine and
  produced a timeout in the harness, not a deviation. The narrative file waveE_E5.md did not exist when E3 wrote this.
Evidence: research/v7/evidence/waveE_E5_webgpu_real_adapter.json (read by E3, not re-run), waveC_C1.md, docs/CONFORMANCE.md
Remaining risk: one adapter, one browser, headless with a blocklist override; real device loss, a second vendor and a
  non-flagged browser are not covered. The f32 deviation claim is limited to those 20 cases.
Next safe action: finish the partial run (explain the timeout), record browser and driver versions, add a second adapter.
Status: OPEN (partial)
```

## B-V7-04 Firefox and WebKit NOT_RUN
```
ID: B-V7-04
Severity: P3
Category: INTEROP / UX_A11Y
Observed: browser matrix is Chromium plus two Chromium phone emulations. docs/WEB_ENGINES.md says Firefox and
  WebKit are NOT_RUN.
Next safe action: add the engines to a hosted CI matrix, accept the visual baselines per platform.
Status: OPEN (NOT_RUN)
```

## B-V7-05 Clean Windows machine installation NOT_RUN
```
ID: B-V7-05
Severity: P2 (AGENTS_V7 21.3.2 requires it)
Category: RELEASE
Observed: the onedir EXE and native zips were smoked from a temp directory with a clean venv as a non-administrator
  on the build machine, which has Python, the Vulkan SDK and MSVC installed. A missing Visual C++ runtime, antivirus
  or SmartScreen behaviour, or a per-user profile difference would not have been noticed.
Evidence: research/v7/PACKAGING_AUDIT.md
Next safe action: extract the zip on a clean Windows VM without development tools and run package_smoke.py.
Status: OPEN (NOT_RUN)
```

## B-V7-06 LRAT, drat-trim and cake_lpr checkers NOT_RUN
```
ID: B-V7-06
Severity: P3
Category: RESEARCH / RELEASE
Observed: drat-trim, lrat-check and cake_lpr are not installed; the in-repo checker has no LRAT reader. Proof labels
  therefore stop at DRAT_CHECKED (in-repo) and MODEL_VERIFIED; EXTERNAL_DRAT_CHECKED, LRAT_CHECKED and
  CAKELPR_CHECKED_VECTOR are not claimed for 7.0.0. Their licences are UNVERIFIED in LICENCE_REGISTER.md.
Evidence: research/v7/evidence/waveA_A4.md, research/v7/SAT_PROOF_REVIEW.md
Next safe action: install the tools at pinned versions, open their licences, run fixed vectors in the nightly lane.
Status: OPEN (NOT_RUN)
```

## B-V7-07 T6-09 and T6-10 hardware follow-ups need authorised spend
```
ID: B-V7-07
Severity: P3 (not a release gate)
Category: HARDWARE / RESEARCH
Observed: further QG hardware runs (T6-09) and a fresh held-out BMV drift and uncertainty analysis (T6-10) need a
  provider run. No spend, credit, credential or QPU call was authorised or made by any V7 task.
Evidence: research/v7/evidence/waveB_B2.md
Next safe action: the maintainer authorises a per-run budget in writing; until then these stay NOT_RUN.
Status: BLOCKED (authorisation)
```

## B-V7-08 Legacy VulkanEngine reports a device in software-emulation mode
```
ID: B-V7-08
Severity: P3
Category: HARDWARE / UX
Affected: cq_hecs.exe subcommands qasm, stress and test (src/vulkan_engine.cpp)
Minimal reproduction: run them with no usable Vulkan ICD. VulkanEngine::initialize() returns true in "software
  emulation mode", so they do not refuse the way vrts, ghz, echo and maxcut now do (P-03 fix, exit 3).
Expected: a typed refusal or an explicit CPU-reference label.
Observed: unchanged legacy behaviour; documented in docs/PACKAGING.md. Its failure paths are also not routed
  through the fault-injection layer.
Evidence: research/v7/evidence/waveD_D3.md, waveA_A2.md
Next safe action: route the engine through acquire_vulkan() or label its output, with a test.
Status: OPEN
```

## B-V7-09 Release and nightly workflows have not run; package.yml ran once and failed in two jobs
```
ID: B-V7-09
Severity: P1 for a release decision (not for the candidate)
Category: RELEASE
Observed: release.yml now calls package.yml as a reusable workflow (workflow_call). package.yml ran once on the PR at
  38e799b and failed in two jobs (B-V7-15); release.yml itself has not run. Only YAML parse, SHA pinning,
  permissions, trigger set and asset names are linted for it (tests/test_native_release_workflow.py, 16). The
  reusable call, the final artifact naming, the download-artifact merge and the SHA256SUMS job (skipped) are unproven.
  docs/RELEASE_PROCESS.md says the same. The Vulkan package smoke on a hosted runner is warning-only.
Evidence: research/v7/evidence/waveD_D3.md, research/v7/PACKAGING_AUDIT.md
Remaining risk: a push to main triggers release.yml and a production Vercel deploy. main is not protected.
Next safe action: run package.yml on the feature branch (workflow_dispatch or PR), read the logs, fix, repeat.
  Do not merge or tag before that run is green on the exact SHA (AGENTS_V7 section 21).
Status: OPEN
```

## B-V7-10 Historical SYK v1 hardware run is invalid (F-09, immutable)
```
ID: B-V7-10
Severity: P3 (historical finding, no action on the data)
Category: RESEARCH
Observed: research/qg_2026 finding F-09: the Stage-4 SYK v1 hardware run is INVALID (exact-versus-Trotter mislabel
  and a mirror circuit that is not the inverse), so its measured and "ideal" values disagree (mirror 0.947
  versus forward 0.118). The raw files are retained under research/qg_2026/raw/syk_qpu and must not be edited.
  The v7 SYK oracle (cqhecs/quantum_gravity/syk_trotter.py) recomputes the ideal value with an exact-inverse mirror.
Claim boundary: no SYK hardware claim is made; the stage is INCONCLUSIVE (F-09, F-10, F-11).
Evidence: research/qg_2026/FINDINGS.md, research/v7/evidence/waveB_B2.md
Status: OPEN (kept as a permanent negative result; closes nothing)
```

## B-V7-11 Skip-budget gate fails on the freeze run
```
ID: B-V7-11
Severity: P2 (AGENTS_V7 21.1.2: no unexplained skip)
Category: RELEASE
Minimal reproduction: python scripts/skip_budget.py --junitxml <freeze_junit.xml> --check
Expected: OK.
Observed: FAILED. 134 skips against a budget written for 105. Seven reasons are unbudgeted (native executable and
  DLLs not found because CQ_HECS_BUILD_DIR was not exported; web/Playwright skip; python-sat and
  qiskit-ibm-runtime absent on 3.13.13) and 'CQ_HECS_EXE not set' grew from 4 to 6.
Root cause: the freeze ran without the native build directory and optional extras; SKIP_BUDGET.json predates it.
Evidence: research/v7/TEST_MATRIX.md (V7 section), research/v7/BASELINE_V7.md addendum (4 qiskit-ibm-runtime skips)
Fix attempted: none by E3 (SKIP_BUDGET.json is not in E3's area, and the budget must not be widened just to pass).
Next safe action: re-run the full suite with CQ_HECS_BUILD_DIR set (and, for the optional lanes, qiskit-ibm-runtime
  and python-sat installed), re-check; update the budget only with a written reason per reason string.
Status: OPEN
```

## B-V7-12 RELEASE_NOTES.md still describes 4.0.0 and is the release body
```
ID: B-V7-12
Severity: P1 for publication
Category: DOCS / RELEASE
Minimal reproduction: head RELEASE_NOTES.md shows "Version: 4.0.0, Release date: 2026-11-01"; release.yml
  ("Assemble the release body") runs `cat RELEASE_NOTES.md` into the GitHub release body.
Expected: the 7.0.0 notes (RELEASE_NOTES_DRAFT.md content, finalised).
Observed: a v7.0.0 release would be published with 4.0.0 notes. scripts/check_version.py only rejects the strings
  0.1.0 and 0.2.0 in that file, so the version gate does not catch it.
Evidence: E2 reported it (waveE_E2.md); E3 confirmed by reading both files.
Fix attempted: none by E3 (the files are outside E3's area).
Next safe action: replace RELEASE_NOTES.md with the 7.0.0 notes at publication and make check_version.py require
  the current VERSION in that file.
Status: OPEN
```

## B-V7-13 release.yml can tag a commit that is not on main (see SECURITY_AUDIT P2-1)
```
ID: B-V7-13
Severity: P2
Category: SECURITY / RELEASE
Observed: at the committed 38e799b, release.yml has no ancestry check: a pushed v* tag on a side branch (or a
  force-moved tag) reaches the publish path as long as required CI is green for that SHA (checked with
  `git show HEAD:.github/workflows/release.yml`; no `merge-base --is-ancestor`). The working tree carries an
  uncommitted edit that adds a "Release guard" step (`git merge-base --is-ancestor "${RELEASE_SHA}" origin/main`);
  it is not committed, has no negative test run by E3 and has never run on a hosted runner.
Next safe action: confirm the guard, with a negative test, on the final freeze SHA and in a hosted dry run.
Status: IN_PROGRESS (owner: E4 and the integrator; E3 only records it)
```

## B-V7-14 Preview and production evidence for the candidate is missing
```
ID: B-V7-14
Severity: P1 for a release decision
Category: RELEASE
Observed: a Vercel preview status for 38e799b reports SUCCESS, but nobody has compared the deployed bundle's version
  and source SHA with the candidate, and no anonymous E2E ran against the preview URL. The production deployment is
  not authorised or verified. AGENTS_V7 21.2.8, 21.2.9, 21.5.4 and 21.5.5 are therefore NOT_RUN. README, CHANGELOG
  and RELEASE_NOTES_DRAFT correctly say that no v7.0.0 tag or release exists.
Next safe action: after the CI is green on the final SHA, read the preview's embedded version and SHA, run the E2E
  against the preview, and record both.
Status: OPEN
```

## B-V7-15 Hosted CI on 38e799b is red
```
ID: B-V7-15
Severity: P1 for a release decision
Category: INTEROP / RELEASE
Affected version/commit: 38e799b, PR #55, runs 44994613449 (package), 44994613455 and 44994611308 (ci)
Minimal reproduction: gh run view 44994613449 / 44994613455 --json jobs (read-only). Failing jobs and tests:
  * Linux Vulkan lane, Python 3.11: 5 failed, 4413 passed, 35 skipped. Python 3.12/3.13/3.14 lanes: the same 4 of
    them (3.12: 4 failed, 4241 passed, 158 skipped).
    - tests/test_qg_replay.py::test_every_processed_number_is_reproduced_from_raw_counts (manifest hash of
      bmv_drift/bmv-drift-t2-YZ/counts.csv differs on Linux; cause not diagnosed)
    - tests/test_sat_external_isolated.py x2 (expects Windows status 0x40000409, sees POSIX exit code 9)
    - tests/test_web_shared_conformance.py::FixtureIntegrity (fixture text embeds the generator's Qiskit version:
      2.6.1 committed, 2.6.2 or 2.5.1 in CI)
    - tests/test_native_cpu_only.py::test_core_reports_cpu_only_capability (3.11 lane only: undefined symbol
      cq_core_build_capabilities in the Linux _cq_hecs_core.so)
  * Wheel and sdist job: clean-venv smoke FAIL studio_health_and_stop, OSError [Errno 98] Address already in use.
  * Native cq-hecs-cpu/vulkan (MSVC) job: CMake "Visual Studio 17 2022 could not find any instance" on the runner.
  * Windows full Python suite job: in progress for about 2 h in the step "Full Python suite" (possible hang;
    no result).
Expected: every required check green on the exact candidate SHA (AGENTS_V7 section 21).
Observed: red or unfinished on the SHA the README calls the freeze SHA.
Root cause: unknown for each. All but the MSVC image item are test or smoke portability defects that the Windows
  freeze run could not show. Other agents have uncommitted edits to tests/test_qg_replay.py,
  cqhecs/quantum_gravity/replay.py and tests/test_sat_external_isolated.py at the time of writing; E3 did not verify
  that they fix the first three items.
Evidence: research/v7/evidence/waveE_E3.md; TEST_MATRIX.md V7.E
Fix attempted: none by E3 (outside its area).
Remaining risk: the freeze figure "4269 passed, 0 failed" is a Windows, Python 3.13.13 result; it does not describe
  the Linux or compatibility lanes. The README states the Windows figure only; "all CI green" is not claimed
  anywhere and must not be.
Next safe action: fix the tests and the smoke port handling, normalise the version-bearing fixture, check the MSVC
  generator on the runner image, find why the Windows job is stuck, commit, push to the feature branch, and wait for
  every job on the new SHA.
Status: OPEN
```
