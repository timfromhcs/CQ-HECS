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
