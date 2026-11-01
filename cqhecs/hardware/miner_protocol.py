"""Typed, read-only view of the stock `/api/system/info` as `hcs.sha.miner.v1`.

Unknown or invalid values become `None`; secrets are never copied.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

SCHEMA = "hcs.sha.miner.v1"
MCU = "ESP32-S3"


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _str(value):
    return value if isinstance(value, str) and value else None


def normalize_info(raw: dict, device_id: str, now: datetime | None = None) -> dict:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema": SCHEMA,
        "device_id": device_id,
        "board_version": _int(raw.get("boardVersion")),
        "asic_model": _str(raw.get("ASICModel")),
        "mcu": MCU,
        "firmware_version": _str(raw.get("version")),
        "firmware_build_id": _str(raw.get("buildId")),
        "running_partition": _str(raw.get("runningPartition")),
        "research_enabled": False,
        "research_armed": False,
        "pool_connected": None,
        "active_jobs": None,
        "temperature_c": _num(raw.get("temp")),
        "power_w": _num(raw.get("power")),
        "frequency_mhz": _num(raw.get("frequency")),
        "hashrate_ghs": _num(raw.get("hashRate")),
        "timestamp_utc": ts,
    }
