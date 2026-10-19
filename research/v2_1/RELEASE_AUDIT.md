# CQ-HECS v2.0.0 Release Audit & v2.1 Release Readiness

**Audited Reference Date:** 2026-10-19  
**Auditor:** CQ-HECS Autonomous Engineering & Research Mission  
**Baseline Git Range:** `19df10cdc80f26dc9bb81b4438192c084845f477` (v2.0.0 Tag) to `ef7cbbda47c39cdad0f77050c1e6a8c0c2727cf1` (`origin/main`)  

---

## 1. Published Release v2.0.0 Audit

| Field | Detail | Evidence Label |
| :--- | :--- | :--- |
| Release Tag Name | `v2.0.0` | **observed locally**, **observed in GitHub Actions** |
| Tag Object SHA | `9ed0a3af0b4dd154ba01ebe0644a8afd46ecee95` | **observed locally** |
| Target Tag Commit | `19df10cdc80f26dc9bb81b4438192c084845f477` (Merge PR #2) | **observed locally**, **observed in GitHub Actions** |
| Publication Timestamp | `2026-10-19T13:33:30Z` | **observed in GitHub Actions** / GitHub API |
| Release Workflow Run | Run ID `39261093300`, duration 40s, conclusion `success` | **observed in GitHub Actions** |
| Canonical Version | `2.0.0` | **observed locally**, **derived from source** |

### Published Assets and Verified SHA-256 Hashes

The assets published under GitHub Release `v2.0.0` were recorded in `audit/release_tracking.json`:

1. `cqhecs-2.0.0-py3-none-any.whl`:
   - SHA-256: `7b55f73ceb61d865d208fbd8b6a970424797aaa81df1763b6fe34bb323fba5e2`
   - Evidence Label: **derived from source**, **observed in GitHub Actions**.
2. `cqhecs-2.0.0.tar.gz`:
   - SHA-256: `730fd84f16280d64925b55be35aa6eb480319edb9363852f000e57d1f30aa5e3`
   - Evidence Label: **derived from source**, **observed in GitHub Actions**.
3. `cqhecs-sbom.spdx.json`:
   - SHA-256: `85a1163cc770e2281605d27ec12dcabe446a02408df9bf414c30f26d5c43fb78`
   - Evidence Label: **derived from source**, **observed in GitHub Actions**.
4. `RELEASE_NOTES_v2.0.0.md`:
   - SHA-256: `6020c2db7a8e0c2317c0286d8daf2491219f28243c5886be6fc7d8d02cbab6e4`
   - Evidence Label: **derived from source**, **observed in GitHub Actions**.
5. `sha256sums.txt`:
   - SHA-256: `8c50c39d100e3c4088da4f4ddb31e258224854396f42e884f5c29739292927be`
   - Evidence Label: **derived from source**, **observed in GitHub Actions**.

---

## 2. Commit Analysis: v2.0.0 to `origin/main`

Two commits exist on `origin/main` that follow the tagged commit `19df10c`:

1. **Commit `714d675` ("fix(release): cover every published asset in sha256sums.txt")**:
   - In the initial v2.0.0 release workflow, `generate_sbom_and_checksums.py` executed *before* `RELEASE_NOTES_v2.0.0.md` was copied into `dist/`. Consequently, `sha256sums.txt` lacked a line for the release notes.
   - Commit `714d675` reordered the steps in `.github/workflows/release.yml`, modified `scripts/generate_sbom_and_checksums.py` so that only `sha256sums.txt` itself is skipped when generating digests, and updated `audit/release_tracking.json`.
   - Evidence Label: **derived from source**, **observed locally**.

2. **Commit `ef7cbbd` ("Merge pull request #3 from timfromhcs/fix/release-checksum-coverage")**:
   - Merged PR #3 into `main`. CI run `39262998612` on `main` succeeded.
   - Evidence Label: **observed in GitHub Actions**.

**Finding:** The published `v2.0.0` release tag points to `19df10c`, while the asset coverage fix is in `ef7cbbd`. Under SemVer and release safety rules (§0), `v2.0.0` remains immutable. The fix is already present in `origin/main` and will naturally be part of the `v2.1.0` release.

---

## 3. Immediate P0 Architectural & Correctness Audit

### P0-A. Mutation-Harness Trustworthiness

- **Code Inspected:** `scripts/run_mutation_tests.py` and `tests/test_mutation_harness_meta.py` (if present) or inline contract assertions.
- **Current Logic:**
  - The script executes baseline assertions on unmutated code first.
  - 7 mutants are tested in isolated environments:
    - Mutant 1: Tableau phase corruption
    - Mutant 2: Stabilizer-rank branch coefficient
    - Mutant 3: MPS non-unitary site tensor
    - Mutant 4: Sparse-Pauli error-bound suppression
    - Mutant 5: Unresolved-flag suppression
    - Mutant 6: Path C fabricated wide counts
    - Mutant 7: Bit-order reversal
  - Each mutant is evaluated against an independent assertion that verifies whether the injection was detected.
- **Audit Finding:**
  - On the current codebase, baseline assertions pass and 7/7 mutants are detected (killed), exiting with code 0.
  - However, contract requirements in `GEMINI.md` §3 (P0-A) demand explicit meta-tests that deliberately supply a broken baseline, a surviving mutant, and a killed mutant to ensure the harness exits non-zero on any harness fault or surviving mutant.
  - Evidence Label: **derived from source**, **observed locally**.

### P0-B. Path C Contract and 200+ Qubit Sampling

- **Code Inspected:** `cqhecs/backends/path_c_mps_exact.py`.
- **Current Logic:**
  - Circuit is represented as an array of rank-3 tensors (physical dimension 2, left/right bond dimensions).
  - Two-qubit gates are applied by contracting adjacent sites, performing SVD (`numpy.linalg.svd`), and splitting tensors.
  - When sampling is requested (`_sample_counts`), the code checks:
    ```python
    if self.num_qubits > 20:
        return {}
    ```
    and computes the full dense statevector via `to_statevector()`, which expands to $2^n$ amplitudes in RAM ($16 \times 2^{20} = 16\text{ MB}$, but at 200 qubits $16 \times 2^{200}$ would exceed all physical universe storage).
- **Audit Finding:**
  - Refusal to fabricate counts above 20 qubits is strictly adhered to (`return {}`), which prevents false claims.
  - However, to achieve the primary goal of 200+ qubit full-register sampling on low-entanglement/1D MPS states, CQ-HECS requires an **MPS-native sequential conditional sampler** (e.g. right-to-left canonical gauge / norm environment contraction, sequential bit collapse, and conditional marginal evaluation) without ever generating a dense statevector.
  - Evidence Label: **derived from source**, **observed locally**.

### P0-C. Path A Shot-Count Behavior

- **Code Inspected:** `cqhecs/backends/path_a_tableau.py`.
- **Current Logic:**
  - For Clifford circuits, measurements are handled via stabilizer tableau updates.
  - A historical ceiling `MAX_RESAMPLE_SHOTS = 100` existed for wide circuits to limit execution time.
- **Audit Finding:**
  - Truncating or clamping shots without returning the exact requested number of real samples violates the principle that `sum(counts.values()) == shots`.
  - Path A must be capable of generating 1,000+ true independent stabilizer samples efficiently by tableau cloning/resetting, without artificial shot caps.
  - Evidence Label: **derived from source**, **observed locally**.

### P0-D. Path B Resource Bounds

- **Code Inspected:** `cqhecs/backends/path_b_stabilizer_rank.py`.
- **Current Logic:**
  - Decomposition of non-Clifford gates (e.g. $T = \cos(\pi/8) I - i \sin(\pi/8) Z$) into stabilizer branches.
  - Each branch maintains a dense statevector up to `MAX_STATEVECTOR_QUBITS = 22`.
- **Audit Finding:**
  - The 22-qubit limit is a practical statevector RAM bound ($16 \times 2^{22} \approx 64\text{ MB}$ per branch).
  - Dense statevector simulation cannot scale to 200 qubits on Path B without fundamentally different representation (sparse tableau sum or observable Monte Carlo). Thus, Path B must honestly retain its explicit capability limit, while 200-qubit workloads are routed to Path A, Path C, or Path D.
  - Evidence Label: **derived from source**.

### P0-E. Path D Observables API & Error Bounds

- **Code Inspected:** `cqhecs/backends/path_d_sparse_pauli.py`.
- **Current Logic:**
  - Backward Heisenberg propagation of Pauli operators under Clifford + non-Clifford gates.
  - Currently evaluates single-qubit $Z_q$ and all pair parities $Z_q Z_r$ by default.
  - For $n=200$, calculating all pair observables requires $\binom{200}{2} = 19,900$ distinct backward propagations.
- **Audit Finding:**
  - A selective `observables` request API is required so large circuits can request specific target expectation values without incurring $O(n^2)$ overhead.
  - The error bound $\epsilon \le \sum |c_i|$ on discarded Pauli coefficients is certified for expectation values, but does not provide a bitstring distribution guarantee. This distinction is preserved in documentation and API.
  - Evidence Label: **derived from source**.

---

## 4. Release Safety & Governance Checklist

1. **Tag Immutability:** `v2.0.0` is untouched and unchanged.
2. **Dedicated Branch:** All work proceeds on `agent/v2-1-200q-20261019`.
3. **No Mocks in Acceptance:** Acceptance tests use real executions against independent oracles (`Statevector`, `Aer`, `Stim`).
4. **Hardware Honesty:** Physical GPU remains labeled `NOT_VERIFIED` unless real dispatch is executed and measured on verified hardware.
5. **Release Target:** `2.1.0` cleanly reflects new capabilities (MPS sequential sampler, 200+ qubit support on structured circuits, selective observables API).
