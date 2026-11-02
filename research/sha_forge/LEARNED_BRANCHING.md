# Learned branching for OMNIWAVE ("JEV")

Written 2026-11-02. Design note for the component the operator asked for: a small
trained model that guides OMNIWAVE's branching, applied to real SAT data from this
project, built into the engine rather than bolted on.

## What is learned, and what is not

**Learned:** which *unassigned variable* a front splits on. That is a heuristic
choice inside a complete search.

**Not learned:** SAT/UNSAT. Every verdict still comes from the search: `SAT` only with
a model verified clause by clause against the original CNF, `UNSAT` only with a DRAT
proof accepted by `cqhecs.drat`. A model that is wrong, untrained, missing or
adversarial can only make the search slower or the tree larger - never make a wrong
answer appear. That property is what makes shipping a learned heuristic acceptable at
all, and it is asserted by a test (`test_learned_policy_cannot_change_verdicts`).

## The signal

For a front (a cube under which unit propagation has reached a fixpoint), every
unassigned variable is a candidate. The label used in training is the cheapest useful
oracle available in this engine: **does assigning this variable immediately refute one
of its two branches?** In a front where propagation almost decides everything (the
structured instances: pigeonhole, parity, the SHA encodings), a variable whose
assignment propagates to a conflict prunes half of that front for free. A variable
that refutes *both* branches refutes the front outright.

That is look-ahead, measured rather than assumed: the training labels come from running
the engine's own propagation, on the project's own instance families.

## Features (deterministic, integer-valued, no floating-point drift across machines)

For a candidate variable `v` at a given front:

| Feature | Meaning |
|---|---|
| `occ2`, `occ3`, `occk` | occurrences in open clauses of length 2, 3, >= 4 |
| `pos`, `neg` | occurrences with positive / negative polarity in open clauses |
| `balance` | `min(pos,neg)` - a pure variable is nearly free to fix |
| `depth` | cube depth of the front |
| `nogood` | occurrences in the currently kept nogoods |
| `wave` | the wave the front belongs to |
| `jwd` | the front's Jeroslow-Wang score for this variable, quantised |

## Two backends, one interface

1. **`FeatureScorer` (default when a model exists):** a logistic regression over the
   features above, stored as a small JSON file of weights. Fast (microseconds),
   dependency-free (numpy only), reproducible bit-for-bit.
2. **`HfScorer` (optional):** a fine-tuned `google/bert_uncased_L-2_H-128_A-2`
   (4.4 M parameters) trained on the same features rendered as a short token string.
   It exists because the operator asked for a HuggingFace fine-tune, it is measured
   against the logistic scorer, and it is only used if it is actually better - the
   engine does not care which one it gets.

Both implement:

```python
class BranchPolicy(Protocol):
    def choose(self, candidates: Sequence[Candidate]) -> int | None: ...
```

`None` means "no opinion", and the engine falls back to Jeroslow-Wang. That fallback is
tested.

## Where the weights live

The trained weights are **not** committed: a binary artefact in a source repository is
a supply-chain question nobody asked. The repository ships the training script, the
feature definition, the tests and the measured table; the weights live next to the
results (`sha_forge_results/omniwave_jev/`) and are loaded by path
(`OmniwaveConfig.learned_model`). Without a path the engine behaves exactly as before.

## Training protocol

- Data: the families in `scripts/omniwave_efficiency.py` plus the SHA encodings, split
  **by instance** into train/validation/test (no front from a test instance is in the
  training set).
- Labels: the failed-literal oracle above, computed by the engine's own `_propagate`.
- Model: logistic regression (numpy, L2) and, for the HF backend, the tiny BERT with
  3 epochs, learning rate 5e-5, batch 16, CPU.
- Selection on validation only; the test split is read once, at the end.
- Acceptance: the learned policy must beat `jw` by >= 20 % on at least one family and
  regress no family by more than 10 %, with identical verdicts. Otherwise it stays
  opt-in and the note says so.
