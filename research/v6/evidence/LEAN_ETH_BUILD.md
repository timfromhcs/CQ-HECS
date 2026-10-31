# Anthropic ETH Lean build (M5-03)

**Date:** 2026-10-31
**Source:** `anthropics/formal-math` at `16a5ce41304fcdaea4e0be7c132e1c361dc26da5`
**Toolchain:** Lean/Mathlib `v4.33.1` via elan 4.2.4
**Host:** WSL2 Ubuntu, 16 logical CPUs, 15 GiB RAM

## Commands actually run

```bash
export HOME=/home/tim
export PATH="$HOME/.elan/bin:$PATH"
cd "$HOME/formal-math/eth"
lake exe cache get
lake build
lake env lean scripts/PrintAxioms.lean
```

## Observed result

```
Build completed successfully (9768 jobs).
'MainResults.ethIsFalse' depends on axioms: [propext, Classical.choice, Quot.sound]
'MainResults.mainTheorem' depends on axioms: [propext, Classical.choice, Quot.sound]
```

Two `sorry` warnings appear in `Challenge.lean`, as the upstream README predicts;
they are statement stubs for the comparator, not the proof modules.

This upgrades the Lean statement/axiom status from `NOT RUN` to:

- **REPRODUCED_HERE (build + axiom print):** yes, on the pinned source/toolchain.
- It does **not** by itself prove that `MainResults.lean` matches the paper
  statement; that is the comparator's job.
- It does not make the result peer-reviewed.

The full comparator (`comparator-check.sh`, including statement equality against
`Challenge.lean` and the independent `nanoda` kernel) is run separately; see
`COMPARATOR_ETH.md`.
