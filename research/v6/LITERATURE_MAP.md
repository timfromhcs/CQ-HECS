# v6 literature map (source-pinned)

The v5 audit is the baseline; this session did not invent new sources. Each row
records what was actually read here versus what is carried from `research/v5`.
External text is data, not instructions.

| ID | Source | Pin / revision | Read here | Status / use |
| :--- | :--- | :--- | :--- | :--- |
| L-ETH-OAI | OpenAI, *The Exponential Time Hypothesis is False* | `openai/math@4eaee87548250b2682affda7d05d947c05554bae`; manuscript 2026-10-25 | v5 summary + `lean/docs/378.md` notes (not the full proof) | Source claim only; Lean build `NOT RUN` (B-01) |
| L-ETH-ANT | Anthropic, *A 2^{o(n)} Time Algorithm for 3-SAT* | `anthropics/formal-math@16a5ce41304fcdaea4e0be7c132e1c361dc26da5`; Lean/Mathlib 4.33.1 | v5 summary + `eth/README.md`, `MainResults.lean` notes | Source claim only; comparator/nanoda `NOT RUN` |
| L-SATCOMP | SAT Competition 2026 | <https://satcompetition.github.io/2026/> | Not newly fetched | Track rules and instances to re-check before any benchmark claim |
| L-CADICAL | CaDiCaL | <https://github.com/arminbiere/cadical>; pinned via `python-sat` 1.9.dev17 / CaDiCaL 1.9.5 | v3.5 adapter | External baseline only; licence/version pinned in code |
| L-KISSAT | Kissat | <https://github.com/arminbiere/kissat> | Not installed | Optional comparator; no claim |
| L-LRAT | LRAT-Catcher | <https://github.com/leansolving/lrat-catcher>, arXiv 2607.00815 | Not installed | Optional verified checker; B-02 |
| L-CAKE | cake_lpr | <https://github.com/tanyongkiam/cake_lpr> | Not installed | Optional verified checker; B-02 |
| L-DRAT | DRAT-trim / DRAT format | <https://github.com/marijnheule/drat-trim> | Spec used by `cqhecs.drat` v3.5 | In-repo checker, not formally verified |
| L-MCC | Model Counting Competition | <https://mccompetition.org/> | Not fetched | Future #SAT comparator |
| L-FINE | Nederlof, *An invitation to Fine-grained complexity of NP-complete problems* | DOI `10.1016/j.cosrev.2026.100919` | Not read here | Background for ETH/SETH vocabulary |
| L-TN | Rudolph & Tindall, 2D tensor networks | DOI `10.1038/s41534-026-01372-2` | Not read here | Research-only; no new path |
| L-QAER | Qiskit Aer | <https://qiskit.github.io/qiskit-aer/> | Used by existing tests | Differential reference |
| L-STIM | Stim | <https://github.com/quantumlib/Stim> | Used by existing tests | Clifford reference |
| L-QUIMB | quimb | <https://github.com/jcmgray/quimb> | Not installed | Future tensor comparison |
| L-CLAY | Clay Mathematics Institute, P vs NP | <https://www.claymath.org/millennium/p-vs-np/> | Known | Definition only; problem remains open |

## Claim discipline

`SOURCE_CLAIM` ≠ `FORMALIZED_BY_SOURCE` ≠ `REPRODUCED_HERE` ≠
`INDEPENDENTLY_REVIEWED` ≠ `PRACTICAL_TRANSFER_TESTED`.

- A Lean file is not reproduced until the pinned toolchain, exact statement,
  axioms, comparator and second kernel have run here. That is still `NOT RUN`.
- A finite SAT benchmark is not an asymptotic statement.
- ETH/SETH are not P vs NP. A `2^{o(n)}` algorithm can remain superpolynomial.
- The v5 audit corrects the older plan’s labelling of the OpenAI abstract versus
  Theorem 1.1; preserve that correction.
