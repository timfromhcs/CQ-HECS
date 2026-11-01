# HCS SHA Forge — Hypotheses

Status vocabulary: `PROPOSED`, `IN_PROGRESS`, `SUPPORTED_IN_SCOPE`, `INCONCLUSIVE`, `REJECTED`, `DEFERRED`.

## H-SHA-01 — Independent reference conformance — `SUPPORTED_IN_SCOPE`
- **Statement:** The Python and TypeScript references compute FIPS 180-4 SHA-256, SHA-256d and 64-round traces identically.
- **Oracles:** `hashlib`, `node:crypto`, Web Crypto, NIST/CAVS vectors, genesis header, constants re-derived from prime roots, and cross-language trace equality (Python-generated fixture compared round by round in TS).
- **Success:** every vector, boundary length (0,1,54–57,63–65,119–129,1000) and 300 random messages agree; every round satisfies the T1/T2 equations.
- **Falsification:** any single disagreement. Negative controls (wrong IV, no feed-forward, endian swap, mutated K, off-by-one rounds) must all change the digest — they do.
- **Scope:** the declared software workload only. Says nothing about hardware.

## H-WGPU-01 — WebGPU u32 kernel matches the CPU oracle — `SUPPORTED_IN_SCOPE` (one browser)
- **Statement:** The WGSL batch compression kernel equals the CPU reference for 64 and 20 rounds on the self-test blocks.
- **Evidence:** self-test passed in the in-app Chromium (adapter present); 65 536-block batch's first 64 outputs matched the CPU.
- **Not tested:** other browsers/adapters, device loss mid-run (covered only by mocked fallback tests), adversarial limits.
- **Falsification:** any mismatch on any adapter → the probe already refuses that backend.

## H-WGPU-02 — WebGPU is faster than the browser CPU path — `INCONCLUSIVE`
- One run on one machine measured ≈4.6 M compressions/s (incl. transfer) vs ≈0.115 M/s for the TypeScript reference. That is a single un-repeated measurement; the TS reference is deliberately readable, not optimised. No general speed claim is made. Required: repeated runs, median/p95, hardware metadata, an optimised CPU baseline.

## H-ASIC-01 — Returned BM1366 nonces re-verify on the host — `PROPOSED` (`NOT TESTED`)
- Host-side `replay_candidate` exists and rejects flipped nonces. No ASIC data has been captured.

## H-ASIC-02 — Research firmware keeps ≥90 % of the baseline hashrate at an equivalent operating point — `DEFERRED`
- Needs the 60-minute baseline, a built research image, and operator approval to flash. None exist yet. Gate must be re-defined if metric, frequency, power or window differ.

## H-BRIDGE-01 — The bridge fails closed — `SUPPORTED_IN_SCOPE` (simulated device)
- Excluded/mismatched/missing-identity devices never yield telemetry; foreign or absent Origin cannot pair; GET on mutation routes → 405; work/backup routes → 403 `READ_ONLY` without touching the device. Tested against a fake device and in a real browser against `--simulate`. **Not tested against the physical unit.**
