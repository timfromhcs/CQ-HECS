# Reduced-round SHA-256 as SAT: what was encoded, measured, and refused

Status: **IMPLEMENTED and MEASURED for the sizes below; every larger preimage
size is UNRESOLVED.** The encoder lives in `cqhecs/sha/preimage_sat.py`, the
evidence-producing tests in `tests/test_sha_preimage_sat.py`.

This record connects the SHA track (`cqhecs/sha/*`) to the exact SAT/#SAT track
(`cqhecs/sat.py`). It contains bounded experiments only. It is **not** a claim
about the hardness of SHA-256, not a preimage attack, not a complexity-theory
result, and not evidence for or against `P = NP`.

## 1. What is encoded

Everything is built from clauses written out by hand; no CNF library, no
algebraic shortcut, no "the known answer is already known" propagation.

| Component | Encoding | Clauses / variables per bit |
|---|---|---|
| `AND`, `OR`, `XOR` | Tseitin definition, two-input gates | 3 / 1, 3 / 1, 4 / 1 |
| `NOT` | a negated literal | 0 / 0 |
| `ADD` (FIPS 180-4 §4.1.3) | ripple-carry chain of full adders (`p = a⊕b`, `s = p⊕c`, `a∧b`, `p∧c`, `∨`) | 17 / 5 |
| `ROTR`, `SHR` (§3.2) | free re-wiring; a shift of ≥ W bits is the constant 0 | 0 / 0 |
| `Ch`, `Maj` (§4.1.2) | `(x∧y)⊕(¬x∧z)`, `(x∧y)⊕(x∧z)⊕(y∧z)` | 10 / 3, 17 / 5 |
| `Σ0`, `Σ1`, `σ0`, `σ1` (§4.1.2) | two word XORs of rotations/shifts | 8 / 2 |

Constants (`K`, `IV`, the fixed message words, `TRUE`/`FALSE`) are literals of a
single variable pinned by a unit clause, so the gate code never special-cases
them. Tautologies that appear when two operands are the same literal (very
common for constants) are dropped by the clause emitter; that is the only
simplification performed, and it is a logical identity, not a heuristic.

Per round, at W = 32, the encoder allocates exactly **47·W variables and 162·W
clauses** in the steady state (two Σ, Ch, Maj, and seven adders: `h+Σ1`,
`+Ch`, `+K`, `+W_t`, `Σ0+Maj`, `t1+t2`, `d+t1`). The feed-forward adds 40·W
variables. The first two rounds are slightly cheaper in clauses because gates on
two constants collapse tautologies.

The message schedule (§5.2.2 step 1) is expanded **in CNF** for rounds above 16;
nothing is pre-computed in Python and then pasted in as constants when a word is
free. Two entry points exist:

* `build_verification_instance(block, rounds)` — the sixteen message words are
  constants from the block and all eight output words are asserted. It is
  satisfiable exactly when the clauses and the reference agree.
* `build_partial_preimage_instance(block, rounds, free_words)` — the listed
  schedule inputs are fresh variables, the rest stay fixed, and the output state
  is asserted to a target (by default the reference output of that block, so the
  block's own words are one witness).

Both return a `SatInstance` carrying the DIMACS text, the variable and clause
counts, the literals of all 24 words, and decoders so a model can be turned back
into words. `verify_model()` replays a model against
`sha256_reference.compress` (W = 32) or against the width-parameterised model
(other widths) and reports `agrees`, `decoded_state`, `recomputed_state` and
`formula_satisfied` separately.

### Word width

`width=32` is SHA-256. `width=8` and `width=16` are **toys**: the same wiring
with every rotation amount reduced modulo W and shifts of ≥ W bits contributing
zero. The test suite checks that the width-parameterised Python model equals
`sha256_reference.compress` at W = 32, so the toy path is the same algorithm with
a smaller word, not a different algorithm. **A W = 8 result is not a statement
about SHA-256.** The toy widths exist for two reasons only: an exhaustive Python
search can be the oracle, and UNSAT can be certified cheaply.

## 2. Measured CNF size, W = 32

Block `bytes(range(64))`, no output assertion (encoder only), so these numbers
describe the circuit and not the claim:

| rounds | variables | clauses |
|---:|---:|---:|
| 1 | 2 785 | 8 859 |
| 2 | 4 289 | 14 177 |
| 3 | 5 793 | 19 518 |
| 4 | 7 297 | 24 865 |
| 5 | 8 801 | 30 049 |
| 6 | 10 305 | 35 233 |
| 7 | 11 809 | 40 417 |
| 8 | 13 313 | 45 601 |

`variables(rounds) = 1 + 40·W + 47·W·rounds` holds exactly for every measured
round count; the clause delta is exactly `162·W = 5 184` from round 5 on. The
clause-to-variable ratio is ≈ 3.4, so "more than five clauses per variable"
would be false here — the tests assert the measured closed form and a 3–4 band
instead of inventing a nicer-looking inequality.

Toy widths:

| width | rounds | variables | clauses |
|---|---:|---:|---:|
| 8 | 1 | 697 | 2 206 |
| 8 | 20 | 8 449 | 28 997 |
| 8 | 64 | 31 681 | 109 429 |
| 16 | 1 | 1 393 | 4 425 |
| 16 | 20 | 16 897 | 58 001 |
| 16 | 64 | 63 361 | 218 865 |

Full-width verification instances (output asserted, 256 extra unit clauses):

| rounds | variables | clauses | decision |
|---:|---:|---:|---|
| 1 | 2 785 | 9 115 | SAT |
| 2 | 4 289 | 14 433 | SAT |
| 4 | 7 297 | 25 121 | SAT |
| 8 | 13 313 | 45 857 | SAT |
| 16 | 25 345 | 87 329 | SAT |
| 32 | 59 137 | 203 489 | SAT |
| 64 | 126 721 | 437 985 | SAT |

Reference digests, so a future run can prove it built the same formula:

| instance | vars | clauses | `CNF.sha256` |
|---|---:|---:|---|
| verify, W = 32, rounds = 1, block `bytes(range(64))` | 2 785 | 9 115 | `2a25d0c413c2b3ae46efb8ae753cea033795e2536645f4807b4eb17dd5377a50` |
| verify, W = 32, rounds = 8, block `bytes(range(64))` | 13 313 | 45 857 | `79a86f02ae723bd5a5e2d3479e1fc8b725e76ca9520065b31a7b866dd891453d` |
| preimage, W = 8, rounds = 2, free word 0 | 1 081 | 3 603 | `203e37271c08a9124c08d7d0a1c6542a57e48aba5883582b731a8d0a3f05b918` |

## 3. What was decided, and how it was checked

### 3.1 The encoder agrees with the reference (differential test)

For rounds 1, 2, 4, 8 and three blocks (counting, all-zero, a mixed pattern), and
additionally for rounds 16, 32 and 64 at W = 32, the verification instance is
`SAT`, the model is verified clause by clause by `cqhecs.sat`, the decoded output
state equals `sha256_reference.compress(IV, words, rounds)`, and `verify_model`
reports `agrees: True` with `reference: "cqhecs.sha.sha256_reference.compress"`.

That is two independent implementations agreeing: bit arithmetic in Python
versus a Tseitin circuit decided by DPLL. The 64-round case is the full
compression function; it is a *correctness* statement about the clauses only,
because every input word is a constant.

### 3.2 One flipped output bit is UNSAT, with proofs

Flipping one bit of the asserted output state makes the instance UNSAT at every
tested round count, and the verdict carries evidence:

* `cqhecs.sat` produces a tree-resolution refutation that
  `check_refutation` replays: **1 step** (a single leaf, no decisions), because
  the formula is propagation-complete — the fixed inputs determine every gate,
  so the flipped assertion conflicts during unit propagation.
* OMNIWAVE produces a DRAT log that `cqhecs.drat` accepts: W = 32, rounds = 8,
  45 857 clauses, 1 lemma, checked in under a second. The test re-checks the same
  log itself with `drat.check_drat` rather than trusting the engine that wrote
  it.

So the UNSAT verdicts here are not bare "the search found nothing".

### 3.3 A genuine preimage search whose oracle is exhaustive enumeration

All numbers below come from `cqhecs.sat` on the CNF; the oracle is a Python loop
over *every* assignment of the free words using only the width-parameterised
integer model, never the clauses.

| instance | free bits | CNF count | exhaustive search | agreement |
|---|---:|---:|---|---|
| W = 8, rounds = 2, free word 0 | 8 | 1 | 1 preimage (the block's own word) | model set identical |
| W = 8, rounds = 2, free words 0,1 | 16 | 1 | 1 preimage out of 65 536 | model set identical |
| W = 16, rounds = 2, free word 0 | 16 | 1 | 1 preimage out of 65 536 | model set identical |
| W = 8, rounds = 20, free word 15 | 8 | 1 | 1 preimage out of 256 | value and state identical |

`count_models` returns `COUNTED` with an exact integer, and `enumerate_models`
returns `complete=True` with `complete_certified=True`. Because every gate is a
total function of its inputs, the auxiliary variables are determined by the
schedule words, so the model count equals the number of accepted free-word
assignments — which is what the exhaustive oracle counts. The 20-round case is
the interesting one: it goes through the *encoded* message schedule, i.e. the σ
functions are clauses, not Python arithmetic.

An unreachable target at W = 8, rounds = 2 is UNSAT with a checked
tree-resolution certificate (1 step) and the exhaustive search confirms zero
preimages.

### 3.4 The one fact that must not be over-read

At W = 32 with **one** free schedule word and the full 256-bit output asserted,
the built-in DPLL returns SAT with **zero decisions** for rounds 1, 2, 3, 4, 5, 6,
8, 12 and 16 (measured wall time 0.10 s at 1 round to 4.55 s at 16 rounds) and the
decoded word equals the block's word. Unit propagation alone inverts the circuit.

That is not a preimage attack and not a weakness of SHA-256:

* the asserted output supplies 256 constrained bits for 32 unknowns, so the
  system is heavily over-determined at these round counts;
* the round output literally contains the intermediate `t1`, so `out[4] = d + t1`
  pins `t1`, and `t1 = h + Σ1(e) + Ch(e,f,g) + K + W_t` then pins `W_t` through
  the adder's own definitional clauses;
* nothing in this experiment removes any output bit or reduces the number of
  known message words in a realistic way.

The honest summary is: *the encoder's gates are complete enough that unit
propagation is a decoder for small round counts; the interesting question is
where that stops, and it is not a statement about 64-round SHA-256.*

## 4. What did not finish (UNRESOLVED)

| experiment | outcome | why |
|---|---|---|
| W = 32, 1 free word, 17 rounds, output asserted | **UNRESOLVED**, no answer inside any practical budget | the search needs no decisions, so unit propagation does all the work; the encoder is a decoder here and the instance is simply too large to propagate to a conclusion in the budget |
| W = 32, 1 free word, 18 / 19 / 20 rounds | **UNRESOLVED**, killed | same as above |
| W = 8, 1 free word, 17 rounds, free word **0** | **UNRESOLVED**: `UNKNOWN` after 1 023 decisions / 466 conflicts (30 s requested, 67 s wall) | the free word feeds every round through the schedule; propagation is no longer decisive and DPLL searches |
| W = 32 preimage with the output *not* over-determined (e.g. asserting one output word) | not attempted | out of scope for this record; no claim |
| 64-round preimage of any kind | not attempted, and not claimed feasible | the 64-round *verification* instance (437 985 clauses) is decided in ≈1 s only because all 1 024 message bits are constants |

### The timeout observation, and its fix

The first run of this work recorded a real defect in `cqhecs/sat.py`: the deadline
was checked every 1024 search *nodes*, and an instance that needs no decisions
runs inside a single node, so one `_propagate()` call could scan the formula for
minutes. Measured then: a 17-round, one-free-word instance produced **no answer
after 150 s with a 45 s budget**.

Fixed in the same module (not worked around): the deadline is now also checked at
the top of every propagation pass, in the branching heuristic, and every 4096
watch visits inside the watched-literal propagation. Re-measured on the same
instance (27 489 variables, 94 529 clauses): a **3 s budget returns `UNKNOWN`
after 3.23 s** — an overshoot of one clause pass instead of the whole search.
`tests/test_sat_deadline.py` pins this for both engines, and the 161 existing SAT
and DRAT tests are unchanged.

Freeing the *last* schedule word (index 15) at W = 8 is easy (0 decisions,
0.12 s at 17 rounds) while freeing word 0 at the same size is UNRESOLVED — the
position of the unknown in the schedule decides whether propagation can run
backwards. Both are now recorded facts.

## 5. Reproduce

```bash
cd E:\qCSHA\CQ-HECS
$env:PYTHONPATH="."

# the whole evidence bundle (32 tests, ~12 s)
python -m pytest tests/test_sha_preimage_sat.py -q

# lint gate used by the repository
python -m flake8 cqhecs tests --select=E9,F
```

Sizes and decisions, without pytest:

```bash
python - <<'PY'
import time
from cqhecs.sha import preimage_sat as ps
from cqhecs import sat as S

blk = bytes(range(64))
for r in range(1, 9):
    i = ps.sha256_round_cnf(ps.masked_iv(), ps.block_words(blk), r)
    print("encoder", r, i.num_vars, i.num_clauses)

for r in (1, 8, 64):
    i = ps.build_verification_instance(blk, r)
    f = i.to_cnf()
    t = time.perf_counter()
    res = S.solve(f, timeout_seconds=180, certify=False)
    print("verify", r, i.num_vars, i.num_clauses, round(time.perf_counter() - t, 2),
          res.status, ps.verify_model(i, res.assignment)["agrees"])
PY
```

Toy preimage with the exhaustive oracle:

```bash
python - <<'PY'
from cqhecs.sha import preimage_sat as ps
from cqhecs import sat as S

blk = bytes((i * 37 + 11) & 0xFF for i in range(64))
w = ps.block_words(blk, 8)
target = ps.width_compress(ps.masked_iv(8), w, rounds=2, width=8)
hits = [v for v in range(256)
        if ps.width_compress(ps.masked_iv(8), [v] + list(w[1:]), rounds=2, width=8) == target]
i = ps.build_partial_preimage_instance(blk, 2, [0], width=8)
f = i.to_cnf()
print("exhaustive", hits, "cnf", S.count_models(f, timeout_seconds=60)["count"], i.num_vars, i.num_clauses)
PY
```

## 6. Non-claims

* No claim that full 64-round SHA-256 preimage is feasible, infeasible, easy or
  hard in any complexity-theoretic sense.
* No claim that these clause counts and decision counts extrapolate to 64 rounds.
  The one 64-round number here is a *verification* instance with every message
  bit fixed.
* No claim that unit-propagation inversion at 16 rounds and below is a weakness:
  it is over-determination of a heavily reduced system, and §3.4 says why.
* No statement about `P` versus `NP`; a curve or a table of runtimes cannot
  decide that, and none is offered as evidence either way.
* The DRAT checker used here is `cqhecs.drat` — a forward RUP/RAT checker, not a
  formally verified one. No external checker was run for these proofs (NOT RUN).
* The toy widths are not SHA-256; their only role is to make an exhaustive oracle
  possible.

## 7. Environment

Windows 11 (`win32`), CPython 3.14.6, `pytest 9.1.1`, AMD Ryzen 7 7735HS
platform; timings above are single-machine wall clock, not a benchmark protocol.
Deterministic sizes: the encoder allocates variables in a fixed order, so
`CNF.sha256` is a stable fingerprint of each formula.
