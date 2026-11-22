# LEAN_BUILD.md — CQ-HECS Lean workspace build and axiom audit (V7 W4)

Recorded 2026-11-21 on branch `agent/v6-rc`, completing the build the previous session started but
did not finish (`evidence/LEAN_ENV.md` §6). Toolchain: Lean 4.33.1 / Lake 5.0.0-src+819816b, Windows
x86_64 (`leanprover/lean4:v4.33.1`); Mathlib pinned to
`leanprover-community/mathlib4@0df444a360eaa60ab8c11dca51a86af692955474` (the same pin as the
external `anthropics/formal-math` ETH artifact). Nothing in the shipped Python/C++ package depends
on Lean.

## 1. Commands and results

```sh
cd formal
lake exe cache get          # exit 0, "Completed successfully in 319330 ms"
lake build                  # exit 0, "Build completed successfully (8708 jobs)"
lake env lean scripts/PrintAxioms.lean   # exit 0
```

`PrintAxioms.lean` output (verbatim):

```
'CQHECS.truncation_bound' depends on axioms: [propext, Classical.choice, Quot.sound]
'CQHECS.expectation_truncation_bound' depends on axioms: [propext, Classical.choice, Quot.sound]
```

Both lemmas therefore build with only the three standard axioms — the same exit criterion the
external ETH artifact uses. Level: **`FORMALIZED_LEMMA`** for the two named lemmas only (V7 §7.4);
this is not a refinement proof of the shipped implementation.

## 2. Lemmas proved (`formal/CQHECS/Bound.lean`)

- **L-BOUND-01** `truncation_bound` — `|∑_{i∈s} cᵢ| ≤ ∑_{i∈s} |cᵢ|`: the real-arithmetic triangle
  inequality behind the Path D truncation bound.
- **L-BOUND-01b** `expectation_truncation_bound` — for Pauli expectations `e` with `|e i| ≤ 1`,
  `|∑_{i∈s} cᵢ·eᵢ| ≤ ∑_{i∈s} |cᵢ|`. This is the Path D bound with the physical hypothesis
  `|⟨P⟩| ≤ 1` explicit; `|⟨P⟩| ≤ 1` is itself assumed (and separately testable), not proved here.

## 3. Honest notes and anomalies

- **Mathlib was rebuilt from source despite the cache.** `lake exe cache get` reported
  "Decompressing 3447 already-cached file(s) (5243 already decompressed); No files to download", yet
  `lake build` still compiled ~8708 jobs (most of Mathlib). The build is therefore reproducible but
  not cache-fast on this host; it took roughly 25 minutes wall time.
- **The first attempt stalled.** The initial background run piped `lake build` through
  `Tee-Object`; the `lean` process went idle (≈0 CPU, no disk I/O) with the process still alive. It
  was killed and re-run with plain file redirection (`cmd /c "lake build > log 2>&1"`), after which
  it completed and reported real diagnostics. No Lean/Mathlib files were modified.
- **First diagnostics were real and were fixed.** The scaffolding theorem used the `∑ i in s, f i`
  notation, which this environment did not resolve (`unexpected token 'in'; expected ','`). The
  lemmas now use `s.sum (fun …)` directly and build; L-BOUND-01b was added in the same pass.
- **Boundary unchanged:** no CQ-HECS lemma is `STATEMENT_MATCHED`, `KERNEL_RECHECKED` or
  `REFINEMENT_LINKED`; Comparator/nanoda statement checks and the Python-oracle link remain W4/W5
  work. See `FORMAL_ASSURANCE_PLAN.md` §4.
