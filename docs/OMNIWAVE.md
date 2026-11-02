# OMNIWAVE

Exhaustive cube search with checked UNSAT proofs, plus an optional learned branch
heuristic. This page is the reference for what it is, what it is measured to do, and
what it deliberately does not claim.

Status: **supported, with the scope below** (no longer "experimental" as a label, but
not a general-purpose SAT solver either - see *Scope*). The engine still carries no
performance claim beyond the measured table in §4.

## 1. What it is

A *front* is a cube: a set of decision literals. The engine keeps fronts in one
priority queue, processes the deepest first, and for each front:

1. runs unit propagation under the cube (over the original clauses and the shared
   nogoods),
2. if the cube is refuted, logs `¬cube` as a lemma (RUP at that point) and shares it as
   a nogood when it is short enough,
3. if every clause is satisfied, verifies the model clause by clause against the
   original CNF and reports `SAT`,
4. otherwise splits on one unassigned variable and pushes **both** children, so
   coverage is exhaustive by construction.

When both children of a node are refuted, `¬node` is logged; a refuted root means the
empty clause, which completes a DRAT refutation that `cqhecs.drat` checks. The checker
shares no code with the engine.

Status rules, unchanged by anything below:

| Verdict | Requirement |
|---|---|
| `SAT` | a model verified against the original CNF |
| `UNSAT` | the search covered the space **and** the DRAT check accepted the proof |
| `UNKNOWN` | timeout, node/front budget, cancellation, or a proof the checker rejected |

## 2. What changed on 2026-11-02

**Propagation.** `_propagate` now uses occurrence lists: assigning a literal only
re-examines the clauses that contain it, instead of rescanning the whole formula on
every pass. Profiling pigeonhole-8-7 had shown the old loop at 78 % of the runtime
(15 M dictionary lookups for 5 188 fronts).

**Learned branching (opt-in).** `branch="learned"` lets a trained scorer pick the
branch variable. It is **off by default and it did not win**: see §5.

## 3. Knobs

| Option | Default | Meaning |
|---|---|---|
| `waves` | 4 | independent search directions (BFS orders from different start variables) |
| `workers` | 2 | worker threads (Python threads share the GIL: organisation, not speed) |
| `branch` | `"auto"` | `auto`, `jw`, `bfs`, or `learned` |
| `learned_model` | `None` | weights file (JSON) or fine-tuned model directory; required for `learned` |
| `bcp` | `"scalar"` | `scalar`, `batch` (CPU batched BCP) or `vulkan` (verified against the CPU reference) |
| `share_max_len` | 8 | longest refuted cube that is shared as a nogood |
| `check_proof` | `True` | run the independent DRAT check before returning `UNSAT` |
| `timeout_seconds` | 10 | wall-clock budget for the whole search |

## 4. Measured (2026-11-02, one machine, one repetition per cell)

`scripts/omniwave_efficiency.py` regenerates this table. `waves=1, workers=1`,
25 s budget, proofs checked.

| Instance | Before (full-scan propagation) | After (occurrence lists) | Verdict |
|---|---|---|---|
| pigeonhole-8-7 (30 vars, 81 clauses) | 31.07 s, 10 079 fronts | **29.81 s**, 10 079 fronts | UNSAT, proof checked |
| pigeonhole-9-8 | UNKNOWN at 25 s, 35 885 fronts | UNKNOWN at 25 s, 37 927 fronts | unchanged (more work per second) |
| Tseitin 3x3 | 0.00 s, 31 fronts | 0.00 s, 31 fronts | UNSAT, proof checked |
| random 3-SAT (70 vars) | 0.31 s | **0.27 s** | UNSAT, proof checked |
| random 3-SAT (60 vars) | 0.15 s | **0.13 s** | UNSAT, proof checked |
| SHA-256 encoding, W=16, 8 rounds | 0.26 s | **0.11 s** (2.4x) | SAT, model verified |

The heavy graded instance (pigeonhole) barely moved: its cost is the number of fronts,
not the cost of one front. That is stated here instead of being smoothed into an
average.

**Against CaDiCaL**, the engine is still much slower on general instances; the
benchmark script prints both so the gap stays visible. Nothing here changes that.

## 5. Learned branching: built in, measured, and not promoted

`cqhecs/omniwave/learned.py` and `scripts/train_branch_jev.py` implement a small
learned scorer - a logistic model over ten integer features, and an optional
fine-tuned `google/bert_uncased_L-2_H-128_A-2` (4.4 M parameters) over the same
features rendered as text. Training data comes from the project's own instances; the
label is the cheap failed-literal oracle ("does assigning this variable refute one of
its branches?"), produced by the engine's own propagation.

Result on the **held-out** instance (pigeonhole-8-7, never seen in training):

| Policy | Verdict | Time | Fronts |
|---|---|---|---|
| Jeroslow-Wang (default) | UNSAT | 27.4 s | 10 079 |
| Learned scorer | UNKNOWN | 60 s (budget) | 157 973 |

The greedy one-step label is the wrong target: it prefers variables that refute a
branch immediately, which produces a much worse tree than JW's clause weighting. The
scorer therefore stays **opt-in**, the default is unchanged, and the negative result is
recorded rather than tuned away (`FINDINGS.md`, F-15).

Safety property, asserted by `tests/test_omniwave_learned.py`: a learned policy can
only choose among unassigned variables, so it cannot change an answer - `SAT` is still
verified against the original CNF and `UNSAT` still needs a checked proof. An
adversarial stub policy yields the same verdict as JW.

## 6. Scope and non-claims

- Not a replacement for CaDiCaL or Kissat; on general instances it is slower.
- No CDCL: no clause learning from conflicts, no restarts, no VSIDS/LRB. Those are the
  SOTA ingredients this engine deliberately trades for exhaustive coverage and simple
  proofs.
- The learned scorer is not advertised as an improvement; it is available, measured and
  off by default.
- The Browser build cannot run the Python engine; the web documentation reports its
  measured results, it does not claim a client-side OMNIWAVE.
