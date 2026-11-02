"""One provenance card for every run, whichever surface produced it.

`hcs.run.v2` exists because the same run was described differently in Python, in the CLI and
in the browser: three field names, three places for the digest, and no shared idea of what
"the result" is. A card answers four questions without the reader having to trust a page:

1. **What was run?** the exact input text and its SHA-256;
2. **by what?** engine kind, precision and execution mode;
3. **with which reproducibility data?** the seed, the software version and the source
   revision;
4. **with what limits?** the non-claims that belong to the result.

Rules this module enforces (each has a test in ``tests/test_provenance.py``):

* the digest is always over the payload stored in the card, so a card can be checked
  without any other file;
* the three error kinds (deliberate approximation, floating point, finite shots) are
  separate fields and may be ``null`` - never a zero that pretends to be a measurement;
* a v1 document (``cqhecs.web.run/1.0`` / ``1.1``) is **recognised and refused**, not
  silently reinterpreted as v2;
* a payload above the size limit is refused with an error instead of being truncated.

The JSON Schema lives in ``docs/provenance/hcs.run.v2.schema.json`` and is the shared
contract: the browser test validates its card against the same file.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

SCHEMA = "hcs.run.v2"
SCHEMA_FILE = Path(__file__).resolve().parents[1] / "docs" / "provenance" / "hcs.run.v2.schema.json"
LEGACY_SCHEMAS = ("cqhecs.web.run/1.0", "cqhecs.web.run/1.1")
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024

KINDS = ("circuit", "cnf")
PRECISIONS = ("f64", "f32", "exact-integer", "n/a")
MODES = ("EXACT", "SAMPLED", "NOISY_CLASSICAL", "REAL_HARDWARE", "REFUSED")

REQUIRED = ("schema", "created_at", "software", "input", "engine", "result", "limits")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_revision() -> str:
    """The commit the software was built from, or ``"unknown"`` outside a checkout.

    ``"unknown"`` is a deliberate value, not a placeholder that looks like a commit: the
    schema requires at least seven characters so that an empty string cannot pass, and the
    validator accepts this one word because pretending to a revision is worse.
    """
    env = os.environ.get("CQHECS_SOURCE_REVISION")
    if env:
        return env
    try:
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and len(revision) >= 7 else "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Software:
    name: str
    version: str
    source_revision: str

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "version": self.version, "source_revision": self.source_revision}


@dataclass(frozen=True)
class Input:
    kind: str
    payload: str
    digest_algorithm: str = "SHA-256"
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_text(self.payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "payload": self.payload,
            "digest_algorithm": self.digest_algorithm,
            "digest": self.digest,
            **dict(self.extra),
        }


@dataclass(frozen=True)
class Engine:
    kind: str
    precision: str
    mode: str

    def to_dict(self) -> Dict[str, str]:
        return {"kind": self.kind, "precision": self.precision, "mode": self.mode}


@dataclass(frozen=True)
class Errors:
    """Three separate error kinds; ``None`` means "not quantified", not "zero"."""

    approximation: Optional[float] = None
    numerical: Optional[float] = None
    sampling: Optional[float] = None

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "approximation": self.approximation,
            "numerical": self.numerical,
            "sampling": self.sampling,
        }


@dataclass(frozen=True)
class Result:
    status: str
    elapsed_ms: float
    error: Errors = field(default_factory=Errors)
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "elapsed_ms": float(self.elapsed_ms), "error": self.error.to_dict(), **dict(self.detail)}


@dataclass
class RunCard:
    software: Software
    input: Input
    engine: Engine
    result: Result
    limits: List[str]
    seed: Optional[int] = None
    created_at: str = field(default_factory=_now)
    schema: str = SCHEMA

    def to_dict(self) -> Dict[str, Any]:
        document: Dict[str, Any] = {
            "schema": self.schema,
            "created_at": self.created_at,
            "software": self.software.to_dict(),
            "input": self.input.to_dict(),
            "engine": self.engine.to_dict(),
            "seed": self.seed,
            "result": self.result.to_dict(),
            "limits": list(self.limits),
        }
        return document

    def write(self, path: Path | str) -> Path:
        target = Path(path)
        payload_bytes = len(self.input.payload.encode("utf-8"))
        if payload_bytes > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"input payload is {payload_bytes} bytes, above the {MAX_PAYLOAD_BYTES} byte limit; "
                "a truncated card would be worse than no card"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target


def build(
    *,
    software: Software,
    input_kind: str,
    payload: str,
    engine_kind: str,
    precision: str,
    mode: str,
    status: str,
    elapsed_ms: float,
    limits: Iterable[str],
    seed: Optional[int] = None,
    error: Optional[Errors] = None,
    detail: Optional[Mapping[str, Any]] = None,
    input_extra: Optional[Mapping[str, Any]] = None,
) -> RunCard:
    """Build a card, refusing nonsense instead of writing it down."""
    if input_kind not in KINDS:
        raise ValueError(f"input kind must be one of {KINDS}")
    if precision not in PRECISIONS:
        raise ValueError(f"precision must be one of {PRECISIONS}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if not payload:
        raise ValueError("the payload must not be empty: a card without its input cannot be checked")
    if seed is not None and not isinstance(seed, int):
        raise ValueError("seed must be an integer or None")
    limits = [str(item) for item in limits if str(item).strip()]
    if not limits:
        raise ValueError("a card needs at least one stated limit")
    return RunCard(
        software=software,
        input=Input(kind=input_kind, payload=payload, extra=input_extra or {}),
        engine=Engine(kind=engine_kind, precision=precision, mode=mode),
        result=Result(status=status, elapsed_ms=float(elapsed_ms), error=error or Errors(), detail=detail or {}),
        limits=limits,
        seed=seed,
    )


def detect_schema(document: Mapping[str, Any]) -> Optional[str]:
    value = document.get("schema")
    return value if isinstance(value, str) else None


def validate(document: Mapping[str, Any]) -> List[str]:
    """Return a list of problems; an empty list means the document is a v2 card."""
    problems: List[str] = []
    schema = detect_schema(document)
    if schema in LEGACY_SCHEMAS:
        return [
            f"schema {schema!r} is a v1 web card; it is not reinterpreted as {SCHEMA} - "
            "regenerate it, or read it with the v1 reader"
        ]
    if schema != SCHEMA:
        return [f"schema is {schema!r}, expected {SCHEMA!r}"]

    for key in REQUIRED:
        if key not in document:
            problems.append(f"missing required field {key!r}")
    if problems:
        return problems

    software = document["software"]
    if not isinstance(software, Mapping):
        problems.append("software must be an object")
    else:
        for key in ("name", "version", "source_revision"):
            if not isinstance(software.get(key), str) or not software.get(key):
                problems.append(f"software.{key} must be a non-empty string")
        revision = software.get("source_revision")
        if isinstance(revision, str) and len(revision) < 7:
            problems.append("software.source_revision must identify a commit (at least 7 characters)")

    inp = document["input"]
    if not isinstance(inp, Mapping):
        problems.append("input must be an object")
    else:
        if inp.get("kind") not in KINDS:
            problems.append(f"input.kind must be one of {KINDS}")
        payload = inp.get("payload")
        if not isinstance(payload, str) or not payload:
            problems.append("input.payload must be a non-empty string")
        else:
            if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
                problems.append(f"input.payload exceeds {MAX_PAYLOAD_BYTES} bytes")
            if inp.get("digest") != sha256_text(payload):
                problems.append("input.digest does not match SHA-256 of input.payload")
        if inp.get("digest_algorithm") != "SHA-256":
            problems.append("input.digest_algorithm must be 'SHA-256'")

    engine = document["engine"]
    if not isinstance(engine, Mapping):
        problems.append("engine must be an object")
    else:
        if not isinstance(engine.get("kind"), str) or not engine.get("kind"):
            problems.append("engine.kind must be a non-empty string")
        if engine.get("precision") not in PRECISIONS:
            problems.append(f"engine.precision must be one of {PRECISIONS}")
        if engine.get("mode") not in MODES:
            problems.append(f"engine.mode must be one of {MODES}")

    seed = document.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        problems.append("seed must be an integer or null")

    result = document["result"]
    if not isinstance(result, Mapping):
        problems.append("result must be an object")
    else:
        if not isinstance(result.get("status"), str) or not result.get("status"):
            problems.append("result.status must be a non-empty string")
        elapsed = result.get("elapsed_ms")
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
            problems.append("result.elapsed_ms must be a number >= 0")
        error = result.get("error")
        if not isinstance(error, Mapping):
            problems.append("result.error must be an object")
        else:
            for key in ("approximation", "numerical", "sampling"):
                value = error.get(key)
                if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0):
                    problems.append(f"result.error.{key} must be a number >= 0 or null")

    limits = document["limits"]
    if not isinstance(limits, list) or not limits or not all(isinstance(item, str) and item for item in limits):
        problems.append("limits must be a non-empty list of non-empty strings")

    return problems


def read(path: Path | str) -> Dict[str, Any]:
    """Load a card and refuse anything that is not a valid v2 document."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate(document)
    if problems:
        raise ValueError("; ".join(problems))
    return document
