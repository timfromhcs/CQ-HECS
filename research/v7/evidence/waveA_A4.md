# Wave A, agent A4: SAT isolation, separator calibration, proof tamper matrix, MaxSAT contract

Date 2026-11-21. Branch release/v7-stable. Edits limited to the A4 owned area. No commit made.

## W3-11 python-sat child-process isolation: DONE (code + tests); 3.14 abort NOT reproduced (not run on 3.14)
- python-sat not installed in the main interpreter (Python 3.13.13). Installed `python-sat 1.9.dev24`
  into a throwaway venv under the scratchpad only (`pip install python-sat numpy pytest qiskit hypothesis`).
- Finding: the native abort IS reproducible on Python 3.13.13 / Windows 11, not only 3.14. After a
  `with_proof=True` SAT solve, the interpreter exits with 0xC0000409 AFTER the result was produced
  (plain script, no cqhecs: Solver(name='cadical195', with_proof=True) solve + delete + exit => rc 0xC0000409).
  `with_proof=False` exits 0. Not suppressed: recorded in the result note.
- Implementation (`cqhecs/sat_external.py`): `solve_external` split into `_run_cadical` (raw,
  untrusted) + `_finish` (parent-side verification: model vs original CNF; DRAT check by
  `cqhecs.drat`). New `solve_external_isolated` runs the raw solve in `python -m cqhecs.sat_external --worker`.
  - child crash with no result, hard-deadline kill, garbage/unparseable output => UNKNOWN, exit code in note.
  - complete result then abnormal exit (the observed case) => result is re-verified by the parent and
    the note carries "WARNING: isolated child exited abnormally (exit code ... = 0xc0000409)".
  - lying child (bad model, empty/false proof) => UNKNOWN / uncertified.
  - python-sat missing in child => BackendUnavailable (no silent fallback).
- Tests: `tests/test_sat_external_isolated.py` (12 tests; 11 pass without python-sat, the real
  round trip runs only where python-sat is installed).

## W4-08 separator width calibration: DONE
- `cqhecs/sat_separator.py`: `predicted_table_bound(w) = 2**(w+1)`; `count_by_elimination(preflight=True)`
  returns UNKNOWN before any table is allocated when the bound exceeds the budget (never a partial
  count); `predicted_table_bound` reported next to observed `max_table`. Default behaviour unchanged.
- `scripts/sat_separator_calibration.py` raw rows: `research/v7/evidence/waveA_A4_separator_calibration.json`
  (31 rows, 0 violations of observed <= predicted, max induced width 14, bound at AUTO width 14 = 32768 <= 500000).
- Tests added to `tests/test_sat_separator.py` (120 random bound checks + preflight, validation).
  Result: 441 passed.
- Limit: the bound is an upper bound, conservative for sparse tables; it is not a runtime estimate.

## SAT proof pipeline tamper matrix: DONE for DRAT (in-repo checker, label DRAT_CHECKED)
- `tests/test_drat_tamper.py` (16 tests) on the fixed CaDiCaL pigeonhole_6_5 vector (235 steps): delete first
  lemma, measured 125/235 single-step deletions rejected (some lemmas are redundant, so not all),
  truncations, dropped empty clause, reversed, swapped steps, flipped literal (113/126 broken),
  tampered proofs against a satisfiable formula never accepted, wrong formula, budget/timeout => valid=None,
  malformed line => rejected.
- Timeouts/budgets => UNKNOWN or uncertified: already covered by test_sat_deadline / test_unified_deadline (re-run, pass).
- NOT RUN / NOT SUPPORTED: LRAT replay with the in-repo checker (it has no LRAT reader; ladder rung
  LRAT_CHECKED not claimed); drat-trim (EXTERNAL_DRAT_CHECKED), cake_lpr (CAKELPR_CHECKED_VECTOR)
  lanes skipped, no binaries here.

## MaxSAT typed contract: DONE
- `cqhecs/sat.py`: `max_sat_checked` (`hcs.sat.maxsat.v1`). Above max_vars returns UNKNOWN with
  `limit_reached=True`, no optimum/assignment, no raise. OPTIMAL only after exhaustive enumeration and
  re-verification; `optimality_certificate` is always None (not proof-carrying).
  `max_sat` unchanged. CLI (`cqhecs/cli.py`, outside the owned area) still calls `max_sat`; wiring is for the integrator.
- Tests appended to `tests/test_sat_models.py` (64 pass).

## Commands and counts
- `python -m pytest <19 SAT/DRAT/unified/omniwave test files> -q`: 1314 passed, 58 skipped (main interpreter,
  python-sat skips included).
- throwaway venv (Python 3.13.13, python-sat 1.9.dev24): `tests/test_sat_external_isolated.py tests/test_sat_external.py`
  56 passed, 1 skipped (the unavailable-path test).
- Full pytest suite: NOT RUN (per rules). Python 3.14: NOT RUN. drat-trim, cake_lpr, lrat-check: NOT RUN.
