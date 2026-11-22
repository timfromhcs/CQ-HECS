# RELEASE_CANDIDATE_AUDIT.md (V7 section 21 skeleton)

Created 2026-11-22 by task D5 on branch `release/v7-stable` (HEAD at creation `51969fd`, PR #55).
Originally a skeleton (D5); filled by E3 (below) with a status per row. The integrator re-checks every row at the final freeze SHA. Per AGENTS_V7.md section 21, any missing, unknown, stale,
not-run, blocked or SHA-mismatched row means NO RELEASE; status is `RELEASE_CANDIDATE_ONLY` at best.

Candidate SHA (provisional): `38e799b3650e74a47d3a72184da50b5a85d5bb8b` (the PR #55 head when E3 filled this table; the tree carries uncommitted Wave E edits, so the final freeze SHA is `UNKNOWN`). Baseline SHA: `25e16e5` (see `BASELINE_V7.md`).

Status values used below: `PASS`, `FAIL`, `NOT_RUN` (blocked rows are `NOT_RUN` with the blocker named). Filled by E3 on 2026-11-22 from the evidence listed in each row; E3 re-ran only what `evidence/waveE_E3.md` lists. A `PASS` that rests on an integrator record or on a Windows-only run says so. A row is `NOT_RUN` when any part of its condition has no result, however green the rest. Hosted CI for `38e799b` is red (B-V7-15): an unqualified release is not possible.

Known context from Waves A-D that the integrator must not mistake for a pass: see `evidence/waveD_D5.md` (mutation 95/95 on a snapshot copy, not in place; Python 3.14 abort 0xC0000409 reproduces at interpreter exit; Lean assurance is specification level only).


## 21.1 Code and correctness

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.1.1 | Exact baseline and final candidate SHAs recorded; no dirty source tree for candidate artifact generation. | NOT_RUN | Baseline `25e16e5` recorded (BASELINE_V7.md). Candidate is provisionally `38e799b3650e74a47d3a72184da50b5a85d5bb8b`; the final freeze SHA is not fixed and the tree has uncommitted Wave E edits, so artifact generation from a clean tree has not happened. Owner/path: research/v7/BASELINE_V7.md; git rev-parse at freeze |
| 21.1.2 | All required Python tests pass; coverage follows current CI policy; no unexplained skip/deselection. | FAIL | Windows 3.13.13: 4269 passed, 134 skipped, 0 failed (freeze_pytest.txt), but `skip_budget.py --check` FAILS (134 vs 105, 7 unbudgeted reasons; B-V7-11). Hosted Linux 3.11 lane: 5 failed; 3.12/3.13/3.14 lanes: 4 failed each; hosted Windows lane unfinished (B-V7-15, TEST_MATRIX V7.E). Owner/path: tests/ full run log (freeze); research/v7/SKIP_BUDGET.json |
| 21.1.3 | C++20 CPU-only build, tests and install pass. | NOT_RUN | CPU-only build and CTest 15/15 locally (integrator-recorded) and the hosted Linux CPU-only job passed at `38e799b`; the install step has no recorded result. Owner/path: native CPU-only build/ctest/install log (freeze) |
| 21.1.4 | Vulkan build/tests pass on each claimed support level; no fake physical-GPU claim from software ICD. | PASS | Scope: physical AMD iGPU on Windows/MSVC CTest 26/26 (integrator-recorded; A2) and hosted Linux lavapipe (software ICD) 26/26 + 3/3, labelled conformance only (waveE_E3.md). No physical-GPU claim is made from the software ICD; other GPUs are not claimed. Owner/path: native Vulkan ctest log + device/ICD record (freeze) |
| 21.1.5 | Paths A–D pass correctness, numerical, resource, negative and independent differential tests. | PASS | Windows freeze run, full suite 0 failed; the hosted failures are in other tests (QG replay, SAT isolation, web fixture, native cpu-only). Differential suites against Qiskit/Stim ran (A5, B1). Owner/path: tests/test_correctness_contracts.py, differential suites; freeze log |
| 21.1.6 | E/F/G are either promoted after their research gates or clearly marked research-only and absent from stable defaults. | PASS | B5: E/F/G `RESEARCH_ONLY`; `git diff 25e16e5 HEAD -- cqhecs/router.py` is empty; no `cqhecs/` module imports the prototypes (grep by E3). Owner/path: router/ExecutionPlan tests; freeze log |
| 21.1.7 | Router capability and refusal semantics pass tests; no silent fallback. | PASS | tests/test_execution_plan.py, test_cross_surface_parity.py, test_circuit_repeated_operands.py are in the 4269 passed (Windows freeze). Owner/path: research/v7/FEATURE_COVERAGE.md; router stability tests |
| 21.1.8 | SAT models verified against original CNF; UNSAT proof formats correctly checked; #SAT/MaxSAT contracts correct. | NOT_RUN | Models re-verified against the original CNF and DRAT checked in-repo (A4, 16 tamper tests); `hcs.sat.count.v1` and typed MaxSAT tested. LRAT, `drat-trim` and `cake_lpr` are NOT_RUN (B-V7-06); python-sat exit abort OPEN (B-V7-01). Owner/path: SAT/proof suites; research/v7/SAT_PROOF_REVIEW.md |
| 21.1.9 | QG BMV/SYK/Z₂ model assumptions and result surfaces are explicit; historical campaigns immutable; local tests reproduce. | FAIL | Windows: replay 353 checks, 0 failed (B2). Hosted Linux: `tests/test_qg_replay.py::test_every_processed_number_is_reproduced_from_raw_counts` fails on the manifest hash of `bmv_drift/.../counts.csv` (B-V7-15), so the immutability/replay condition does not hold on every platform. Model assumptions are explicit (qg_doc_consistency OK). Owner/path: QUANTUM_GRAVITY_LAB tests; QGRAVITY.md; campaign immutability check |
| 21.1.10 | Noise model fit/eval separation and device profile provenance complete. | PASS | B4: 15 governance tests (FIT/EVAL separation, channel checks, provenance labels) in the suite; scope is governance, not a held-out evaluation (H-NOISE-01 NOT_RUN). Owner/path: calibration v3 tests; research/v7/NOISE_QEC_RESEARCH.md |
| 21.1.11 | Formal workspace builds cleanly; all promoted theorem specs and axiom/proof audits pass; implementation-verification level is honestly reported. | PASS | `lake build` 8711 jobs exit 0 after `38e799b` (lean_freeze_build.txt); `PrintAxioms` within three standard axioms (D5 at `c098971`; `formal/` unchanged since). Specification-level `FORMALIZED_LEMMA` only; Comparator/nanoda NOT_RUN. Owner/path: formal/ lake build + PrintAxioms; research/v7/evidence/LEAN_BUILD.md; evidence/waveD_D5.md |

## 21.2 Web completion — no deferral

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.2.1 | All applicable `PLAN.md` and V7 features represented in the Web feature coverage matrix. | PASS | FEATURE_COVERAGE web column closed (13 web cells); `tests/test_feature_coverage.py` + `test_web_shared_conformance.py` 199 passed (E3 re-run). Owner/path: research/v7/FEATURE_COVERAGE.md (web column) |
| 21.2.2 | Circuit, router, result, SAT, #SAT/MaxSAT, noise, research/evidence, QG, export/import and guide flows are functional where applicable. | PASS | Playwright 128 passed, 1 skipped (integrator-recorded); hosted job 'Web emulator (WASM core, tests, build, E2E)' success at `38e799b`. Owner/path: web e2e logs (freeze) |
| 21.2.3 | WebGPU/WASM precision and fallback are explicit and tested. | NOT_RUN | WASM fallback and precision declared and tested; WebGPU f32 on a real adapter ran only partially (E5 `RUN_PARTIAL`: one AMD RDNA2 adapter, 20 cases, worst TV 7.8e-8, one case timed out; B-V7-03), so the condition is not fully shown. Owner/path: web precision/fallback tests (freeze) |
| 21.2.4 | API/backend integration uses real data; no hardcoded fake success. | NOT_RUN | No no-hardcoded-success audit of `web/` is recorded for the candidate. Owner/path: web/ integration tests; no-hardcoded-success audit (freeze) |
| 21.2.5 | All route, worker-failure, cancellation, timeout, unsupported and empty states tested. | PASS | `web/e2e/states.spec.ts` inside the 128 passed (C1); hosted E2E success. Owner/path: web/e2e state specs (freeze) |
| 21.2.6 | E2E, accessibility, browser matrix, mobile layouts and visual regression gates pass. | NOT_RUN | Chromium + two Chromium phone emulations pass (axe, visual baselines for win32 only); Firefox and WebKit NOT_RUN (B-V7-04). Owner/path: web e2e/axe/visual/browser-matrix logs (freeze) |
| 21.2.7 | Bundle limits and memory/resource limits are enforced and documented. | PASS | Hosted 'Type check and production build' step success at `38e799b`; bundle budget and token contrast are part of `npm run build` (package.json). Step command not read; E3's local `npm run build` was inconclusive. Owner/path: web bundle-size gate log (freeze) |
| 21.2.8 | Vercel Preview URL is reachable and deployment SHA equals candidate SHA. | NOT_RUN | A Vercel preview status is SUCCESS for `38e799b`; the deployed bundle's version and SHA were not compared (B-V7-14). Owner/path: Vercel Preview check (needs remote CI; PR #55) |
| 21.2.9 | Production deploy is authorized and post-deploy SHA/domain/assets/smokes are verified. | NOT_RUN | No production authorization or deploy; none attempted. Owner/path: production deploy authorization record (maintainer) |

## 21.3 Windows EXE completion — no deferral

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.3.1 | `scripts/build_exe.ps1` or its reviewed replacement builds from candidate SHA. | PASS | Integrator built the onedir folder from `38e799b` (hash in PACKAGING_AUDIT); hosted 'Windows onedir folder' job success. Owner/path: scripts/build_exe.ps1 log; research/v7/PACKAGING_AUDIT.md |
| 21.3.2 | ZIP extracts on a clean supported Windows machine/VM and runs outside source tree. | NOT_RUN | No clean Windows VM (B-V7-05). Owner/path: clean-VM extraction log (NOT_RUN locally) |
| 21.3.3 | CLI, circuits, provenance, SAT/proof, QG local workflows, Studio, API and MCP pass all applicable tests. | NOT_RUN | `smoke-exe-indep.json`: 14 PASS, 1 SKIPPED (version, doctor, Bell, SAT, DRAT, QG, Studio, MCP). The opt-in `tests/test_exe_smoke.py` skipped in the freeze run (`CQ_HECS_EXE not set`, 6). Owner/path: EXE smoke test log (freeze) |
| 21.3.4 | Included assets/modules/DLLs are complete; no implicit local Python or repository dependency. | NOT_RUN | Content inspection of the folder PASS (263 members); absence of an implicit local Python/repo dependency is only provable on a clean machine. Owner/path: EXE content inventory (freeze) |
| 21.3.5 | Missing Vulkan/device/provider is a typed, honest state—not crash or silent fake behavior. | NOT_RUN | Native CLI typed refusal tested (D3, 7 passed at `f912160`; skipped in the freeze run for lack of the build dir); the frozen app's `vulkan_loader: not_available` path is NOT_RUN end to end (PK7-07); `qasm`/`stress`/`test` still emulate (B-V7-08). Owner/path: typed refusal tests (tests/test_native_vulkan_refusal.py etc.) |
| 21.3.6 | Windows-specific paths, child process shutdown, port conflict, permissions and non-admin usage pass. | PASS | Smoke reports (non-admin, temp dir): forceful and graceful stop leave no process and free the port; `studio_port_conflict` PASS (P-01 fixed). Owner/path: Windows-specific tests (freeze) |
| 21.3.7 | EXE package contents, version, source SHA, SBOM and checksum match manifest. | FAIL | SHA256SUMS agrees with the five artifacts; the wheel SBOM is the build venv, lists `autocommand` as LGPLv3 and mismatched versions (PK7-01); licences UNVERIFIED (PK7-02). Owner/path: EXE manifest/SBOM/checksum (freeze) |
| 21.3.8 | Published ZIP downloaded and independently hash-verified. | NOT_RUN | Nothing is published. Owner/path: published ZIP hash verification (post-publish) |

## 21.4 Other product surfaces and release artefacts

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.4.1 | Python wheel and sdist built from same candidate SHA and clean-venv tested. | FAIL | Local clean-venv smoke 15 PASS at the integrator's build; hosted 'Wheel and sdist' job FAILS at `38e799b` (`studio_health_and_stop`, Address already in use). Owner/path: wheel/sdist build + clean-venv log (freeze) |
| 21.4.2 | Studio/API/MCP parity and local-security contract pass. | PASS | test_cross_surface_parity, test_studio_security, MCP suites in the Windows freeze run; 181 security/fuzz tests re-run by E3. Owner/path: Studio/API/MCP parity tests |
| 21.4.3 | README EN/DE/FR, docs, version, changelog, release notes, migration, citation and API docs consistent. | FAIL | `RELEASE_NOTES.md` still describes 4.0.0 and is the release body (B-V7-12); web 'Exact' headline, README freeze-SHA wording and docs findings are open (CLAIM_AUDIT E3 section). Version surfaces agree (check_version.py, 81 doc tests PASS). Owner/path: README EN/DE/FR + docs consistency checks (freeze) |
| 21.4.4 | SBOM/license inventory/dependency audit and secret scan pass. | FAIL | Secret scan PASS (343 commits); npm audit 0 vulnerabilities (C5); wheel SBOM wrong and licences UNVERIFIED (SEC-P2-2, SEC-P2-3); gitleaks, trufflehog, cargo audit, manifest pip-audit NOT_RUN. Owner/path: SBOM, research/v7/LICENCE_REGISTER.md, research/v7/SECURITY_AUDIT.md |
| 21.4.5 | Release workflow and GitHub Actions permissions/pins audited. | FAIL | 41 action uses all pinned, 0 unpinned (security_audit.py); but at `38e799b` `release.yml` has no check that a tag is on main (SEC-P2-1, B-V7-13) and has never run (B-V7-09). Owner/path: SECURITY_AUDIT.md section Actions; scripts/security_audit.py |
| 21.4.6 | Exact Web/EXE/package artifacts built from the same frozen source commit. | NOT_RUN | All five artifacts were built from `38e799b` by the integrator; they must be rebuilt from the final freeze SHA, and the Web build artifact is not part of that set. Owner/path: artifact manifests (freeze) |
| 21.4.7 | All claims link to same-SHA or explicitly historical evidence. | NOT_RUN | CLAIM_AUDIT.md maps claims to evidence, with open items; integrator-recorded numbers are not committed same-SHA logs; final SHA not fixed. Owner/path: research/v7/CLAIM_AUDIT.md; EVIDENCE_LEDGER.md |

## 21.5 Release authorization and tag

| # | Condition | Status | Evidence path / owner |
|---|---|---|---|
| 21.5.1 | Independent verifier signs off the release audit. | NOT_RUN | No independent verifier has signed. Owner/path: independent verifier record (NOT_RUN) |
| 21.5.2 | All P0/P1 blockers closed; residual risks and deferred research are explicitly listed. | FAIL | Open P1 items: B-V7-09, B-V7-12, B-V7-14, B-V7-15; open P2: B-V7-01, 05, 11, 13. Owner/path: research/v7/BLOCKERS.md |
| 21.5.3 | Maintainer has explicitly authorized merge/tag/publish/deploy. | NOT_RUN | No maintainer authorization recorded. Owner/path: maintainer authorization (NOT_RUN) |
| 21.5.4 | Exact tag and GitHub release point to the exact tested SHA. | NOT_RUN | No tag or release exists. Owner/path: tag/release check (NOT_RUN) |
| 21.5.5 | Vercel production deployment points to the exact audited SHA. | NOT_RUN | No production deployment for this SHA. Owner/path: Vercel production check (NOT_RUN) |
| 21.5.6 | Release downloads, hash manifests, SBOM and clean install verified. | NOT_RUN | Nothing is published. Owner/path: post-release download verification (NOT_RUN) |
| 21.5.7 | Final report includes commands, logs, counts, skipped tests, known limits, non-claims and rollback instructions. | NOT_RUN | `FINAL_REPORT.md` exists as a DRAFT only; it cannot be final before the freeze and the checks above. Owner/path: research/v7/FINAL_REPORT.md (NOT_RUN) |

Verifier sign-off: `NOT_RUN`. Release status: `RELEASE_CANDIDATE_ONLY` (not `STABLE`).

Tally of the 42 rows (E3, provisional SHA `38e799b`): PASS 13, FAIL 8, NOT_RUN 21, BLOCKED 0. Any FAIL or NOT_RUN row means no release.
