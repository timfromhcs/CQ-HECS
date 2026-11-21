"""Typed experiment envelope ``cqhecs.qg.experiment.v1``.

This envelope links (never duplicates) an ``hcs.run.v2`` run card and adds the fields a
Quantum Gravity experiment needs: model/hypothesis identity, the execution surface, the
backend classification, raw measurement fields, and *separate, nullable* uncertainty
classes.

Rules enforced here:

* there is **no** ``error_bound = 0`` default — every uncertainty field is ``None`` until a
  defensible bound or interval is produced;
* a document whose major schema version is unknown is refused with a migration message;
* counts, bit order and the measurement map travel together with the shots that produced
  them, so a reader can always re-derive the estimator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from cqhecs.quantum_gravity.catalog import EXECUTION_SURFACES

SCHEMA = "cqhecs.qg.experiment.v1"
SCHEMA_MAJOR = 1
SCHEMA_PREFIX = "cqhecs.qg.experiment.v"

STATUSES = (
    "COMPLETED",
    "PARTIAL",
    "UNRESOLVED",
    "REFUSED",
    "FAILED",
    "PENDING",
    "QUEUED",
    "RUNNING",
    "NOT_RUN",
)

#: Uncertainty classes that must stay separate; all are nullable.
UNCERTAINTY_CLASSES = (
    "numerical_error",
    "approximation_error",
    "trotter_error",
    "shot_error",
    "device_noise_model_error",
    "calibration_uncertainty",
)


class SchemaVersionError(ValueError):
    """Raised when a document's major schema version is not supported."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class QGExperimentResult:
    campaign_id: str
    experiment_id: str
    hypothesis_id: str
    model_id: str
    model_version: str
    execution_surface: str
    status: str
    source_revision: str = "unknown"
    software_version: str = "unknown"
    input_digest: Optional[str] = None
    manifest_digest: Optional[str] = None
    backend_id: Optional[str] = None
    backend_type: Optional[str] = None
    provider_job_id: Optional[str] = None
    shots_requested: Optional[int] = None
    shots_returned: Optional[int] = None
    counts: Optional[Dict[str, int]] = None
    bit_order: Optional[str] = None
    measurement_map: Optional[Mapping[str, Any]] = None
    observable_estimates: Mapping[str, Any] = field(default_factory=dict)
    estimator: Optional[str] = None
    calibration_timestamp: Optional[str] = None
    calibration_digest: Optional[str] = None
    transpilation: Optional[Mapping[str, Any]] = None
    limitations: List[str] = field(default_factory=list)
    refusal_reason: Optional[str] = None
    raw_artifact_paths: List[str] = field(default_factory=list)
    run_card: Optional[Mapping[str, Any]] = None
    created_at: str = field(default_factory=_now)
    schema: str = SCHEMA
    # separate, nullable uncertainty classes
    numerical_error: Optional[float] = None
    approximation_error: Optional[float] = None
    trotter_error: Optional[float] = None
    shot_error: Optional[float] = None
    device_noise_model_error: Optional[float] = None
    calibration_uncertainty: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("measurement_map", "transpilation", "run_card"):
            if data.get(key) is not None:
                data[key] = dict(data[key])
        return data

    def validate(self) -> List[str]:
        problems: List[str] = []
        if self.schema != SCHEMA:
            problems.append(f"schema is {self.schema!r}, expected {SCHEMA!r}")
        if self.execution_surface not in EXECUTION_SURFACES:
            problems.append(
                f"execution_surface {self.execution_surface!r} is not one of {EXECUTION_SURFACES}"
            )
        if self.status not in STATUSES:
            problems.append(f"status {self.status!r} is not one of {STATUSES}")
        for name in ("campaign_id", "experiment_id", "hypothesis_id", "model_id", "model_version"):
            if not getattr(self, name):
                problems.append(f"{name} must be a non-empty string")
        if self.shots_returned is not None and self.counts is not None:
            if sum(self.counts.values()) != self.shots_returned:
                problems.append("counts total does not equal shots_returned")
        for name in UNCERTAINTY_CLASSES:
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                problems.append(f"{name} must be a number >= 0 or null")
        if self.status == "REFUSED" and not self.refusal_reason:
            problems.append("a REFUSED result must state a refusal_reason")
        if self.status == "COMPLETED" and not self.limitations:
            problems.append("a COMPLETED result must state at least one limitation")
        return problems

    def write(self, path: Path | str) -> Path:
        problems = self.validate()
        if problems:
            raise SchemaVersionError("; ".join(problems))
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        import json

        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target


def build_experiment_result(**kwargs: Any) -> QGExperimentResult:
    """Build and validate an envelope, returning it only if the fields are consistent."""
    result = QGExperimentResult(**kwargs)
    problems = result.validate()
    if problems:
        raise SchemaVersionError("; ".join(problems))
    return result


def from_dict(document: Mapping[str, Any]) -> QGExperimentResult:
    """Load an envelope, refusing an unknown major schema version with guidance."""
    schema = document.get("schema")
    if not isinstance(schema, str) or not schema.startswith(SCHEMA_PREFIX):
        raise SchemaVersionError(
            f"document schema {schema!r} is not a {SCHEMA_PREFIX}<major> envelope"
        )
    major_text = schema[len(SCHEMA_PREFIX):]
    if not major_text.isdigit() or int(major_text) != SCHEMA_MAJOR:
        raise SchemaVersionError(
            f"schema major version {major_text!r} is not supported (this build reads v{SCHEMA_MAJOR}); "
            "run the documented migration or upgrade CQ-HECS"
        )
    known = set(QGExperimentResult.__dataclass_fields__)  # type: ignore[attr-defined]
    payload = {k: v for k, v in document.items() if k in known}
    return QGExperimentResult(**payload)
