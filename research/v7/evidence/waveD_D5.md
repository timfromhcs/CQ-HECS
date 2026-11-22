# Wave D, task D5: mutation pin, Python 3.14 lane, Lean L-RESULT-01, audit skeletons

Date 2026-11-22, branch `release/v7-stable`, HEAD `51969fd` (tree dirty from other Wave D agents). Windows 11.
No git commit/add/stash/checkout/push. No QPU, Open Quantum call, credential or spend. Version not bumped.

## 1. Mutation harness pin and README lines

- `tests/test_mutation_harness_meta.py::test_the_documented_mutant_count_matches_the_table` no longer pins `64`.
  It now asserts `len(harness.MUTANTS) >= 64` (sanity floor: the table may grow but never silently shrink) and
  that mutant names are unique. Prose in the module docstring no longer quotes a number.
  `python -m pytest tests/test_mutation_harness_meta.py -q` -> 5 passed, 1 deselected (slow sweep opt-in).
- README EN (lines 290, 905), DE (148), FR (147): `64/64 (earlier baseline)` -> `95/95` labelled as a snapshot run
  (W15) to be re-run in place at freeze. These are the only README lines touched.
- Full sweep run on a **snapshot copy** (robocopy of the worktree without `.git`, `node_modules`, builds, venvs),
  because the harness rewrites production sources and other agents edit them concurrently. NOT run in place:
  the integrator must re-run `python scripts/run_mutation_tests.py` in place at the freeze.
  Result on the snapshot: `mutants: 95 | checks: 71`, `Baseline OK: 71 checks pass on unmutated source.`,
  **`Mutation score: 95/95 killed (100.0%)`** (scratchpad `mut_D5.txt`). The snapshot contained other agents'
  in-progress edits at copy time, so this is not a freeze result.

## 2. Python 3.14 lane (report only)

Throwaway venv (scratchpad `venv314`, CPython 3.14.6), `pip install -e ".[dev]" qiskit-ibm-runtime python-sat`
(python-sat 1.9.dev24). Nothing was installed into the repo tree (no new untracked files from the install).

| Tests | Result |
|---|---|
| `test_v3_calibration_bridge.py`, `test_v3_noisy_expectation.py` | 33 passed, 0 skipped (these skip on 3.13 without qiskit-ibm-runtime) |
| `test_sat_external.py`, `test_sat_external_isolated.py` | 56 passed, 1 skipped (unavailable-path test, correctly unreachable with python-sat present) |
| all three groups in one process | 77 passed |

**The native abort reproduces on 3.14.6.** After every pytest process that ran the external CaDiCaL tests, all tests
had passed and the process exit code was `-1073740791` = `0xC0000409` (observed for the SAT group alone and for the
combined run). A bare `Cadical153` solve without proof logging exited 0. This agrees with A4's finding that the abort
is not 3.14-specific (it was reproduced on 3.13.13 with `with_proof=True`). It is an external-package interpreter-exit
defect, recorded and **not suppressed**; the isolated-child design (`solve_external_isolated`) already treats a
complete result followed by an abnormal exit as "re-verified by the parent, with a warning". CI running these tests
in the main process on Windows can therefore still see a non-zero exit with all tests green.

## 3. Lean: L-RESULT-01 (result-contract state/flag consistency)

New `formal/CQHECS/Result.lean` (imported from `formal/CQHECS.lean`), a pure specification model of
`cqhecs/result.py`: `SimState`, `deriveState failed unresolved exact errZero` (mirror of `__post_init__`) and
`totalBound` (mirror of the state guard in `total_error_bound`). Seven theorems: `unresolved_derives_unresolved`,
`failed_wins`, `unresolved_never_certified_or_exact`, `exact_requires`, `unresolved_has_no_certified_value`,
`unresolved_flags_expose_no_value`, `value_only_for_exact_or_certified`. No `sorry`.

Commands (stdin from /dev/null, output redirected to files):
- `lake env lean CQHECS/Result.lean` -> rc 0, no diagnostics (33 s warm).
- `lake build` -> `Build completed successfully (8711 jobs)`, rc 0.
- `lake env lean scripts/PrintAxioms.lean` -> rc 0; the seven new lemmas depend on `[propext]` (four Bool-only ones)
  or `[propext, Classical.choice, Quot.sound]` (three using real numbers); all 26 audited lemmas are within the
  standard three axioms.

Honest anomaly: the first `lake build` and a first direct `lean` run hung for about 20 and 8 minutes at ~0 CPU
(cold-cache I/O on the Mathlib oleans on this machine; `import Mathlib` alone took 2 m 40 s cold). I killed my own
two processes, then everything completed in seconds-to-minutes on a warm cache. No defect in the source was
involved; this is recorded because it is an environment cost for CI planning.

Python pin: `tests/test_formal_result_contract.py` (3 passed) enumerates all 16 `(failed, unresolved, exact,
err==0)` combinations through the real `SimulationResult`, compares the derived state with a transcription of the
Lean table, checks that unresolved/failed results (even with `counts` set) give `total_error_bound is None`, and
checks that the Lean file still names the seven lemmas and contains no `sorry`.

Assurance wording: `FORMALIZED_LEMMA` for the named specification lemmas only. Nothing here says `SimulationResult`
is formally verified, and nothing about what a backend places in `counts`/`probabilities` (covered by Python tests).
`formal/README.md` lemma table updated (L-RESULT-01 row; L-SEP-01 and L-SAT-01 remain backlog).

## 4. Audit skeletons

- `research/v7/RELEASE_CANDIDATE_AUDIT.md`: all 42 AGENTS_V7.md section 21 checkboxes (21.1: 11, 21.2: 9, 21.3: 8,
  21.4: 7, 21.5: 7) listed, each `UNKNOWN`, none ticked, with the evidence path the integrator fills at freeze.
- `research/v7/HYPOTHESIS_REGISTER_V7.md`: rows updated (V7-LEAN-01 -> SUPPORTED_IN_SCOPE at specification level;
  H-QUANT-01/V7-E -> INCONCLUSIVE, RESEARCH_ONLY; V7-F and V7-G -> NOT_SUPPORTED for promotion, RESEARCH_ONLY; H-SAT-03 note)
  plus a "Waves A-D status update" table with before/after and basis. Unchanged and said so: H4-SAT-01, H4-PAULI-01,
  H-SAT-06, H-NOISE-01 (NOT_RUN), H-UX-01 (PARTIAL), H4-ROUTE-01 (DEFERRED).

## NOT RUN

In-place mutation sweep; full pytest suite; Python 3.14 run of the whole suite (only the three targeted groups);
Comparator/nanoda statement check for the new lemma; refinement link between `Result.lean` and `result.py`.
