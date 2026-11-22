# v4 findings

## F-001 H4-SAT-01: variable elimination #SAT -- SUPPORTED_IN_SCOPE (correctness), descriptive speed
Raw data: `evidence/sat_separator_bench.json` (script
`scripts/sat_separator_benchmark.py`, 3 repeats, 30 s timeout, fixed seeds,
Python 3.13.13, Windows 11, single process). Environment fields are in the JSON.

**Correctness:** 0 mismatches across 11 families x 3 methods. Test oracles:
`tests/test_sat_separator.py` -- all 3,000+ formulas with <= 3 clauses over 3
variables (exhaustive), 300 random formulas vs brute force and the DPLL counter,
tautology/duplicate/free-variable/empty-clause edge cases, >2^53 counts as
decimal strings, budget and deadline refusals (`UNKNOWN`, never partial), and a
deliberately broken join that the oracle catches.

**Speed (median wall ms; C = counted, U = UNKNOWN):**

| Family | width | dpll | separator | auto |
|---|---:|---:|---:|---:|
| chain-200 | 1 | 77.6 C | 4.6 C | 4.5 C |
| chain-2000 | 1 | 19157 U | 365 C | 365 C |
| grid-3x25 | 3 | 1107 C | 2.6 C | 2.6 C |
| grid-4x20 | 4 | 2046 C | 3.7 C | 3.6 C |
| grid-5x12 | 5 | 464 C | 3.0 C | 3.0 C |
| banded-n80-w8 | 7 | 2736 C | 7.0 C | 6.9 C |
| banded-n120-w10 | 7 | 30025 U (timeout) | 13.2 C | 13.1 C |
| banded-n60-w14 | 11 | 185 C | 13.9 C | 13.8 C |
| random3sat-n24-r4.26 | 17 | 3.1 C | 67.7 C | 4.8 C |
| random3sat-n32-r3.0 | 21 | 23.3 C | 396.5 C | 26.6 C |
| random3sat-n40-r4.26 | 27 | 25.3 C | 232 U (table budget) | 32.6 C |

Reading: on bounded-width structured families variable elimination is
orders of magnitude faster; on high-width random 3-SAT it is slower or refuses,
and `auto` avoids that loss at a planning cost of 1.5-7 ms. This is a finite
benchmark on synthetic families; it establishes **no** asymptotic or general
speedup claim and says nothing about industrial instances. The default method
therefore stays `dpll`; `auto` is opt-in. The `auto` width limit (14) was fixed
before this run and not tuned on it (see HYPOTHESES.md).

## F-002 Latent defect fixed: DPLL `count_models` crashed on deep formulas (CORRECTNESS/RESOURCE)
Found by this benchmark. Reproducer: `count_models(CNF chain of 2000 vars)` raised
an uncaught `RecursionError` in v3.7.0 instead of a typed result. Regression
test `test_dpll_counter_refuses_deep_recursion_instead_of_crashing` failed before
the fix. The counter now returns `UNKNOWN` with an explicit note (no count
claimed). Severity: medium (no wrong answer, but an unhandled exception in a
public API and MCP/Studio surface).

## F-003 H4-PAULI-01: native X/Y/Z observables -- SUPPORTED_IN_SCOPE
All 203 oracle tests pass. 150 randomized truncated circuits (>= 50 with a
non-zero bound) never exceeded their own certified bound; 120 untruncated random
circuits agree with Qiskit to 1e-9; every single-qubit gate x letter and every
two-qubit Pauli x {cx, cz, swap} entry matches to 1e-12; the Y-phase mutation is
caught. In 60 random truncated circuits the per-observable maximum was strictly
below the shared-sum bound in more than 10 (asserted), i.e. the new bounds are
tighter, never looser, by construction. `expectation_values(method="sparse_pauli")`
now runs once instead of once per basis-rotation pattern; its reported
`error_bound` per value is the observable's own bound (previously the group
total). Callers that read the old looser number get a smaller, still valid one.

## F-004 Path C "exact" label audit (D12, W3-03) — NOT REPRODUCED
The reported defect (Path C claims `exact=True`/`error_bound=0.0` while discarding
nonzero Schmidt values below the relative 1e-13 floor) is **not a defect at the Python
surfaces**. The code already: (a) keeps `error_bound=0.0` as "no deliberate budget
approximation"; (b) leaves `numerical_error_bound=None` with
`metadata["numerical_error_bound_reason"]` containing "not derived" (it does not compose
the per-SVD discarded mass into a state-norm bound it cannot derive); and (c) reports the
discarded mass only as `metadata["discarded_spectral_mass_diagnostic"]`. Existing tests
pin all three: `tests/test_correctness_contracts.py` (the discarded-mass test asserts
`numerical_error_bound is None`, the reason string, and that the diagnostic is never
presented as a bound). CLI and Studio serialise `result.to_dict()` and `metadata`, so the
diagnostic is visible there too. Remaining (not W3-03): the Studio/Web **UI copy** that
renders a result state should state the qualifier in plain language — deferred to the
Wave 7 provenance UI. Recorded as an audit, not a fix.

## F-005 Path B vs a plain dense statevector (P1-04/W3-04) — dense dominates
Raw data: `evidence/PATHB_DOMINANCE.json` (`scripts/bench_path_b_vs_dense.py --quick`,
3 repeats, 2000 shots, fixed seed, Qiskit `Statevector` as the dense baseline; git SHA,
Python and OS are in the JSON). Median wall seconds, ratio = Path B / dense:

| n | T | branches | dense (s) | Path B (s) | ratio |
|--:|--:|--:|--:|--:|--:|
| 8 | 0 | 1 | 0.0005 | 0.0013 | 2.7x |
| 8 | 8 | 256 | 0.0006 | 0.0373 | 57.7x |
| 12 | 0 | 1 | 0.0012 | 0.0024 | 2.0x |
| 12 | 4 | 16 | 0.0013 | 0.0168 | 12.6x |
| 12 | 8 | 256 | 0.0014 | 0.2524 | 181.2x |

Reading: on every measured case Path B is slower than a plain dense statevector, by 2x at
T=0 up to ~181x at T=8. Path B is a branch decomposition that contracts onto a dense
statevector and carries none of the sparse-extent advantage that would justify a
stabilizer-rank method. This is a finite measurement on this machine, not an asymptotic
claim. It is the input to the P1-04 decision (relabel Path B honestly as a low-T dense
branch-sum method and re-order the router under H4-ROUTE-01). No router change is made in
Wave 3; the decision is recorded in `DECISIONS.md`.


---

# V7 findings (E3, 2026-11-22)

Append-only. IDs are `F-V7-NN`. Each finding names its evidence and whether it is fixed. Category labels follow
AGENTS.md section 14.

## F-V7-01 Repeated gate operands were accepted as valid (CORRECTNESS, FIXED)
`qreg q[2]; cx q[0],q[0];` returned `EXACT` counts `{'00': 64}` on auto and on forced paths A, B and C, while Qiskit
and the browser refuse it (found by C1 while building the conformance corpus). Fixed at the shared layer in
`c655e92`: `gate_manifest.repeated_operands()`, a `QASMParseError(category="repeated_operand")` and the
terminal-measurement sorter refuse before routing. `tests/test_circuit_repeated_operands.py` covers every
multi-qubit gate in the manifest. Evidence: `waveC_C1.md`, `waveD_D1.md`. Status: FIXED.

## F-V7-02 `eval` on QASM parameter text in the shipped legacy bridge (SECURITY, FIXED)
SEC-M2: a hostile `.qasm` could reach `os` through the class graph despite `__builtins__: None`. Replaced by the
bounded `parse_angle_expression`; non-grammar text such as `pi**2` is now refused (a deliberate fail-closed
behaviour change, listed in `MIGRATION_V7.md`). Evidence: `SECURITY_AUDIT.md`, `waveD_D1.md`. Status: FIXED.

## F-V7-03 A 25-byte DIMACS header chose the allocation (RESOURCE, FIXED)
SEC-M1: `p cnf 10000000000000 0` led to `MemoryError`. `MAX_DIMACS_VARS = 1,000,000` now refuses with
`CNFFormatError` in `parse_dimacs`, shared by CLI, Studio, MCP and the Python API. A directly built `CNF(...)` is
not capped (documented). Evidence: `waveD_D2.md`. Status: FIXED.

## F-V7-04 Native `cq_hecs.exe` printed `VERIFIED` with no Vulkan device (HARDWARE/UX, FIXED for four commands)
P-03: `vrts`, `ghz`, `echo` and `maxcut` ignored the failed device initialisation. They now refuse with exit 3 and
a typed `vulkan_unavailable`; `--cpu-reference` is an explicit, labelled opt-in. `qasm`, `stress` and `test` still use
the legacy engine's software-emulation mode (B-V7-08). Evidence: `waveD_D3.md`. Status: FIXED, partly open.

## F-V7-05 External CaDiCaL aborts the interpreter after a complete result (INTEROP, OPEN, external)
python-sat with proof logging exits `0xC0000409` after the result on Windows, on CPython 3.13.13 and 3.14.6,
reproducible without cqhecs. cqhecs isolates the solve in a child and re-verifies in the parent; it does not hide
the abort. Evidence: `waveA_A4.md`, `waveD_D5.md`. Status: OPEN (B-V7-01).

## F-V7-06 Paths E, F and G do not clear their gates (RESEARCH, recorded negative results)
E is `INCONCLUSIVE` (wins mostly from a generic greedy order against a weak baseline, 12 to 16 qubits, E-5 not
implemented); F fails F-1 and F-4 on held-out seeds; G fails G-1 with a 0 percent win. The router is unchanged.
Evidence: `waveB_B5.md`. Status: RESEARCH_ONLY.

## F-V7-07 The wheel SBOM lists the build venv (RELEASE/LICENCE, OPEN)
The `38e799b` wheel SBOM has 23 components including `setuptools` and its vendored `autocommand` 2.2.2 declared
`LGPLv3`, and versions that differ from the EXE SBOM. It is not the runtime dependency closure. An uncommitted
`--closure-of` change targets it. Evidence: `LICENCE_REGISTER.md`, `PACKAGING_AUDIT.md` PK7-01. Status: OPEN.

## F-V7-08 The skip budget does not hold at the freeze (RELEASE, OPEN)
134 skips against a budget of 105, seven unbudgeted reasons, all environmental (native build directory not exported,
optional extras absent). The budget gate is the mechanism working as intended; it was not widened. Evidence:
`TEST_MATRIX.md` V7.A. Status: OPEN (B-V7-11).

## F-V7-09 The release body would be the 4.0.0 notes (DOCS/RELEASE, OPEN)
`release.yml` pastes `RELEASE_NOTES.md`, which still says "Version 4.0.0"; `check_version.py` does not catch it.
Evidence: `CLAIM_AUDIT.md`. Status: OPEN, P1 for publication (B-V7-12).

## F-V7-10 The release workflow does not check that a tag is on main (SECURITY/RELEASE, OPEN at the commit)
At `38e799b` there is no ancestry guard; an uncommitted edit adds one. Evidence: `SECURITY_AUDIT.md` SEC-P2-1.
Status: OPEN (B-V7-13).

## F-V7-11 Path B "exact" wording lacked the numerical-zero policy (DOCS/NUMERICAL, partly open)
Fixed in README and ARCHITECTURE (W1, C4). `docs/V2_IMPLEMENTATION_MATRIX.md` still says "algebraically exact
decomposition, float64 arithmetic" without the 1e-15 branch drop. Evidence: `CLAIM_AUDIT.md`. Status: OPEN (P3).

## F-V7-12 Hosted CI on the candidate is red although the Windows freeze run is green (INTEROP/RELEASE, OPEN)
At `38e799b` the PR runs fail on Linux and in packaging: five Python failures in the 3.11 Vulkan lane (four in the 3.12
to 3.14 lanes), the wheel clean-venv smoke (`Address already in use`) and the MSVC native package job (no Visual Studio
17 2022 on the runner); the Windows full-suite job was unfinished after two hours. The failing tests are platform or
environment sensitive (Linux manifest hash in the QG replay, a Windows exit status in two isolation tests, a Qiskit
version string in the web fixture, a missing capability symbol in the Linux core build). The Windows-only freeze figure
(4269 passed, 0 failed) hid all of them. Evidence: `evidence/waveE_E3.md`, `TEST_MATRIX.md` V7.E. Status: OPEN (B-V7-15).
