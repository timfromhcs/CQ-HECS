# Migrating from 2.x to 3.0

v3 changes a few contracts on purpose: in each case the old behaviour could
report something that was not true. This page lists every change a caller can
observe, in order of how likely it is to affect you.

## 1. Hardware profiles: schema 2.0

| | 1.0 | 2.0 |
| :--- | :--- | :--- |
| Read by v3 | yes, unchanged | yes |
| Written by `calibration_import` | — | always |
| Extra fields | — | `calibration_flags`, `source_sha256` |

- A 1.0 document still loads. It may not contain the 2.0 fields; a 1.0
  document that does is refused with `InvalidProfileError`.
- `BackendProfile.migrated_to_v2()` returns a 2.0 copy. Every physics field
  (topology, gate and readout errors, T1/T2, durations) is copied unchanged,
  and the new fields stay empty: migration never invents flags or digests.
  The derived noise model is identical before and after.
- From the command line:

  ```bash
  cq-hecs profile migrate old_profile.json new_profile.json
  ```

  The input can be a bare profile or the output of
  `cq-hecs --format json profile show <name>`.
- There is no downgrade from 2.0 to 1.0.

## 2. Python SAT engine (`python_bridge.sat_engine`)

| Field | 2.x | 3.0 |
| :--- | :--- | :--- |
| `satisfiable` | `bool` | `True`, `False`, or **`None`** (unknown) |
| `verified` | `True` for every non-SAT result, including timeouts | `True` only for a checked witness or an exhaustive UNSAT |
| `status` | — | `SAT_VERIFIED`, `UNSAT_PROVEN`, `TIMEOUT_UNKNOWN` |
| `timed_out` | — | `True` when the budget ran out |

Code that tested `if not result.satisfiable:` treated a timeout as UNSAT. Use
`result.status == UNSAT_PROVEN` instead. `num_pruned_cycles` now counts hits
in an exact memo of refuted states, not hash matches.

## 3. DIMACS parsing (Python)

`DIMACSParser.parse_string` now follows the native parser's grammar and
raises `DIMACSParseError` (a `ValueError`) instead of repairing input:

- a clause may span lines and ends only at `0` (2.x split it per line);
- `0` alone is an empty clause, which makes the formula UNSAT (2.x dropped it);
- an unterminated final clause, a malformed or duplicate header, a negative
  count, a non-integer token and a literal above the declared variable count
  are errors.

## 4. Exact rings (C++)

`cq::Cyclotomic8` and `cqhecs::algebra::ExactRingElement` throw
`std::overflow_error` when a coefficient or the exponent `k` would leave
`int64_t`/`uint32_t`. Arithmetic operators are no longer `noexcept`. Equality
compares canonical forms and never throws or overflows.

## 5. Dashboards

`python -m python_bridge.tui_dashboard`, `cli_runner dashboard` and the native
`cq_hecs dashboard` show synthetic values only. They now need `--demo`, exit
with a usage error without it, and label every frame
`SIMULATED DATA - NOT A MEASUREMENT`.

## 6. Vulkan device selection (native)

Set `CQ_HECS_VULKAN_DEVICE` to a device index or a case-insensitive name
substring to pick a device. If the request matches nothing, initialisation
fails; it never falls back to another device. Without the variable the
automatic order is discrete GPU, integrated GPU, software rasteriser, other.

## 7. Additions that need no change

- Sycamore gates: `fsim`, `syc`, `phased_x`, `sqrt_x`, `sqrt_y`, `sqrt_w`
  (see `docs/QASM_CONTRACT.md` §6).
- `cq-hecs reference run --dataset r-io-7` and `cq-hecs noise-fit`
  (measured Open Quantum data; `research/v3/OPENQUANTUM_RUN_PLAN.md`).
- `calibration_status` in the `r-io-7` evaluation output.
