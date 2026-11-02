"""Firmware profile: what build is on the miner, pinned by hash, verified against the device.

A profile is a small, reviewable record written next to a built image:

    {
      "schema": "hcs.sha.firmware_profile.v1",
      "version": "v4.0.2-rc1-timsminer-sha-research",
      "project": "esp-miner",
      "chip": "ESP32-S3",
      "source_commit": "abc1234",
      "image_sha256": "…",
      "image_bytes": 1234567,
      "board_version": "201",
      "asic_model": "BM1366",
      "features": ["sha256", "sha256d", "round_trace", "reduced_rounds"],
      "build_flags": {"CONFIG_TIMSMINER_SHA_RESEARCH": "y", "...": "..."},
      "research_limits": {"max_jobs": 64, "max_runtime_s": 900, "max_temperature_c": 65,
                          "max_trace_rounds": 64, "max_message_bytes": 512},
      "compute": "software_cpu",
      "asic_access": "none"
    }

Two rules make it useful rather than decorative:

1. The recorded digest is re-checked against the real file before any flash
   decision (:meth:`FirmwareProfile.verify_image`). A profile whose hash does not
   match the artefact is refused, not "updated".
2. `asic_access` must be `"none"` and `compute` must be `"software_cpu"`. The
   BM1366 executes SHA-256d internally and exposes nonces, not round state; a
   profile that claims otherwise is rejected here so the claim cannot travel into
   a report or a UI panel (:func:`reject_asic_round_claim`).

Matching against a live device is deliberately narrow: the running app reports its
version and project, and the device status reports the MCU and ASIC. Anything
missing or different fails closed with a reason.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "hcs.sha.firmware_profile.v1"
ALLOWED_PROJECTS = frozenset({"esp-miner"})
ALLOWED_CHIPS = frozenset({"ESP32-S3"})
ALLOWED_COMPUTE = frozenset({"software_cpu"})
EXPECTED_ASIC_ACCESS = "none"
REQUIRED_FIELDS = (
    "schema",
    "version",
    "project",
    "chip",
    "image_sha256",
    "features",
    "build_flags",
    "research_limits",
)
# Feature names the firmware may advertise. Anything else is a claim we have not
# implemented, so it is refused rather than ignored.
KNOWN_FEATURES = frozenset({"sha256", "sha256d", "round_trace", "reduced_rounds"})
# Names that would imply reading state out of the ASIC.
FORBIDDEN_FEATURES = frozenset({"asic_rounds", "asic_round_trace", "asic_internal_state", "asic_iv"})


class ProfileError(ValueError):
    """A profile is malformed or makes a claim this project does not support."""


@dataclass(frozen=True)
class ProfileMatch:
    ok: bool
    reason: str


def _hex64(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ProfileError(f"{field} must be a 64-character sha256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ProfileError(f"{field} is not hexadecimal") from exc
    return value.lower()


def reject_asic_round_claim(capabilities: Mapping[str, Any]) -> None:
    """Raise if a capability document claims ASIC-internal SHA state.

    Applied to the firmware's live `/api/research/capabilities` and to a profile,
    so neither a device nor a local file can introduce the claim that the ASIC
    exposes rounds.
    """
    if not isinstance(capabilities, Mapping):
        raise ProfileError("capabilities must be an object")
    limitations = capabilities.get("limitations") or {}
    access = str(limitations.get("asic_access", "")).strip().lower()
    if access and access != EXPECTED_ASIC_ACCESS:
        raise ProfileError(f"capabilities claim asic_access={access!r}; this project supports 'none' only")
    compute = str(capabilities.get("compute", "")).strip().lower()
    if compute and compute not in ALLOWED_COMPUTE:
        raise ProfileError(f"capabilities claim compute={compute!r}; expected software_cpu")
    for name in capabilities.get("features") or ():
        lowered = str(name).strip().lower()
        if lowered in FORBIDDEN_FEATURES:
            raise ProfileError(f"capabilities claim feature {name!r}, which the hardware cannot provide")
        if lowered not in KNOWN_FEATURES:
            raise ProfileError(f"capabilities list unknown feature {name!r}")


@dataclass(frozen=True)
class FirmwareProfile:
    version: str
    project: str
    chip: str
    image_sha256: str
    features: tuple
    build_flags: Mapping[str, str]
    research_limits: Mapping[str, Any]
    source_commit: str = ""
    image_bytes: int = 0
    board_version: str = ""
    asic_model: str = ""
    compute: str = "software_cpu"
    asic_access: str = EXPECTED_ASIC_ACCESS

    def __post_init__(self):
        if not self.version:
            raise ProfileError("version is required")
        if self.project not in ALLOWED_PROJECTS:
            raise ProfileError(f"project {self.project!r} is not an ESP-Miner application")
        if self.chip not in ALLOWED_CHIPS:
            raise ProfileError(f"chip {self.chip!r} is not a supported target")
        if self.compute not in ALLOWED_COMPUTE:
            raise ProfileError(f"compute {self.compute!r} is not supported")
        if self.asic_access != EXPECTED_ASIC_ACCESS:
            raise ProfileError("asic_access must be 'none': the ASIC exposes nonces, not round state")
        if set(self.features) & FORBIDDEN_FEATURES:
            raise ProfileError("a feature claims ASIC-internal state")
        unknown = set(self.features) - KNOWN_FEATURES
        if unknown:
            raise ProfileError(f"unknown features: {sorted(unknown)}")
        _hex64(self.image_sha256, "image_sha256")
        limits = self.research_limits or {}
        for key in ("max_jobs", "max_runtime_s", "max_temperature_c"):
            if key not in limits:
                raise ProfileError(f"research_limits.{key} is required")

    # -- construction
    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FirmwareProfile":
        if not isinstance(data, Mapping):
            raise ProfileError("profile must be an object")
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            raise ProfileError(f"profile is missing required fields: {missing}")
        if data["schema"] != SCHEMA:
            raise ProfileError(f"profile schema is {data['schema']!r}, expected {SCHEMA!r}")
        features = data["features"]
        if not isinstance(features, (list, tuple)) or not features:
            raise ProfileError("features must be a non-empty list")
        flags = data["build_flags"]
        if not isinstance(flags, Mapping):
            raise ProfileError("build_flags must be an object")
        limits = data["research_limits"]
        if not isinstance(limits, Mapping):
            raise ProfileError("research_limits must be an object")
        return cls(
            version=str(data["version"]),
            project=str(data["project"]),
            chip=str(data["chip"]),
            image_sha256=str(data["image_sha256"]),
            features=tuple(str(f) for f in features),
            build_flags={str(k): str(v) for k, v in flags.items()},
            research_limits=dict(limits),
            source_commit=str(data.get("source_commit", "")),
            image_bytes=int(data.get("image_bytes", 0)),
            board_version=str(data.get("board_version", "")),
            asic_model=str(data.get("asic_model", "")),
            compute=str(data.get("compute", "software_cpu")),
            asic_access=str(data.get("asic_access", EXPECTED_ASIC_ACCESS)),
        )

    @classmethod
    def load(cls, path) -> "FirmwareProfile":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # -- verification
    def verify_image(self, image_path) -> ProfileMatch:
        """Re-hash the artefact and compare with the recorded digest."""
        path = Path(image_path)
        if not path.is_file():
            return ProfileMatch(False, "image file does not exist")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != self.image_sha256:
            return ProfileMatch(False, "image digest does not match the profile")
        size = path.stat().st_size
        if self.image_bytes and size != self.image_bytes:
            return ProfileMatch(False, f"image size {size} != recorded {self.image_bytes}")
        return ProfileMatch(True, "image digest matches the profile")

    def matches_device(self, status: Mapping[str, Any]) -> ProfileMatch:
        """Compare a live `/api/research/status` document with this profile."""
        if not isinstance(status, Mapping) or not status:
            return ProfileMatch(False, "no device status")
        if str(status.get("schema", "")) != "hcs.sha.miner.v1":
            return ProfileMatch(False, "device status schema is not hcs.sha.miner.v1")
        if status.get("kind") not in (None, "research_status"):
            return ProfileMatch(False, "device document is not a research status")
        if not status.get("research_enabled"):
            return ProfileMatch(False, "device does not have research mode enabled")
        version = str(status.get("firmware_version") or "")
        if version != self.version:
            return ProfileMatch(False, "firmware version differs")
        if str(status.get("mcu") or "") != self.chip:
            return ProfileMatch(False, "MCU differs")
        if self.asic_model and str(status.get("asic_model") or "") != self.asic_model:
            return ProfileMatch(False, "ASIC model differs")
        if self.board_version and str(status.get("board_version") or "") != self.board_version:
            return ProfileMatch(False, "board version differs")
        build_id = str(status.get("firmware_build_id") or "")
        if build_id:
            if not build_id.startswith(self.image_sha256[:16]):
                return ProfileMatch(False, "firmware build id does not match the image digest")
        return ProfileMatch(True, "device matches the pinned profile")

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "version": self.version,
            "project": self.project,
            "chip": self.chip,
            "source_commit": self.source_commit,
            "image_sha256": self.image_sha256,
            "image_bytes": self.image_bytes,
            "board_version": self.board_version,
            "asic_model": self.asic_model,
            "features": list(self.features),
            "build_flags": dict(self.build_flags),
            "research_limits": dict(self.research_limits),
            "compute": self.compute,
            "asic_access": self.asic_access,
        }
