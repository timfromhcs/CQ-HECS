"""Backup manifest and restore preview. Every verification flag comes from a check that really ran."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "hcs.miner.backup.v1"
ESP_IMAGE_MAGIC = 0xE9
APP_DESC_MAGIC = 0xABCD5432
CHIP_IDS = {0: "ESP32", 2: "ESP32-S2", 5: "ESP32-C3", 9: "ESP32-S3", 12: "ESP32-C2", 13: "ESP32-C6", 16: "ESP32-H2"}
# Slots an OTA application image may be written to. `factory` is never a restore target.
RESTORE_SLOTS = ("ota_0", "ota_1")


@dataclass(frozen=True)
class ImageInfo:
    valid: bool
    chip: str | None = None
    project: str | None = None
    version: str | None = None
    reason: str = ""


def _cstr(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def inspect_app_image(data: bytes) -> ImageInfo:
    """Parse the ESP image header and esp_app_desc_t of an application image."""
    if len(data) < 24 + 8 + 256:
        return ImageInfo(False, reason="image too short")
    if data[0] != ESP_IMAGE_MAGIC:
        return ImageInfo(False, reason="bad image magic")
    chip = CHIP_IDS.get(struct.unpack_from("<H", data, 12)[0])
    if chip is None:
        return ImageInfo(False, reason="unknown chip id")
    desc = data[32 : 32 + 256]
    if struct.unpack_from("<I", desc, 0)[0] != APP_DESC_MAGIC:
        return ImageInfo(False, chip=chip, reason="no app descriptor (not an application image)")
    return ImageInfo(True, chip=chip, project=_cstr(desc[48:80]), version=_cstr(desc[16:48]))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_backup_manifest(
    *, image_path, device_id, board_version, asic_model, mcu, firmware_version, running_partition,
    slot_size, expected_project, expected_size=None, expected_sha256=None,
) -> dict:
    path = Path(image_path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    info = inspect_app_image(data)
    complete = (expected_size is None or len(data) == expected_size) and (
        expected_sha256 is None or digest == expected_sha256
    )
    verification = {
        "sha256_recomputed": _sha256_file(path) == digest,
        "transfer_complete": complete,
        "esp_image_info_valid": info.valid,
        "chip_match": info.valid and info.chip == mcu,
        "project_match": info.valid and info.project == expected_project,
        "descriptor_match": info.valid and info.version == firmware_version,
        "fits_slot": 0 < len(data) <= slot_size,
    }
    return {
        "schema": SCHEMA,
        "device_id": device_id,
        "board_version": board_version,
        "asic_model": asic_model,
        "mcu": mcu,
        "firmware_version": firmware_version,
        "running_partition": running_partition,
        "image_file": path.name,
        "image_size": len(data),
        "sha256": digest,
        "slot_size": slot_size,
        "expected_project": expected_project,
        "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verification": verification,
    }


def manifest_is_verified(manifest: dict) -> bool:
    v = manifest.get("verification") or {}
    required = ("sha256_recomputed", "transfer_complete", "esp_image_info_valid", "chip_match",
                "project_match", "descriptor_match", "fits_slot")
    return manifest.get("schema") == SCHEMA and all(v.get(k) is True for k in required)


def recheck_manifest(manifest: dict, image_path) -> bool:
    """Recompute every claim from the image file itself; never trust stored flags."""
    path = Path(image_path)
    if not path.is_file():
        return False
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest.get("sha256") or len(data) != manifest.get("image_size"):
        return False
    info = inspect_app_image(data)
    return bool(
        info.valid
        and info.chip == manifest.get("mcu")
        and info.project == manifest.get("expected_project")
        and info.version == manifest.get("firmware_version")
        and 0 < len(data) <= manifest.get("slot_size", 0)
    )


def restore_preview(manifest: dict, image_path, profile, target_slot: str) -> dict:
    """Describe a restore without performing it. `allowed` is False unless every gate holds."""
    problems = []
    if not manifest_is_verified(manifest):
        problems.append("backup manifest is not verified")
    if not recheck_manifest(manifest, image_path):
        problems.append("image file no longer matches the manifest")
    if manifest.get("device_id") != profile.device_id:
        problems.append("backup belongs to a different device")
    if target_slot not in RESTORE_SLOTS:
        problems.append("target must be an OTA application slot")
    elif target_slot == manifest.get("running_partition"):
        problems.append("target slot is the running partition")
    return {
        "allowed": not problems,
        "problems": problems,
        "device_id": manifest.get("device_id"),
        "firmware_version": manifest.get("firmware_version"),
        "sha256": manifest.get("sha256"),
        "image_size": manifest.get("image_size"),
        "target_slot": target_slot,
        "requires_operator_confirmation": True,
    }
