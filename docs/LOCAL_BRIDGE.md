# Local bridge (read-only release)

The bridge is the only component allowed to talk to a physical miner. The website never does.

```bash
# No hardware, no LAN access: deterministic simulated device
python -m cqhecs.hardware.bridge --origin http://127.0.0.1:5173 --simulate

# One exact allowlisted unit (profile file stays on your machine, never in Git)
python -m cqhecs.hardware.bridge --origin https://<your-origin> --profile timsminer.profile.json --device-host <exact-host>
```

`timsminer.profile.json` has `device_id`, `hostname` (must be `timsminer`), `board_version` (`201`), `asic_model` (`BM1366`) and `mac`.
Profile construction fails for any other hostname; `blackharkminer` and `timminer2` are explicitly excluded.

## Guarantees (all covered by `tests/test_sha_bridge.py`, `tests/test_hardware_policy.py`)

- Binds to loopback only; wildcard origins rejected at construction.
- Exact-origin CORS; `POST /pair` needs an allowed `Origin`, body `{"purpose":"read_only"}`, returns a bearer token with a TTL; `POST /pair/revoke` ends it.
- Mutating routes are POST-only, rate limited (30 per 60 s), limited to 4 KiB, with unknown JSON keys rejected.
- `GET /devices/<id>/info` and `GET /telemetry` read the stock info endpoint of the one configured host, verify identity (hostname, board, ASIC, MAC) and return `hcs.sha.miner.v1` with `null` for unknown values. Excluded or mismatching devices return 403 with no telemetry.
- `POST /research/jobs`, `/research/pause`, `/research/cancel`, `/backup/export` answer `403 READ_ONLY` and never reach the device.
- `POST /restore/preview` only describes; `allowed` is false without a verified backup manifest.
- There is no proxy, scan, register, UART or firmware route. Unknown paths return 404.
- Hostile clients: digit-only `Content-Length` (else 400), 408 on stalled bodies (5 s socket timeout), at most 32 concurrent connections (503 beyond), aborted clients are silent, errors are JSON.
- The miner is protected from request bursts: device reads are cached for 1 s (failures too) and limited to 120 per minute.
- Headers, bodies and tokens are never logged.

## Browser permission

The page asks the browser for local-network access only after you click **Connect local TimsMiner**. Denied, blocked or unreachable
all show a clear message and no retry loop starts. Chrome/Edge behaviour on specific versions is not yet recorded (blocker B-07).

## Measured: a browser cannot reach the miner directly

On 2026-11-02, Chromium 156.0.8078.4 was asked to fetch two read-only endpoints of
the allowlisted unit from a page served on loopback, from `http://127.0.0.1:4173`
and from `http://localhost:4173`:

```
Access to fetch at 'http://<device>/api/system/info' from origin 'http://localhost:4173'
has been blocked by CORS policy: Permission was denied for this request to access
the `local` address space.
TypeError: Failed to fetch        (status 0, 0 bytes)
```

`navigator.permissions.query({name: "local-network-access"})` reports `prompt` for
both origins: the capability exists, but it needs an operator gesture and a
prompt, and a page cannot grant it silently. The device's own CORS headers are not
the blocker - they allow private ranges; the browser's Local Network Access policy
is.

Consequence, and why the bridge is not optional: the web UI cannot talk to the
miner. Every device read goes through the loopback bridge, which is the only
component with network access to the unit. A future "direct browser" mode would
need an explicit operator permission prompt per origin, and must be designed for
the case where the operator declines.

Reproduce: `node web/scripts/measure-lan-access.mjs http://<device> http://localhost:4173`
(Playwright/Chromium, no writes to the device).
