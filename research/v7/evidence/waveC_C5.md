# Wave C, task C5: W15 hardening (fuzz, property, resource, mutation, security audit)

Date 2026-11-22, branch `release/v7-stable`, Windows 11, Python 3.13.13 (PATH `python`), pytest 9.2.0,
hypothesis 6.170.14. No commit, add, stash, checkout or push was run. No QPU, Open Quantum call, credential or
credit spend. Version not bumped.

## Files written (all inside the C5 owned area)

New tests: `tests/test_fuzz_requests.py`, `tests/test_fuzz_dimacs_parser.py`, `tests/test_fuzz_qasm_parser.py`,
`tests/test_resource_limits.py`, `tests/test_property_cancellation.py`, `tests/test_property_security_audit.py`.
New script: `scripts/security_audit.py`. Extended: `scripts/run_mutation_tests.py` (extend only).
Documents: `research/v7/SECURITY_AUDIT.md` (new), `research/v7/LICENCE_REGISTER.md` (updated), this file.
`.github/workflows/*.yml`: audited, **not edited** (all 26 actions already SHA-pinned).

## 1. New tests

Command:
`python -m pytest tests/test_fuzz_requests.py tests/test_fuzz_dimacs_parser.py tests/test_fuzz_qasm_parser.py tests/test_resource_limits.py tests/test_property_cancellation.py tests/test_property_security_audit.py -q -p no:cacheprovider`

Result: **205 passed, 14 xfailed in 29.1 s** (hypothesis `derandomize=True`, so runs are reproducible).
`flake8 --select=E9,F` over the six test files and both scripts: 0.

| File | Passed | xfail (strict) | Covers |
|---|---:|---:|---|
| `test_fuzz_requests.py` | 54 | 8 | StudioState fuzz (sat solve/count, simulate, plan), HTTP bodies (malformed, oversized, nested, hostile Content-Length, random bytes to four routes), `/static/` traversal, preset names, "no request key names a file", MCP `handle` on arbitrary messages, out-of-range tool arguments, MCP stdout is JSON-RPC lines only |
| `test_fuzz_dimacs_parser.py` | 31 | 3 | arbitrary text, round-trip, whitespace/newline invariance, junk token, truncation, wrong clause count, brute-force differential for `solve` and `count_models`, constructor contract, digests |
| `test_fuzz_qasm_parser.py` | 21 | 1 | noise text, structured statements, one-character mutations, resource-hostile input (huge/negative register, deep parentheses, `9**9**9`, NUL, 2 MiB identifier, >16 MiB document), 100k-gate program parses completely, angle expressions |
| `test_resource_limits.py` | 20 | 2 | separator exact-or-UNKNOWN property vs brute force, preflight allocates nothing, `count_models` timeouts, `solve` timeout/node budget, `max_sat_checked` limit/weights/optimum vs brute force, UNRESOLVED circuit carries no counts/probabilities, forced path raises, bad shots |
| `test_property_cancellation.py` | 59 | 0 | cancel once-only, `CANCELLED` with no verdict, late result dropped, unknown/malformed cancel is a no-op, duplicate id, capacity `SERVER_BUSY`, abandoned workers count, 40 cancel-vs-completion races, 32 parallel ids |
| `test_property_security_audit.py` | 20 | 0 | scanner positive controls and placeholder negatives, tracked tree has no secret-shaped string, every Action SHA-pinned, Studio/MCP static contract, no new dynamic-code primitive |

### The 14 xfail markers are real defects, not skips

Each is `xfail(strict=True)` with its `SEC-` id; once the defect is fixed the test XPASSes, which strict mode
turns into a failure that says "remove the marker". Details and reproductions are in `SECURITY_AUDIT.md`.

| Tests | Finding | One-line reproducer |
|---|---|---|
| `test_random_spec_must_be_an_object` x3, `test_sweep_sizes_must_be_a_list` | SEC-L1 | `StudioState.sat_solve({"random": "x"})` raises `AttributeError` (HTTP 500) |
| `test_deeply_nested_json_is_a_typed_400` | SEC-L2 | POST `[` x 200000 gives HTTP 500 (`RecursionError`) |
| `test_mcp_non_object_params_are_invalid_params` x3 | SEC-L3 | `handle({"method":"tools/call","params":[1]})` raises `AttributeError` |
| `test_non_ascii_or_decorated_integers_are_refused` x3 | SEC-L4 | `parse_dimacs("p cnf 20 1\n1_0 0\n")` accepts literal 10; `+1` and U+0661 accepted |
| `test_formula_declaring_an_absurd_variable_count_is_a_typed_refusal` | SEC-M1 | `solve(parse_dimacs("p cnf 10000000000000 0\n"))` raises `MemoryError` |
| `test_count_too_large_to_serialise_is_typed` | SEC-L5 | `count_models(parse_dimacs("p cnf 20000 1\n1 0\n"))` raises `ValueError` (4300-digit limit) |
| `test_legacy_bridge_parameter_text_cannot_call_into_the_os_module` | SEC-M2 | `python_bridge.qasm_engine.QASMParser._eval_param_expr(<subclass-walk payload>)` returns `os.cpu_count()` (16.0) |

None of these files is in the C5 owned area, so none was fixed here: they are for the integrator.

## 2. Mutation harness

Extended `scripts/run_mutation_tests.py`: +18 checks, +31 mutants (64 -> 95 listed, 71 checks).
Run on a snapshot copy of the tree because the harness rewrites production sources and other agents edit
`cqhecs/service.py`, `cqhecs/mcp_server.py` and `cqhecs/studio/app.py` concurrently.

| Run | Output file (scratchpad) | Result |
|---|---|---|
| 1 | `mut_run1.txt` | baseline BROKEN: snapshot lacked `tests/data`; copy error, not a project defect |
| 2 | `mut_run2.txt` | baseline BROKEN: snapshot lacked `benchmarks/sat`; copy error |
| 3 | `mut_run3.txt` | baseline OK (72 checks); **92/96 killed**; survivors below |
| 4 | `mut_run4.txt` | baseline OK (71 checks); 94/95; one HARNESS ERROR (crash, not a valid kill) |
| 5 | `mut_run5.txt` | baseline OK (71 checks); **95/95 killed (100.0%)** |

Survivors of run 3 (all in the new mutants; the 64 pre-existing mutants were all killed):

| Mutant | Severity if real | Verdict | Action |
|---|---|---|---|
| Calibration run skips policy validation | LOW | **equivalent**: `service.calibration_provenance` repeats the guard and raises the same `ServiceError("invalid_policy")` | removed from `MUTANTS`, reason recorded in the source; behavioural check kept |
| MaxSAT accepts negative weights | MEDIUM (wrong optimum) | check was weak: negative is also rejected by inner `max_sat`, NaN is not | check now also tries NaN |
| Separator preflight disabled | MEDIUM (unbounded table) | check was weak: a mid-run budget refusal also reports `max_table == 0` | check now requires reason to say "preflight" |
| DIMACS unterminated clause accepted | LOW | check was weak: the old text was caught by the clause-count check | new text has a matching count |

The harness logic was not touched (only checks, mutants and the equivalent-mutant note were added); the
score was not tuned: three survivors were genuine gaps in my checks and are closed by checks that observe a
real behavioural difference.

Run 5 summary line: `Mutation score: 95/95 killed (100.0%)`; `Baseline OK: 71 checks pass on unmutated source.`

### Follow-ups for the integrator

1. **`tests/test_mutation_harness_meta.py` fails** (`test_the_documented_mutant_count_matches_the_table`:
   `95 != 64`). It pins the table size; the harness extension changed it. Not in the C5 area. The expected
   count and the prose (`64-mutant`) should be updated to 95 (and `README.md` lines 290 and 905 quote 64/64).
   This is the only failing test in the full run below, and it was caused by this task.
2. Re-run `python scripts/run_mutation_tests.py` **in place** at the freeze (anchors in `service.py`,
   `mcp_server.py`, `studio/app.py` were still changing during this task).
3. Fix or schedule SEC-M1 and SEC-M2 (MEDIUM); the six LOW findings are in `SECURITY_AUDIT.md`.

## 3. Security audit

`python scripts/security_audit.py --history --json-out <file>`: secrets in tree 0, secrets in history 0
(332 commits), code findings 1 (SEC-M2), Studio/MCP static contract 0, Actions unpinned 0, other 0
(26 `uses:` entries, all SHA-pinned; explicit `permissions` everywhere). `gitleaks`, `trufflehog`, `cargo audit`
and project-manifest `pip-audit -r`: **NOT RUN** (not installed / would install packages).

`pip-audit` 2.10.1 (found under Python 3.14) with `--path` on the Python 3.13 site-packages: 8 advisories, all
on `pip 26.0.1` (dev tooling). `npm audit` in `web/`: 0 vulnerabilities (also with `--omit=dev`).

Licences: `LICENCE_REGISTER.md` rows updated from installed-package metadata and `web/package-lock.json`;
python-sat, nanobind, qiskit-ibm-runtime and all external tools stay `UNVERIFIED`.

## 4. Full Python suite

Command: `python -m pytest tests -q -rs -p no:cacheprovider` (PATH python, run once, at the end).
The tree was **still being changed by other Wave C agents** while it ran (git status showed modified
`cqhecs/service.py`, `mcp_server.py`, `studio/app.py`, docs and web files), so this is a snapshot of a moving
tree, not a freeze result.

Result: **1 failed, 4109 passed, 126 skipped, 1 deselected, 15 xfailed in 554.5 s (9:14).**

- The 1 failure is `tests/test_mutation_harness_meta.py::TestMutationAnchors::test_the_documented_mutant_count_matches_the_table`
  (`95 != 64`), caused by the harness extension above. No other failure.
- 15 xfailed = the 14 strict markers above plus 1 that was already in the tree.
- 126 skipped by reason (`-rs`, grouped; 35 distinct skip lines): native `cq_hecs_core.dll` / `cq_hecs.dll`
  not found (6 + 4), `CQ_HECS_EXE` not set (6), `qiskit-ibm-runtime` not installed (4), legacy
  VulkanQpuBackend needs the native build (3), `python-sat` not installed (2), native build instructions (2),
  `CQ_LRAT_CHECK`, `CQ_DRAT_TRIM`, `CQ_CAKE_LPR` unset (1 each), OMNIWAVE BCP native library absent (1), and
  an "optional" skip (1). Those lanes are NOT RUN here; none is a pass.
- Full log kept in the session scratchpad as `full_suite.txt`; not committed.

## NOT RUN

gitleaks, trufflehog, cargo audit, `pip-audit -r requirements.txt`, native/Vulkan tests, Playwright/axe,
in-place mutation run, any lane needing `qiskit-ibm-runtime`, `python-sat`, drat-trim, lrat-check, cake_lpr.
