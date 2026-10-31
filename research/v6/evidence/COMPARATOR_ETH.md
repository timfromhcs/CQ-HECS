# Anthropic ETH Comparator + nanoda check (M5-03)

**Date:** 2026-10-31
**Source:** `anthropics/formal-math` at `16a5ce41304fcdaea4e0be7c132e1c361dc26da5`
**Project toolchain:** Lean/Mathlib `v4.33.1`
**Runner:** `bash ../.github/scripts/comparator-check.sh`

## Pinned tools used by the script

| Tool | Commit |
| :--- | :--- |
| Comparator | `575674928e239f5bc452aab72d1dd7b0f1326494` |
| lean4export | `15f6055e299ad5b89345e533cc2192f4cc00f659` |
| nanoda_lib | `68d5ca9db226849b41a6fff59d796ff19d0a8840` |
| landrun | `811cfff51ceaf3d9843708aa6d22e9b84ccac8b4` |

## Observed output (abridged)

```
project /home/tim/formal-math/eth, toolchain leanprover/lean4:v4.33.1
== comparator @ 575674928e239f5bc452aab72d1dd7b0f1326494
Build completed successfully (16 jobs).
== lean4export @ 15f6055e299ad5b89345e533cc2192f4cc00f659
Build completed successfully (6 jobs).
== nanoda_lib @ 68d5ca9db226849b41a6fff59d796ff19d0a8840
== landrun @ 811cfff51ceaf3d9843708aa6d22e9e9b84ccac8b4
== comparator comparator.json
Building Challenge
⚠ Challenge.lean:12:8: declaration uses `sorry`
⚠ Challenge.lean:16:8: declaration uses `sorry`
Build completed successfully (8708 jobs).
Building Solution
Build completed successfully (9516 jobs).
Running nanoda kernel on solution
nanoda kernel accepts the solution
Running Lean default kernel on solution.
Lean default kernel accepts the solution
Your solution is okay!
PASS comparator.json
All 1 comparator configuration(s) accepted.
```

(The landrun hash in the transcript above is abbreviated/wrapped by the shell;
the script's pinned value is `811cfff51ceaf3d9843708aa6d22e9b84ccac8b4`.)

## Status

- `REPRODUCED_HERE`: build, statement equality against `Challenge.lean`,
  standard-axiom check, and the independent `nanoda` kernel all pass.
- The two `sorry` warnings are the upstream statement stubs in `Challenge.lean`;
  they are not proof holes in `Solution`.
- This verifies the **Lean artifact** against its stated challenge. It does not
  prove that the Lean statement matches every sentence of the paper, and it is
  not peer review.
- The project still must not say “CQ-HECS proved ETH is false”. Its own claim is
  only that it re-ran the pinned artifact's checks on this machine.
