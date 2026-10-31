# v6 findings

Status: `CONFIRMED` = reproduced in this session with a test or command.
`SUSPECTED` = code reading only. `FIXED` includes the regression test location.

## F-01 — Partial assignment could vacuously satisfy a negative literal (CONFIRMED, FIXED)

`CNF.is_satisfied` used `assignment.get(abs(lit), False) == (lit > 0)`. For an
unassigned variable and a negative literal, both sides are `False`, so the clause
counted as satisfied. A caller that passes a partial assignment (or a model that
omits declared variables) could receive a false `True`.

- Reproduction: `parse_dimacs("p cnf 1 1\n-1 0\n").is_satisfied({})` returned `True`.
- Fix: `CNF._clause_satisfied` distinguishes `None` (unassigned) from `False`.
- Regression: `tests/test_sat_watched.py::test_partial_assignment_does_not_satisfy_negative_literal`.
- Impact on shipped solver: low — `_DPLL.model()` returns every declared variable and
  `solve_external` fills every variable — but the public predicate was unsound.

## F-02 — Original DIMACS bytes were not retained (FIXED)

`CNF.sha256` hashes the canonical `to_dimacs()` rendering, so formatting changes
were invisible. `CNF` now also carries `original_sha256` (compare=False) and
`parse_dimacs` stores the SHA-256 of the input text. SAT result contract `1.2`
adds `formula_original_sha256` next to `formula_sha256`; the CLI, MCP and Studio
formula summaries expose both. Regression:
`tests/test_sat_soundness.py::test_original_and_canonical_digests_are_both_retained`.
Note: `load_dimacs` reads text with universal newlines, so the digest binds the
parsed text, not necessarily the raw on-disk byte sequence.

## F-03 — Certificate budget could double the advertised wall clock (FIXED)

`solve()` ran the main search with `timeout_seconds`, then `_certify()` with a fresh
`certificate_timeout_seconds` defaulting to the same value. The configured certificate
budget is now additionally capped by the remaining solve deadline. If no time remains,
the verdict stays `UNSAT` but `certified=False` and the note says the deadline was
exhausted. Existing certificate tests still pass.

## F-04 — DIMACS duplicate literals were rejected by Python but accepted by native (FIXED)

`CNF.__post_init__` rejects `p cnf 2 1 / 1 1 0`, while
`python_bridge.sat_engine` and the C++ parser accept duplicates. The Python
`parse_dimacs` now removes repeated literals inside a clause (`1 1 0` → `1`)
before constructing the strict `CNF`; direct `CNF(...)` construction still
rejects duplicates. Tautologies (`1 -1 0`) remain clauses. Tests:
`test_duplicate_literals_are_normalized_not_rejected` and the updated
`test_malformed_dimacs_is_rejected` list. This changes a previously documented
rejection, so it is recorded in the changelog.

## F-05 — Interpreter aborted at exit after the Vulkan status probe (CONFIRMED, FIXED)

The first full `pytest` run printed `1617 passed, 6 skipped, 1 deselected` but the
process exited 1. A later full run (1754 passed) exited `-1073740791`
(`0xC0000409`, stack buffer overrun). The trigger was isolated to
`cqhecs.omniwave.gpu.status()`: the lazily created native `VulkanContext` was
destroyed during DLL unload, after the Vulkan loader/driver teardown.

- Reproduction: `python -c "from cqhecs.omniwave import gpu; gpu.status()"` exited
  `-1073740791`; `python -c "from cqhecs.omniwave.engine import …; run()"` exited 0.
- Fix: new C ABI `cq_omniwave_shutdown()` resets the global context while the
  loader is mapped; `gpu.py` registers it with `atexit` when the library loads.
- Regression: `tests/test_omniwave_gpu_shutdown.py` runs the probe in a fresh
  process and asserts exit code 0. `tests/test_studio.py` now exits 0.
- This was a pre-existing v3.5.0 defect, not caused by the watched engine.

## F-06 — Quick Tseitin benchmark case times out (CONFIRMED, FIXED)

The first quick design used `tseitin_grid(5×5)` at a 10 s timeout; both engines
returned `UNKNOWN`, wasting 60 s and testing nothing. The quick suite now uses
4×4 and the full suite uses 4×5 (a 31-variable UNSAT parity instance that finishes
in about one second). Larger grids belong in a separate stress table.

## F-07 — Browser SAT contract does not expose the new input digest (OPEN)

`web/src/sat.ts` implements its own DPLL and mirrors `status`, `certification`,
`verified`, decisions/propagations/conflicts and certificate steps. It does not
compute `formula_original_sha256` and has no watched engine. This is consistent
with the documented “separate browser engine” boundary, but the v3.6 plan asks
for contract parity where feasible. Track as T6-M3-06; do not claim byte-identical
contracts between Python and Web before it is implemented and tested.

## F-08 — A prebuilt v3.5 native library does not contain the shutdown symbol (NOTE)

`cq_omniwave_shutdown` is a new C ABI symbol. A prebuilt `cq_hecs.dll` from
v3.5.0 does not contain it; `gpu.py` then skips the hook and the old unload crash
can still occur. Release artifacts must be rebuilt from this source, and the
process-exit regression test should run against the built artifact in CI.

## F-09 - python-sat 1.9.dev17/CaDiCaL aborts the Python 3.14 process at exit (CONFIRMED, EXTERNAL)

On this Windows/Python 3.14.6 machine, importing and closing `pysat.solvers` with
CaDiCaL terminates the interpreter with `0xC0000409` after the work has finished
(a minimal `Solver(name="cadical195")` script reproduces it). The SAT tests
themselves pass; the exit code is the problem. The same adapter is exercised in
the Linux CI lane, where python-sat is a pinned optional dependency.

- Impact: a local full-suite run with python-sat installed reports a spurious
  non-zero exit after 2016 passing tests.
- Mitigation: run the full local suite without python-sat (the optional tests
  skip), and run `tests/test_sat_external.py` in a dedicated process while
  recording the external exit-code defect.
- This is not a CQ-HECS native crash and must not be hidden in release evidence.
- Next: pin/test a python-sat build that exits cleanly on Python 3.14, or keep
  the external adapter in a subprocess boundary.
