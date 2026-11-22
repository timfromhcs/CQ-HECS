# RELEASE_CANDIDATE_AUDIT.md (V7 section 21 skeleton)

Created 2026-11-22 by task D5 on branch `release/v7-stable` (HEAD at creation `51969fd`, PR #55).
This is a SKELETON. No checkbox is ticked. Every row is `UNKNOWN` or `NOT_RUN` until the integrator
fills it at freeze with same-SHA evidence. Per AGENTS_V7.md section 21, any missing, unknown, stale,
not-run, blocked or SHA-mismatched row means NO RELEASE; status is `RELEASE_CANDIDATE_ONLY` at best.

Candidate SHA: `UNKNOWN` (fill at freeze). Baseline SHA: `UNKNOWN` (see `BASELINE_V7.md`).

Status values: `UNKNOWN` (nothing recorded), `NOT_RUN` (cannot or has not been run), later `PASS` / `FAIL` / `BLOCKED` with a same-SHA evidence path.

Known context from Waves A-D that the integrator must not mistake for a pass: see `evidence/waveD_D5.md` (mutation 95/95 on a snapshot copy, not in place; Python 3.14 abort 0xC0000409 reproduces at interpreter exit; Lean assurance is specification level only).


## 21.1 Code and correctness

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.1.1 | Exact baseline and final candidate SHAs recorded; no dirty source tree for candidate artifact generation. | UNKNOWN | research/v7/BASELINE_V7.md; git rev-parse at freeze |
| 21.1.2 | All required Python tests pass; coverage follows current CI policy; no unexplained skip/deselection. | UNKNOWN | tests/ full run log (freeze); research/v7/SKIP_BUDGET.json |
| 21.1.3 | C++20 CPU-only build, tests and install pass. | UNKNOWN | native CPU-only build/ctest/install log (freeze) |
| 21.1.4 | Vulkan build/tests pass on each claimed support level; no fake physical-GPU claim from software ICD. | UNKNOWN | native Vulkan ctest log + device/ICD record (freeze) |
| 21.1.5 | Paths A–D pass correctness, numerical, resource, negative and independent differential tests. | UNKNOWN | tests/test_correctness_contracts.py, differential suites; freeze log |
| 21.1.6 | E/F/G are either promoted after their research gates or clearly marked research-only and absent from stable defaults. | UNKNOWN | router/ExecutionPlan tests; freeze log |
| 21.1.7 | Router capability and refusal semantics pass tests; no silent fallback. | UNKNOWN | research/v7/FEATURE_COVERAGE.md; router stability tests |
| 21.1.8 | SAT models verified against original CNF; UNSAT proof formats correctly checked; #SAT/MaxSAT contracts correct. | UNKNOWN | SAT/proof suites; research/v7/SAT_PROOF_REVIEW.md |
| 21.1.9 | QG BMV/SYK/Z₂ model assumptions and result surfaces are explicit; historical campaigns immutable; local tests reproduce. | UNKNOWN | QUANTUM_GRAVITY_LAB tests; QGRAVITY.md; campaign immutability check |
| 21.1.10 | Noise model fit/eval separation and device profile provenance complete. | UNKNOWN | calibration v3 tests; research/v7/NOISE_QEC_RESEARCH.md |
| 21.1.11 | Formal workspace builds cleanly; all promoted theorem specs and axiom/proof audits pass; implementation-verification level is honestly reported. | UNKNOWN | formal/ lake build + PrintAxioms; research/v7/evidence/LEAN_BUILD.md; evidence/waveD_D5.md |

## 21.2 Web completion — no deferral

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.2.1 | All applicable `PLAN.md` and V7 features represented in the Web feature coverage matrix. | UNKNOWN | research/v7/FEATURE_COVERAGE.md (web column) |
| 21.2.2 | Circuit, router, result, SAT, #SAT/MaxSAT, noise, research/evidence, QG, export/import and guide flows are functional where applicable. | UNKNOWN | web e2e logs (freeze) |
| 21.2.3 | WebGPU/WASM precision and fallback are explicit and tested. | UNKNOWN | web precision/fallback tests (freeze) |
| 21.2.4 | API/backend integration uses real data; no hardcoded fake success. | UNKNOWN | web/ integration tests; no-hardcoded-success audit (freeze) |
| 21.2.5 | All route, worker-failure, cancellation, timeout, unsupported and empty states tested. | UNKNOWN | web/e2e state specs (freeze) |
| 21.2.6 | E2E, accessibility, browser matrix, mobile layouts and visual regression gates pass. | UNKNOWN | web e2e/axe/visual/browser-matrix logs (freeze) |
| 21.2.7 | Bundle limits and memory/resource limits are enforced and documented. | UNKNOWN | web bundle-size gate log (freeze) |
| 21.2.8 | Vercel Preview URL is reachable and deployment SHA equals candidate SHA. | UNKNOWN | Vercel Preview check (needs remote CI; PR #55) |
| 21.2.9 | Production deploy is authorized and post-deploy SHA/domain/assets/smokes are verified. | UNKNOWN | production deploy authorization record (maintainer) |

## 21.3 Windows EXE completion — no deferral

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.3.1 | `scripts/build_exe.ps1` or its reviewed replacement builds from candidate SHA. | UNKNOWN | scripts/build_exe.ps1 log; research/v7/PACKAGING_AUDIT.md |
| 21.3.2 | ZIP extracts on a clean supported Windows machine/VM and runs outside source tree. | UNKNOWN | clean-VM extraction log (NOT_RUN locally) |
| 21.3.3 | CLI, circuits, provenance, SAT/proof, QG local workflows, Studio, API and MCP pass all applicable tests. | UNKNOWN | EXE smoke test log (freeze) |
| 21.3.4 | Included assets/modules/DLLs are complete; no implicit local Python or repository dependency. | UNKNOWN | EXE content inventory (freeze) |
| 21.3.5 | Missing Vulkan/device/provider is a typed, honest state—not crash or silent fake behavior. | UNKNOWN | typed refusal tests (tests/test_native_vulkan_refusal.py etc.) |
| 21.3.6 | Windows-specific paths, child process shutdown, port conflict, permissions and non-admin usage pass. | UNKNOWN | Windows-specific tests (freeze) |
| 21.3.7 | EXE package contents, version, source SHA, SBOM and checksum match manifest. | UNKNOWN | EXE manifest/SBOM/checksum (freeze) |
| 21.3.8 | Published ZIP downloaded and independently hash-verified. | UNKNOWN | published ZIP hash verification (post-publish) |

## 21.4 Other product surfaces and release artefacts

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.4.1 | Python wheel and sdist built from same candidate SHA and clean-venv tested. | UNKNOWN | wheel/sdist build + clean-venv log (freeze) |
| 21.4.2 | Studio/API/MCP parity and local-security contract pass. | UNKNOWN | Studio/API/MCP parity tests |
| 21.4.3 | README EN/DE/FR, docs, version, changelog, release notes, migration, citation and API docs consistent. | UNKNOWN | README EN/DE/FR + docs consistency checks (freeze) |
| 21.4.4 | SBOM/license inventory/dependency audit and secret scan pass. | UNKNOWN | SBOM, research/v7/LICENCE_REGISTER.md, research/v7/SECURITY_AUDIT.md |
| 21.4.5 | Release workflow and GitHub Actions permissions/pins audited. | UNKNOWN | SECURITY_AUDIT.md section Actions; scripts/security_audit.py |
| 21.4.6 | Exact Web/EXE/package artifacts built from the same frozen source commit. | UNKNOWN | artifact manifests (freeze) |
| 21.4.7 | All claims link to same-SHA or explicitly historical evidence. | UNKNOWN | research/v7/CLAIM_AUDIT.md; EVIDENCE_LEDGER.md |

## 21.5 Release authorization and tag

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.5.1 | Independent verifier signs off the release audit. | UNKNOWN | independent verifier record (NOT_RUN) |
| 21.5.2 | All P0/P1 blockers closed; residual risks and deferred research are explicitly listed. | UNKNOWN | research/v7/BLOCKERS.md |
| 21.5.3 | Maintainer has explicitly authorized merge/tag/publish/deploy. | UNKNOWN | maintainer authorization (NOT_RUN) |
| 21.5.4 | Exact tag and GitHub release point to the exact tested SHA. | UNKNOWN | tag/release check (NOT_RUN) |
| 21.5.5 | Vercel production deployment points to the exact audited SHA. | UNKNOWN | Vercel production check (NOT_RUN) |
| 21.5.6 | Release downloads, hash manifests, SBOM and clean install verified. | UNKNOWN | post-release download verification (NOT_RUN) |
| 21.5.7 | Final report includes commands, logs, counts, skipped tests, known limits, non-claims and rollback instructions. | UNKNOWN | research/v7/FINAL_REPORT.md (NOT_RUN) |

Verifier sign-off: `NOT_RUN`. Release status: `RELEASE_CANDIDATE_ONLY` (not `STABLE`).
