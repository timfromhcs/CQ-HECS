# Migration notes — SAT / unified portfolio (stream S, Wave 3)

## `UnifiedResult` gains `certified` and `proof_level` (D3, W3-09) — ADDITIVE

`solve_unified` previously labelled any engine `UNSAT` as "DRAT proof checked by cqhecs.drat"
and `UnifiedResult` had no certification field. Now:

- `UnifiedResult.certified` (bool) and `UnifiedResult.proof_level`
  (`MODEL_VERIFIED` | `TREE_RESOLUTION_CHECKED` | `DRAT_CHECKED` | `UNCERTIFIED` | `REJECTED` |
  `NONE`) are derived from the engine's own result, and appear in `to_dict()`.
- `solve_unified(..., require_certified=True)` refuses an uncertified `UNSAT` (records the
  attempt as `UNKNOWN`) and keeps searching: "UNSAT with a checked certificate, or UNKNOWN".
- `attempts[].proof` now reads `UNCERTIFIED: ...` where the proof was not accepted, instead of
  `DRAT proof checked by cqhecs.drat`.

## `SATResult.proof_status` — ADDITIVE

Machine-readable outcome of an UNSAT proof check: `accepted` | `rejected` | `undecided` |
`disabled` | `None`. Set by `cqhecs.sat` (tree-resolution) and `cqhecs.sat_external` (DRAT).
`certified` is True only for `accepted`. `to_dict()` includes `proof_status`.

No status string changed meaning; this is additive. Consumers that only read `status` and
`assignment` are unaffected. A consumer that previously trusted an `UNSAT` + a non-null
`attempts[].proof` as "proof checked" must now check `certified`/`proof_level`.
