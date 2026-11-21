# CQ-HECS formal workspace (Lean 4)

Specification-level Lean lemmas for shipped CQ-HECS invariants (V7 W4, `research/v7/FORMAL_ASSURANCE_PLAN.md`).

**Boundary.** A proved specification is a `FORMALIZED_LEMMA`, **not** a refinement proof of the
Python/C++ implementation. No CQ-HECS implementation is `FORMALLY_VERIFIED`. The code mapping and
the Python oracle for each lemma are recorded in `FORMAL_ASSURANCE_PLAN.md`.

## Toolchain

- `lean-toolchain`: `leanprover/lean4:v4.33.1` (elan).
- `mathlib` pinned to `leanprover-community/mathlib4@0df444a360eaa60ab8c11dca51a86af692955474`
  (the same pin as the external `anthropics/formal-math` ETH artifact, so the compiled cache is
  shared).

## Build

```sh
lake exe cache get      # download precompiled Mathlib
lake build
lake env lean scripts/PrintAxioms.lean   # axiom audit (added with the first lemma set)
```

A green build is `FORMALIZED_LEMMA` for the named lemma only. Comparator/nanoda statement checks
(the ETH-artifact method) are a later W4 step.

## Lemma status

| Lemma | File | Status |
|---|---|---|
| L-BOUND-01 (Path D truncation bound, real-arithmetic form) | `CQHECS/Bound.lean` | **FORMALIZED_LEMMA** — `lake build` green; `#print axioms` → `[propext, Classical.choice, Quot.sound]` |
| L-BOUND-01b (Path D form `\|∑ cᵢeᵢ\| ≤ ∑\|cᵢ\|` with `\|⟨P⟩\| ≤ 1`) | `CQHECS/Bound.lean` | **FORMALIZED_LEMMA** — same build and axiom audit |
| L-STAB-01, L-PAULI-01, L-SEP-01, L-SAT-01, L-RESULT-01 | — | backlog |

`FORMALIZED_LEMMA` means the named specification statement builds with only the standard axioms; it
is **not** a refinement proof of the Python/C++ implementation (V7 §7.4). Exact commands and output:
`research/v7/evidence/LEAN_BUILD.md`.
