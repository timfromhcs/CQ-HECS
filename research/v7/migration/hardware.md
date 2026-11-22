# Migration notes — hardware / noise (stream N, Wave 3)

## Uncovered gates are no longer silently noiseless (D4, W3-06) — ADDITIVE

The noise model is built from `gate_errors` + declared `basis_gates`; circuits are not
transpiled into that basis. A gate the profile never declared (e.g. `h`, `t`, or `sx` which
lowers to `h.s.h`) ran with no channel while the result stayed `NOISY_CLASSICAL`.

New:
- `BackendProfile.uncovered_gates(instructions) -> list[str]`.
- `FakeHardwareBackend(..., uncovered_gate_policy="warn"|"refuse"|"ideal")` (default `warn`).
  `refuse` raises `OutOfModelError` before simulating.
- `SimulationResult.uncovered_gates` (also in `metadata` and `to_dict`).

Caller action: a circuit that used to run (silently noiseless) still runs under the default
`warn`; read `uncovered_gates` to know which gates had no channel. Pass
`uncovered_gate_policy="refuse"` to fail closed instead.

## Synthetic profiles carry no capture timestamp (D4, W3-07) — ADDITIVE

`create_linear_profile` previously stamped `capture_timestamp` with the current time. It is now
`None` for the synthetic profile, so two calls serialise identically and a synthetic profile
cannot be mistaken for a dated device calibration.
