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
| flash encryption / secure boot | both **off**; download mode enabled; USB-Serial/JTAG (VID 303A PID 1001) | MEASURED over USB (espefuse summary, read-only) |
| partition table | nvs 0x9000, phy_init 0xf000, factory 0x10000 (4 MiB), www 0x410000 (3 MiB), ota_0 0x710000, ota_1 0xb10000, otadata 0xf10000, coredump 0xf12000; flash 16 MiB | MEASURED (parsed from the verified backup) |
| full flash backup | 16 777 216 bytes, SHA-256 `83621fb91e580f5d4614c80714ad24ba7a98dbe8bc17e49d473daa34a48e5c54`, verified against the chip, two private copies | MEASURED |

Implication of `factory`: the running app is in the factory slot; both OTA slots are not running. An OTA would write `ota_0` and leave `factory` untouched, so `POST /api/system/boot` with the previous slot is the soft rollback (if the new image reaches the API); the USB backup is the hard rollback.

Excluded units: `blackharkminer`, `timminer2` (operator decision, enforced in `miner_capabilities.py`).
No IP address, MAC, BSSID, wallet or pool user is recorded in this repository.
