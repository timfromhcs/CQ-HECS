# Device profile — `timsminer`

Expected from repository sources (not verified live): Bitaxe Ultra board 201, ESP32-S3, one BM1366, device-specific network pin.

| Field | Value | Verified |
|---|---|---|
| hostname | `timsminer` | MEASURED 2026-11-01 (one read-only GET) |
| board version | `201` | MEASURED |
| ASIC | `BM1366` | MEASURED |
| MAC / BSSID | full MAC kept in a local profile file outside the repo; never committed. Tail matches the repository docs. BSSID not read. | MEASURED (MAC) |
| firmware | `v4.0.2-rc1-timsminer`, ESP-IDF v6.0.2 | MEASURED |
| running partition | **`factory`** (not `ota_0`/`ota_1`) | MEASURED |
| operating point at first sample | 485 MHz, 1100 mV set, ≈339 GH/s (1 h avg ≈325, expected ≈434), 65 °C, ≈11.5 W, 0 % ASIC error, 15 863 accepted / 53 rejected | MEASURED, single sample |
| flash encryption / secure boot | unknown | `NOT_RUN` |

Implication of `factory`: the running app is in the factory slot, so a backup of the running image reads `factory`, and both OTA slots are currently not running. Backup route, restore target and "other slot" rules in `docs/MINER_BACKUP_RESTORE.md` must be checked against this before M3.

Excluded units: `blackharkminer`, `timminer2` (operator decision, enforced in `miner_capabilities.py`).
No IP address, MAC, BSSID, wallet or pool user is recorded in this repository.
