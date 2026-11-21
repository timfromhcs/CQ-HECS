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

## B-008 Flaky loopback test: test_sha_bridge.py::test_strict_json_validation
```
ID: B-008
Severity: Low (test reliability)
Category: RESOURCE
Affected: tests/test_sha_bridge.py::test_strict_json_validation (SHA hardware bridge)
Minimal reproduction: full-suite run under load once raised ConnectionAbortedError [WinError 10053]; the same test and its whole file pass deterministically in isolation and on re-run.
Expected: a loopback HTTP test must not depend on host scheduling under load.
Observed: a transient socket abort fails the test.
Root cause (or unknown): loopback socket read racing a client-side close under CPU load; not caused by this session's changes (the bridge code is untouched).
Fix attempted: none this session.
Remaining risk: a full-suite run can report one spurious failure; the release gate must re-run a failed test before treating it as a defect.
Next safe action: make the bridge test retry/robust to ConnectionAborted (Wave 7/10 hardening).
Status: OPEN
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
