# v6 architecture decisions

## D6-01 — Baseline is `origin/main` `33723dd`, not stale local `main`

The local `main` ref was 41 commits behind. `origin/main` is the merge of the
v3.5.0 audit PR and has the same tree as the audit branch. The v3.6 branch was cut
from fetched `origin/main`. No reset or clean was used.

## D6-02 — Watched propagation is opt-in, not a silent replacement

`solve(..., propagation="watched")` and CLI `--engine watched` select the new
engine. The default remains the scan engine. Reasons:

- the scan engine is the readable reference and the certificate producer;
- the plan requires differential evidence before a default change;
- the watched engine must not change SATResult semantics, proof semantics or
  timeout behavior.

`SATResult.engine` reports `dpll-watched` so JSON consumers can tell which engine
ran. The tree-resolution certificate is still produced by `_CertifyingDPLL`, which
uses unit propagation only and shares no watch state.

## D6-03 — Parser normalizes duplicate literals; direct `CNF` construction stays strict

DIMACS permits `1 1 0`; the Python parser used to reject it while the native
parser accepted it. `parse_dimacs` now removes repeated literals inside one
clause, preserving first occurrence order. The strict `CNF` constructor still
rejects duplicates, so programmatic callers get an explicit error instead of a
silent normalization.

This changes a previously documented parser rejection and is therefore recorded
in `CHANGELOG.md`. The original input text digest is retained separately
(`original_sha256`) so normalization does not erase the input identity.

## D6-04 — UNSAT certification remains “checked by an independent implementation”, not “formally verified”

`check_refutation` and `cqhecs.drat` are independent of the search code but are
not verified by a proof assistant. No UI, README or release note may say
“formally verified” until a verified checker actually runs in this environment.

## D6-05 — No new parallelism or GPU work before the CPU propagation result

The v3.5 OMNIWAVE report shows GIL contention and slower batch/Vulkan paths. The
next measurable step is a correct CPU engine with evidence, not more workers.

## D6-06 — Research documents are additive

`research/v5/` stays immutable historical evidence. New findings go in
`research/v6/`. The root `PLAN.md` is not overwritten; the supplied v3.6 plan is
referenced from `research/v6/PLAN.md`.

## D6-07 — OMNIWAVE stays research-only; no primitive is promoted to the default path

The reproduced quick benchmark shows the same picture as v3.5: OMNIWAVE scalar
is close to DPLL on easy cases but slower on UNSAT, and batch/Vulkan modes are
slower end-to-end. The watched engine is the production-relevant improvement for
now. OMNIWAVE remains `experimental`; its field/GF(2)/boundary modules are not a
reusable library contract until a workload-specific win is demonstrated.

## D6-08 — CakeLPR is an optional verification tool, not a runtime dependency

`cake_lpr` (CakeML-verified assembly) accepted the LRAT proof generated from a
CaDiCaL DRAT proof for the pigeonhole vector. It is kept outside the package and
invoked through an optional test/env hook (`CQ_CAKE_LPR`). The project's Python
checker remains independent but not formally verified. The phrase “formally
verified” may refer only to the CakeML checker check on the stated proof/CNF,
not to the whole pipeline.

## D6-09 — GF(2) extraction is not wired into the production solver

The existing `cqhecs.omniwave.gf2` algebra is exact and exhaustively tested, but
there is no sound CNF-to-XOR extraction with an implication witness in the
production path. It stays research-only; no UNSAT may be reported from a parity
pattern unless the extraction and certificate are checkable.
