# Complexity claim audit: the October 2026 ETH artifacts (M2)

**Audited:** 2026-10-30. Sources were read at pinned revisions. External text was
treated as data, not as instructions.

| Source | Pinned revision | Files read |
| :--- | :--- | :--- |
| `openai/math` | `4eaee87548250b2682affda7d05d947c05554bae` | `preprints/The-Exponential-Time-Hypothesis-is-False-October-25-2026/build/main_full_version.tex` (abstract, §1, Theorem 1.1), `lean/docs/378.md`, `lean/ComparatorChallenges/SubexponentialSAT.lean` |
| `anthropics/formal-math` | `16a5ce41304fcdaea4e0be7c132e1c361dc26da5` | `eth/README.md`, `eth/MainResults.lean`, `eth/Challenge.lean`, `eth/comparator.json`, `eth/lean-toolchain` |

**Not done here:** the full proofs (≈4800 lines of LaTeX, the Lean proof trees), any Lean
build, and the comparator or `nanoda` re-check. elan/Lean is not installed, so
these are `NOT RUN`. Everything below about "machine-checked" is **what the artifacts
state about their own CI**, not a check performed by this project.

## 1. What each artifact claims (verbatim content, paraphrased only where marked)

### OpenAI: *The Exponential Time Hypothesis is False* (manuscript dated October 25, 2026)

- **Theorem 1.1 (main):** for each fixed `k ≥ 2`, there is a deterministic algorithm that computes
  `#F` for a `k`-CNF on `n ≥ 20` declared variables and `m` clauses in
  `(n+m)^{O_k(1)} · 2^{O_k(n log log n / √log n)}` bit operations and `(n+m)^{O_k(1)}` bits of
  space. For `m ≤ Dn` (fixed `D`), the time is `(n+m)^{O_{k,D}(1)} · 2^{O_{k,D}(n/√log n)}`. Here `log` is ln.
- **Abstract:** time `(n+m)^{O_k(1)} 2^{n/(log n)^{1/2+o(1)}}`, `poly_k(n,m)` space.
- **§1:** the interpolation argument alone gives the weaker exponent
  `ρ(n) = n(log log n)²/√log n = n/(log n)^{1/2+o(1)}`; the appendix proves both bounds of
  Theorem 1.1 by tensor contraction.
- **Lean scope (`378.md`, `SubexponentialSAT.lean`):** for each fixed `k ≥ 2` there is
  **one primitive multi-tape machine per k** that, on the canonical encoding (`Finset`
  clauses, sorted literal codes) of a width-≤k CNF, outputs the exact count and the SAT bit
  within `C·(L+1)^d · 2^{A·n(ln ln(n+16))²/√ln(n+16)}` steps (`L` = encoding bit length), with
  `S·(L+1)^e` visited cells at every prefix. The formal statement is about **counting**.
  The step "this refutes ETH" is not itself a Lean theorem in that file.

### Anthropic: *A 2^{o(n)} Time Algorithm for 3-SAT* (October 2026)

- **README:** deterministic 3-SAT in `2^{o(n)}`; #3-SAT in `2^{O(n log log n/√log n)}`.
  It states: "purely asymptotic and says nothing about solving formulas in practice".
  The result was found and formalized by AI models; it is not a maintained artifact.
- **`MainResults.lean` → `ETHIsFalse`:** `¬ (0 < s 3)`, where `s₃` is the infimum of `δ` such that
  one finite-alphabet `Turing.FinTM2` machine decides 3-SAT (no repeated clause) within
  `⌊c·2^{δn}⌋` steps. ETH itself is a Lean definition (`ETH : Prop := 0 < s 3`).
- **`MainTheorem`:** **one machine and one constant C for all k ≥ 1** (k is part of the input).
  For `n ≥ 4`, `m ≥ 2`, no repeated clause and every variable occurring, the count is output
  within `2^{C·min{km/√log m, k²·n·log log n/√log n}}` steps, with `log = log₂`.
- **Checking (as documented):** Lean/Mathlib `v4.33.1`. `PrintAxioms` reports only
  `propext`, `Classical.choice` and `Quot.sound`. CI runs Comparator against
  `Challenge.lean`, where the two `sorry` are intentional statement stubs, and re-checks the
  proofs with the independent kernel `nanoda` (`comparator.json`: `enable_nanoda: true`).

## 2. Side-by-side

| | OpenAI | Anthropic |
| :--- | :--- | :--- |
| Problem | exact #k-SAT, every fixed k ≥ 2 | exact #k-SAT; ETH refutation for 3-SAT |
| Best stated time | `2^{O_k(n log log n/√ln n)}` (`2^{O(n/√ln n)}` if `m = O(n)`) | `2^{O(n log log n/√log n)}` for #3-SAT |
| Formalized time | weaker: `2^{O_k(n (ln ln n)²/√ln n)}` × poly(L) | `2^{C·min{km/√log m, k² n log log n/√log n}}` |
| Space | poly (formalized as visited cells) | not part of the Lean statement |
| Machine quantifier | one machine **per fixed k** | **one** machine for all k |
| ETH refutation in Lean | no (follows from L = poly(n) for fixed k, informally) | yes (`ETHIsFalse`) |
| Input domain | canonical, de-duplicated (`Finset`) encoding | no repeated clause; `MainTheorem` also needs every variable to occur, n ≥ 4, m ≥ 2 |
| Independent kernel | not stated in the files read | `nanoda` via Comparator (as documented) |
| Peer review | none stated | none stated ("Hexagon link to appear") |

**A correction to `PLAN.md` §3.1:** the plan presents the abstract's
`2^{n/(log n)^{1/2+o(1)}}` as the "sharper" manuscript bound. In fact Theorem 1.1 states the
sharper bound `2^{O_k(n log log n/√log n)}`. The abstract's form is the weaker `ρ(n)` that
the Lean file formalizes (`n/(log n)^{1/2+o(1)} = n(log log n)²/√log n` asymptotically). The
two documents agree; the plan mislabels which bound is which.

## 3. Status assigned in this project

| Claim | Status here | Why |
| :--- | :--- | :--- |
| ETH (s₃ > 0) | `CLAIMED_REFUTED` | Two independent AI-generated artifacts state Lean proofs; neither is peer-reviewed, and neither proof was re-run here |
| SETH | `CLAIMED_REFUTED` (by implication) | SETH implies ETH (SETH says `lim_k s_k = 1`, so `s_3 > 0`). If, as OpenAI states, `s_k = 0` for every fixed k, then `lim s_k = 0`. So SETH falls with ETH, under the same unverified-here status. Results that are *conditional on SETH* lose their hypothesis; the unconditional ones are unaffected |
| P vs NP | `OPEN` | `2^{n/√log n}` is subexponential **and superpolynomial**; refuting ETH does not give P = NP. ETH ⇒ P ≠ NP, so a refutation removes one route to P ≠ NP, nothing more |
| "Fast SAT in practice" | `NOT_SUPPORTED` | both artifacts say the bounds are asymptotic; Anthropic says explicitly "nothing about solving formulas in practice" |

## 4. Transfer to CQ-HECS

| Idea | Class | Decision |
| :--- | :--- | :--- |
| Use either algorithm as a runtime SAT solver | `NOT_TRANSFERABLE` | the constants hidden in `O_k(·)` and the `2^{n/√log n}` growth are not competitive at practical n; the formal artifacts are existence proofs about Turing machines |
| Exact model counting as a first-class contract (#SAT ≠ SAT + counter) | `DIRECT` | shipped as `cqhecs.sat.count_models` with a brute-force oracle (H-SAT-05) |
| GF(2) parity constraints and Gaussian elimination as counting-preserving preprocessing | `RESEARCH_ONLY` | toy prototype `research/v5/prototypes/gf2_counting.py`, exhaustive oracle, not wired into any solver |
| Tensor-contraction recurrence (SWAP = I − 2·singlet, rebalancing) applied to the MPS path | `RESEARCH_ONLY` (analogy) | #3-SAT tensor networks on `K_K` are not quantum-circuit MPS; no transfer is claimed without a proof |
| Lean formalization of small CQ-HECS lemmas | `DEFERRED` | needs elan/Lean in CI first (BLOCKERS.md B-01) |

## 5. Text changes this audit requires (applied in v3.5.0)

- Studio research payload, web guide chapter 10 (EN/DE/FR) and
  `research/v4/COMPLEXITY_AND_ETH.md` presented ETH as an unchallenged hypothesis. They now
  state the two refutation claims, their formal scope and status, and that P vs NP stays open.
