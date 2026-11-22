# CLAIM_AUDIT.md — public-claim audit (V7 W1)

First cut, 2026-11-21, branch `agent/v6-rc` (base `25e16e5`, README status `v5.0.0`). Method:
read each public claim and mark it against code/tests on this checkout. Statuses:
`VERIFIED` (code/tests agree), `PARTIAL` (true but under-stated / missing a caveat), `STALE`
(no longer true), `UNVERIFIABLE_HERE` (needs a surface/tool not available in this session),
`TODO` (not audited yet). This is a first cut: the README (EN), `README.de.md`, `README.fr.md`,
`ARCHITECTURE.md`, `docs/**`, `web/README.md` and `PLAN.md` claims are audited fully in W1/W2.

## Root `README.md`

| Claim | Location | Status | Evidence / note |
|---|---|---|---|
| Version `v5.0.0` | line 32 | VERIFIED | `scripts/check_version.py` → all surfaces 5.0.0 |
| Path A "exact GF(2) symplectic evolution, `error_bound=0.0`" | line 330 | VERIFIED | `path_a_stabilizer.py`; tests |
| Path B "22 qubits (implementation ceiling)" | line 331 | VERIFIED | `path_b_stabilizer_rank.py` `MAX_STATEVECTOR_QUBITS = 22` |
| Path B "exact algebraic decomposition, float64 evaluation" | line 331 | **FIXED (W1)** | A branch with \|weight\| ≤ 1e-15 is dropped (W3-02). The README now states the numerical-zero policy and that the dropped mass is reported in `error_bound`, matching Path C's phrasing. |
| Path C "no deliberate truncation; `numerical_error_bound=None`" | line 332 | VERIFIED | W3-03 audit (FINDINGS F-004): discarded mass is a diagnostic; `numerical_error_bound` is None with a reason |
| Path C dense conversion ≤ 20 / sampling cap 500 | line 332 | VERIFIED | source constants |
| Path D bound `Δ ≤ Σ abs(c_P)`; "no certified joint distribution" | line 333 | VERIFIED | `path_d_sparse_pauli.py`; tests |
| "Not a QPU … This package has never executed a job on physical hardware. One externally submitted reference suite (`r-io-7`)…" | lines 293–297 | **FIXED (W1)** | The paragraph now names the 2026 Quantum Gravity campaign (`research/qg_2026`) alongside `r-io-7` and keeps the package-API-vs-external-runner distinction explicit. |
| "Not a GPU-accelerated simulator. Vulkan verified for native primitives, not end-to-end" | lines 298–300 | VERIFIED | matches the native boundary; CPU-only build verified (W4-16) |
| "`exact=True` means no deliberate approximation; float64/numerical-rank remain" | lines 301–302 | VERIFIED | `SimulationResult` contract |
| "Not a P = NP result" | line 303 | VERIFIED | no such claim in code/evidence |
| "WebGPU honestly `NOT RUN` here" | line 44 | VERIFIED | probe found no `navigator.gpu`; e2e runs headless without GPU |
| Browser engine is its own WASM f64 / WebGPU f32, not A–D | README/`web/README.md` | VERIFIED | `web/src/**` independent statevector |
| Hardware-noise claims (M-FIT/M-FIT-2, qubit-0 anomaly, calibration) | lines 137–210 | UNVERIFIABLE_HERE | historical evidence in `research/**`; a held-out audit is W8/W10 |

## Architecture and localized documentation

| Claim | Location | Status | Evidence / note |
|---|---|---|---|
| Root `ARCHITECTURE.md` is canonical current architecture | root | VERIFIED | describes the four-path architecture; matches `cqhecs/router.py` + backends |
| `docs/ARCHITECTURE.md` is historical v2 | `docs/ARCHITECTURE.md` header | VERIFIED | header already says "CQ-HECS Architecture (v2, historical)" and points away from the aspirational VRTS-300 spec; the split V7 §17.1 asks to resolve is therefore already labelled, only a cross-link from the root doc could be added |
| "eliminates silent bond-dimension truncation (χ = 48)" | root `ARCHITECTURE.md` §1 | VERIFIED | `scripts/verify_no_silent_truncation.py` PASS (forbidden χ=48 patterns absent) |
| `README.de.md`, `README.fr.md` mirror the English README | DE/FR | PARTIAL | both describe `hcs.sat.unified.v1`, run cards and proof status; they do not yet mention the Wave-3/4 additive fields (`certified`/`proof_level`, `hcs.sat.count.v1`, `error_scope`). Full number/field parity is a W2/W15 obligation. |

## Not yet audited (W1/W2 obligations) - first-cut list, audited in the E3 section at the end of this file

- `docs/**` (API_REFERENCE, WEB_ENGINES, CONFORMANCE, QUANTUM_GRAVITY_LAB, DESIGN_SYSTEM,
  UNIFIED_SOLVER, PROVENANCE) — section-by-section claim check.
- `web/README.md` and `web/vercel.json` deployment claims.
- `CHANGELOG.md`, `RELEASE_NOTES.md`, `CITATION.cff`, `GEMINI*.md` staleness.
- Deeper numeric parity between `README.md`, `README.de.md` and `README.fr.md`.

## Findings to action

1. **README Path B wording** (line 331): FIXED — added the numerical-zero caveat
   (`error_bound` reports dropped mass) to match Path C's honest phrasing.
2. **README "never executed a job on physical hardware"** (lines 293–297): FIXED — now references
   the QG campaign and keeps the package-vs-external-runner distinction explicit.
3. Both were documentation corrections of *truthfulness*, not code defects. `check_version.py`
   and the suite were re-run after the edit (docs-only).


---

# E3 completion of the W1 audit (2026-11-22, candidate `38e799b`)

The "Not yet audited" list above is now audited. Method: each document was read for its status banner, version and
number claims, precision words ("exact", "certified", "verified", "GPU", "real hardware") and its statements about
what was not run, then compared with the code or an evidence file. Statuses as above. Fix status is `FIXED`
(by a V7 commit), `OPEN` (a finding with an owner) or `NONE` (nothing to fix). Mechanical checks that backed it:
`python scripts/check_version.py` (7.0.0 on every surface), `pytest tests/test_doc_consistency_v7.py
tests/test_readme_languages.py` (81 passed), `scripts/qg_doc_consistency.py` (OK), a diff of the numbers quoted in
README EN, DE and FR (4269, 134, 95/95, 167/167, 128, 26/26, 15/15, `38e799b` appear in all three).

## docs/**

| Document | Claim checked | Status | Fix status / note |
|---|---|---|---|
| `docs/ARCHITECTURE.md` | banner says historical, points to the root file | VERIFIED | NONE |
| `docs/API_REFERENCE.md` | MCP has 21 tools; `contract_version` 1.2; protocol checked against 2025-06-18 only; cancellation abandons compute | VERIFIED | `len(mcp_server.TOOLS) == 21` read from the code; states the 2025-06-18 limit itself |
| `docs/STUDIO.md` | bearer token, `/api/v1`, `/api/plan`, 403 for paid QG routes | VERIFIED | NONE; the old "no authentication" text is gone |
| `docs/UNIFIED_SOLVER.md` | schema `hcs.sat.unified.v1` | VERIFIED | matches `cqhecs/unified.py` `SCHEMA` |
| `docs/OMNIWAVE.md` | status label, no CDCL, slower than CaDiCaL | PARTIAL | the limits are stated correctly (no CDCL, slower than CaDiCaL on general instances, no performance claim beyond the measured table), but line 7 says the engine is "no longer 'experimental' as a label" while `AGENTS.md` section 1 calls it explicitly experimental. A label choice for the maintainer, not a false number. OPEN (P3, owner: docs/SAT)
| `docs/CONFORMANCE.md` | WebGPU f32 on a real page is `NOT_RUN`; corpus counts | VERIFIED | agrees with `waveC_C1.md` (21 circuits, 4 refusals, 1 skip) |
| `docs/WEB_ENGINES.md` | WebGPU used only with an adapter; Firefox/WebKit `NOT_RUN`; WebGPU limit formula | VERIFIED | NONE |
| `docs/WEBGPU_WASM_BACKENDS.md` | backend probe order for the SHA forge; "passed in the in-app Chromium" | UNVERIFIABLE_HERE | different subsystem (miner forge); a Chromium without an adapter is not a real-GPU result; see B-V7-03 |
| `docs/QUANTUM_GRAVITY_LAB.md` | finite models, no physical claim, route list | VERIFIED | covered by `qg_doc_consistency.py` |
| `docs/DESIGN_SYSTEM.md` | tokens equal `web/src/styles.css` | PARTIAL (not token-by-token compared) | the token-contrast gate in `npm run build` covers the contrast part only |
| `docs/PROVENANCE.md` | run-card JSON example | PARTIAL | the example carries `"version": "5.0.0"`; it is an illustration, but a reader may copy it. OPEN (P3) |
| `docs/PACKAGING.md`, `docs/RELEASE_PROCESS.md` | asset names, that workflows are unproven | VERIFIED | `PACKAGING.md` line 36 and `RELEASE_PROCESS.md` line 5 say the workflows have not run; clean-machine install `NOT_RUN` (line 121); matches B-V7-09 and B-V7-05 |
| `docs/QASM_CONTRACT.md` | strict reader, bounded angle grammar | VERIFIED for the repeated-operand rule | line 144 requires pairwise distinct operands, matching `c655e92`; `test_circuit_repeated_operands.py` pins the code (the other sections were not re-read) |
| `docs/BENCHMARKS.md` | banner "STALE - NOT CURRENT RESULTS" | VERIFIED | correctly labelled; NONE |
| `docs/V2_IMPLEMENTATION_MATRIX.md` | Path B "algebraically exact decomposition, float64 arithmetic" | PARTIAL | omits the W3-02 numerical-zero policy (branches with weight at most 1e-15 are dropped and the mass is reported in `error_bound`) that README and ARCHITECTURE now state; the file has no historical banner. OPEN (P3, owner: docs) |
| `docs/MIGRATION_V3.md`, `docs/EMBEDDING_GUIDE.md`, `docs/LOCAL_BRIDGE.md`, `docs/MINER_BACKUP_RESTORE.md`, `docs/SHA_ROUND_ANALYZER.md`, `docs/TIMSMINER_RESEARCH_MODE.md`, `docs/USAGE_GUIDE.md` | version strings, readiness claims | PARTIAL (read for status and version words only; no stale "latest" or "formally verified" wording found by `grep`; not claim-by-claim) | NONE; `USAGE_GUIDE.md` is edited by another agent at writing |

## web/README.md, deployment

| Claim | Status | Note |
|---|---|---|
| WASM f64 core keeps every amplitude; agrees with Qiskit below 1e-12 | VERIFIED | `web/tests` Qiskit fixtures; the page's own wording names double precision |
| WebGPU f32 cross-checked against the exact core "up to 20 qubits" | VERIFIED | `engine.worker.ts` cross-checks when `n <= 20` |
| Safe width at most 27 qubits; runs over 90 s refused | VERIFIED | `device.ts` `WASM_MAX_QUBITS = 27`, `MAX_RUN_SECONDS = 90` |
| Heading "An exact quantum-circuit emulator"; page title "Exact quantum emulator"; feature card "Exact, not approximate" (EN, DE, FR) | PARTIAL | the card text itself says double precision and 1e-12 agreement, but a headline "exact" next to float64 is the wording AGENTS.md 0.1 warns about (float64 is not symbolic exactness; WebGPU is f32; noisy runs are Monte Carlo). OPEN (P3, owner: web) |
| "Every push to `main` deploys to production" | VERIFIED | consistent with `docs/RELEASE_PROCESS.md`; `web/vercel.json` has framework, build command and headers only, no branch gate; B-V7-09 and B-V7-14 apply |

## CHANGELOG, RELEASE_NOTES, CITATION, SECURITY, GEMINI

| Document | Claim checked | Status | Fix status / note |
|---|---|---|---|
| `CHANGELOG.md` | `[7.0.0]` section marked "unreleased candidate", no tag; "no 6.x release" | VERIFIED | `git tag` lists v5.0.0 as the newest tag; check_version requires the section |
| `RELEASE_NOTES.md` | describes the current release | **STALE** | still "Version 4.0.0, Release date 2026-11-01"; `release.yml` pastes this file into the release body; `check_version.py` only rejects 0.1.0 and 0.2.0 there. OPEN (P1 for publication, B-V7-12). `RELEASE_NOTES_DRAFT.md` holds the 7.0.0 text |
| `RELEASE_NOTES_DRAFT.md` | sections implemented / experimental / measured / formally checked / not supported / not run | VERIFIED | edited by E2 at writing; the numbers match `waveE_E2.md` |
| `CITATION.cff` | version 7.0.0; abstract states not a QPU, no P versus NP claim | VERIFIED | `date-released: 2026-11-22` is a date for a release that does not exist yet; set it to the real publication date. OPEN (P3, at publication) |
| `SECURITY.md` | "7.0.x supported: Yes" | PARTIAL | true only once 7.0.0 is published; fine for a release-candidate branch, but would be wrong if the branch were read as released. NONE |
| `GEMINI.md`, `GEMINI_HANDOFF.md` | status | VERIFIED | both carry an explicit HISTORICAL banner ("Do not act on the tasks below") and name the current records |

## README EN, DE, FR parity

| Claim | Status | Note |
|---|---|---|
| The verification numbers and the freeze SHA are identical in the three READMEs | VERIFIED | extracted with a script; `tests/test_readme_languages.py` passes (10 tests) |
| DE and FR mirror EN | PARTIAL | EN is 1,327 lines, DE and FR are 208 each: they are condensed summaries, not translations, so a statement present only in EN (for example detailed limits) is absent in DE and FR. Number parity is tested; limit-statement parity is not |
| DE and FR carry a "Historical lane" table with 21/21 CTest and 60/60 mutants | VERIFIED as history | each is labelled with its own SHA and is not presented as current |
| All three say no `v7.0.0` tag or release exists | VERIFIED | regex check over the three files |
| README verification table cites freeze SHA `38e799b` and "artifacts built from `38e799b`; not published" | PARTIAL, will go stale | correct today; the artifacts will be rebuilt at the final freeze SHA, and a later commit makes "freeze SHA `38e799b`" wrong. The integrator must change README, DE, FR, `waveE_E2.md` and the pinned test together. OPEN (P2 at freeze) |

## Findings to action (E3)

1. `RELEASE_NOTES.md` is 4.0.0 content and is the release body: OPEN, P1 for publication (B-V7-12).
2. README freeze-SHA wording will be stale once the final SHA differs from `38e799b`: OPEN, P2 at freeze.
3. Web "Exact" headline next to float64/f32/Monte Carlo: OPEN, P3.
4. `docs/V2_IMPLEMENTATION_MATRIX.md` Path B wording lacks the numerical-zero caveat; `docs/OMNIWAVE.md` drops the "experimental" label that `AGENTS.md` uses: OPEN, P3.
5. `docs/PROVENANCE.md` example says 5.0.0; `CITATION.cff` `date-released` precedes any release: OPEN, P3.
6. DE and FR are condensed, so only numbers are in parity: documented here, accepted unless the maintainer wants
   full translations.

No document claims a P versus NP, ETH or SETH result, a QPU job submitted by the package, formal verification of a
component, or an end-to-end GPU speedup. Nothing in this audit was edited outside the E3 area; findings 1, 3, 4 and 5
belong to other owners.
