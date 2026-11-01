# Research firmware contract (ESP-Miner branch `feat/timsminer-sha-research-mode`)

Status: **IMPLEMENTED, FLASHED AND VALIDATED ON `timsminer`** (2026-11-02). The
miner ran the research image, served a 64-round software trace that the Python
reference accepted unchanged, and returned to mining afterwards. The evidence is
in §5 and in `FIRMWARE_BUILD.md`.

## 1. What the firmware adds

A build-time feature flag (`CONFIG_TIMSMINER_SHA_RESEARCH`, default `n`) that adds
nine named routes and a software SHA-256 oracle:

| Route | Method | Effect |
|---|---|---|
| `/api/research/status` | GET | typed status (`hcs.sha.miner.v1`, `kind: research_status`); also runs the watchdog |
| `/api/research/capabilities` | GET | declared features and explicit limitations |
| `/api/research/challenge` | POST | issues a 6-digit pairing token **to the serial log only** |
| `/api/research/arm` | POST | `{"token":"…"}`, single use, TTL-bounded |
| `/api/research/pause` / `resume` / `cancel` / `disarm` | POST | session transitions |
| `/api/research/sha256` | POST | software trace of a client-supplied 64-byte block, or a message digest |

Nothing in this surface writes flash, changes a partition, reboots the device,
touches the pool/worker/wallet, or raises a thermal/power/frequency limit.

## 2. What it deliberately is not

- **Not ASIC round access.** The BM1366 computes SHA-256d internally and returns
  nonces over the UART. There is no readable round state, no writable message
  block, no selectable IV. `capabilities.limitations.asic_access` is `"none"`, and
  `cqhecs.hardware.firmware_profile.reject_asic_round_claim()` refuses any
  document that claims otherwise — including a locally written profile.
- **Not a generic compute service.** The oracle accepts one 64-byte block (or a
  ≤512-byte message), a round count 0–64 and a feed-forward flag. Nothing else.
- **Not a remote shell.** No register writes, no `exec`, no arbitrary path.

## 3. Authorisation model

`main/research/research_guard.c` is dependency-free decision logic with 105 host
assertions (`simulation/test_research_guard.c`). A session can only be armed with:

1. a token offered by `POST /challenge` and typed back within its TTL (default
   120 s), consumed on success, never re-usable;
2. `identity_verified`: this build is the `esp-miner` application, on an
   ESP32-S3, with an initialised ASIC and a known board;
3. no pool connection and no share in flight (`pool_connected`,
   `share_in_flight`);
4. a fresh chip temperature below the Kconfig ceiling (default 65 °C, hard-capped
   at 70 in Kconfig and 85 in the guard — it can only tighten the device's own
   protection);
5. a measured power below 30 W, *when power is measured*; unknown power is
   recorded as `power_verified: false` rather than silently assumed good;
6. remaining job and time budget (default 64 jobs / 900 s, 15 min active time
   excluding pauses).

Unknown is unsafe: a missing or NaN temperature, a backwards clock, or an
unverified identity all end the session. A failed `/arm` does **not** burn the
token, so a stray request cannot invalidate the operator's pending challenge; a
successful arm does consume it.

Temperature and power are read from the values the power-management task already
publishes (`POWER_MANAGEMENT_MODULE.chip_temp_avg`, `.power`); the HTTP handler
never touches I2C/PMBus, so a research request cannot stall the sensor bus.

## 4. The trace contract

`POST /api/research/sha256` with `{"block_hex": "<128 hex>", "rounds": 64,
"feed_forward": true}` streams:

```json
{"schema":"hcs.sha.device_sha256.v1","kind":"block_trace","compute":"software_cpu",
 "asic_access":"none","firmware_version":"…","trace":{ /* hcs.sha.trace.v1 */ }}
```

The nested trace is the unmodified Python-compatible document, so
`cqhecs.sha.round_trace.replay()` validates it without a special case. Provenance
lives in the envelope only, because `replay()` compares round objects field by
field and an extra key inside a round would look like tampering.

## 5. Evidence produced so far

The first real session on the unit (2026-11-02, 12/12 steps):

| Check | Result |
|---|---|
| `GET /api/research/status` | `research_enabled: true`, `state: disarmed`, `identity_verified: true`, thermal 53 °C, ceiling 65 °C |
| `GET /api/research/capabilities` | `compute: software_cpu`, `asic_access: none`, features `sha256, sha256d, round_trace, reduced_rounds` |
| `POST /api/system/pause` | `pool_connected` became `false` → `arm` accepted |
| Pairing | 6-digit token read from the COM3 console, `arm` → `state: armed` |
| `POST /api/research/sha256` (64 bytes of zero, 64 rounds) | 64 rounds returned; **`cqhecs.sha.round_trace.replay()` accepted every value**, `output_state = da5698be…837a9d8`, identical to the host C implementation |
| `POST /api/research/sha256` (`616263`, `sha256d`) | `4f8b42c2…c6358` — the published SHA-256d("abc") value |
| `GET /api/system/backup/info` | `factory`, offset 65 536, 4 194 304 bytes, `complete_chip_backup: false` |
| `GET /api/system/backup/running-app` | 4 194 304 bytes downloaded, SHA-256 equal to the metadata |
| `POST /api/research/disarm` + `/api/system/resume` | disarmed; mining resumed and climbed again |

Host suites:

| Evidence | Where |
|---|---|
| SHA oracle: 84 assertions (FIPS KAT, padding boundaries, genesis SHA-256d, 10⁶×"a", trace invariants, JSON shape, streaming split-equivalence, hex helpers) | `ESP-Miner/simulation/test_research_sha.c` |
| Authorisation guard: 115 assertions (every refusal path, budgets, token reuse, pause accounting, watchdog, mining-activity semantics, thermal age limits) | `ESP-Miner/simulation/test_research_guard.c` |
| Cross-language check: device-shaped traces accepted by `round_trace.replay()` | `scripts/verify_firmware_trace.py` |
| Device client + profile tests: 32 | `tests/test_firmware_research.py` |

Three implementations agree on the same block: the device's C, the host's C (same
source, different compiler) and the Python reference. That is the cross-check the
project asked for, and it happened on the hardware rather than in a simulator.

Two real defects were found by these runs and fixed (see `FIRMWARE_BUILD.md`):
the JSON prebuffer that made every research route fail silently, and the
pause/thermal semantics above.

## 6. How to use it from this repository

```bash
# pin the built image
python scripts/sha_forge_firmware.py profile --image <esp-miner.bin> \
    --version <version> --commit <sha> --out <profile.json>

# check the live device really runs that build
python scripts/sha_forge_firmware.py status --host <device> --profile <profile.json>

# capture a verified trace as evidence
python scripts/sha_forge_firmware.py trace --host <device> --block <128 hex> --out <results dir>
```

`ResearchClient` refuses: a response that is not JSON, a trace that fails replay,
a block or round count different from the request, `asic_access != "none"`, a
`compute` other than `software_cpu`, a redirect, or a body over 256 KiB.

## 7. Remaining risk

- The pairing token is only as private as the device's serial console. Anyone who
  can read the log endpoint can complete pairing. The firmware is therefore a
  same-LAN, single-operator surface; it must not be exposed to the internet.
- A research image must carry the per-device BSSID pin and static fallback. The
  CI artefact does not, and flashing it left the unit on a non-routing mesh node
  (defect D-2 in `FIRMWARE_BUILD.md`). The image that is validated on the unit is
  the locally built per-device variant, not the CI artefact.
- Research jobs share the CPU with the mining task; there is no preemption
  between them. The job budget exists for that reason.
- The thermal reading during a session is the last measurement taken before the
  pause, bounded by an age window. It is an upper bound, not a live value, and the
  status says so (`temperature_source`).
