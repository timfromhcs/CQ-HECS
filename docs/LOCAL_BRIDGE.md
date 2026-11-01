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
- Headers, bodies and tokens are never logged.

## Browser permission

The page asks the browser for local-network access only after you click **Connect local TimsMiner**. Denied, blocked or unreachable
all show a clear message and no retry loop starts. Chrome/Edge behaviour on specific versions is not yet recorded (blocker B-07).
