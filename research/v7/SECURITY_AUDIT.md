# Security and hardening audit (W15 / C5)

Date: 2026-11-22. Branch `release/v7-stable` (PR #55). Scope: Python package `cqhecs` and `python_bridge`,
Studio HTTP server, stdio MCP server, GitHub Actions workflows, dependency manifests, git history of this
branch. Method and limits are stated per section. Nothing here is a penetration test, and a clean scan is
not a proof of absence.

Reproduce: `python scripts/security_audit.py --history --json-out <file>`; `python -m pytest tests/test_property_security_audit.py tests/test_fuzz_requests.py tests/test_fuzz_dimacs_parser.py tests/test_fuzz_qasm_parser.py tests/test_resource_limits.py tests/test_property_cancellation.py`.

## 1. Findings

Severity scale: HIGH = remote or cross-origin compromise or data loss with default settings; MEDIUM =
local-user or malformed-input compromise, or unbounded resource use from a small input; LOW = wrong error
class, leniency or hardening gap with no direct compromise; INFO = observation.

No HIGH finding. No credential, token or private key was found in the tree or the branch history.

Status column as of the freeze (E3, 2026-11-22): the production-code findings reported by C5 were fixed in Wave D
(commits `c655e92`, `c631cf8`) and their strict `xfail` markers were removed, so the tests are now plain passing
tests. The original C5 wording, kept for history: findings in production code were reported to the integrator and
pinned by `xfail(strict=True)` tests.

| ID | Sev | Where | Status |
|---|---|---|---|
| SEC-M1 | MEDIUM | `cqhecs/sat.py` `parse_dimacs`, solver allocation | FIXED (`c631cf8`, `MAX_DIMACS_VARS = 1,000,000`; `evidence/waveD_D2.md`) |
| SEC-M2 | MEDIUM | `python_bridge/qasm_engine.py:164` `eval` | FIXED (`c655e92`, shared `parse_angle_expression`; `evidence/waveD_D1.md`) |
| SEC-L1 | LOW | `cqhecs/studio/app.py` request typing | FIXED (`c631cf8`; `evidence/waveD_D2.md`) |
| SEC-L2 | LOW | `cqhecs/studio/app.py` `_read_json` | FIXED (`c631cf8`; `evidence/waveD_D2.md`) |
| SEC-L3 | LOW | `cqhecs/mcp_server.py` `handle` | FIXED (`c631cf8`; `evidence/waveD_D2.md`) |
| SEC-L4 | LOW | `cqhecs/sat.py` `parse_dimacs` | FIXED (`c631cf8`; `evidence/waveD_D2.md`) |
| SEC-L5 | LOW | `cqhecs/sat.py` `count_models` | FIXED (`c631cf8`, `int_to_decimal_string`; `evidence/waveD_D2.md`) |
| SEC-L6 | LOW | dev environment `pip` | INFO for the repo, host-side |
| SEC-I1 | INFO | Studio responses lack CSP / frame-ancestors | OPEN (no `Content-Security-Policy` in `cqhecs/studio/app.py` at `38e799b`; accepted INFO) |
| SEC-I2 | INFO | MCP `id` of any JSON type is echoed | no action |

### SEC-M1 (MEDIUM): a DIMACS header can demand unbounded memory

- Reproduction: `parse_dimacs("p cnf 10000000000000 0\n")` returns a `CNF`; `solve(...)` then raises
  `MemoryError` (about 0.01 s). `p cnf 10000000 1 / 1 0` solves in 0.7 s; solve and count memory grow
  linearly in the declared `num_vars`, so a ~25 byte request chooses the allocation. Through Studio
  `POST /api/sat/solve {"cnf": "p cnf 999999999999 0\n"}` the server answers 500 `internal_error`
  (`MemoryError`); the `clauses` form is capped at 200 variables, the `cnf` form is not.
  MCP `cqhecs_sat_solve` returns `isError` with `MemoryError`.
- Impact: local denial of service (the Studio needs the bearer token, so the caller already holds it; MCP
  callers are the local model host). Not remote with default settings.
- Mitigation proposed: cap `num_vars` in `parse_dimacs` or in `_formula_from_request` with a typed
  `CNFFormatError` / `StudioError` (for example 5,000,000; the Studio `clauses` path already uses 200), and
  return typed `UNKNOWN` from the solver instead of allocating. Pinned by
  `tests/test_resource_limits.py::test_formula_declaring_an_absurd_variable_count_is_a_typed_refusal`.

### SEC-M2 (MEDIUM): `eval` on QASM parameter text in the shipped legacy bridge

- Where: `python_bridge/qasm_engine.py`, `QASMParser._eval_param_expr`:
  `eval(expr, {"__builtins__": None, "math": math}, {})`. `python_bridge` is packaged in the wheel
  (`pyproject.toml` `packages.find include`).
- Reproduction (observed): the expression
  `[c for c in ().__class__.__base__.__subclasses__() if c.__name__=='_wrap_close'][0].__init__.__globals__['cpu_count']()`
  returns `16.0`, the host CPU count: the string reached `os` through the class graph despite
  `__builtins__: None`. That is arbitrary function calls on the `os` module from a QASM file, so a hostile
  QASM file can run code in the process that parses it. The shipped `cqhecs` parser is not affected (it
  has a bounded recursive-descent angle grammar, `_MAX_ANGLE_LENGTH` 512, depth 200).
- Impact: code execution for whoever feeds the legacy bridge an untrusted `.qasm`. The `cq-hecs` CLI, Studio
  and MCP use `cqhecs.circuit_parsing`, not this module; the exposure is `python_bridge` users and the
  benchmarks that import it.
- Mitigation proposed: replace the `eval` with `cqhecs.circuit_parsing.parse_angle_expression`.
  Pinned by `tests/test_fuzz_qasm_parser.py::test_legacy_bridge_parameter_text_cannot_call_into_the_os_module`.
  Not exploited beyond a harmless `cpu_count()` call.

### SEC-L1 (LOW): wrong error class for mistyped request fields

`{"random": "x"}`, `{"random": [1]}`, `{"random": 5}` to `sat_solve` raise `AttributeError` (HTTP 500
`internal_error` instead of a 4xx); `{"sizes": 5}` to `sat_sweep` is refused only because `int()` over a non-iterable
happens to raise `TypeError` (422 rather than a `StudioError`). No data is returned, the server survives.
Pinned: `test_random_spec_must_be_an_object`, `test_sweep_sizes_must_be_a_list`.
Fix: type-check `request["random"]` (`isinstance(..., Mapping)`) and `sizes` before use.

### SEC-L2 (LOW): deeply nested JSON gives HTTP 500

`POST` of `[` x 200,000 raises `RecursionError` inside `json.loads`; `_read_json` catches only
`UnicodeDecodeError`/`ValueError`, so the response is 500 `internal_error`. The body bound (1 MB) limits
the depth to 1,000,000 levels; Python's recursion guard turns it into an exception, not a crash. Fix: catch
`RecursionError` and answer 400 `invalid_json`. Pinned: `test_deeply_nested_json_is_a_typed_400`.

### SEC-L3 (LOW): MCP `tools/call` with non-object `params`

`handle({"method": "tools/call", "params": [1]})` raises `AttributeError` (`params.get`). Through
`StdioServer` it becomes JSON-RPC `-32603 internal error` rather than `-32602 invalid params`; the server
does not crash. Fix: validate `params` is a dict at the top of the branch. Pinned:
`test_mcp_non_object_params_are_invalid_params`.

### SEC-L4 (LOW): the DIMACS parser accepts non-DIMACS integer spellings

`parse_dimacs` uses `int()`: `1_0` is accepted as 10, `+1` as 1 and non-ASCII digits (for example Arabic-Indic
U+0661) as 1. DIMACS is ASCII digits with an optional `-`. Whether the native parser rejects these spellings was not checked here.
Effect: two different files can denote one formula
(the canonical `sha256` agrees, `original_sha256` differs), which is a provenance and differential-testing hazard, not a
compromise. Fix: validate tokens against `-?[0-9]+` with `re.ASCII`. Pinned:
`test_non_ascii_or_decorated_integers_are_refused`.

### SEC-L5 (LOW): an exact count over ~4300 digits raises `ValueError`

`count_models(parse_dimacs("p cnf 20000 1\n1 0\n"))` raises `ValueError: Exceeds the limit (4300 digits) for
integer string conversion` from `str(value)` in `_count_models_dpll`. Studio maps it to 422; the Python API
raises an untyped error where the contract says typed `UNKNOWN`/refusal. Fix: serialise counts with
`sys.set_int_max_str_digits` scoped or a hex/bit-length fallback, or return a typed refusal. Pinned:
`test_count_too_large_to_serialise_is_typed`.

### SEC-L6 (LOW, host-side): `pip 26.0.1` has 8 advisories in the dev environment

`pip-audit` (installed under Python 3.14, run against the Python 3.13 `site-packages` with `--path`, which
queries advisory data but installs nothing) reported PYSEC-2026-196, -2875, -2876, -3721, all fixed in pip
26.1 to 26.2. `pip` is build tooling on the audit host, not a project dependency; CI installs from
`constraints/ci-py311.txt`. No project runtime dependency had an advisory. Action: update pip on the host.

### SEC-I1 (INFO): no `Content-Security-Policy` or `frame-ancestors` on Studio pages

Responses carry `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. A CSP (`default-src 'self'`,
`frame-ancestors 'none'`) would add defence in depth for the Studio UI. The bearer token and Host/Origin
allow-lists already block cross-site API use (see section 3).

### SEC-I2 (INFO): MCP echoes a JSON-RPC `id` of any JSON type

`id: [1]` is answered with `id: [1]`. Harmless; the JSON-RPC spec restricts ids to string, number or null.

## 2. Secret scan

- Tool: `scripts/security_audit.py` (committed regex scanner; `gitleaks` and `trufflehog` are **not
  installed** on the audit host, so the dedicated scanners were NOT RUN).
- Patterns: AWS access key ids, GitHub tokens, Slack tokens, private-key blocks, `sk-` style keys, Google
  API keys, JWTs, Hugging Face and npm tokens, assigned `api_key`/`secret`/`password` literals of 24+
  characters, credentials in URLs. Documentation placeholders are skipped by name.
- Result: 0 hits in every tracked file (1,900+ files, binaries skipped) and 0 hits in the lines added by any of the
  343 commits reachable from `HEAD` at `38e799b` (`--history`, re-run 2026-11-22; it was 332 at the first C5 run). Positive controls (planted keys of each pattern) are
  asserted in `tests/test_property_security_audit.py`, so a silent scanner would fail that test.
- Limits: pattern-based; high-entropy strings with no known prefix, secrets split across lines, encoded or
  compressed content and untracked or ignored files are not covered. Other branches and stashes were not scanned.
  The repository ignores provider credential files by design; their absence from history is what the scan
  observed, not something it can prove for other clones.

## 3. Studio and MCP contracts

Verified by static checks (`scan_studio_contract`), existing `tests/test_studio_security.py`, the new
`tests/test_fuzz_requests.py`, and mutation checks (section 6):

| Contract | Evidence |
|---|---|
| Default bind `127.0.0.1` | static check; `--host` default in the CLI |
| Per-launch random bearer token (`secrets.token_urlsafe(32)`), constant-time compare | static check; mutants "token not checked" and "non-bearer scheme" are killed |
| Token delivered in the URL fragment, never in a query string | static check; existing test |
| Host and Origin allow-lists | killed mutants; foreign Host is 400, foreign Origin is 403 |
| JSON-only POST (415) and 1 MB body bound (413) | killed mutants; fuzzed bodies never 5xx (`test_random_bytes_to_every_post_route_never_5xx`) |
| No CORS allow header | static check; `OPTIONS` test exists |
| No request field names a file | `test_requests_cannot_name_a_file_to_read_or_write` (nine key names; a planted file is never read or rewritten) |
| `/static/` serves an allow-list only; traversal attempts (`..`, `%2e%2e`, backslash, `//etc/passwd`, NUL) get 400/404 | `test_static_path_traversal_is_never_served` |
| Presets cannot resolve to files | `test_preset_names_never_resolve_to_files` |
| MCP stdout carries only JSON-RPC lines; diagnostics go to stderr | static AST check (no `print()` to stdout in `mcp_server.py`); `test_mcp_stdout_is_only_json_rpc_lines` |
| MCP has no network listener | static: stdio only |
| MCP out-of-range arguments are typed refusals | `test_mcp_out_of_range_inputs_are_typed_refusals` |
| MCP cancellation | 59 test cases in `tests/test_property_cancellation.py`: once-only answer, `CANCELLED` without verdict, late result dropped, capacity counted for abandoned workers, 40 cancel-vs-completion races, 32 parallel ids |

Symlink escape for output paths: **not applicable to the network surfaces**. No Studio or MCP request field
selects a path the server writes, and no request field selects a path it reads (above). Output paths exist only
as CLI flags (`--json-out`, `--proof-out`, `--out`, `--output`) chosen by the person running the command in
their own shell; following a symlink there is ordinary file-system behaviour, not a privilege boundary, so
no containment check was added. If a future route accepts a path, this section must be reopened.

## 4. Dynamic-code and deserialisation scan

AST scan of `cqhecs/` and `python_bridge/` for `pickle`, `cPickle`, `marshal`, `shelve`, `dill`,
`cloudpickle`, `eval`, `exec`, `os.system`, `shell=True`, `yaml.load` without a Loader: one hit, SEC-M2.
`tests/test_property_security_audit.py::test_no_new_dynamic_code_primitives` fails on any new one.
Scope limit: `subprocess` calls without `shell=True` are not flagged and were not individually reviewed.

## 5. GitHub Actions audit

`scan_actions` over `.github/workflows/{ci,nightly,package,release}.yml`: 41 pinned action uses (26 at the first C5 run on three workflows; `package.yml` was added since), **all 41 pinned to a
40-hex commit SHA** with a version comment; 0 unpinned. Every workflow has an explicit top-level
`permissions: contents: read`; `release.yml` raises permissions per job (`contents: write` only on the
publishing job, `actions: read` on the CI verification job). No `pull_request_target`, no `github.event`
text (titles, bodies, branch names) interpolated into a `run:` step, no download piped into a shell. No pin edits were
needed, so `ci.yml` and `nightly.yml` are unchanged. Not checked: whether each SHA still corresponds to
the commented tag (needs the network and per-action history); the SBOM and `release.yml` secrets
handling belong to C2.

## 6. Dependency audit

| Ecosystem | Tool | Result |
|---|---|---|
| Python (host `site-packages`, Python 3.13) | `pip-audit` 2.10.1 `--path` | only `pip` 26.0.1 affected (SEC-L6); no project dependency flagged |
| Python (project manifest `requirements.txt` / extras) | `pip-audit -r` | NOT RUN: it resolves by installing into a temporary environment, which this task does not do |
| npm (`web/`) | `npm audit` | 0 vulnerabilities (info 0, low 0, moderate 0, high 0, critical 0), with and without `--omit=dev` |
| Rust (`web/wasm`) | `cargo audit` | NOT RUN (not installed); `Cargo.lock` lists only the in-repo crate |
| Native C++ | n/a | no third-party source vendored (CMake `find_package` of the Vulkan SDK and optional nanobind only) |

Licences: see `LICENCE_REGISTER.md`.

## 7. Mutation testing

`scripts/run_mutation_tests.py` was extended with 18 new behavioural checks and 31 new source mutants
covering the Wave A/B surfaces: `service.py` (forced path, strict source), MCP (protocol negotiation,
cancel once-only, late-result drop, `CANCELLED` without verdict, capacity), Studio guard (token, scheme,
Host, Origin, body bound, JSON-only), `calibration_v3` (label consistency, refuse/warn policy, freshness,
trace preservation), `max_sat_checked` (limit boundary, weights, re-verification), the separator preflight
and bound, and DIMACS/QASM limits. Final run: **95/95 killed (100.0%)** on a snapshot copy of the tree,
baseline OK on all 71 checks. Full output: `research/v7/evidence/waveC_C5.md`.

Honest history of that number, because a 100% is only worth something with its path:

- First run: 92/96, four survivors, all new. Three were weak checks of mine and were strengthened, not
  skipped: the NaN-weight case (the inner `w < 0` test lets NaN through, so only the outer guard stops it),
  the separator preflight (a mid-run budget refusal also reports `max_table == 0`, so the check now requires
  the reason to say "preflight"), and the DIMACS unterminated-clause case (the old text was also caught by the
  clause-count check, the new text is not).
- One mutant was **equivalent** and was removed with a written reason in the harness source:
  `service.run_with_calibration` and `service.calibration_provenance` both guard the policy and raise the
  same `ServiceError(code="invalid_policy")`, so deleting the first changes nothing observable.
- One harness error (a mutated NaN path crashed the check instead of raising the typed error) was resolved by
  treating the untyped failure as the observed defect, in that check only.
- Pre-existing 64 mutants: all still killed.

The harness was run against a copy of the tree (`cqhecs/`, `python_bridge/`, `scripts/`, `schemas/`,
`research/`, `tests/data`, `benchmarks/sat`), not in place: it rewrites production sources, and other agents
edit this tree concurrently. **The integrator must re-run it in place at the freeze**, because the anchors in
files that were still changing (`service.py`, `mcp_server.py`, `studio/app.py`) are exact text and the
`tests/test_mutation_harness_meta.py` count pin still says 64 (now 95); see the evidence file.

Scope: this is a mutation score over listed patches, not a correctness proof.

## 8. Not done

- `gitleaks`/`trufflehog` (not installed), `cargo audit`, project-manifest `pip-audit`.
- No dynamic testing of the Studio over a non-loopback interface, no TLS review (the Studio speaks plain
  HTTP on loopback; exposing it on a LAN would send the bearer token in clear, and the Host allow-list
  already refuses LAN host names).
- No review of the native C++ code or of the web front end beyond what the existing Playwright/axe suites cover.

## Wave D status update (2026-11-22)

SEC-M1 (DIMACS var cap, MAX_DIMACS_VARS=1,000,000), SEC-M2 (python_bridge eval removed), SEC-L1..L5 and P-01 are FIXED
(evidence: research/v7/evidence/waveD_D1.md, waveD_D2.md); the strict xfail tests are now plain passing tests.
Positive-control vectors in tests are allow-listed explicitly in scripts/security_audit.py SECRET_ALLOW (each with a reason).
Not examined: web/src/main.ts `new Function` (user-authored JS builder, by design) and cqhecs/service.py dynamic `__import__`.


## Freeze update (E3, 2026-11-22, candidate `38e799b`)

Re-run: `python scripts/security_audit.py --history` returned `secrets_tree` 0, `secrets_history` 0,
`history_commits_scanned` 343, `code` 0, `studio_mcp_contract` 0, `findings_total` 0, `actions_unpinned` 0,
`actions_other` 0, `actions_inventory` 41 (four workflows: `ci.yml`, `nightly.yml`, `package.yml`, `release.yml`).
Targeted tests re-run on the working tree (HEAD plus Wave E edits): `test_property_security_audit.py`,
`test_fuzz_requests.py`, `test_fuzz_dimacs_parser.py`, `test_fuzz_qasm_parser.py`, `test_resource_limits.py`:
**181 passed**, no `xfail` remaining (the 14 strict xfails of the first C5 run were converted to passing tests in
Waves D1/D2). The scanner is pattern-based; `gitleaks`, `trufflehog`, `cargo audit` and a manifest-level `pip-audit`
remain NOT_RUN. Note on section 7: the mutation count pin that the original text says "still says 64" was fixed in
D5 (`tests/test_mutation_harness_meta.py` now asserts a floor of 64, not a literal); the harness has 95 mutants and
the freeze run in place was 95/95 (`evidence/waveE_E2.md`, integrator-recorded).

### Status of every finding at the freeze

| ID | Sev | Status | Evidence |
|---|---|---|---|
| SEC-M1, SEC-M2 | MEDIUM | FIXED | `c631cf8`, `c655e92`; 181 tests above |
| SEC-L1 to SEC-L5 | LOW | FIXED | `c631cf8` |
| P-01 (Studio on an occupied port) | medium | FIXED (`StudioPortError`, exit 4, `allow_reuse_address` off on Windows) | `evidence/waveD_D2.md` |
| SEC-L6 | LOW, host-side | INFO: `pip` on the audit host; not a project dependency | section 6 |
| SEC-I1 | INFO | OPEN, accepted: no CSP or `frame-ancestors` on Studio pages | section 1 |
| SEC-I2 | INFO | no action | section 1 |

### P2 findings from the independent freeze audit (not in the C5 list)

These were found by the freeze audit after the C5 work. E3 verified the state of each at the committed `38e799b`
by reading the files; none is fixed in a commit yet.

| ID | Sev | Finding | State at `38e799b` | Evidence of the fix in progress |
|---|---|---|---|---|
| SEC-P2-1 | P2 | `release.yml` can create a release from a `v*` tag on a commit that is not on `main` (no ancestry check; a tag on a side branch or a force-moved tag passes if CI for that SHA is green) | OPEN at the commit: `git show HEAD:.github/workflows/release.yml` has no `merge-base --is-ancestor` | the working tree has an uncommitted "Release guard" step against `origin/main`; unverified, never run on a hosted runner (B-V7-13) |
| SEC-P2-2 | P2 | The wheel SBOM lists non-dependency entries (build-venv tooling such as setuptools and its vendored packages, wheel, pip) because it enumerates every distribution in the venv rather than the runtime closure; a consumer would read tooling as shipped dependencies. Observed by E3 in the `38e799b` `cqhecs-7.0.0-wheel.cdx.json`: 23 components, including `setuptools` 79.0.1 and its vendored `autocommand` 2.2.2 declared `LGPLv3`, and `qiskit` 2.6.2 / `scipy` 1.17.1 that differ from the EXE SBOM (2.5.1 / 1.16.3) | OPEN at the commit: no `--closure-of` option, no assertion in `release.yml` | the working tree adds `--closure-of cqhecs`, a `cqhecs:source-revision` property and a release-time assertion (uncommitted; not run by E3) |
| SEC-P2-3 | P2 | Licences of shipped or CI-run components are `UNVERIFIED`: CPython runtime and Microsoft VC++ runtime DLLs in the EXE folder, python-sat, nanobind, qiskit-ibm-runtime, CaDiCaL, Kissat, drat-trim, cake_lpr, Lean/Mathlib; scipy and qiskit-aer ship vendored native libraries that are not individually inventoried | OPEN | `LICENCE_REGISTER.md` (rows `UNVERIFIED`, reconciled by E3 for the CI-pinned build versions) |

Release implication: SEC-P2-1 and SEC-P2-2 are fixes to make before a tag is pushed; SEC-P2-3 must be opened and
recorded or accepted in writing by the maintainer (AGENTS_V7 section 21.4.4). None is exploitable from the default
local Studio or MCP surface; they concern the release pipeline and the published inventory.

Not examined at the freeze: the web `new Function` JavaScript circuit builder (`web/src/main.ts`, user-authored code
run in the viewer's own browser, by design) and the dynamic `__import__` in `cqhecs/service.py`; `subprocess` calls
without `shell=True` were not individually reviewed.
