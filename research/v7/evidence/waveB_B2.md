# Wave B, agent B2: QG model audit (W8) and QG ExecutionPlan parity (T6-01)

Scope: model quantities only. No QPU job, no Open Quantum call, no credit, no credential. Raw
evidence and `JOB_LEDGER.jsonl` were only read (replay opens files read-only; a test hashes
raw/processed/qasm before and after a replay and asserts equality).

## Commands run (Windows, Python 3.13.13, pytest 9.2.0)

| Command | Result |
|---|---|
| `python -m pytest tests/test_qg_bmv_competing.py -q` | 41 passed (after 2 repair cycles, below) |
| `python -m pytest tests/test_qg_syk_trotter.py -q` | 48 passed |
| `python -m pytest tests/test_qg_gauge_leakage.py -q` | 25 passed |
| `python -m pytest tests/test_qg_execution_plan.py -q` | 15 passed |
| `python -m pytest tests/test_qg_replay.py -q` | 11 passed |
| `python -m pytest tests/test_execution_plan.py tests/test_qg_*.py tests/test_quantum_gravity_*.py -q` | 261 passed |
| `python -m pytest tests -q -k "doc or consistency or llms"` | 31 passed, 3 skipped (pre-existing skips) |

Full pytest suite: NOT RUN (instructed). Mutation suite, native, web: NOT RUN (not in owned area).

## Repair cycles (root causes)

1. Wootters concurrence via `eigvals(rho rho_tilde)` and `sqrt` gave 5.8e-9 error on pure states
   (sqrt of rounding noise). Root cause: taking a square root of eigenvalues near 1e-17. Fix: use
   singular values of `sqrt(rho) (Y(x)Y) conj(sqrt(rho))`. One cycle.
2. My own test assumed `<XX> = cos(theta)`. Wrong: ZZ commutes with XX so `<XX> = 1`; the phase is in
   YZ/ZY. Test corrected to the derived values (they match the historical QPU analysis). One cycle.

## Deliverables

- BMV: `cqhecs/quantum_gravity/bmv_competing.py`, notes `research/qg_2026/BMV_MODEL_NOTES.md`, frozen table
  `research/qg_2026/models/bmv_competing_table.json`. Competing models: quantum ZZ, classical feedback (LOCC),
  shared randomness, declared dephasing, null. Independent oracle: Wootters spin-flip, cross-checked with the
  partial-transpose route and `abs(sin theta)`. Fidelity witness bound verified on 200 random separable states.
  Physical `theta` mapping is a typed refusal (`QG_NO_DIMENSIONAL_MODEL`). Convention bridge to QGRAVITY.md
  (`theta = 2 theta_qg`) tested against `expm`.
- SYK: `cqhecs/quantum_gravity/syk_trotter.py`. QASM compiler for Pauli rotations, Trotter and exact-inverse mirror
  circuits; QASM unitary (via Qiskit) equals the dense product of per-term matrix exponentials exactly (including global
  phase) for 13 Pauli labels and 5 (n, seed, steps) cases. Mutation checks: swapped non-commuting terms and `sdg -> s`
  are both detected. Frozen seeded reference `research/qg_2026/models/syk_reference_n3_seed20260101.json` (couplings,
  spectrum, exact p000). Error table `models/syk_trotter_error_table_n3_seed20260101.json` (dense spectral error vs
  closed-form first-order commutator bound):

  | steps | measured spectral error | bound | P(000) Trotter | P(000) exact |
  |---|---|---|---|---|
  | 1 | 1.526 | 6.714 | 0.2326 | 0.4280 |
  | 2 | 0.8562 | 3.357 | 0.3335 | 0.4280 |
  | 4 | 0.4390 | 1.679 | 0.4001 | 0.4280 |
  | 8 | 0.2202 | 0.8393 | 0.4200 | 0.4280 |
  | 16 | 0.1100 | 0.4196 | 0.4256 | 0.4280 |
  | 32 | 0.05494 | 0.2098 | 0.4272 | 0.4280 |

  The bound held in every tested case (seeds 1..6 and the frozen instance); it is a loose first-order bound and
  excludes device noise and shot error. Majorana tests extended: squares, pairwise anti-Hermiticity, Hermitian
  four-products, JW total parity as a Z-string.
- Z2 gauge: leakage observable in `cqhecs/quantum_gravity/gauge.py` (`gauss_projector`, `gauss_leakage`,
  `gauss_violation_profile`, `link_rotation`, `apply_link_z_error`, `leakage_under_evolution`). Oracles: single-link Z
  rotation leaks exactly `sin^2(eps)` on exactly the endpoint vertices; incoherent Z error leaks exactly `p`; second-order
  short-time oracle `L (lambda t)^2` within 5%. Null controls: X rotation, X field, zero-strength Z field, plain
  Hamiltonian evolution (all leak 0).
- Plan parity: `cqhecs/quantum_gravity/plan.py`. The embedded plan equals the generic `build_execution_plan` output
  exactly (same dict and digest); the envelope adds model identity, surface, engine and precision from the selected path,
  `physical_execution = False`, and a run-card fragment. Refusals (dynamic circuit, forced unsupported path, memory
  budget) propagate with `engine = None`. A QPU surface cannot be planned. `execution_plan.py` was not edited.
- Replay: `cqhecs/quantum_gravity/replay.py`. 353 checks, 0 failed: SHA-256 manifests of all seven raw directories, counts,
  shots, correlators, standard errors, 95% intervals, deviations, SYK p000, smoke supports/fractions, drift deltas, XX trend,
  and ideal values recomputed from the frozen QASM.

## Findings from the replay (recorded, nothing patched)

- R-SYK-V1-IDEAL: the v1 `ideal_p000` values (0.428017, 1.0) are the exact matrix exponential and the return-to-zero
  ideal, not the submitted Trotter circuits (whose own statevector gives 0.232584 and 0.010325). This reproduces the already
  recorded correction F-09. v3 ideals match the QASM and the 1-step Trotter reference (0.232584).
- R-PHASESCAN-XX: in `processed/bmv_phase_scan.json` the XX points carry `expected_sin = sin(theta)` and a derived
  `ratio`, but ZZ commutes with XX so the frozen circuits' ideal XX correlator is 1.0 at every theta. The XX `ratio` is
  therefore not a phase-recovery ratio (YZ/ZY ratios are valid). Processed file left unchanged (historical).

## Not done / NOT RUN

- QG plan envelope exposure through CLI, MCP and Studio (`cli.py`, `mcp_server.py`, `studio.py` belong to other owners):
  NOT WIRED. Python module and tests are done.
- T6-02 Studio/Web QG screens: out of scope.
- Fresh held-out BMV drift/uncertainty analysis (T6-10) and further hardware runs (T6-09): NOT RUN; no spend authorised.
- No dimensional (physical-units) BMV model: deliberately refused.
