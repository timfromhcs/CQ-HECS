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
