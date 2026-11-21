# LEAN_ENV.md — Lean toolchain and external formal-math artifacts (V7 W4)

Recorded 2026-11-21 on branch `agent/v6-rc`. Evidence for the Lean formal workspace setup and
the downloaded external math artifacts. This is **external evidence**, not a CQ-HECS proof.

## 1. Lean toolchain (installed this session)

- Installed with the official `elan` Windows installer (`elan-init.exe` from
  `github.com/leanprover/elan/releases/latest`, `elan-x86_64-pc-windows-msvc.zip`).
- `elan` default toolchain set to `4.33.1`. Installed toolchain:
  - `leanprover/lean4:v4.33.1` — **Lean 4.33.1** (x86_64-w64-windows-gnu, commit
    `819816b2e0a3bf405af45ae5c7af2491d8f5bee6`), **Lake 5.0.0-src+819816b**.
- Location: `%USERPROFILE%\.elan` (PATH added to HKCU\Environment). No Lean dependency is added
  to the shipped Python/C++ package.

## 2. External artifacts downloaded (for statement comparison / methodology)

Cloned to a scratch dir (outside the repository); **not vendored** — licences permit reading,
not redistribution.

- `anthropics/formal-math` at commit **`16a5ce41304fcdaea4e0be7c132e1c361dc26da5`** (the pin the
  v6 evidence already recorded). Contains three formalized research results:
  - **`eth/`** — *A 2^{o(n)} Time Algorithm for 3-SAT* (Claude / Anthropic). Refutes ETH and
    gives a #k-SAT counting machine. Lean/Mathlib pinned `v4.33.1`. Apache-2.0.
  - **`zeta23/`** — *More than two thirds of the zeta zeros are simple and on the critical line*
    (Alpöge & Furman, arXiv:2608.13637).
  - **`3sum-apsp/`** — *Truly Subquadratic 3SUM and Truly Subcubic APSP* (Alman & Vassilevska
    Williams).
- `openai/math` (shallow clone) — holds the OpenAI ETH preprint and its Lean scope note.

## 3. The `eth` artifact: exact statements and method

`eth/MainResults.lean` states the two claims; `eth/Challenge.lean` restates them without proof;
`eth/Solution.lean` proves them. Method and checks (from `eth/README.md`, `comparator.json`):

- Machine model: Mathlib `Turing.FinTM2` (`TM2ComputableAux Bool Bool`), a deterministic
  finite-stack machine; time = number of steps.
- `MainResults.ETH` := `0 < s 3` (s_k = infimum of δ with a 2^{δn} algorithm for k-SAT);
  `ETHIsFalse` := `¬ ETH`.
- `MainResults.MainTheorem` := one machine + one constant `C`, chosen before `k` and the formula,
  that counts `numSat φ` for every k-CNF (k ≥ 1, clauses ≤ k literals, no clause repeated,
  m ≥ 2, n ≥ 4, every variable occurs) within
  `2^{C · min{ k·m/√(log m), k²·n·log log n/√(log n) }}` steps.
- Proof check: `lake exe cache get` → `lake build` → `lake env lean scripts/PrintAxioms.lean`
  (expects only `propext`, `Classical.choice`, `Quot.sound`). Full check:
  `bash ../.github/scripts/comparator-check.sh` runs **Comparator** (statement equality against
  `Challenge.lean`) plus the independent **nanoda** kernel (`enable_nanoda: true`).
- Two `sorry` warnings come from `Challenge.lean` (deliberate statement stubs), not the proof.

**Condensed idea (from the README, for AI re-derivation):** tensor-network contraction on K_K
with e(9K^16) = 0.9·e(K)+O(1/K); place nodes on a grid so each rectangle's diagonals form a SWAP;
per bit SWAP = I − 2·singlet, group by singlet number → ℓ+1 operators; merge each row or column,
regroup into K classes. This rederives only 3-SAT ∈ O(2^{δn}) for every δ > 0, not the sharper
bound.

## 4. Boundary (unchanged by this download)

- These are **external** AI-authored research artifacts; this download does not review them and
  does not make CQ-HECS prove ETH/LRAT/etc.
- The paper-vs-formalized runtime-formula nuance (PLAN.md §3.1/§3.3) must be carried into
  `LITERATURE_MAP.md` exactly; do not cite the abstract and the Lean scope note interchangeably.
- No CQ-HECS lemma is `FORMALIZED_LEMMA` yet; see `FORMAL_ASSURANCE_PLAN.md`.

## 5. Build status

`cd eth && lake exe cache get && lake build && lake env lean scripts/PrintAxioms.lean` was started
in the background this session; result recorded when it completes (see `EXECUTION_LOG.md`). A
missing/failed build is reported as `NOT RUN`, never as PASS.
