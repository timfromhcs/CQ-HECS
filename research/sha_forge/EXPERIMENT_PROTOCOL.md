# HCS SHA Forge — Experiment protocol

Applies to every future experiment (software, WebGPU, ASIC). Hardware steps need operator approval first.

1. **Pre-register** in `HYPOTHESES.md`: scope, workload (exact operation, compression calls per candidate, midstate yes/no), baseline, oracle, budget, threshold, falsification. Do not change the metric after seeing results.
2. **Record the environment:** commit SHAs, toolchain, browser feature flags and adapter limits (no UA fingerprinting), firmware version/build id and running partition for hardware, clock/voltage/thermal state, measurement window.
3. **Verify independently:** every candidate (nonce, trace, solver witness) is recomputed by a separate path; the producer never certifies itself.
4. **Repeat and report spread:** median/p95/min/max over repeated runs; single runs are observations.
5. **Units:** never put compressions/s, rounds/s and ASIC GH/s on one axis without a stated conversion. Missing samples stay gaps.
6. **Negative results are kept.** `UNRESOLVED` means budget exhausted, never `UNSAT`.
7. **Hardware gate order:** read-only identity → 60-minute baseline → verified backup (two copies) → approved bounded test → verified restore. A step not run is `NOT TESTED`.
