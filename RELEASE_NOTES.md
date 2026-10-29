# CQ-HECS Release Notes

**Version:** 2.5.0
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.5.0.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.4.0` is a **feature release** on top of `v2.3.0`. It adds exact Pauli
expectation values (CLI and Python), nine more exact gate lowerings and a
small independent dense reference simulator, and it closes three result-contract
findings from the v2.4 audit. It adds **no new simulation path, no new exactness
claim and no GPU acceleration**.

Existing `2.x` result metadata stays compatible; the only behavioural changes
are that `SimulationResult.total_error_bound` is `None` in cases where it used to
print a misleading number, and that circuits using the newly lowered gates now run
instead of being refused.

| Surface | Status in 2.5.0 |
| :--- | :--- |
| `cqhecs` four-path router/backends | supported; composite gates lowered exactly |
| `cqhecs.expectation` (Pauli expectation values) | supported; exact on Clifford and dense registers, certified beyond |
| `cqhecs.backends.dense_reference` | supported reference / oracle, up to 26 qubits (22 by default) |
| `cq_hecs::core::StateVectorSimulator` | supported dense reference, <= 28 qubits |
| `cq_hecs::core::MPSSimulator` | experimental CPU reference |
| Vulkan compute primitives | dispatch verified on one AMD iGPU; no end-to-end GPU acceleration |
| `cqhecs::vulkan::VulkanEngine` | planner-only memory allocator |
| Legacy native QASM executor | legacy phase ledger; keeps its smaller gate set |

## 2. Added

### Pauli expectation values

```bash
cq-hecs expect name:bell -o ZZ -o XX -o YY
cq-hecs --format json expect name:ising6 -o "X0 X1" -o Z0
```

```python
from cqhecs import expectation_values
res = expectation_values(circuit, {"H": [(0.5, "ZZ"), (-1.25, "XX")]})
res.values, res.method, res.exact, res.error_bound
```

| Engine | When | Result |
| :--- | :--- | :--- |
| `stabilizer` | Clifford circuit, <= 4096 qubits | exact `-1, 0, +1` read from the tableau, no sampling |
| `dense` | up to 22 qubits (ceiling 26) | exact float64 statevector; no deliberate approximation |
| `sparse_pauli` | wider non-Clifford circuits | Path D, certified bound; `None` + `unresolved` if the bound exceeds the tolerance |

`method="auto"` takes the first row that applies. Pauli strings are dense Qiskit
labels (`IZX`, rightmost = qubit 0) or sparse (`X0 Z2`). Mid-circuit measurement
and `reset` are refused; terminal measurements are ignored. Path D keeps its
gate set, so a wide circuit with `cp`/`crx`/... is refused with an explicit
message rather than approximated.

### More exact gate lowerings

`r`, `iswap`, `dcx`, `ecr`, `cu3`, `cu`, `csx`, `c3x`, `c4x` (Qiskit `mcx`
with 3 or 4 controls). Each is checked as a unitary identity against Qiskit,
global phase included. Wider `mcx` stays refused.

## 3. Fixed

- **CQ-NEXT-H0:** `total_error_bound` is `None` for unresolved or failed
  results, for independent-marginal counts and whenever `error_bound_covers`
  is not a distribution metric. Path D's observable bound is never composed
  into a total-variation number for sampled counts.
- **CQ-NEXT-H1:** Path C's numerical-rank floor can drop a nonzero Schmidt
  coefficient; results report `numerical_rank_truncation_applied`,
  `discarded_singular_value_sum` and `numerical_status`, separate from
  `bond_dimension_truncation_applied`. Wording of `exact` now matches.
- **H8:** documented the simultaneous (union-bound) meaning of
  `hoeffding_proportion_bound` and the conservative `K ln 2` replacement; both
  bounds are pinned by exact-formula tests.
- Qiskit `ExperimentResult.header` forwards the above contract fields.
- Width of an instruction list with an idle top qubit no longer shrinks inside
  Path D when called through the expectation API.

## 4. Tests

- New: `tests/test_expectation.py` (20), `tests/test_cli_expect.py` (7),
  `tests/test_confidence_bounds.py` (8); lowering tests extended to 12.
- Oracles: Qiskit `Statevector`/`SparsePauliOp`, closed-form stabilizer
  states, and exhaustive comparison of all `4^n` Pauli strings between the
  stabilizer and dense engines on random Clifford circuits.
- Mutation gate: 14 mutants (new: stabilizer-expectation sign, dense Pauli-Y
  orientation).
- Random differential fuzzing (not committed, run during the audit): 500 mixed
  circuits on Path C and 300 on Paths A/B against `Statevector`, all agreeing.
- Exact-SHA Linux/Windows CI results are recorded in the pull request and the
  published release, not inferred from local runs.

## 5. Limits and non-claims

- The dense engine is float64 without a roundoff bound; its `error_bound` of
  `0.0` means "no deliberate approximation".
- `sparse_pauli` certifies expectation values only, never a sampled
  distribution, and supports Path D's gate set.
- Expectation values for non-Clifford circuits above 22 qubits depend on the
  Pauli-term budget; unresolved is a normal outcome.
- No noise models, density matrices, mid-circuit measurement or reset.
- Vulkan evidence covers primitive dispatch only; there is no end-to-end GPU
  acceleration claim. No real quantum hardware was used.
- Web search was unavailable while this release was prepared, so the SOTA
  comparison relies on repository metadata (GitHub API) and the earlier
  OpenAI Math audit, not on fresh papers. See `research/v2_4/`.

## 6. Installation and smoke test

```bash
python -m pip install cqhecs-2.4.0-py3-none-any.whl
cq-hecs version
cq-hecs doctor
cq-hecs --format json expect name:bell -o ZZ -o XX
```

The pure-Python wheel does not contain the native C++/Vulkan binaries. Build
those from source with CMake and a C++20 toolchain if you need the native
reference paths.

## 7. Evidence

- `CHANGELOG.md` - `[2.4.0]` section.
- `research/v2_4/` - baseline, hypotheses, findings, test matrix, literature map.
- `tests/test_expectation.py`, `tests/test_confidence_bounds.py`.
- The published release body records the exact source SHA and required CI run.
