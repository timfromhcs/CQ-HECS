# CQ-HECS v3 — how hypotheses are tested, which gates exist, and when a PR or a release happens

**Status:** process document, 2026-10-30. **v3.0.0 released** the same day;
all gates PASS (`research/v3_0_0/RELEASE_AUDIT.md`). Binding together with
`research/v3/V3_STABLE_PLAN.md` (gates V3-A…F) and `GEMINI.md` §16
(gates A…J). Where the two overlap, the stricter rule applies.

---

## 1. Hypothesis lifecycle

A hypothesis is a falsifiable statement with a fixed test. It moves through
these states and only forward:

| State | Meaning | Allowed actions |
| :--- | :--- | :--- |
| `PROPOSED` | Idea with a claim and a data source | Change anything |
| `PREREGISTERED` | Claim, metric, split, seeds, stop rules and verdict rule are written **and committed** before any data is looked at | Nothing about the test may change; a change creates a new hypothesis ID |
| `RUN` | Data was collected exactly as preregistered | Record raw data and digests |
| `SUPPORTED` / `REJECTED` / `INCONCLUSIVE` | Verdict computed by the preregistered rule | Record the number, CI, n and scope in the same sentence |
| `EXPLORATORY_POST_HOC` | Anything designed after seeing the data | Report as a mechanism check only; confirm on new data under a new ID |

### 1.1 Steps for a new hypothesis

1. **Write it down** in `research/v3/HYPOTHESES.md` with a new ID
   (`H-V3-n`): claim, data, metric, test, verdict rule.
2. **Fix the protocol** in its own file when it involves data collection
   (example: `OPENQUANTUM_RUN_PLAN.md`): circuits or inputs with SHA-256,
   FIT/EVAL split, seeds, shots, bootstrap size, stop rules.
3. **Write the evaluation code and test it on synthetic data first**, with
   the synthetic data generated from a known model inside the test only.
   The code must refuse incomplete or tampered input with a typed error.
4. **Commit and merge the preregistration before collecting data.** The
   commit SHA is the proof of order.
5. **Collect data.** For paid QPU runs: quote first, show the total, wait for
   an explicit "yes" for that total, then submit. Never commit credentials.
6. **Pin the raw data** (`result.json`, `circuit.qasm`, `job.json` per job)
   and compute the verdict with the committed code, unchanged.
7. **Reproduce offline** from a clean checkout
   (`cq-hecs reference run --dataset <id>`); record any difference.
8. **Record the verdict** in `HYPOTHESES.md`, `V3_STABLE_PLAN.md` progress
   log, `EXECUTION_LOG.md`, and — if user-visible — the README, each with
   scope (backend, date, n, shots).
9. **Never repair a model and re-score it on the same data as a
   confirmation.** That is `EXPLORATORY_POST_HOC` (example: H-V3-9).

### 1.2 Verdict rule used so far

Paired `ΔTV = TV(real, model) − TV(real, reference)` per circuit;
`SUPPORTED` if the 95 % bootstrap interval of the median (circuits
resampled, 5000 draws, seed 20261030) lies below 0, `REJECTED` if above 0,
otherwise `INCONCLUSIVE`; incomplete data is labelled `incomplete: k/n`.

---

## 2. Gates for v3.0.0 Stable

Each gate is `PASS`, `FAIL`, `NOT RUN`, `SKIP (reason)`, `BLOCKED (reason)`
or `INCONCLUSIVE`. **Status as of this document** (live audit, 2026-10-30):

### 2.1 V3 plan gates (`V3_STABLE_PLAN.md` §4)

| Gate | Requirement | Status | Evidence / what is missing |
| :--- | :--- | :--- | :--- |
| V3-A | all R-CAL snapshots import or are refused with a typed reason | PASS | `tests/test_v3_calibration_bridge.py` |
| V3-B | Aer parity on preregistered families | PASS (amended criterion E-V3-02; original 1e-9 recorded as not met on manila) | `V3_STABLE_PLAN.md` W2 |
| V3-C | Sycamore gates (`fsim`, `√X`, `√Y`, `√W`, `phased_x`) differential-tested; mutation harness extended | PASS | `tests/test_sycamore_gates.py`; mutants 39–40 (40/40 killed) |
| V3-D | ≥ 1 real I/O dataset with complete circuits, pinned, hypothesis outcome recorded | PASS — R-IO-7, H-V3-8 `SUPPORTED` (one backend, one day) | `evidence/openquantum/` |
| V3-E | schema 2.0 documented, migration tested, CLI/JSON contract tests | PASS | `docs/MIGRATION_V3.md`, `tests/test_schema_migration.py` |
| V3-F | CI 7/7 on the release SHA, release assets re-hashed, RELEASE_AUDIT | PASS | `research/v3_0_0/RELEASE_AUDIT.md` |

### 2.2 Mission gates (`GEMINI.md` §16) and the §3 audit leads

| Gate / lead | Status | Notes |
| :--- | :--- | :--- |
| 3.1 Python DPLL timeout → `satisfiable=False, verified=True` | **FIXED** (CQ-V3-01) | `research/v3/DEFECT_REGISTER.md` |
| 3.2 hash-based pruning closes branches | **FIXED** Python + native (CQ-V3-02/02b) | exact memo, brute-force differential |
| 3.3 DIMACS Python/native parity | **FIXED** (CQ-V3-03) | 13 grammar cases, Python = native |
| 3.4 exact-ring `int64` overflow | **FIXED** (CQ-V3-04) | checked arithmetic, boundary tests |
| 3.5 `assert` in Release test | **FIXED** (CQ-V3-05) | 4 files + WILL_FAIL meta-test |
| 3.6 synthetic telemetry shown as live | **FIXED** (CQ-V3-06) | demo-only, labelled every frame |
| 3.7 Vulkan device selection observability | **FIXED** (CQ-V3-07) | policy test; physical GPU still unverified |
| 3.8 hard-coded UI versions | **FIXED** (CQ-V3-08) | canonical version in both UIs |
| Gate A repository truth | PASS | |
| Gate B scientific correctness | PASS after CQ-V3-01…04 | |
| Gate C quantum correctness | PASS within declared scope | existing differential suites |
| Gate D SAT correctness | PASS after CQ-V3-01…03 | brute-force differential, mutants 36–38 |
| Gate E hardware/GPU truth | PASS (fake ≠ real; R-IO-7 is external data; no physical-GPU claim) | |
| Gate F UX/observability | PASS after CQ-V3-06/08 | |
| Gate G software quality | PASS locally; CI on the PR | 38/38 mutants, CTest 21/21 |
| Gate H performance | PASS by abstention: no performance claim | |
| Gate I supply chain | PASS | SBOM and checksums independently verified; no credentials in assets |
| Gate J docs/release | PASS | `v3.0.0` published from `86784b4`; downloaded wheel smoke-tested |

**Hard stop:** any unresolved P0, false UNSAT, false hardware provenance,
fake live telemetry, unguarded exact-arithmetic overflow, hidden
approximation, broken release provenance or failed mandatory CI blocks v3.

---

## 3. When a PR is opened and merged

1. **One coherent change per PR** (a defect class, a feature, a docs sync).
   Branch from current `main`; never force-push shared history.
2. **Before opening:** `flake8 cqhecs tests scripts python_bridge --select=E9,F`,
   `python scripts/check_version.py`, `python scripts/verify_no_silent_truncation.py`,
   the full `pytest`, `cq-hecs selftest`, and — for native changes — a CMake
   build with CTest.
3. **PR body:** problem, change, test evidence with numbers, limitations,
   and what is explicitly not claimed.
4. **Merge** only when all 7 CI jobs are green on the PR head SHA and nothing
   is conflicted. A red CI caused by the base branch is fixed in the PR, not
   waited out.
5. After merging, the next PR starts from the new `main`.

## 4. When and how a release happens

A release is cut only when every gate in §2 is `PASS` (or a documented
`SKIP` that the gate allows). Otherwise the additive work ships as a minor
release (`2.6.0`) or stays on `main` unreleased — never as v3 Stable.

Steps:

1. **Release-candidate PR** that changes only release surfaces:
   `scripts/version.py` → `3.0.0`, then every surface that
   `scripts/check_version.py` checks (`pyproject.toml`, `cqhecs.__version__`,
   CMake, `CITATION.cff`, `llms*.txt`, docs), `CHANGELOG.md` (move
   `[Unreleased]` to `[3.0.0] — date`), `RELEASE_NOTES.md`, README status.
2. **CI on the exact candidate SHA:** 7/7 jobs green.
3. **Merge** the release-candidate PR. The release workflow publishes the
   canonical version from `main` when its tag is missing.
4. **Verify the published release:** download every asset, recompute
   SHA-256 independently, compare with the release's checksum file, install
   the wheel in a clean venv and run the CLI smoke.
5. **Write `research/v3_0_0/RELEASE_AUDIT.md`**: source SHA, CI run URLs,
   asset list with independently recomputed hashes, gate table with final
   status, known limitations. Merge it as a docs PR.
6. A defect found after publication gets an erratum and a patch release;
   published assets are never edited.

## 5. Ordered work plan to v3.0.0

| # | Step | Gate(s) | Done when |
| ---: | :--- | :--- | :--- |
| 1 | Merge PR #25 (M-FIT-2, red-main fix) | G | **done** (`098d12f`) |
| 2 | Fix 3.1/3.2: SAT status enum, timeout = `UNKNOWN`, collision-safe pruning, brute-force differential | D, B | **done** — `DEFECT_REGISTER.md` |
| 3 | Verify/fix 3.3 DIMACS parity | D | **done** — `DEFECT_REGISTER.md` |
| 4 | Fix 3.4/3.5: checked ring arithmetic, Release-safe test checks | B | **done** — `DEFECT_REGISTER.md` |
| 5 | Fix 3.6/3.8: telemetry labelled `DEMO DATA`/`UNKNOWN`, version from the canonical surface | F | **done** — `DEFECT_REGISTER.md` |
| 6 | Verify 3.7 Vulkan device observability; document or fix | E | **done** — `DEFECT_REGISTER.md` |
| 7 | V3-C Sycamore gates + mutants | V3-C | **done** |
| 8 | V3-E migration guide + migration test | V3-E | **done** |
| 9 | Release candidate PR → CI → merge → verify assets → RELEASE_AUDIT | V3-F, J, I | **done** — `v3.0.0` released 2026-10-30 |

Each step is its own PR, merged before the next starts, so `main` stays
releasable and every gate change has its own CI evidence.
