"""Device allowlist: exactly one permitted unit (`timsminer`); known fleet members are excluded.

Identity is never decided by IP alone. Every field of the local profile must match
the live `/api/system/info` data; anything missing or different fails closed.
MAC/BSSID values live only in a local profile file and are never committed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PERMITTED_HOSTNAME = "timsminer"
EXCLUDED_HOSTNAMES = frozenset({"blackharkminer", "timminer2"})
SUPPORTED_ASIC = "BM1366"
SUPPORTED_BOARD = "201"


def _norm(value) -> str:
    return str(value).strip().lower() if value is not None else ""


def is_excluded(hostname) -> bool:
    return _norm(hostname) in EXCLUDED_HOSTNAMES


@dataclass(frozen=True)
class DeviceProfile:
    device_id: str
    hostname: str
    board_version: str
    asic_model: str
    mac: str

    def __post_init__(self):
        if is_excluded(self.hostname):
            raise ValueError(f"device {self.hostname!r} is explicitly excluded")
        if _norm(self.hostname) != PERMITTED_HOSTNAME:
            raise ValueError(f"only {PERMITTED_HOSTNAME!r} may be allowlisted, got {self.hostname!r}")
        if not self.mac:
            raise ValueError("a MAC is required: identity must not rest on the hostname alone")

    @classmethod
    def load(cls, path) -> "DeviceProfile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**{k: str(data[k]) for k in ("device_id", "hostname", "board_version", "asic_model", "mac")})


@dataclass(frozen=True)
class IdentityResult:
    ok: bool
    reason: str


def check_identity(info: dict, profile: DeviceProfile) -> IdentityResult:
    """Compare live system info with the local profile. Fail closed on anything unexpected."""
    if not isinstance(info, dict):
        return IdentityResult(False, "no device info")
    hostname = info.get("hostname")
    if is_excluded(hostname):
        return IdentityResult(False, f"device {hostname!r} is excluded from this project")
    checks = (
        ("hostname", info.get("hostname"), profile.hostname),
        ("board version", info.get("boardVersion"), profile.board_version),
        ("ASIC model", info.get("ASICModel"), profile.asic_model),
        ("MAC", info.get("macAddr"), profile.mac),
    )
    for label, live, expected in checks:
        if live is None or _norm(live) == "":
            return IdentityResult(False, f"{label} missing from device info")
        if _norm(live) != _norm(expected):
            return IdentityResult(False, f"{label} mismatch")
    if _norm(profile.asic_model) != _norm(SUPPORTED_ASIC) or _norm(profile.board_version) != SUPPORTED_BOARD:
        return IdentityResult(False, "unsupported board or ASIC in profile")
    return IdentityResult(True, "identity matches the allowlisted profile")
