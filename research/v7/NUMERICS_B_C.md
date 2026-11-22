# NUMERICS_B_C: Path B / Path C numerical assurance (W6, agent B1)

Status vocabulary: PROVEN = follows from an argument written here; TESTED = checked
on enumerated finite cases against an independent dense reference (Qiskit
`Statevector`) at float64 tolerance; NOT DERIVED = no bound is claimed.

## Result-field semantics (unchanged)

- `error_bound` Path C = `0.0` means "no deliberate budget approximation"; it is not a
  round-off bound. Path B = total dropped branch weight (see below).
- `numerical_error_bound` is `None` for both paths: no end-to-end float64 bound is
  derived. `None` means "not derived", never zero.
- Typed refusal on resource limits: Path C returns `unresolved=True`, `exact=False`,
  `error_bound=inf`, empty counts. Path B raises `StabilizerRankError` / `ValueError`.

## Path B

| Claim | Status |
|---|---|
| The T / RZ / RX / RY expansions `c0*I + c1*P` are algebraically exact | PROVEN (algebra in source comments; matches dense on tests) |
| Dropped branch (|weight| <= 1e-15) perturbs the unnormalised state by at most its |weight| (each Clifford branch state has unit norm, triangle inequality) | PROVEN |
| `error_bound` = sum of dropped |weight| | PROVEN as bound on the dropped-branch contribution only |
| Total float64 error of the branch sum is <= `error_bound` | FALSE in general. Observed: 12 x rx(0.1) on 2 qubits gives dropped mass 2.4e-16 but observed norm deviation 1.1e-13. Round-off dominates; hence `numerical_error_bound=None` |
| State agrees with dense reference to 1e-12 (3 families: Clifford+T, rotations, random low-T) | TESTED |
| Counts within the Hoeffding `sampling_error_bound` (20000 shots, fixed seed) | TESTED |
| Conditioning | Born sum is checked (refuse if not within 1e-6 of 1) then probabilities are renormalised. Metadata now reports `born_norm_sum`, `norm_deviation`, `renormalization_factor`, `renormalization_applied`, `discarded_branch_count`. A deliberately doubled state is refused (TESTED) |
| Finding: the drop policy is nearly unreachable | A single rotation by a small angle (|theta| < 1e-7) is classified Clifford, so no branch is created. Drops occur only via products of many small weights (tested with 12 gates). Recorded, not a defect |

## Path C

| Claim | Status |
|---|---|
| Gate operand/axis mapping, non-adjacent swap network, Qiskit endianness | TESTED on 10 circuit families (Bell, GHZ, QFT, long-range, swap network, reversed-operand controlled rotations, inverse identity, random n=3,5,7) vs dense, max abs amplitude error < 1e-10 |
| Reduced density matrices on subsets match dense (1e-10) | TESTED |
| Sampled counts within Hoeffding bound (4 families, 20000 shots) | TESTED |
| SVD instrumentation added: `max_discarded_singular_value`, `max_discarded_relative`, `min_retained_relative`, `svd_count`, `svd_steps_with_discard`, `state_norm_sq_at_sampling` (metadata only; no behaviour change) | TESTED |
| Relative floor 1e-13 on the tiny families: nothing discarded above the floor, smallest retained relative value > 1e-13 | TESTED |
| The floor can discard a genuine Schmidt value | TESTED: crx(4e-14) is discarded, reported (`numerical_rank_truncation_applied=True`, status `numerical_rank_reduced`), observed state error < 1e-12, no certificate issued |
| Sum of per-SVD discarded values bounds the final-state error | NOT DERIVED (does not compose across rewrites; kept as diagnostic only) |
| Mapping defects are detectable | TESTED by injection: removing swap-back, dropping the operand-order conversion, and skipping the endianness reversal each fail the dense/count comparison |
| Resource refusal gives typed UNRESOLVED with no counts | TESTED (1 MB budgets; either completes or is UNRESOLVED) |

## Not covered

No analytic float64 error propagation for either path; no n > 7 dense comparison for
Path C (statevector ceiling 20 is a resource limit, not exercised here); no GPU/native
variants; no tolerance sweeps beyond the cases above.

## Files

Source (instrumentation only): `cqhecs/backends/path_b_stabilizer_rank.py`,
`cqhecs/backends/path_c_mps_exact.py`. Tests: `tests/test_path_b_numerics.py`,
`tests/test_path_c_numerics.py`.
