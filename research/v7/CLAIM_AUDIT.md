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

## Not yet audited (W1/W2 obligations)

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
