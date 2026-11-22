# FINAL_REPORT.md: CQ-HECS 7.0.0 (DRAFT, not final)

**STATUS: DRAFT until release.** Written by E3 on 2026-11-22 at the provisional candidate `38e799b`. AGENTS_V7 section 23
says this report is written only after all waves reach a terminal state; they have not (Wave E is open, the hosted CI is
red, nothing is tagged or published). Every field marked `FILL AT FREEZE` is empty on purpose. This draft must not be
quoted as a release statement. Release status today: `RELEASE_CANDIDATE_ONLY`, not `STABLE`.

Structure: AGENTS_V7 section 23, items 1 to 16. `QGRAVITY.md` does not exist in this checkout (the root path is absent, as
AGENTS_V7 section 24 anticipates), so its section 13.1 could not be followed; the QG material is under item 10 and in
`docs/QUANTUM_GRAVITY_LAB.md`.

## 1. SHAs, branch, tag, version

| Field | Value |
|---|---|
| Starting SHA | `25e16e5` (merge of PR #54 into `main`; package version 5.0.0, tag `v5.0.0`) |
| Branch | `release/v7-stable` (an earlier working branch was `agent/v6-rc`) |
| Pull request | #55 https://github.com/timfromhcs/CQ-HECS/pull/55 (OPEN, mergeable at 08:38 UTC) |
| Provisional candidate SHA | `38e799b3650e74a47d3a72184da50b5a85d5bb8b` (version bump to 7.0.0, decision D-009) |
| Final freeze SHA | `FILL AT FREEZE` |
| Ending SHA after merge | `FILL AT FREEZE` |
| Tag | none exists; `v5.0.0` is the newest tag (there is no 6.x release; 6 was an internal planning label) |
| Version | 7.0.0 on every surface (`scripts/check_version.py`, E3 re-run) |
| Commits since the start | 343 reachable from `HEAD` in total; the V7 series runs from `711fa5e` to `38e799b` |

## 2. Wave and task completion matrix

Vocabulary: PASS, FAIL_FIXED, BLOCKED, NOT_RUN, DEFERRED, REJECTED. Detail per task: `TASKS.md`, `PLAN_COVERAGE.md`.

| Wave | Task | Result | Evidence |
|---|---|---|---|
| A | MCP threading, cancel, negotiation; service layer; OpenAPI | PASS (compute is abandoned, not stopped; MCP revisions after 2025-06-18 NOT_RUN) | `waveA_A1.md` |
| A | Native VkResult checks, fault injection, C ABI hardening, sanitizer lane | PASS locally (MSVC ASan); hosted GCC-12 ASan+UBSan 9/9 PASS; Clang NOT_RUN | `waveA_A2.md`, `waveE_E3.md` |
| A | WebGPU-loss fallback, keyboard and touch composer, mobile e2e | PASS (Chromium; real GPU loss NOT_RUN) | `waveA_A3.md` |
| A | python-sat isolation, separator preflight, DRAT tamper matrix, typed MaxSAT | PASS (python-sat abort OPEN, external) | `waveA_A4.md` |
| A | Lean Path A and Pauli lemmas; spec-correspondence tests | PASS at specification level | `waveA_A5.md` |
| B | Path B/C error-story metadata | PASS | `waveB_B1.md` |
| B | QG models, SYK oracle, Z2 leakage, replay | PASS for finite models; hosted Linux replay test FAILS (B-V7-15) | `waveB_B2.md` |
| B | QG Lab in Web and Studio | PASS | `waveB_B3.md` |
| B | Calibration schema v3, FIT/EVAL enforcement | PASS (governance only; held-out evaluation NOT_RUN) | `waveB_B4.md` |
| B | Paths E, F, G prototypes | DEFERRED / not promoted: `RESEARCH_ONLY` (E `INCONCLUSIVE`, F and G `NOT_SUPPORTED`) | `waveB_B5.md` |
| C | Web conformance corpus, states, import/export, visual specs | PASS (Chromium) | `waveC_C1.md` |
| C | Packaging, SBOM, manifest | PASS locally; hosted package workflow FAILS in two jobs (B-V7-15); wheel SBOM wrong (PK7-01) | `waveC_C2.md`, `PACKAGING_AUDIT.md` |
| C | QG plan on four surfaces, calibration policy | PASS | `waveC_C3.md` |
| C | Documentation | PASS for pinned statements; open items in `CLAIM_AUDIT.md` | `waveC_C4.md` |
| C | Fuzz, property, resource, mutation, security audit | PASS | `waveC_C5.md` |
| D | C1-FIND-01 repeated operands; SEC-M2 `eval` | FAIL_FIXED | `waveD_D1.md` |
| D | SEC-M1, SEC-L1..L5, P-01 | FAIL_FIXED | `waveD_D2.md` |
| D | P-03 Vulkan refusal, P-06 `/Brepro`, P-07 release assets, P-08 | FAIL_FIXED (workflows not proven) | `waveD_D3.md` |
| D | Studio ExecutionPlan panel | PASS | `waveD_D4.md` |
| D | Lean L-RESULT-01, mutation pin, Python 3.14 lane report | PASS | `waveD_D5.md` |
| E | E2 documentation freeze numbers | PASS (integrator figures recorded) | `waveE_E2.md` |
| E | E3 research record | PASS (this draft and the other records) | `waveE_E3.md` |
| E | E1, E4, E5 | NOT_RUN by E3; state `FILL AT FREEZE` | no evidence files when written |
| Not promoted | Path C graph-aware ordering, CNF-to-XOR with witness, optional CDCL, learned router, held-out noise evaluation, MaxSAT MCP tool, Studio i18n | DEFERRED | `TASKS.md`, `HYPOTHESES.md` |

## 3. Architecture changes and API/schema migrations

Single authoritative architecture file: root `ARCHITECTURE.md` (the `docs/ARCHITECTURE.md` file carries a historical
banner). New shared service layer (`cqhecs/service.py`) behind CLI, MCP, Studio and Python; `cq-hecs plan`; OpenAPI 3.1
(`schemas/studio.openapi.json`, `/api/v1`); MCP negotiation with `outputSchema` and `structuredContent` at 2025-06-18;
`hcs.sat.count.v1`; typed MaxSAT; calibration schema v3; QG plan envelope. Behaviour changes that a caller can see:
repeated gate operands refused, non-grammar QASM angle text refused in `python_bridge`, DIMACS header cap of 1,000,000
variables, strict ASCII DIMACS integers, exact decimal counts above 4300 digits, occupied Studio port exits 4, native
`cq_hecs.exe` refuses with exit 3 without a Vulkan ICD, C ABI rejects wide T/RZ circuits. Migration notes:
`MIGRATION_V7.md`. Release notes: `RELEASE_NOTES_DRAFT.md` (the shipped `RELEASE_NOTES.md` is still 4.0.0; B-V7-12).

## 4. Formal theorems, axioms, checker outputs, exact scope

Lean 4.33.1, Mathlib `0df444a`, workspace `formal/`. `lake build` exit 0, 8711 jobs after `38e799b`
(`evidence/lean_freeze_build.txt`). Statements: `L-BOUND-01` and `L-BOUND-01b` (Path D truncation bound), `L-PAULI-01`
(`pauli_mul`, `pauli_comm`, single-qubit conjugation rules for H, S, X, Y, Z), `L-STAB-01` (`omega_*` for H, S, CX, CZ,
SWAP; `omega_run`; `tableau_invariant`), `L-RESULT-01` (seven lemmas on the state/flag table of `SimulationResult`).
`PrintAxioms` for the 26 audited lemmas: only `propext`, `Classical.choice`, `Quot.sound`. No `sorry`. Label:
`FORMALIZED_LEMMA` for these statements. Not shown: Comparator and nanoda re-checks for the V7 lemmas (NOT_RUN),
CX/CZ/SWAP sign column, `measure`, non-Clifford Path D conjugation, n-qubit lifting of `pauli_comm`.

## 5. Refinement proofs versus test correspondence

There is **no** implementation refinement proof. Every link from a Lean statement to code is a test: 132
spec-correspondence tests (`test_stabilizer_spec_correspondence.py`, `test_path_d_spec_correspondence.py`) and
`test_formal_result_contract.py` (3). No component is `FORMALLY_VERIFIED_COMPONENT`.

## 6. Tests and counts

Windows, CPython 3.13.13, at `38e799b` (integrator-recorded, `freeze_pytest.txt` read by E3): Python 4269 passed, 134
skipped, 1 deselected, 0 failed (711.68 s); skip-budget gate FAILS (B-V7-11). Mutation 95/95 killed in place. Web unit
167/167 (E3 re-ran). Playwright 128 passed, 1 skipped (WebGPU, no adapter; a separate partial real-adapter run by E5 measured 20 cases, worst TV 7.8e-8). Native CTest 26/26 (Vulkan, AMD iGPU) and
15/15 (CPU-only). Studio plan UI 6 pytest plus a real-browser axe run. E3 re-runs: 81 doc/language tests, 181
security/fuzz tests, 199 conformance/coverage tests, `flake8 --select=E9,F` 0, version, truncation and QG-doc gates.
**Hosted CI for `38e799b` is red** (TEST_MATRIX V7.E): Linux 3.11 lane 5 failed, compatibility lanes 4 failed each,
wheel smoke and MSVC native package jobs failed, Windows full-suite job unfinished after two hours; ASan+UBSan (gcc-12,
9/9), CPU-only, lavapipe CTest 26/26, web emulator and Windows onedir jobs passed. `FILL AT FREEZE`: the counts on the
final SHA, all lanes.

## 7. Environments

Windows 11 Pro 10.0.26200; CPython 3.13.13 (and 3.14.6 for the Python 3.14 lane report); Node 22.23.1; rustc/cargo 1.96.0;
CMake 4.4.0; MSVC 19.44 (Visual Studio 2022); Vulkan SDK 1.4.357; AMD Radeon integrated GPU; Lean 4.33.1; Qiskit 2.6.1
locally (2.5.1 in the constrained CI lane); Stim 1.16.0. Hosted: ubuntu runner images (gcc-12, LLVM 21.1.8 llvmpipe) and
a Windows runner. Browser: Playwright Chromium and two Chromium phone emulations. Not run: Firefox, WebKit, macOS. Wave E1 and E4 evidence files (`waveE_E1.md`, `waveE_E4.md`) appeared after E3 began; E1 diagnoses the same six CI failures (root causes: CRLF digests, POSIX 8-bit exit status, version-string fixture, glob matching the nanobind extension, runner now ships a newer Visual Studio, TIME_WAIT), E4 hardens `release.yml`. Neither fix is pushed, so remote CI is still red; E3 did not verify them.

## 8. Benchmarks

Raw data: `evidence/PATHB_DOMINANCE.json` (Path B slower than dense statevector on every measured case, 2x to 181x),
`evidence/sat_separator_bench.json`, `evidence/waveA_A4_separator_calibration.json` (31 rows, observed table at most
`2**(w+1)`), `tests/research_prototypes` outputs (B5). All are finite measurements on one Windows machine with fixed
seeds. No asymptotic or cross-solver speedup is claimed. No benchmark was run by E3.

## 9. SAT proof evidence

Models re-verified against the original CNF; UNSAT by the in-repo DRAT checker (`DRAT_CHECKED`), tamper matrix on the
pigeonhole 6/5 vector (16 tests; single-deletion rejection 125/235, some lemmas are redundant); timeouts give `UNKNOWN`
or `certified=False`. Independent checkers `drat-trim`, `lrat-check`, `cake_lpr`: NOT_RUN (B-V7-06); the in-repo checker has
no LRAT reader. External CaDiCaL runs in an isolated child; the python-sat exit abort `0xC0000409` is an open external
defect (B-V7-01).

## 10. QG, noise and QPU results

No QPU job, provider call, credit or spend by any V7 task. The QG workbench studies finite models (BMV effective
interaction, small-N SYK, Z2 leakage) and replays the historical campaign offline (353 checks, 0 failed on Windows). The
historical external suite `r-io-7` (25 jobs on one Rigetti device through Open Quantum, 1 credit each) is evaluation data
from before V7. The Stage-4 SYK v1 run is INVALID (F-09) and the stage is INCONCLUSIVE. T6-09 and T6-10 are BLOCKED on
authorisation (B-V7-07). Noise: governance only; no held-out validation (H-NOISE-01 NOT_RUN). Spend reconciliation for V7: 0.

## 11. Security, SBOM, licences, dependencies

`SECURITY_AUDIT.md`: no HIGH finding; SEC-M1, SEC-M2, SEC-L1..L5 and P-01 FIXED; SEC-I1 (no CSP) accepted INFO; three P2
findings open at the commit (tag-from-non-main in `release.yml`, wheel SBOM lists build tooling including an
LGPL-declared vendored package, unverified licences). Secret scan 0 in tree and in 343 commits; 41 pinned action uses.
`npm audit` 0; `cargo audit`, `gitleaks`, `trufflehog`, manifest `pip-audit` NOT_RUN. `LICENCE_REGISTER.md` reconciled with
the candidate EXE SBOM (13 components); wheel SBOM to be regenerated.

## 12. Web Preview and Production

Production: `https://cq-hecs-web.vercel.app`, anonymous `HTTP 200` recorded by E2 (2026-11-22); the build that serves it is
not the candidate (no merge has happened). Preview: a Vercel status for `38e799b` reports SUCCESS; the preview URL, its
embedded version and SHA, and the anonymous E2E against it are `FILL AT FREEZE` (B-V7-14). Post-deployment checks:
`NOT_RUN`.

## 13. Windows release ZIP

Names and SHA-256 of the artifacts built from `38e799b` (re-hashed by E3; to be rebuilt at the final SHA, so these will
change; details in `PACKAGING_AUDIT.md`):

| Artifact | SHA-256 |
|---|---|
| `cqhecs-7.0.0-windows-x64.zip` | `b088ec5239ec42e6814d957c16db50ffc806da106d96f88604f776585205f490` |
| `cqhecs-7.0.0-py3-none-any.whl` | `a65d66ce9983307904463e2eb051040706c7ba0231c18ea4d106d6d707ab4f78` |
| `cqhecs-7.0.0.tar.gz` | `0a6220b56d8c35c7d75a5be951516ca9b8ccbb92e911af18c85c3beda7a3e656` |
| `cq-hecs-cpu-7.0.0-windows-x64.zip` | `7a98816b7375332045499cb56243ef92793a2a207005519de8a86632e0272d70` |
| `cq-hecs-vulkan-7.0.0-windows-x64.zip` | `76b3b085a892ebe1645bd545b1c871fd78c7edf786d8c3cd3eb02a5b3c0c34d8` |

Clean-machine test: NOT_RUN (B-V7-05). Published-ZIP download verification: NOT_RUN (nothing is published). The
Windows application is a PyInstaller onedir folder shipped as a zip, not a single-file executable or installer.

## 14. Known defects, non-claims, limits, deferred work, external blockers

Open defects and blockers: `BLOCKERS.md` (B-V7-01 to B-V7-15). The P1 ones: release and package workflows unproven
(B-V7-09), `RELEASE_NOTES.md` is the 4.0.0 text and is the release body (B-V7-12), preview and production unverified
(B-V7-14), hosted CI red (B-V7-15). P2: skip budget (B-V7-11), tag-from-non-main (B-V7-13), clean-machine install
(B-V7-05), python-sat abort (B-V7-01).

Non-claims. No P versus NP, ETH or SETH result. No speedup over CaDiCaL, sharpSAT, d4, Aer, Stim or any Pauli-propagation
tool. No end-to-end GPU acceleration (WebGPU f32 ran on one real adapter only partially: E5 `RUN_PARTIAL`, 20 cases, worst TV 7.8e-8). `exact=True`, `error_bound=0` and float64 do
not mean symbolic exactness. The Path D bound certifies requested observables only, not samples or distributions. No
formal verification of any component. The QG workbench studies models, not nature. Paths E, F, G, the Path C ordering,
CNF-to-XOR extraction and CDCL are not shipped features. No QPU job was submitted by the package. No claim that all CI
is green.

Limits: Windows and one AMD iGPU for native Vulkan (and one RDNA2 adapter for the partial WebGPU run); Chromium only for browsers; Python 3.13.13 for the full local suite;
DE and FR READMEs are condensed summaries; Studio plan panel is English only.

## 15. Reproduction commands, artifact paths, checksums

Commands: `python scripts/check_version.py`; `python scripts/verify_no_silent_truncation.py`;
`python scripts/qg_doc_consistency.py`; `python -m pytest tests/ -q -rs --junitxml=...`;
`python scripts/skip_budget.py --junitxml ... --check`; `python scripts/run_mutation_tests.py` (in place);
`python scripts/security_audit.py --history`; `cd web && npm ci && npm test && npm run build && npx playwright test`;
`cmake -S . -B build -DCQ_BUILD_TESTS=ON && ctest -C Release` (and with `-DCQ_ENABLE_VULKAN=OFF`);
`cd formal && lake build && lake env lean scripts/PrintAxioms.lean`; packaging through `scripts/build_exe.ps1`,
`scripts/package_native.ps1`, `scripts/package_archive.py`, `scripts/sbom_cyclonedx.py`, `scripts/make_manifest.py`.
Checksums: section 13 and `PACKAGING_AUDIT.md`; the final `SHA256SUMS` is `FILL AT FREEZE`. Logs in the session
scratchpad (`freeze_pytest.txt`, `mutation_freeze.txt`, job logs) are not in the repository; copy what the final report
cites into `research/v7/evidence/` at freeze.

Rollback instructions: **placeholder, owned by E4.** See `docs/RELEASE_PROCESS.md` (sections on withdrawing a release and
Vercel rollback). Nothing was deployed, tagged or published by the V7 tasks, so there is nothing to roll back today.

## 16. Release decision and authorization record

Decision: **no release.** `RELEASE_CANDIDATE_AUDIT.md` has 13 PASS, 8 FAIL, 21 NOT_RUN of 42 rows at the provisional SHA;
any FAIL or NOT_RUN row means no release (AGENTS_V7 section 21). Independent verifier sign-off: NOT_RUN. Maintainer
authorization to merge, tag, publish or deploy: none recorded. This section is `FILL AT FREEZE` for the final decision.

## Negative and inconclusive results kept in this report

Path B is slower than a dense statevector on every measured case. Path E is `INCONCLUSIVE`; Paths F and G fail their
gates. The SYK v1 hardware run is invalid. The H-NOISE-01 held-out evaluation was not run. The skip budget fails. Hosted
CI is red on the candidate. The wheel SBOM was wrong. A fixture that embeds a Qiskit version string made a test
environment-dependent.
