# Decisions (v5)

## D-01 Release target is v3.5.0, not v4.0.0

All changes are additive: new result fields, new functions and an optional
extra. No public Python, C-ABI, CLI or JSON field is removed or reinterpreted. Under SemVer
that is a minor release. `research/v4/ROADMAP_V4.md` criteria 2 (M-FIT-2 decision) and 3
(CDCL + DRAT in CI for the built-in engine) are still open.

## D-02 External solver plus an in-repo DRAT checker, instead of drat-trim

`python-sat` (already pinned in CI as `1.9.dev17`) bundles CaDiCaL 1.9.5, which emits DRAT
proofs. No drat-trim, cake_lpr or GRAT binary is available on this machine or in CI. A small
**forward DRAT checker** (`cqhecs.drat`) is written independently of the solver. It accepts a
proof only if every added lemma is RUP or RAT against the current clause database, the
proof derives the empty clause, and the formula digest matches. Status mapping:

- CaDiCaL SAT → model re-checked clause by clause against the original CNF → `SAT`.
- CaDiCaL UNSAT and the DRAT check passes → `UNSAT`, `certification = DRAT_CHECKED`.
- CaDiCaL UNSAT and the check fails or is out of budget → `UNSAT`, `certification = UNCERTIFIED`.
- `python-sat` missing → structured `BACKEND_UNAVAILABLE`, never a silent fallback.

This is a checker independent of the solver's own code, but it is not formally verified the way
`cake_lpr` is. The docs say so.

## D-03 Certification is a separate field, status values are unchanged

`status` stays `SAT | UNSAT | UNKNOWN` (existing callers keep working). A new
`certification` field takes one of `MODEL_VERIFIED | TREE_RESOLUTION_CHECKED | DRAT_CHECKED |
UNCERTIFIED | NONE`. `certified` (bool) is kept. `contract_version` is added.

## D-04 #SAT gets its own function and result type

`count_models` returns `COUNTED` with an exact integer, serialized as a decimal string so
large counts survive JSON, or `UNKNOWN` on budget. It never reuses `SAT`/`UNSAT`.

## D-05 Research prototypes live under `research/v5/prototypes/`

Nothing there is imported by `cqhecs`. Each prototype has its own exhaustive-oracle test.

## D-06 OMNIWAVE ships in v3.5.0 as an experimental engine

The add-on asked for OMNIWAVE in the same stable release. It is additive (a new
`engine` value, a new module, new endpoints), so it fits a minor release. It is marked
experimental (`cqhecs.omniwave.EXPERIMENTAL = True`, docs, Studio tag) because its
performance is far behind CaDiCaL and its representation modules may change. Its
correctness contract is not experimental: SAT needs a verified model and UNSAT needs a
DRAT proof accepted by `cqhecs.drat`. The GF(2) prototype from D-05 moved into
`cqhecs.omniwave.gf2`; `research/v5/prototypes/gf2_counting.py` re-exports it.

## D-07 The Vulkan BCP kernel is verified by default, not trusted

`evaluate_batch_vulkan(..., verify=True)` compares every GPU pass with the CPU
reference and raises on a difference; the engine uses it by default
(`OmniwaveConfig.verify_gpu`). A wrong GPU answer would cost soundness only through
the search order (the DRAT check would still reject a bad UNSAT), but a silent kernel
bug must not reach users. CTest checks the kernel against a C++ reference so CI with
lavapipe covers it without Python. No GPU speedup is claimed.
