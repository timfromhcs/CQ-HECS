# waveA_A5.md — A5: baseline delta and W5 Lean (Path A/D specification lemmas)

Branch `release/v7-stable`, HEAD `6fe4f01`, 2026-11-21. Nothing committed (integrator commits).

## 1. Baseline delta (2899/105 vs 2896/109)

Command (single full run, scratchpad outputs):
`python -m pytest tests/ -q -rs -p no:cacheprovider --junitxml=<scratch>/a5.xml` ->
`2896 passed, 109 skipped, 1 deselected in 459.45s` (Python 3.13.13, pytest 9.2.0).
`python scripts/skip_budget.py --junitxml a5.xml --check` -> FAILED, `unbudgeted skip reason (4x)`.

Cause (full table in `BASELINE_V7.md` addendum): 4 tests skip because `qiskit-ibm-runtime` is not
installed in the 3.13.13 interpreter (baseline ran on 3.14.6, which has 0.51.0); +1 passing test
`test_oversized_body_is_consumed_before_the_413` from `2f0d362`. Verified:
`py -3.14 -m pytest tests/test_v3_calibration_bridge.py tests/test_v3_noisy_expectation.py` -> 33 passed, 0 skipped.
`SKIP_BUDGET.json` not modified.

## 2. Lean (W5): L-STAB-01 and L-PAULI-01

Toolchain Lean 4.33.1, Mathlib `0df444a`. All commands run from `formal/` with stdin from `/dev/null`
and output redirected to a file (a pipe or an open stdin stalls `lean` on this host, as in LEAN_BUILD.md).

- `lake build` -> exit 0, `Build completed successfully (8710 jobs)` (~7 min; Mathlib rebuilt, same as W4).
- `lake env lean scripts/PrintAxioms.lean` -> exit 0. All 19 listed theorems
  (the 2 Bound lemmas + 17 new) report `[propext, Classical.choice, Quot.sound]` only. `decide` proofs
  introduced no extra axiom.

New files: `formal/CQHECS/Pauli.lean`, `formal/CQHECS/Stabilizer.lean`; `CQHECS.lean`,
`scripts/PrintAxioms.lean`, `formal/README.md` updated.

| Theorem | Statement | Code it specifies |
|---|---|---|
| `pauli_mul` | `(X^a Z^b)(X^c Z^d) = (-1)^(bc) X^(a+c) Z^(b+d)` (2x2 complex) | Path D stored basis `X^x Z^z` |
| `pauli_comm` | `P(a,b)P(c,d) = (-1)^(ad+bc) P(c,d)P(a,b)` | symplectic form <-> commutation (single qubit) |
| `h_conj` `s_conj` `x_conj` `y_conj` `z_conj` | `U Q(a,b) U^dag = (-1)^k Q(...)` on Hermitian letters; H via `hh/√2` | Path A `apply_h/s/x/y/z` sign (`r`) and bit rules |
| `sgd_mul_sg`, `hh_mul_hh` | `S†S = 1`, `hh² = 2·1` | side facts for the above |
| `omega_hGate` `omega_sGate` `omega_cxGate` `omega_czGate` `omega_swapGate` | each tableau gate bit-update preserves `omega(p,q) = Σ x_i z'_i + z_i x'_i` over F_2 | `apply_h/s/cx/cz/swap` bit columns |
| `omega_run`, `tableau_invariant` | any supported gate list preserves `omega` for all row pairs; initial `D_i=X_i`, `S_j=Z_j` relations (stabilizers commute, destabilizers commute, `D_i`/`S_j` anticommute iff `i=j`) persist | Path A tableau invariant |

Existing L-BOUND-01 / 01b (`Bound.lean`) is the Path D bound; unchanged.

### Exact assurance level

`FORMALIZED_LEMMA` for the named specification statements. They are theorems about hand-written Lean
models. They are **not** `REFINEMENT_LINKED` (no proof that the NumPy code implements the model),
not `STATEMENT_MATCHED` and not `KERNEL_RECHECKED` (Comparator/nanoda not run for these). The Lean
`Gate`/`act` model covers H, S, Sdg (S thrice), CX, CZ (= H·CX·H), SWAP on the (x,z) bits only.

NOT formalized: CX/CZ/SWAP sign (`r`) column (`r ^= xc zt (xt ^ zc ^ 1)`); `measure`/`_row_sum`; X/Y/Z
gates beyond the single-qubit sign rules; Path D conjugation for non-Clifford (T, rx/ry/rz) gates;
Path D term-expansion/truncation bookkeeping (only the real-arithmetic bound is proved); n-qubit
lifting of `pauli_comm` (omega = 0 iff commute is proved single-qubit only).

## 3. Python spec-correspondence tests (new files, oracle tests only)

- `tests/test_stabilizer_spec_correspondence.py` (66 tests): bit update vs Lean local rules on
  arbitrary rows; `omega` invariance over random 2-6 qubit circuits for all row pairs; rows with signs
  vs dense `U P0 U†` (n<=3); single-qubit sign table vs Lean statements (incl. Sdg); all rows incl.
  signs vs `stim.Tableau` (n<=7, 10 seeds); negative control (dropping the S sign update is caught).
- `tests/test_path_d_spec_correspondence.py` (66 tests): `pauli_mul`/`pauli_comm` on the stored basis
  (all 16 combos each); observable `coeff` = `i^#Y` Hermitian convention; `conjugation_matrix` equals
  `U†PU` for h,s,sdg,x,y,z,t,tdg; Path D reproduces Lean H/X/Y/Z sign rules; truncation inequality
  with `|e|<=1`; certified per-observable bound covers the true Qiskit-statevector error under
  truncation (8 seeds, asserts resolved).

Commands: `python -m pytest tests/test_stabilizer_spec_correspondence.py tests/test_path_d_spec_correspondence.py tests/test_path_d_pauli_observables.py -q`
-> 66 + 269 (incl. the existing 203) passed. `flake8 --select=E9,F` on the two new files: clean.
Qiskit 2.6.1 and Stim 1.16.0 present, so nothing was skipped.

## 4. NOT RUN

- Comparator / nanoda statement + kernel recheck of the new Lean theorems.
- Mutation harness (`scripts/run_mutation_tests.py`) — not run; the new tests were not added as mutation probes.
- Full pytest suite after adding the new test files (only the targeted files; the single full run was
  before them). Expected suite totals therefore rise by 132 passing tests.
- Native/WASM paths: untouched.
