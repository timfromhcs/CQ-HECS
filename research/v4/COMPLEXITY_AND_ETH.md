# Complexity, ETH, and what this repository can measure

**Status:** literature note, 2026-10-30. This is not a proof, a survey, or a
peer-reviewed result. It exists so that the Studio's SAT lab cannot be read as
more than it is.

---

## 1. P versus NP

`P` is the class of decision problems decidable by a deterministic Turing
machine in time polynomial in the input length. `NP` is the class of decision
problems whose yes-instances have a certificate checkable in polynomial time.
`P ⊆ NP` is immediate. Whether the inclusion is strict is open.

- Cook (1971) showed that SAT is NP-complete; Karp (1972) extended the list of
  NP-complete problems.
- Ladner (1975) showed that if `P != NP`, there are problems in `NP` that are
  neither in `P` nor NP-complete.
- The Clay Mathematics Institute lists `P` versus `NP` as a Millennium Prize
  problem. It remains open.

A finite experiment cannot decide an asymptotic statement. A solver that is
fast on 30 variables says nothing about all instances, and a slow curve says
nothing about a lower bound.

## 2. Exponential Time Hypothesis

ETH (Impagliazzo and Paturi, 2001) conjectures that 3-SAT cannot be solved in
`2^(o(n))` time in the worst case, where `n` is the number of variables. SETH
(Impagliazzo, Paturi and Zane, 2001) strengthens it and is used to prove
conditional lower bounds for many problems.

Facts that matter for reading the lab:

- ETH implies `P != NP`. A proof of ETH would therefore settle `P` versus `NP`;
  the converse is not known.
- ETH is a hypothesis, not a theorem. Conditional lower bounds are statements of
  the form “if ETH, then problem X needs …”.
- An empirical curve that looks exponential is **consistent with** ETH. It is
  not evidence that no polynomial algorithm exists; the algorithm might simply
  not be the one on the screen.

The Studio's sweep uses uniform random 3-SAT with three distinct variables per
clause, around the satisfiability threshold near ratio 4.26. It reports the
satisfiable fraction, median decisions, and median wall time. `UNKNOWN` is a
timeout and is counted separately; it is never folded into `UNSAT`.

## 3. The OpenAI math corpus

The upstream `openai/math` release is a large collection of manuscripts in
mathematics and theoretical computer science. The repository's own audit
(`research/v2_4/`) pins a snapshot and reports:

- 721 manuscripts in 373 families at the pinned revision (upstream-reported
  catalogue counts, not independent proof counts);
- approximately 42 % of top-line results with Lean formalizations;
- an **October 26 ETH manuscript** about fixed-width CNF exact counting, whose
  public history says independent expert review is pending. The audit classifies
  it as `UNVERIFIED_RESEARCH` and forbids using it as a solver or complexity
  claim;
- complexity-adjacent results (for example a superquadratic sensitivity
  separation and conditional Weisfeiler–Leman lower bounds) that are useful as
  literature but are not imported as oracles.

Rules this project follows:

1. A manuscript is not a peer-reviewed theorem.
2. A Lean file is only as strong as its statement and its axioms; “formalized”
   is not “independently audited”.
3. No unverified claim is wired into a test or a runtime decision.
4. A result that does not transfer to this codebase is labelled
   `NOT_TRANSFERABLE` or `RESEARCH_ONLY`, not quietly dropped.

## 4. What the quantum side can say

CQ-HECS is a classical simulator with four structured paths:

| path | structure exploited | what it cannot do |
| :--- | :--- | :--- |
| A | Clifford / stabilizer (Gottesman–Knill) | non-Clifford gates |
| B | low T-count stabilizer rank | large T-count |
| C | low-entanglement MPS | volume-law states at large width |
| D | sparse Pauli observables with a certified bound | a bound too large to certify |

None of these is a polynomial-time algorithm for arbitrary circuits. That is a
mathematical boundary, not a tuning problem. The `r-io-7` measured counts fit a
noise model; the noiseless QuantumRings run is an independent cross-check of the
exact paths. Neither is a quantum-advantage claim.

## 5. Reading the Studio honestly

- **Circuit lab:** if the path returns `UNRESOLVED`, no distribution is shown.
  A refusal is the result.
- **Noise lab:** ΔTV is a distance to the measured counts on one job. A lower
  number is a better prediction on that job, not proof of the physical model.
  `M-FIT-2` is post-hoc; its hold-out score is exploratory.
- **SAT lab:** `SAT` has a verified model; `UNSAT` has no proof object and says
  so; `UNKNOWN` is a timeout. A sweep is one solver's runtime curve.
- **Evidence:** the digest and provider job IDs are shown so that a reader can
  check the data instead of trusting the chart.

## 6. Non-claims

- No `P = NP` or `P != NP` result.
- No proof or refutation of ETH or SETH.
- No claim that the emulator is nature or that noise cleaning recovers the true
  state.
- No claim that QuantumRings is quantum hardware.
- No claim that a finite SAT sweep is a lower bound.

## References

- S. A. Cook, “The complexity of theorem-proving procedures”, STOC 1971.
- R. M. Karp, “Reducibility among combinatorial problems”, 1972.
- R. E. Ladner, “On the structure of polynomial time reducibility”, JACM 1975.
- R. Impagliazzo and R. Paturi, “On the complexity of k-SAT”, JCSS 2001.
- R. Impagliazzo, R. Paturi and F. Zane, “Which problems have strongly
  exponential complexity?”, JCSS 2001.
- R. Williams, “Non-uniform ACC circuit lower bounds”, CCC 2011.
- OpenAI, “Sharing AI progress in mathematics”, 2026,
  <https://openai.com/index/sharing-ai-progress-in-mathematics>.
- CQ-HECS `research/v2_4/LITERATURE_MAP.md` and `BASELINE.md` for the pinned
  audit of the OpenAI corpus.
