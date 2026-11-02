# OTA, backup and restore

Canonical description: [`docs/MINER_BACKUP_RESTORE.md`](../../docs/MINER_BACKUP_RESTORE.md).

State: host-side manifest/inspection/restore-preview implemented and tested; firmware backup route **not implemented**; no image downloaded; no OTA performed; rollback is **not** automatic on the stock build (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE` disabled); USB recovery remains the last resort. Gate `M3` = `NOT PASSED`.
