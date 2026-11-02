# P vs NP: what this project's experiments can and cannot say

Written 2026-11-02. This note exists because "more P vs NP research" invites exactly
the claim this project must not make. It states the boundary, and points at the
experiments it is about (`SAT_SHA.md`, `FINDINGS.md`).

## Short version

Nothing in this repository bears on whether P = NP. The experiments here decide
individual SAT instances of a *reduced-round* function. That is a different object
from the complexity question in three independent ways, and each one alone is enough
to make the inference invalid.

## The three gaps

**1. An instance is not a problem.** P vs NP is a statement about how the resources
needed by *families* of inputs grow. A single formula of 27 489 variables is decided
in 3 seconds or not decided at 3 seconds; either way it says nothing about any
asymptotic class. The frontier table in `SAT_SHA.md` §8 reports exactly this kind of
individual instance, with the budget it was given.

**2. Reduced-round SHA is not SHA-256, and SHA-256 is not the problem in P vs NP.**
A formula encoding 16 rounds of SHA-256 with one free message word is a *heavily
over-determined* system (256 constrained output bits against at most 32 unknowns), and
the solver inverts it by propagation rather than by search. Adding rounds removes that
over-determination and the instance stops being decidable in the budget - which is a
measurement about this encoding at this size, not a hardness statement about SHA-256,
and certainly not about NP.

**3. Hardness of a specific function family is not P vs NP.** Even a proof that
inverting full SHA-256 requires exponential time would not settle P vs NP: it would be
a statement about one family inside NP, not about the class. The literature cited in
`LITERATURE_MAP.md` (reduced-step collisions, HashSmash board results) is explicitly
about reduced-round compression functions, and its own authors state that full
SHA-256 is not broken.

## What this project does claim instead

- A **verified pipeline**: every trace the device produces is re-derived
  independently (`DEVICE_RESEARCH.md`), and every UNSAT verdict from these encodings
  carries a certificate that is checked in-repo (`SAT_SHA.md` §3.2).
- A **measured frontier**, with the budget named next to each cell, so a reader can
  see where the method stops instead of being told that it scales.
- **Reproducible scripts** for both (`sha_round_frontier.py`,
  `device_research_campaign.py`, `evaluate_device_traces.py`).

That is the honest output of a SAT-based look at a hash function: a bounded,
certificate-checked tool and a table of what it finished. It is not a complexity-theory
result, and this note is the place where that sentence lives so it cannot drift.

## For the next agent

If a future result here looks like it says something about P vs NP, the first question
is which *family* was decided, at which *sizes*, with which *budget*, and whether the
claim survives gap 1. If the answer is a single instance, it does not.
