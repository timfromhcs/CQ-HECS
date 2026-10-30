# v3 defect register (GEMINI.md §3 audit leads)

Audited against `main` at `098d12f` (2026-10-30). Each lead was reproduced
before a fix; "CONFIRMED" means a failing reproduction existed.

| ID | Lead | Severity | Status | Reproduction | Fix | Regression evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CQ-V3-01 | 3.1 Python DPLL timeout | **P0** | CONFIRMED → fixed | `solve(..., timeout_seconds=0)` on `uf50_hard.cnf` returned `satisfiable=False, verified=True` | `SATSolverResult.status` (`SAT_VERIFIED`/`UNSAT_PROVEN`/`TIMEOUT_UNKNOWN`), `satisfiable=None` on timeout, timeout raised through the search | `tests/test_sat_soundness.py`; mutant 36 |
| CQ-V3-02 | 3.2 hash pruning (Python) | **P0** | CONFIRMED → fixed | 32 forced units + a satisfiable rest returned `UNSAT, verified` (hash over the first 32 variables) | exact memo keyed by the full assignment, inserted only after a completed refutation; the J-Space Gamma hash table no longer decides branches | `tests/test_sat_soundness.py` (adversarial constant hash, 300 random CNFs vs brute force); mutant 37 |
| CQ-V3-02b | 3.2 hash pruning (native) | **P0 (latent)** | CONFIRMED by reasoning → fixed | a 64-bit hash match (with the low bit forced to 1, plus cuckoo eviction) closed a branch as if identical | `std::set` of exact assignments, inserted after refutation, bounded by the table capacity (bounding only skips work) | `tests/cpp/test_sat_parser.cpp`: 400 random CNFs vs brute force at memo capacity 1 and 4096 |
| CQ-V3-03 | 3.3 DIMACS parity | **P1** (P0 effect) | CONFIRMED → fixed | Python split a clause spanning lines (`1 2\n3 0` → `[1,2],[3]`), dropped an empty clause `0` (UNSAT input reported SAT), accepted unterminated clauses and literals above the header | Python parser now implements the native grammar and limits; `DIMACSParseError` | `tests/test_dimacs_parity.py` (13 cases, Python = native); mutant 38 |
| CQ-V3-04 | 3.4 exact-ring overflow | **P1** | CONFIRMED → fixed | `int64` products, shifts, negation of `INT64_MIN` and `k + k` were unchecked in both `cq::Cyclotomic8` and `cqhecs::algebra::ExactRingElement`; `operator==` caught overflow and returned "not equal" | `include/cq/checked_int.hpp`; all arithmetic throws `std::overflow_error`; equality compares unique minimal-k forms without rescaling; `ldexp` for the approximate export | `tests/cpp/test_exact_ring.cpp::test_overflow_is_refused` |
| CQ-V3-05 | 3.5 `assert` in Release | **P1** | CONFIRMED → fixed | `test_exact_ring`, `test_stabilizer_extreme`, `test_constraint_solver`, `test_reversibility` used `assert` without `#undef NDEBUG`; the CI Release build compiled every check out | `#undef NDEBUG` guard; meta-test `test_release_assert_meta` (WILL_FAIL) proves a false check fails in Release | CTest 21/21 |
| CQ-V3-06 | 3.6 synthetic telemetry | **P1** | CONFIRMED → fixed | both dashboards showed sine-wave VRAM/jitter as `ACTIVE`, `PHYSICAL HARVEST`, `Hard Contract`, with keys that did nothing; the Python one crashed on a missing field | dashboards refuse without `--demo`; every frame says `SIMULATED DATA - NOT A MEASUREMENT`; dead key hints removed | `tests/test_demo_dashboard.py`, `tests/test_cli_powershell.py` |
| CQ-V3-07 | 3.7 Vulkan device selection | **P1** | CONFIRMED → fixed | no explicit selection, no reason, identity limited to the name | `device_policy.hpp` (pure, testable), `CQ_HECS_VULKAN_DEVICE=<index or name>` without fallback, vendor/device/driver/API identity and selection reason reported | `tests/cpp/test_vulkan_device_policy.cpp` |
| CQ-V3-08 | 3.8 UI version drift | P2 | CONFIRMED → fixed | native TUI printed `v0.2.0`, Python TUI `2.4.0` | both read the canonical version (`CQ_HECS_VERSION`, `cqhecs.__version__`) | dashboard tests |
| — | 3.9 historical benchmarks | P2 | NOT A DEFECT for v3 | files are labelled by version; no v3 claim cites them | none | README "no performance claim" |
| — | 3.10 README scope | P2 | re-checked at release | | | release audit |

Not covered by this register: physical-GPU verification (no device in this
environment) and real-provider execution inside the package (W6, out of
scope for v3.0.0).
