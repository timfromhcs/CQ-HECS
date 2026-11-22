# SAT_PROOF_REVIEW.md — proof/certificate pipeline review (V7 W2, §11)

Created 2026-11-21 on branch `agent/v6-rc`. Reviews the shipped certificate pipeline against
the V7 §7.4 "proof trust ladder" and the V7 §11 requirements. Based on the code as read on this
checkout (`cqhecs/sat.py`, `sat_external.py`, `omniwave/engine.py`, `drat.py`, `unified.py`).

## Trust ladder — what is actually implemented

| Rung | Meaning | Implemented? | Evidence |
|---|---|---|---|
| `MODEL_VERIFIED` | a SAT assignment re-checked clause-by-clause against the **original** CNF | YES | `sat.py` `SATResult.model_verified`; `unified.solve_unified` re-verifies before returning SAT |
| `TREE_RESOLUTION_CHECKED` | a tree-resolution refutation replayed by the in-repo checker | YES | `sat.py` `_certify`/`check_refutation`; `certification` returns `TREE_RESOLUTION_CHECKED` |
| `DRAT_CHECKED` | a DRAT proof accepted by the in-repo forward RUP/RAT checker | YES | `drat.py` `check_drat`; `sat_external` and `omniwave` use it |
| `EXTERNAL_DRAT_CHECKED` | same vector accepted by a pinned external checker (drat-trim) | NOT RUN here | lane exists only as a test that skips without the tool (`test_drat_external_vector.py`) |
| `LRAT_CHECKED` | an LRAT proof accepted by a selected checker | NO | no LRAT writer/producer in the package |
| `CAKELPR_CHECKED_VECTOR` | a vector accepted by the CakeML `cake_lpr` checker | NO | no lane |
| `FORMALIZED_LEMMA` / `FORMALLY_VERIFIED_COMPONENT` | a shipped lemma/component checked in Lean | NO | V7 W4 not started (no Lean toolchain here) |

## Invariants the pipeline enforces (all covered by tests)

- **A model is never trusted from the engine.** `solve_unified` re-runs `formula.is_satisfied`
  on the returned assignment; a failing model is refused (`tests/test_unified_solver.py`).
- **A status is never upgraded.** An `UNSAT` keeps the engine's proof status; `certified` /
  `proof_level` come from the engine's own result, never from `status == UNSAT` alone (D3, W3-09).
- **A rejected/undecided/disabled proof is not "checked".** `proof_status` is one of
  `accepted`/`rejected`/`undecided`/`disabled`; `certification` is `UNCERTIFIED` unless the
  checker accepted it. `solve_unified(require_certified=True)` returns `UNKNOWN` for an
  uncertified `UNSAT`.
- **Budget exhaustion is undecided.** `drat.py` returns `valid=None` on timeout/size, never
  `True`; the checker documents itself as "not formally verified, unlike cake_lpr".
- **The proof check fits the deadline.** The external adapter and OMNIWAVE bound the proof
  budget by the remaining time (W3-10); a search that refutes the formula but runs out of proof
  time returns `UNKNOWN` (`tests/test_unified_deadline.py`).
- **Deletions only weaken.** A DRAT `d` line removes one copy; deleting an absent clause is an
  error. Honouring deletions cannot make an invalid refutation valid (`drat.py` docstring).

## Required but not yet shipped (V7 W9 obligations)

1. **External verification lane** with a pinned `drat-trim` (and optionally `cake_lpr`),
   producing `EXTERNAL_DRAT_CHECKED` / `CAKELPR_CHECKED_VECTOR` on fixed vectors; a missing
   tool is `NOT RUN`, never PASS. (Linux/nightly; not run here.)
2. **LRAT path** with a named producer and a pinned checker (CakeML `cake_lpr`), scoped to the
   exact vector.
3. **MaxSAT certificates** — the `maxsat` solver returns an optimum; an optimality certificate
   is not shipped. Do not present it as proof-carrying.
4. **Separator/elimination #SAT** returns an exact integer (no certificate); it is a count, not
   a proof, and must not be labelled as one.
5. **No asymptotic/ETH claim** from any of the above; the ETH-formalization artifacts are
   external evidence (`research/v6/evidence/LEAN_ETH_BUILD.md`, `COMPARATOR_ETH.md`), not a
   CQ-HECS proof. The paper-vs-formalized runtime-formula distinction (PLAN.md §3.1) is carried
   into `LITERATURE_MAP.md`.

## Verdict

The shipped pipeline is sound and honest about its scope: it certifies models and (tree-)DRAT
refutations, refuses to upgrade a verdict, and treats budget exhaustion as undecided. It does
**not** claim external or formal verification, and no CQ-HECS artifact is `FORMALLY_VERIFIED`.
W9 materialises the external/LRAT lanes; W4/FORMAL_ASSURANCE materialises any Lean lemma.

## Wave A (A4) addendum, 2026-11-21

- Adapter isolation (W3-11): `sat_external.solve_external_isolated` runs CaDiCaL in a child; the
  parent re-verifies models and DRAT proofs, so the child is untrusted. Crash/hang/garbage => UNKNOWN.
  The python-sat abort 0xC0000409 was reproduced on Python 3.13.13 at interpreter exit after a
  `with_proof` SAT solve; it is recorded in the result note, not suppressed.
- DRAT tamper matrix on the fixed pigeonhole vector: `tests/test_drat_tamper.py`. Trust label stays
  `DRAT_CHECKED`; `EXTERNAL_DRAT_CHECKED`, `LRAT_CHECKED`, `CAKELPR_CHECKED_VECTOR` remain NOT RUN (no in-repo LRAT reader).
- MaxSAT: `max_sat_checked` (`hcs.sat.maxsat.v1`) never reports a size limit as an optimum; the optimum
  is exhaustive and re-verified, still with no proof certificate (item 3 above remains true).
- Separator #SAT: `preflight=True` refuses before allocation using the `2**(w+1)` bound (item 4 above
  remains true: an exact count, not a proof).
- Details: `research/v7/evidence/waveA_A4.md`.
