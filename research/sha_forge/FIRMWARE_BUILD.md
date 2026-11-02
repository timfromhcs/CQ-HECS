# Research firmware: builds, flashes, and what the hardware actually did

Everything below happened on 2026-11-01/02 on `timsminer` (board 201, BM1366,
ESP32-S3, running from the `factory` partition). No value is a projection.

| # | Artefact | SHA-256 | Bytes | Version | Written | Result |
|---|---|---|---:|---|---|---|
| 1 | CI `build-research` run 41359233300 (`105d158`) | `25d9c50f…be0bce3` | 2 769 936 | `v4.0.2-rc1-sha-research` | USB `write-flash 0x10000`, `Hash of data verified` | booted, mined, **research JSON routes failed** (defect D-1) |
| 2 | CI `build-research` run 41360000868 (`941e4b0`) | `e6bff0e0…fe254ba5` | 2 769 952 | `v4.0.2-rc1-sha-research` | USB `write-flash 0x10000`, verified | booted and mined, but the WLAN link was unusable (defect D-2) |
| — | Stock restore from the verified full-flash backup | `83621fb9…e5c54` | 16 777 216 | `v4.0.2-rc1-timsminer` | USB `write-flash 0x0`, verified | mining again, RSSI −65, ~292 GH/s |
| 3 | **per-device local build** (BSSID pin + static fallback recovered from image 0) | `b017b35e…22c9cfc` | 2 770 096 | `v4.0.2-rc1-sha-research` | USB `write-flash 0x10000`, verified | reachable (RSSI −67), research gates still refused `thermal_unsafe` (defect D-3) |
| 4 | **per-device local build after D-3 fix** | `387b1663…4746d3` | 2 770 208 | `v4.0.2-rc1-sha-research` | USB `write-flash 0x10000`, verified | reachable, all 12 session steps green except the arm ordering fixed in the next row |
| 5 | **per-device local build, final** | `10e753fc…1721aa2` | 2 770 480 | `v4.0.2-rc1-sha-research` | USB `write-flash 0x10000`, verified | **12/12 steps green**, trace accepted by the Python reference, mining resumed |

Images 3–5 differ only in the fixes below; the per-device network values are not
in this repository and were read out of the verified backup image (defect D-2),
never guessed and never taken from another unit.

## Defect D-1 — every research JSON route failed (found on hardware, fixed)

Symptom: `GET /api/research/status` closed the connection; the serial log said
`W httpd_uri: uri handler execution failed`. No panic, no reboot, mining carried
on and shares kept being accepted.

Cause: `cJSON_PrintBuffered()` allocates its prebuffer up front and `malloc(0)`
returns NULL on this heap. Both new modules kept their print-buffer hint in a
static that started at 0, so `HTTP_send_json()` returned `ESP_ERR_NO_MEM` without
writing a body. Fixed by starting at 256, like every other API handler in the
repository (commit `941e4b0`). This is exactly the class of defect a host test
cannot catch: it needs the real allocator and the real httpd.

## Defect D-2 — the research image lost the BSSID pin (design gap)

The per-device stock image bakes a BSSID pin and a static fallback; the CI
general build does not. After flashing image 2 the unit associated to a mesh node
that does not route:

```
W connect: NET,event=DHCP_TIMEOUT,attempt=1,step=0,...
W connect: NET,event=IP_FALLBACK_ATTEMPT,rung=last-lease,ip=192.168.178.61,...
E connect: NET,event=GATEWAY_TCP,target=192.168.178.1:80,result=FAILED,errno=113
```

`ping` returned 1 of 2 packets and HTTP timed out on four attempts, so the
research session could not be driven over WLAN. This is the failure mode the
repository's `tools/build_release.sh` documents.

Recovery: the full-flash backup was written back at `0x0`, verified, and the unit
returned to the stock firmware and to mining before any further build work. The
per-device values were then recovered from that backup image (they are string
constants in the image the unit has always run) and baked into a local build.

## Defect D-3 — the gates did not match what `pause` actually does (fixed)

Measured on the unit: `/api/system/pause` stops creating jobs and submitting
shares but **keeps the stratum socket open**, and it **powers the ASIC down**,
after which the temperature path (gated on `ASIC_initalized`) returns −1.

Consequences for the first per-device image: `pool_connected` never became false
(so `arm` would always answer `pool_active`), and the thermal gate answered
`thermal_unsafe` because there was no reading at all.

Fix (`356b985`):

- `research_guard_mining_active(connected, paused, share_in_flight)` decides
  whether a share can still leave the device; an outstanding share blocks even
  when paused.
- The session keeps the last temperature measured while the ASIC was running —
  an upper bound, since a powered-down die cannot get hotter — and the guard
  refuses it once it is older than a bounded window (5 min default, 30 s..1 h).
  The status reports `temperature_source` and `temperature_age_ms`.
- `identity_verified` no longer requires a powered ASIC: the question is which
  build and board is running, not whether the die is clocked.

Five new guard assertions cover the mining-activity semantics and five more cover
the thermal age window (fresh, boundary, stale, and two refused configurations).

## What the final session proved

12 of 12 steps, in this order: identity/version, research status, capabilities,
pause + drain, pairing token over COM3, arm, 64-round trace, `sha256d("abc")`,
backup metadata, 4 MiB backup download matching its digest, disarm, resume.

- The 64-round device trace was accepted **unchanged** by
  `cqhecs.sha.round_trace.replay()`, with output state `da5698be…837a9d8` — the
  same value the host C implementation produces for the all-zero block. Device C,
  host C and the Python reference agree.
- `sha256d("abc") = 4f8b42c2…c6358`, the published value.
- The WLAN backup route served 4 194 304 bytes whose SHA-256 equalled the metadata
  digest, with `complete_chip_backup: false` stated in the payload.
- Mining resumed after every session; the unit is back at full hashrate.

## What this still does not prove

- Nothing about ASIC-internal SHA state: there is none to observe, and the
  capabilities document says `asic_access: none`.
- Nothing about 64-round preimage search; the 64-round trace is a *verification*
  computation of a caller-supplied block, not a search (see `SAT_SHA.md`).
