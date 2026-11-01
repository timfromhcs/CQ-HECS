# HCS SHA Forge — Architecture as built

```
Browser (HTTPS or localhost)          Host-local bridge (127.0.0.1)           TimsMiner (private LAN)
web/forge.html + src/forge/*  ──────▶ cqhecs/hardware/bridge.py  ──────────▶ GET /api/system/info only
 SHA reference, trace, probe          allowlist, tokens, CORS, limits          (nothing else, this release)
 WebGPU u32 kernel + CPU oracle
```

## Components (all new, none replaces an existing CQ-HECS contract)

| Path | Role |
|---|---|
| `cqhecs/sha/sha256_reference.py` | Readable FIPS 180-4 SHA-256, explicit mod-2^32, reduced rounds, explicit IV, `sha256d`. No `hashlib` use. |
| `cqhecs/sha/round_trace.py` | Per-round traces as fixed-width hex (`hcs.sha.trace.v1`), replay that rejects any tampered value, SHA-256d header trace with midstate, nonce candidate replay, differential view. All tagged `SOFTWARE_REPLAY`. |
| `cqhecs/sha/model.py` | `ShaTask` / `ShaResult` / `ShaState` (COMPUTED, CANDIDATE, VERIFIED, UNRESOLVED, UNSUPPORTED, FAILED, SIMULATED) with an integrity digest. Separate from `SimulationResult`. `SIMULATED` only on `DEMO_SIMULATED`; ASIC results require a firmware version. |
| `cqhecs/hardware/state_machine.py` | Explicit states; DEMO cannot reach any hardware state; arming and restore need operator confirmation; FAULT / RECOVERY_REQUIRED have no automatic retry. |
| `cqhecs/hardware/miner_capabilities.py` | Allowlist of exactly `timsminer`; `blackharkminer`, `timminer2` hard-excluded; identity = hostname + board + ASIC + MAC, all must match; missing field fails closed. |
| `cqhecs/hardware/miner_protocol.py` | `/api/system/info` → `hcs.sha.miner.v1`, unknown → `null`, secrets never copied. |
| `cqhecs/hardware/evidence.py` | ESP image/app-descriptor inspection, backup manifest where every flag comes from a check that ran, recheck from file, restore preview. |
| `cqhecs/hardware/bridge.py` | Loopback-only HTTP service, exact-origin CORS, pairing token with TTL, POST-only mutation routes, rate limit, strict JSON, 4 KiB body cap. **Read-only**: work/flash routes answer `403 READ_ONLY`. `--simulate` runs without any LAN access. |
| `web/src/forge/{sha,gpu_sha,backends,demo,i18n,main}.ts`, `forge.html` | Browser analyzer, WGSL u32 batch kernel with CPU oracle self-test, backend probe with visible fallbacks, seeded demo fixtures, EN/DE/FR. |

## What the ASIC path is and is not

The BM1366 executes the firmware's fixed Bitcoin-style SHA-256d job path. It is a nonce-search endpoint. It does not expose
round registers, schedule words or traces, and is not a general SHA accelerator. Nothing in this repository claims otherwise.
The Round Analyzer is software; every value carries `SOFTWARE_REPLAY`.

## Security posture

Bridge never binds beyond loopback; no wildcard CORS; no proxy; no scan; no arbitrary register, UART or flash route;
no logging of headers or bodies; tokens expire and can be revoked; demo mode makes zero non-same-origin requests (E2E-tested).
The bridge's only device call is a GET of the stock info endpoint for one exact configured host, with redirects disabled.
