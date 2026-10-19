# CQ-HECS v2 Literature Map

This map records the literature actually consulted and actually used in the v2
cycle. Papers consulted but not load-bearing for any shipped claim are listed at
the bottom with their status. Nothing here is a substitute for the code's own
verification (see `FORMALIZATION_STATUS.md`).

## Used in shipped claims

| Ref | Statement used | Where it lands | Verification status |
| :--- | :--- | :--- | :--- |
| **Weissman, Ordentlich, Seroussi, Verdú, Weinberger (2003)** — *Inequalities for the L1 deviation of the empirical distribution*, HP Labs Tech Report HPL-2003-97R1 | `Pr(\|P̂ − P\|₁ ≥ ε) ≤ (2^K − 2) exp(−nε²/2)`; TV conversion | `cqhecs/result.py` finite-shot confidence bound | Theorem read from the primary tech report; K=2 reduction matches Hoeffding exactly; empirical violation study rejects every weaker form |
| **Mardia, Jiao, Tánczos, Nowak, Weissman (2019)** — *Concentration Inequalities for the Empirical Distribution*, arXiv:1809.06522 (published in *Information and Inference*) | Context for the recursion-improved L1 concentration; the L1-to-TV factor | Same as above (secondary confirmation of the primary result) | Abstract/metadata verified on arXiv (v3, 2019-10-19); the shipped bound itself does not depend on the tighter recursion result |
| **Gray (2011)** — *Entropy and Information Theory* — and standard Bretagnolle–Huber–Carol writing | The `|P̂−P|₁ = 2·TV` elementary identity and multinomial concentration background | FS1 derivation chain | Standard; not load-bearing beyond the identity |
| **Gottesman (1998)** — *The Heisenberg Representation of Quantum Computers*, arXiv:quant-ph/9807006 | Stabilizer tableau mechanics (Path A) | `path_a_stabilizer.py` | Long-established; correctness here is enforced by oracle comparisons, not the paper |
| **Bravyi, Smith, Smolin (2016)** — *Classification of stabilizer states by Ramsey theory* / the stabilizer-rank expansion (arXiv:1501.02774 others in the lineage) | Finite expansion of non-Clifford rotations into stabilizer branches (Path B) | `path_b_stabilizer_rank.py` | The per-generator matrix identities are what the code verifies; the paper supplies the expansion idea |
| **Weissman-type L1 concentration via the empirical distribution (2003)** — see above | Path B sampling error field | result contract | FS1 |
| **Huang, Kueng, Preskill (2020)** — *Predicting many properties of a quantum system from very few measurements* (arXiv:2002.09552) | The observation-focused (observable-first) framing that Path D follows, with the caveat that classical-shadow variance bounds are for bounded-rank observables under random measurements — a different model from Path D's deterministic truncation | Path D design discussion, `research/v2/METHOD_CATALOG.md` | Used as literature context; no numeric claim is taken from it |
| **Vidal (2003)**, **Schollwöck (2011)** — MPS/tensor-product state simulation | MPS two-site update, gauge freedom, bond dimension semantics (Path C) | `path_c_mps_exact.py` | Implementation correctness is oracle-tested; no asymptotic claim derives from these |
| **Giles, Selinger (2012)** — *Remarks on Tortoise-Hare...*, and the ring `Z[1/√2, i]` | Exact rotation representation behind Path B's algebra | Algebra documented in README/ARCHITECTURE | The exact-arithmetic *implementation* is not shipped as a separate backend in this cycle; float64 is declared (`numerical_mode`) |

## Consulted, no shipped claim

| Ref | Why consulted | Why not load-bearing |
| :--- | :--- | :--- |
| **Stabilizer-rank reduction** (relaxations by Haah, Blinova et al.; extent minimization by Bravyi et al. 2018) | Whether rank-reduction could beat the finite deterministic expansion | Any rank-reduction turns an exact algebra into a certified/stochastic approximation with sampling complexity — changes the result contract; deferred with the method |
| **Schrödinger–Feynman simulation papers** (Markov–Shi 2009; earlier Balauca–Fulga lineage) | Cut-based RAM/time trade-offs | Needs separate cut accounting; deferred (H6c) |
| **Tensor-network contraction-order optimization** (Smith, Grayson, Orús and successors; einsum helpers/libraries) | Possibility of a general-TN backend | No evidence of a regime where MPS-plus-router loses; substantial optimiser work (H6a) |
| **QMDD / QuIDD papers** (Viamontes et al.) | Decision diagram applicability | Regular-structure advantage; licence/maintenance cost 2nd simulator (H6b) |
| **Symmetry methods** (particle-number/parity sectors) | Dimension reduction for invariant-preserving classes | Needs sound invariant detection; an unsafe assumption is the silent-corruption failure class (H6e) |
| **ZX-calculus / graph-state simulation papers** (KP-style) | Graph-like workload classes | No workload identified where it beats A/B/C for the current user surface |
| **Circuit cutting / wire cutting literature** | Overhead accounting | Estimator combination changes output semantics; no hidden overhead permitted |
| **Photonic/scaling-era benchmarking papers and RS competitions** | Understanding adversarial circuit classes | Only context; no capability claim derives from them |
| **OpenAI Math catalogue** (https://github.com/openai/math) | Mission-mandated sweep for formalized probability/complexity statements | No manuscript matched a statement CQ-HECS ships with more tightly than the primary sources above; the catalogue status varies per manuscript and none was load-bearing here |

## Conventions

- The K convention in FS1/`result.py` is *support size* `K` (number of distinct
  outcomes), matching the Weissman tech report's alphabet size `a` — the
  `2^K − 2` factor counts non-trivial subset events `A ⊂ 𝒜`.
- Any new claim that enters the code requires: (1) a primary, readable source;
  (2) a statement-level note in `FORMALIZATION_STATUS.md`; (3) a test that
  validates the *theorem shape*, not just the implementation's formula.
