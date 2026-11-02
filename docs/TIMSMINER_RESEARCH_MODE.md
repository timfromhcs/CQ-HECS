# TimsMiner research mode — specification only, nothing built

This document records the intended scope. **No firmware, ASIC job path or flash exists in this release.** ESP-Miner is unchanged.

## Boundaries

- Target: only the unit named `timsminer` (Bitaxe Ultra board 201, ESP32-S3, one BM1366). `blackharkminer` and `timminer2` are excluded.
- The BM1366 accepts the firmware's Bitcoin-style SHA-256d work format. It does not accept arbitrary blocks, IVs, round counts or intermediate states, and exposes no round registers or traces.
- Telemetry units: `asic_hashrate_ghs` (device estimate for SHA-256d mining work), `nonce_candidates_per_s`, `host_verified_candidates_per_s`, `sha256_compressions_per_s` (software), raw `asic_domain_counter_delta` (units unverified; never shown as a hash counter).

## Planned (each step gated)

1. Fresh 60-minute baseline on the stock firmware, 30 s sampling.
2. Read-only WLAN backup route, verified backup, two copies.
3. Separate per-device research build with `CONFIG_TIMSMINER_SHA_RESEARCH` default off; pool disconnected, no share submission, bounded synthetic jobs through the existing BM1366 packet path only, no frequency/voltage changes.
4. Host recomputes every returned nonce with `cqhecs.sha.round_trace.replay_candidate`.
5. Restore the verified original over WLAN and validate (10 min smoke, 60 min soak).

Requires explicit operator approval before: any upload to the miner, arming, restart, pool or frequency change, restore.
