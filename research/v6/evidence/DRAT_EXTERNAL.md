# External DRAT/LRAT verification (M5-01/M5-02)

**Date:** 2026-10-31
**Goal:** check the in-repo `cqhecs.drat` result against independently developed
checkers, and exercise an LRAT proof with a CakeML-verified checker.

## Inputs

| Item | Value |
| :--- | :--- |
| Formula | `benchmarks/sat/pigeonhole_6_5.cnf` (30 vars, 81 clauses) |
| Formula SHA-256 | `72cddfabadbaf3cdfee8d8032f30e53d72159861d24b250373d1c849c9f611ea` |
| Solver | CaDiCaL 1.9.5 via `python-sat` 1.9.dev17 |
| DRAT proof | `research/v6/evidence/drat/pigeonhole_6_5.cadical.drat` |
| DRAT SHA-256 | `a47360cab8fbc730e8d4d111bfafbccde58c305b148e84829725414bb73604b9` |
| LRAT proof | `research/v6/evidence/drat/pigeonhole_6_5.cadical.lrat` |
| LRAT SHA-256 | `06cdff8d91f965afb85d77e2918801fe9321f8e4a217802926706d07a512a623` |
| External checker | `drat-trim` at `2e3b2dc0ecf938addbd779d42877b6ed69d9a985` |
| Formally verified checker | `cake_lpr` at `a36874a8b750b43fe4b385b8ddbf5b033e46a3fa` (CakeML) |

The proof was generated with:

```python
from pysat.solvers import Solver
with Solver(name="cadical195", bootstrap_with=clauses, with_proof=True) as s:
    s.solve()
    proof = s.get_proof()
```

## Results

`cqhecs.drat.check_drat`:

```
valid=True lemmas=156 rat_lemmas=0
empty clause derived after 156 lemmas
```

`drat-trim` (built in WSL with `gcc -std=gnu99 -O2`):

```
c 81 of 81 clauses in core
c 122 of 157 lemmas in core using 1898 resolution steps
c 0 RAT lemmas in core; 0 redundant literals in core lemmas
s VERIFIED
c verification time: 0.096 seconds
```

Command (from the repository root):

```bash
wsl -e bash -lc "cd '/mnt/d/Quantum EMU/CQ-HECS/.local/tools/drat-trim' && \
  ./drat-trim '/mnt/d/Quantum EMU/CQ-HECS/benchmarks/sat/pigeonhole_6_5.cnf' \
              '/mnt/d/Quantum EMU/CQ-HECS/research/v6/evidence/drat/pigeonhole_6_5.cadical.drat'"
```

## LRAT conversion and CakeML check

`drat-trim -L` converted the DRAT proof to LRAT (9,223 bytes):

```text
c 81 of 81 clauses in core
c 122 of 157 lemmas in core using 1898 resolution steps
s VERIFIED
```

`lrat-check` (drat-trim's independent LRAT checker) then reported `c VERIFIED`.

`cake_lpr`, built from the pinned CakeML-generated assembly, checked the same
LRAT file against the DIMACS formula:

```text
s VERIFIED UNSAT
```

Binary provenance:

- `cake_lpr` SHA-256: `567c0dfe400239149df1ea7382365840746cdae284d8a321661a813fef884fa6`
- `cake_lpr.S` SHA-256: `c5e6f9f60ea674c3dc33f442968fbcad85886242330954795c04347872c51276`
- LRAT SHA-256: `06cdff8d91f965afb85d77e2918801fe9321f8e4a217802926706d07a512a623`

Command:

```bash
wsl -e bash -lc "cd '/mnt/d/Quantum EMU/CQ-HECS/.local/tools/cake_lpr' && \
  ./cake_lpr '/mnt/d/Quantum EMU/CQ-HECS/benchmarks/sat/pigeonhole_6_5.cnf' \
             '/mnt/d/Quantum EMU/CQ-HECS/research/v6/evidence/drat/pigeonhole_6_5.cadical.lrat'"
```

This is the first check in this project performed by a checker whose soundness is
backed by the CakeML formal verification chain, not merely by independent C code.
It verifies **this proof and formula only**; it does not verify the solver, the
DRAT-to-LRAT converter, or any general claim about CQ-HECS.

## Interpretation

- The in-repo checker and an independently written checker agree on this proof.
- `cake_lpr` (CakeML-verified) accepted the LRAT conversion of the same proof.
- This is one external vector, not a proof of checker correctness.
- `drat-trim` and `cqhecs.drat` are independent implementations; `drat-trim` is
  not formally verified. The CakeML check covers the LRAT proof against the CNF,
  not the project's Python checker or the converter.
- The proof file is data, not an instruction. Do not execute it.
- `drat-trim` and `cake_lpr` are not runtime dependencies; they are optional
  verification tools.

## Next

- Add the CakeLPR check to CI as an optional pinned job, so the evidence is
  reproduced on every release candidate.
- Generate vectors from a second producer (not only CaDiCaL).
- Keep the wording precise: the **checker** is formally verified; the project's
  whole proof pipeline is not.
