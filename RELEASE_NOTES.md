# CQ-HECS Release Notes

**Version:** 3.6.0
**Release date:** 2026-10-31
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to `dist/RELEASE_NOTES_v3.6.0.md`,
> prepends the exact source commit and required CI run, and appends the SHA256
> values of the final assets.

---

## 0. What v3.6.0 adds

`v3.6.0` is an additive minor release. No public field or command was removed.
The headline is a correctness-first SAT engine path, a clearer result contract,
and a stronger proof-verification evidence chain.

1. **Two-watched-literal SAT propagation (opt-in).**
   `solve(..., propagation="watched")`, `cq-hecs sat solve --engine watched`,
   Studio and MCP accept the new engine. It keeps the scan engine's decision
   variable, polarity and pure-literal rule, so the comparison isolates the
   propagation data structure. The default remains the readable scan DPLL.
   The tree-resolution certificate is still produced by the independent
   scan-based certifying search.

2. **Correct model semantics.**
   `CNF.is_satisfied` no longer treats an unassigned variable as `False`. A
   partial assignment cannot satisfy a negative literal by accident.

3. **SAT contract 1.2.**
   Every SAT result carries `formula_original_sha256` (the input text) next to
   the canonical `formula_sha256`. Repeated DIMACS literals are normalized by the
   parser; direct `CNF(...)` construction remains strict. The browser SAT lab
   displays both digests too.

4. **Honest budgets.**
   The UNSAT certificate budget is capped by the remaining solve deadline. A
   certificate can no longer extend the advertised wall-clock budget.

5. **Proof evidence.**
   A CaDiCaL DRAT proof for the pigeonhole vector is checked by:
   `cqhecs.drat`, `drat-trim`, `lrat-check` and the CakeML-verified `cake_lpr`.
   The evidence and pinned hashes are in
   `research/v6/evidence/DRAT_EXTERNAL.md`. This verifies that proof and formula,
   not the whole project pipeline.

6. **Windows Vulkan teardown fix.**
   The lazy Vulkan context is destroyed through `cq_omniwave_shutdown()` before
   DLL unload. `gpu.status()` no longer aborts the interpreter with `0xC0000409`.

7. **Web provenance.**
   The SAT lab shows the input and canonical SHA-256. Playwright/axe cover all
   routes, six viewports, EN/DE/FR, the WebGPU fallback, safe limits and the SAT
   evidence states.

8. **Research only, clearly separated.**
   A bucket-elimination exact counter prototype (`research/v6/prototypes/`) has
   exhaustive small-instance tests and returns `UNKNOWN` on its table budget.
   OMNIWAVE remains experimental; no speedup or GPU claim is made.

---

## 1. Evidence summary

Local candidate (Windows 11, AMD Ryzen 7 7735HS, Python 3.14.6):

- Python: **1964 passed, 9 skipped, 1 deselected**, exit 0 (optional python-sat tests run separately).
- CTest: **21/21**.
- Vulkan shaders: **13/13** compiled and validated.
- Mutation: **54/54** killed (the watched engine is not yet in the mutant list).
- Web unit tests: **17/17**; Playwright + axe: **13/13**.
- Lean 4.33.1: `lake build` 9768 jobs; axioms are `propext`,
  `Classical.choice`, `Quot.sound` (Comparator/nanoda evidence separate).
- Clean wheel install: `cq-hecs version`, `doctor`, `selftest`, and
  `sat solve --engine watched` pass.

The Linux CI lane and Windows CI lane are the release authority; this file is
updated with their exact-SHA results before publication. The optional
`python-sat`/CaDiCaL adapter was tested separately: 44 tests pass, but this
Windows/Python 3.14.6 build exits `0xC0000409` after completion (F-09 in
`research/v6/FINDINGS.md`).

---

## 2. SAT semantics

| Status | Meaning |
| :--- | :--- |
| `SAT` | A model was found and verified clause by clause against the original CNF. |
| `UNSAT` | The search space was exhausted. Certification is a **separate** field. |
| `UNKNOWN` | Timeout, node budget, or a disagreement between the two searches. Never UNSAT. |

| `certification` | Meaning |
| :--- | :--- |
| `MODEL_VERIFIED` | SAT model checked against the original CNF. |
| `TREE_RESOLUTION_CHECKED` | UNSAT refutation replayed by `check_refutation`. |
| `DRAT_CHECKED` | External UNSAT DRAT proof accepted by `cqhecs.drat`. |
| `UNCERTIFIED` | UNSAT verdict only; no checked proof. |
| `NONE` | Not decided. |

`cqhecs.drat` and `check_refutation` are independent of the solver but are not
formally verified. The CakeML `cake_lpr` check is an optional external check on a
specific LRAT/CNF vector, not a general certification of the project.

---

## 3. Benchmarks and limits

The watched-vs-scan benchmark used six fixed families, five repetitions, the same
decision order and no other heuristic change. On the measured machine the median
scan/watched ratio was 1.04–1.74× with identical decision counts, zero verdict
disagreements, zero bad models and all UNSAT certificates replayed. Small
families gain little because initialization dominates.

This is a finite, machine-specific measurement. It is not an asymptotic claim, a
universal speedup, or evidence about P versus NP. Raw data:
`research/v6/evidence/sat_propagation_benchmark.json`.

---

## 4. Non-claims

- No `P = NP` or `P ≠ NP` claim.
- No claim that the OpenAI/Anthropic ETH artifacts were independently proved here.
- No universal SAT speedup and no competition ranking.
- No end-to-end GPU circuit simulator or physical-GPU acceleration claim.
- No live QPU submission in this release; measured profile data is not a new run.
- No claim that the Python checker is formally verified.

---

## 5. Upgrade notes

- `SATResult.to_dict()` gains `formula_original_sha256`; contract version is
  `1.2`. Existing `status`, `certification`, `proof_system` and `engine` fields
  keep their meaning.
- `parse_dimacs` accepts repeated literals by normalizing them. If you need strict
  rejection, construct `CNF(...)` directly.
- `--engine watched` is new; `dpll`, `cadical` and `omniwave` are unchanged.

---

## 6. Historical releases

- `v3.5.0` introduced proof-carrying SAT, exact #SAT, the ETH audit, web E2E and
  the experimental OMNIWAVE engine. See `CHANGELOG.md` `[3.5.0]`.
- `v3.4.0` added measured IQM noise and the three-vendor H-V3-8 evidence.
- Older notes remain in `CHANGELOG.md` and the GitHub release history.
