"""
Calibration schema v3 (additive, W10 / M7 proposal).

``cqhecs.calibration/3.0`` wraps an existing :class:`BackendProfile` (schema 1.0
or 2.0, unchanged) with governance metadata that the numeric profile does not
carry: backend identity, calibration timestamp, logical-to-physical layout,
gate basis, units, a provenance label and a freshness window.

Nothing here simulates or calibrates anything. It decides how a profile may be
*described* and when a circuit may be run against it:

* provenance label is one of ``synthetic | measured | derived | post_hoc |
  unknown``; ``measured`` is refused for a synthetic profile or one without a
  timestamp and a source (URI or SHA-256);
* freshness is ``fresh | stale | unknown``; never defaulted to fresh;
* gates the profile has no channel for are handled by an explicit policy
  (``refuse | warn | ideal``) and reported, never dropped silently;
* channel and readout checks (Kraus completeness, Choi Hermiticity and
  positivity, column-stochastic readout) are exposed as one report.

A v3 record is a description of a model input. It is not evidence that the
model predicts a device.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from cqhecs.hardware_bridge import (
    BackendProfile,
    HardwareBridgeError,
    InvalidProfileError,
    NoiseChannel,
    NoiseModel,
)

SCHEMA_V3 = "cqhecs.calibration/3.0"
PROVENANCE_LABELS = ("synthetic", "measured", "derived", "post_hoc", "unknown")
POLICIES = ("refuse", "warn", "ideal")
UNITS = {"t1": "us", "t2": "us", "gate_duration": "ns", "gate_error": "probability",
         "readout_error": "probability", "timestamp": "ISO-8601"}


class UncalibratedGateError(HardwareBridgeError):
    """A circuit uses gates the calibration has no channel for and policy is ``refuse``."""


def _parse_ts(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidProfileError(f"calibration timestamp {text!r} is not ISO-8601") from exc
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass
class CalibrationV3:
    profile: BackendProfile
    provenance_label: str
    backend_identity: str
    layout: Tuple[int, ...] = ()
    max_age_hours: Optional[float] = None
    units: Dict[str, str] = field(default_factory=lambda: dict(UNITS))

    def __post_init__(self) -> None:
        self.validate()

    # -- construction -------------------------------------------------
    @classmethod
    def from_profile(
        cls,
        profile: BackendProfile,
        *,
        provenance_label: Optional[str] = None,
        layout: Optional[Sequence[int]] = None,
        max_age_hours: Optional[float] = None,
    ) -> "CalibrationV3":
        """Wrap ``profile``. Without an explicit label: synthetic -> ``synthetic``, else ``unknown``."""
        label = provenance_label or ("synthetic" if profile.is_synthetic else "unknown")
        return cls(
            profile=profile,
            provenance_label=label,
            backend_identity=f"{profile.provider_name}:{profile.name}",
            layout=tuple(int(q) for q in layout) if layout is not None else (),
            max_age_hours=max_age_hours,
        )

    # -- validation ---------------------------------------------------
    def validate(self) -> None:
        p = self.profile
        if self.provenance_label not in PROVENANCE_LABELS:
            raise InvalidProfileError(
                f"provenance_label must be one of {PROVENANCE_LABELS}, got {self.provenance_label!r}"
            )
        if p.is_synthetic and self.provenance_label in ("measured",):
            raise InvalidProfileError("a synthetic profile cannot be labelled 'measured'")
        if not p.is_synthetic and self.provenance_label == "synthetic":
            raise InvalidProfileError("a non-synthetic profile cannot be labelled 'synthetic'")
        if self.provenance_label == "measured" and not (
            p.capture_timestamp and (p.provenance_uri or p.source_sha256)
        ):
            raise InvalidProfileError(
                "'measured' needs capture_timestamp and provenance_uri or source_sha256"
            )
        _parse_ts(p.capture_timestamp)
        if self.max_age_hours is not None and not (
            isinstance(self.max_age_hours, (int, float)) and math.isfinite(self.max_age_hours)
            and self.max_age_hours > 0
        ):
            raise InvalidProfileError("max_age_hours must be a finite positive number")
        if self.layout:
            if len(set(self.layout)) != len(self.layout):
                raise InvalidProfileError("layout repeats a physical qubit")
            for q in self.layout:
                if q < 0 or q >= p.num_qubits:
                    raise InvalidProfileError(
                        f"layout qubit {q} out of range [0, {p.num_qubits - 1}]"
                    )

    # -- freshness ----------------------------------------------------
    def freshness(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """``unknown`` without a timestamp or window; never assumed fresh."""
        ts = _parse_ts(self.profile.capture_timestamp)
        if ts is None or self.max_age_hours is None:
            return {"status": "unknown", "age_hours": None, "max_age_hours": self.max_age_hours}
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age = (now - ts).total_seconds() / 3600.0
        status = "fresh" if 0.0 <= age <= self.max_age_hours else "stale"
        return {"status": status, "age_hours": age, "max_age_hours": self.max_age_hours}

    # -- gate coverage policy ----------------------------------------
    def check_gates(self, instructions: Any, policy: str = "refuse") -> Dict[str, Any]:
        """Apply ``policy`` to gates the profile has no channel for."""
        if policy not in POLICIES:
            raise ValueError(f"policy must be one of {POLICIES}")
        uncovered = self.profile.uncovered_gates(instructions)
        if uncovered and policy == "refuse":
            raise UncalibratedGateError(
                f"gates {uncovered} have no calibration in {self.backend_identity}; "
                "they would run noiselessly. Use policy 'warn' or 'ideal' to accept."
            )
        warnings: List[str] = []
        if uncovered and policy == "warn":
            warnings.append(f"gates {uncovered} run without noise (no calibration)")
        return {"policy": policy, "uncovered_gates": uncovered, "warnings": warnings,
                "noiseless_gates_accepted": bool(uncovered)}

    # -- serialisation ------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        p = self.profile
        return {
            "schema": SCHEMA_V3,
            "backend_identity": self.backend_identity,
            "calibration_timestamp": p.capture_timestamp,
            "provenance_label": self.provenance_label,
            "provenance_uri": p.provenance_uri,
            "source_sha256": p.source_sha256,
            "layout": list(self.layout),
            "gate_basis": list(p.basis_gates),
            "units": dict(self.units),
            "freshness_policy": {"max_age_hours": self.max_age_hours},
            "profile": p.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CalibrationV3":
        if data.get("schema") != SCHEMA_V3:
            raise InvalidProfileError(f"expected schema {SCHEMA_V3!r}, got {data.get('schema')!r}")
        if "profile" not in data or "provenance_label" not in data:
            raise InvalidProfileError("v3 record needs 'profile' and 'provenance_label'")
        profile = BackendProfile.from_dict(dict(data["profile"]))
        return cls(
            profile=profile,
            provenance_label=data["provenance_label"],
            backend_identity=data.get("backend_identity") or f"{profile.provider_name}:{profile.name}",
            layout=tuple(data.get("layout", ())),
            max_age_hours=(data.get("freshness_policy") or {}).get("max_age_hours"),
            units=dict(data.get("units") or UNITS),
        )


# ---------------------------------------------------------------------------
# Channel and readout checks
# ---------------------------------------------------------------------------


def choi_matrix(kraus: Sequence[np.ndarray]) -> np.ndarray:
    """Unnormalised Choi matrix sum_k vec(K_k) vec(K_k)^dagger (column-stacking)."""
    out = 0
    for k in kraus:
        v = np.asarray(k, dtype=complex).reshape(-1, 1, order="F")
        out = out + v @ v.conj().T
    return out


def check_channel(channel: NoiseChannel, tol: float = 1e-10) -> Dict[str, Any]:
    """Completeness (trace preservation), Choi Hermiticity and positivity; no raising."""
    kraus = channel.kraus_operators
    dim = kraus[0].shape[0]
    comp = float(np.max(np.abs(sum(k.conj().T @ k for k in kraus) - np.eye(dim))))
    choi = choi_matrix(kraus)
    herm = float(np.max(np.abs(choi - choi.conj().T)))
    min_eig = float(np.min(np.linalg.eigvalsh((choi + choi.conj().T) / 2)))
    return {
        "channel": channel.name,
        "completeness_residual": comp,
        "hermiticity_residual": herm,
        "min_choi_eigenvalue": min_eig,
        "ok": comp <= tol and herm <= tol and min_eig >= -tol,
    }


def check_noise_model(model: NoiseModel, tol: float = 1e-10) -> Dict[str, Any]:
    """One report over every channel and every readout matrix of ``model``."""
    channels: List[Dict[str, Any]] = []
    for table in model.channels_1q.values():
        for lst in table.values():
            channels.extend(check_channel(c, tol) for c in lst)
    for table in model.channels_2q.values():
        for lst in table.values():
            channels.extend(check_channel(c, tol) for c in lst)
    readout: List[Dict[str, Any]] = []
    for q, ro in sorted(model.readout_errors.items()):
        m = np.asarray(ro.matrix, dtype=float)
        cols = float(np.max(np.abs(m.sum(axis=0) - 1.0)))
        readout.append({"qubit": q, "column_sum_residual": cols,
                        "ok": bool(np.all(m >= 0.0) and np.all(np.isfinite(m)) and cols <= tol)})
    return {
        "channels": channels,
        "readout": readout,
        "ok": all(c["ok"] for c in channels) and all(r["ok"] for r in readout),
    }
