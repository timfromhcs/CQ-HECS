# FORMAL_ASSURANCE_PLAN.md — Lean workspace and theorem backlog (V7 W4, §7)

Created 2026-11-21 on branch `agent/v6-rc`. Plan for the CQ-HECS formal-assurance workspace.
Status: **IN_PROGRESS** (Lean workspace builds on the pinned toolchain; L-BOUND-01 and L-BOUND-01b
formalized with a standard-axiom audit; L-STAB-01 next). This is a
plan and an honest boundary statement, not a claim of verification.

## 1. Goal and boundary

A small, isolated Lean 4 + Mathlib workspace that proves **specification-level** invariants of
the algorithms CQ-HECS ships, with a pinned toolchain, an axiom audit, and a Comparator/nanoda
statement-equality check. A proved specification is **not** a refinement proof of the Python/C++
implementation (V7 §7.4); the assurance level is displayed per lemma.

## 2. Toolchain and dependencies (V7 §7.2)

- **Lean 4.33.1 + Mathlib 4.33.1**, installed via elan — the same pin the Anthropic
  `formal-math` ETH artifact uses (`research/v6/evidence/LEAN_ETH_BUILD.md`), so caches and
  tooling overlap. `lean-toolchain` pins `leanprover/lean4:v4.33.1`.
- Licences: Lean 4 (Apache-2.0), Mathlib (Apache-2.0). Audit Lean-Quantum, Lean-QIT, FloatLib,
  Comparator, nanoda licences before depending on them; record rows in `LICENCE_REGISTER.md`.
- Nothing in the shipped Python/C++ package depends on Lean; Lean stays developer/CI-only.

## 3. Theorem backlog (V7 §7.3 + AGENTS §4.3)

Ordered by tractability/impact; each maps to a shipped invariant and a Python test already in
the repo.

| ID | Lemma (specification) | Code invariant | Python test | Lean status |
|---|---|---|---|---|
| L-STAB-01 | A Clifford gate update preserves the symplectic (tableau) form | `path_a_stabilizer.py` `apply_*` | `test_four_path_architecture.py`, mutation `qubit_bit_order`/`cz_conjugation` | NOT_STARTED |
| L-PAULI-01 | Pauli multiplication and phase rules; `U†PU` for the supported gates | `path_d_sparse_pauli.py`, `expectation.py` | `test_path_d_pauli_observables.py`, mutation `pauli_y_phase` | NOT_STARTED |
| L-BOUND-01 | `|⟨O_exact⟩ − ⟨O_kept⟩| ≤ Σ_{P∈D} |c_P|` under the code's truncation convention | Path D per-observable bound | F-003; mutation `pauli_bound_accounting` | **FORMALIZED_LEMMA** (`truncation_bound` + Path-D form `expectation_truncation_bound`); `evidence/LEAN_BUILD.md` |
| L-SEP-01 | `#F = Σ_s #F_L(s)·#F_R(s)` for a separator; count-preserving transformations | `sat_separator.py` | `test_sat_separator.py`, mutation `separator_count` | NOT_STARTED |
| L-XOR-01 | An extracted parity equation is entailed by the CNF, with a witness | not shipped (W9) | — | NOT_STARTED |
| L-SAT-01 | Exhaustive split coverage ⇒ parent resolution lemma (OMNIWAVE/DPLL soundness) | `omniwave/engine.py`, `sat.py` | `test_omniwave.py`, `omniwave_sound` mutant | NOT_STARTED |
| L-RESULT-01 | Result-contract consistency (an `UNRESOLVED` result cannot expose a certified value) | `result.py` | `test_correctness_contracts.py` | NOT_STARTED |
| L-MPS-01 | The MPS logical↔site permutation is bijective and the mapped gate sequence is equivalent | `path_c_mps_exact.py` | (ordering is research; W6/W7) | NOT_STARTED |

Each lemma record states: exact statement, assumptions, quantifiers, the code mapping, the
Python oracle, and the assurance level (below).

## 4. Proof-to-code assurance ladder (V7 §7.4)

`EQUIVALENT_TO_SOURCE` (statement matches the artifact's `Challenge.lean`), `FORMALIZED_LEMMA`
(the named lemma builds with standard axioms), `STATEMENT_MATCHED` (Comparator agrees on the
statement), `KERNEL_RECHECKED` (nanoda accepts), `REFINEMENT_LINKED` (implementation linked to
the spec — **no CQ-HECS lemma is here**), `IMPLEMENTATION_VERIFIED` (none). A green `lake build`
is `FORMALIZED_LEMMA` only.

## 5. Build, CI and audit (V7 §7.5)

- Local: `lake exe cache get`, `lake build`, `lake env lean scripts/PrintAxioms.lean`.
- Axiom audit: expect only `propext`, `Classical.choice`, `Quot.sound`.
- Optional CI lane (isolated; Linux): build + axiom print + Comparator/nanoda on the CQ-HECS
  lemmas, mirroring the ETH-artifact method (statement equality against a `Challenge.lean`).
- Provenance: pin `lean-toolchain`, Mathlib revision, and record each build in
  `research/v7/evidence/` with the exact command and SHA.

## 6. Current status

- elan installed; **Lean 4.33.1 / Lake 5.0.0 present** (see `evidence/LEAN_ENV.md`).
- External artifacts downloaded for statement comparison: `anthropics/formal-math` (pinned
  `16a5ce4…`, containing `eth`, `zeta23`, `3sum-apsp`) and `openai/math`.
- **The CQ-HECS workspace builds** (`lake build`, 8708 jobs, exit 0) and both `Bound.lean` lemmas
  pass the axiom audit (`[propext, Classical.choice, Quot.sound]`) — `evidence/LEAN_BUILD.md`. The
  `eth`-artifact build itself was not re-run to completion this session; that is `NOT RUN`.
- **L-BOUND-01 / L-BOUND-01b are `FORMALIZED_LEMMA`.** Next: **L-STAB-01** (stabilizer symplectic
  invariant) and the Comparator/nanoda statement checks.
