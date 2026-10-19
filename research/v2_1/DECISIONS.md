# CQ-HECS v2.1 Architecture & Engineering Decisions

Recorded on 2026-10-19 for the v2.1 engineering and research cycle. Every entry is labeled with its evidence class: **observed locally**, **observed in GitHub Actions**, **derived from source**, **literature claim**, **hypothesis**, or **not yet verified**.

---

## 1. Release & Versioning Policy

### Decision 1.1: SemVer Version Selection (`2.1.0`)
- **Context:** The repository published `v2.0.0` on 2026-10-19. The current cycle introduces new backward-compatible capabilities: MPS sequential full-register sampling without dense statevectors, full-shot Clifford sampling for 200–300 qubits, a selective observables request API on Path D, and an extensive classical simulation literature audit.
- **Decision:** Target `v2.1.0` as a SemVer minor feature release. Do not increment major version (no breaking changes to public APIs) and do not use a patch release `v2.0.1` (since substantial new capabilities are introduced).
- **Evidence Label:** **derived from source**, **hypothesis**.

### Decision 1.2: Strict Immutability of Existing `v2.0.0` Tag
- **Context:** GitHub release `v2.0.0` was tagged at commit `19df10cdc80f26dc9bb81b4438192c084845f477`.
- **Decision:** Never move, delete, force-push, or retag `v2.0.0`. All bug fixes, including the asset checksum ordering fix merged on `main` in `ef7cbbd`, will ship in `v2.1.0`.
- **Evidence Label:** **observed locally**, **observed in GitHub Actions**.

### Decision 1.3: Dedicated Mission Branch Base
- **Context:** `origin/main` was at `ef7cbbda47c39cdad0f77050c1e6a8c0c2727cf1`.
- **Decision:** Branch `agent/v2-1-200q-20261019` was created directly from `origin/main`. All development, tests, and research artifacts will be committed to this branch.
- **Evidence Label:** **observed locally**.

---

## 2. Classical Simulation Architecture Decisions

### Decision 2.1: MPS-Native Sequential Sampling (Path C)
- **Problem:** Currently, Path C converts the MPS to a dense $2^n$ statevector via `to_statevector()` to sample measurement bitstrings, capping counts at $n \le 20$.
- **Decision:** Implement an MPS-native sequential sampling algorithm. For an $n$-qubit MPS, measure qubits sequentially (e.g. from site 0 to $n-1$). At each site $k$, contract the remaining right environment (or maintain right-orthogonal canonical form), compute the marginal probability distribution $P(b_k \mid b_0, \dots, b_{k-1})$ for physical index $b_k \in \{0, 1\}$, draw $b_k$ using the configured RNG seed, project site tensor $k$ onto $b_k$, and proceed to site $k+1$.
- **Benefits:**
  - Memory scales with $n \cdot \chi^2$ rather than $2^n$, where $\chi$ is the bond dimension.
  - Enables true full-register correlated sampling on 200–300 qubit states with low entanglement (such as GHZ, 1D cluster states, shallow brickwork circuits).
  - Preserves exact joint correlations (e.g. GHZ parity).
- **Evidence Label:** **literature claim**, **hypothesis**.

### Decision 2.2: Full-Shot Stabilizer Sampling (Path A)
- **Problem:** Path A in earlier iterations used an internal resampling ceiling (`MAX_RESAMPLE_SHOTS = 100`) for wide circuits, meaning requests for 1,000 shots did not draw 1,000 independent samples.
- **Decision:** Ensure Path A supports arbitrary shot counts (including $\ge 1,000$ shots for 200–300 qubit stabilizer circuits) by reusing the pre-measurement circuit tableau and cloning/resetting only the measurement state. The counts dictionary must strictly satisfy $\sum \text{counts} = \text{shots}$.
- **Evidence Label:** **derived from source**, **hypothesis**.

### Decision 2.3: Preserving Honest Boundaries on Path B
- **Problem:** Path B represents non-Clifford state expansions as branches of dense statevectors, capped at 22 qubits.
- **Decision:** Retain the explicit 22-qubit cap on Path B's dense statevector representation. Do not increase the cap artificially without a sparse or observable representation. 200-qubit circuits with low $T$-count or Clifford structure must be routed to Path A or Path C if low-entanglement.
- **Evidence Label:** **derived from source**, **observed locally**.

### Decision 2.4: Selective Observables API (Path D)
- **Problem:** Path D by default evaluates all single-qubit $Z$ and all pair parities $Z_i Z_j$. At $n=200$, this requires $\sim 20,000$ backward Heisenberg propagations.
- **Decision:** Introduce an explicit `observables` parameter to Path D / Router execution. When specified, only the requested observables are propagated backward and bounded. If omitted on large circuits ($n > 30$), Path D should require explicit observables or bounded subsets rather than stalling on $O(n^2)$ operators.
- **Evidence Label:** **derived from source**, **hypothesis**.

---

## 3. Literature and Research Decisions

### Decision 3.1: OpenAI Math Corpus Audit Execution
- **Context:** The `openai/math` corpus contains hundreds of manuscripts across 372 families.
- **Decision:** Clone/fetch the upstream `openai/math` repository into a research cache. Generate an authoritative machine-readable manifest (`research/v2_1/openai_math/MANUSCRIPT_MANIFEST.jsonl`) and Markdown index (`FAMILY_MAP.md`). Review and categorize every paper. Prioritize families relevant to quantum simulation, query complexity, and sampling algorithms (e.g., Families 284, 283, 279, 275, 267–278, 130, 139).
- **Evidence Label:** **literature claim**, **hypothesis**.

### Decision 3.2: Scientific Honesty Contract
- **Rule:** Never equate query complexity with wall-clock simulation runtime; never claim polynomial classical simulation of universal quantum circuits; never conflate expectation value error bounds with bitstring total variation distance without rigorous proof.
- **Evidence Label:** **derived from source**.

---

## 4. Documentation & Release Timing

### Decision 4.1: README as Final Authored File
- **Rule:** As explicitly instructed in `GEMINI.md` §12, `README.md` will be the very last documentation/source file edited prior to final release freeze and CI run. All code, tests, research documents, and release notes must be complete and passing before the README is updated.
- **Evidence Label:** **derived from source**.
