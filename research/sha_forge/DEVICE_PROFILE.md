# Device profile — `timsminer`

Expected from repository sources (not verified live): Bitaxe Ultra board 201, ESP32-S3, one BM1366, device-specific network pin.

| Field | Value | Verified |
|---|---|---|
| hostname | `timsminer` | `NOT_RUN` (live read pending, B-01) |
| board version | `201` | `NOT_RUN` |
| ASIC | `BM1366` | `NOT_RUN` |
| MAC / BSSID | kept in a local profile file only; never committed | `NOT_RUN` |
| firmware / build id / running partition | unknown until live read | `NOT_RUN` |
| flash encryption / secure boot | unknown | `NOT_RUN` |

Excluded units: `blackharkminer`, `timminer2` (operator decision, enforced in `miner_capabilities.py`).
No IP address, MAC, BSSID, wallet or pool user is recorded in this repository.
