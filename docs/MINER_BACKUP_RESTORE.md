# Miner backup and restore — current state: host side only

**No physical flash is permitted until the backup gate passes.** Status of the gate: **not passed** (see `research/sha_forge/BLOCKERS.md` B-03).

## What a WLAN backup is and is not

An OTA application image is not a full flash, bootloader, partition-table, NVS or eFuse backup. The stock ESP-Miner OTA accepts an
application image only, has no automatic boot rollback and no image signing. Keep the existing USB full-flash backup as the last-resort path.

## Implemented now (host side, tested without hardware)

`cqhecs/hardware/evidence.py`:

- `inspect_app_image` parses the ESP image header (magic `0xE9`, chip id, app descriptor magic `0xABCD5432`, project name, version).
- `build_backup_manifest` writes `hcs.miner.backup.v1`. Each flag (`sha256_recomputed`, `transfer_complete`, `esp_image_info_valid`, `chip_match`, `project_match`, `descriptor_match`, `fits_slot`) comes from a check that actually ran. A truncated download, wrong chip, wrong project or oversize image is never verified.
- `recheck_manifest` recomputes everything from the file; stored flags are never trusted.
- `restore_preview` is allowed only for a verified manifest, the same device id, an OTA slot target that is not the running partition, and never `factory`.

## Not implemented

- The firmware route `GET /api/system/backup/running-app` (read-only, running partition only, no client-supplied offsets) does not exist; ESP-Miner was not modified.
- No image was downloaded; no backup copies exist; no restore was exercised on a bench unit.

## Required order (unchanged from AGENTBUILD §6)

1. Implement and bench-test the read-only backup route (or a backup-exporter image).
2. Download the running app image, verify, store two copies outside the worktree.
3. Only then build a per-device research image and request operator approval to upload once.
4. After research, restore the verified original through the existing OTA path, verify firmware version, partition and telemetry, 10-minute smoke then 60-minute soak.
5. If the restore fails: no retry, no second slot write, `RECOVERY_REQUIRED`, USB rescue.
