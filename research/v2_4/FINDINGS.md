# Findings ledger

Historical findings remain in their original audit files. Entries below apply to the live baseline `ba27bd1e7d814c79b7982ba3a9739f264f054520` unless a later SHA is stated.

## CQ-NEXT-H0 — Distribution metric composition

- Severity: P0 triage (scientific/result contract).
- Status: **INVESTIGATING**.
- Scope: `SimulationResult.total_error_bound` / `to_dict()` and Path D marginal counts.
- Required evidence: executable matrix covering expectation-only, joint counts, non-joint marginal counts, unresolved/failed results, support sizes and absent numerical bounds.
- Disposition: pending; no fix claimed yet.

## CQ-NEXT-H1 — MPS numerical rank and exactness wording

- Severity: P0/P1 triage (numerical contract).
- Status: **INVESTIGATING**.
- Scope: Path C SVD floor, discarded nonzero singular values, `exact`, `error_bound`, numerical metadata.
- Required evidence: singular-spectrum-aware reproduction and independent statevector differential checks.
- Disposition: pending; no fix claimed yet.

## Baseline infrastructure observations

- The mutation harness completed successfully and restored source content; `git diff` showed no source-content changes from its temporary patches.
- Recursive OpenAI Math tree API returned `truncated=true`; no complete manifest count is inferred from that response. Upstream README counts are labelled as upstream-reported.

## Resolution record (candidate branch `agent/cq-hecs-v2.4.0-expectation-values`)

| ID | Severity | Status | Root cause | Fix | Regression test |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CQ-NEXT-H0 | P0 | CONFIRMED -> fixed | `total_error_bound` summed a Path D observable-space bound (and unresolved/failed or independent-marginal results) into a total-variation figure. | `total_error_bound` returns `None` unless the result is a successful, joint distribution whose `error_bound_covers` is a distribution metric. | `tests/test_correctness_contracts.py` (result-state matrix, Path D marginals); `evidence/h0_regression_*.log` |
| CQ-NEXT-H1 | P0/P1 | CONFIRMED -> fixed | The relative singular-value floor can drop a nonzero Schmidt coefficient while the result claimed an unqualified exact state. | Explicit `numerical_rank_truncation_applied`, `discarded_singular_value_sum`, `numerical_status`; bond-budget truncation reported separately; `exact` wording redefined. Forwarded to the Qiskit header. | `tests/test_correctness_contracts.py` (floor boundary eps = 5e-14, 1e-13, 2e-13); `tests/python/test_qiskit_backend_contract.py` |
| CQ-NEXT-H8 | P1 | REVIEWED -> doc fix | Re-derivation of the Weissman/Mardia bound (`phi >= 2`) is correct; the docstring claimed the `-2` correction was "below double precision" for all K (false for K = 3..53) and described the Bonferroni `delta` as per-coordinate. Implementation was already conservative. | Docstrings corrected. | `tests/test_confidence_bounds.py` (8) |
| CQ-NEXT-F1 | P2 | CONFIRMED -> fixed | README error-handling example used `result.unresolved` / `result.diagnostics`, which do not exist on a Qiskit `Result`; it raised `AttributeError`. | Example now reads `job.simulation_results[0]` and the header. | `TestDocumentedErrorHandling` |
| CQ-NEXT-F2 | P2 | CONFIRMED -> fixed (new) | Path D infers width from the highest used qubit of an instruction list; an observable on an idle top qubit was rejected (`bit 4 beyond the 4-qubit system`). | Expectation API appends `id` on the last qubit before every Path D run. Path D itself is unchanged (documented limitation for raw instruction lists). | `tests/test_expectation.py::SparsePauliAgreementTests` |
| CQ-NEXT-F3 | P2 | CONFIRMED -> fixed | Standard gates (`r`, `iswap`, `dcx`, `ecr`, `cu`, `cu3`, `csx`, `mcx` with 3-4 controls) were unknown to the manifest. | Exact lowerings (see `cqhecs/gate_lowering.py`). | `tests/test_gate_lowering.py` (12) |

Unfinished predecessor edit: `cqhecs/backend.py` defined `contract_metadata_keys` but never used it (pyflakes F841 under the new CI lint). Completed by forwarding the keys into `ExperimentResult.header`.

Randomised differential evidence (scratch scripts, not committed): 500 mixed circuits (n = 3..5, 28 gate types incl. all lowerings) on Path C vs Qiskit `Statevector` (TVD <= 0.04 at 20k shots) and 300 circuits on Paths A/B; zero mismatches.
