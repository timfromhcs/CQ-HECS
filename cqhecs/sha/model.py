"""Typed task/result contract for SHA research and hardware, separate from circuit results."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

BACKENDS = (
    "WEBGPU", "WASM_SIMD", "WASM_SCALAR", "BROWSER_CPU", "LOCAL_NATIVE", "ASIC_BM1366", "DEMO_SIMULATED",
)


class ShaState(str, Enum):
    COMPUTED = "COMPUTED"
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    UNRESOLVED = "UNRESOLVED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"
    SIMULATED = "SIMULATED"


@dataclass(frozen=True)
class ShaTask:
    task_id: str
    algorithm: str
    rounds: int
    iv: str
    input_model: str
    target: str
    endian: str
    seed: int
    budget: dict
    backend: str

    def __post_init__(self):
        if not 0 <= self.rounds <= 64:
            raise ValueError("rounds must be between 0 and 64")
        if self.backend not in BACKENDS:
            raise ValueError(f"unknown backend {self.backend!r}")

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _digest(body: dict) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ShaResult:
    task: ShaTask
    state: ShaState
    payload: dict
    software: dict
    firmware_version: str | None = None
    integrity: str = field(default="")

    @staticmethod
    def _body(task, state, payload, software, firmware_version) -> dict:
        return {
            "schema": "hcs.sha.result.v1",
            "task": task.to_dict(),
            "state": state.value,
            "payload": payload,
            "software": software,
            "firmware_version": firmware_version,
        }

    @classmethod
    def create(cls, task, state, payload, software, firmware_version=None) -> "ShaResult":
        if state is ShaState.SIMULATED and task.backend != "DEMO_SIMULATED":
            raise ValueError("SIMULATED results are only valid for the DEMO_SIMULATED backend")
        if task.backend == "DEMO_SIMULATED" and state is not ShaState.SIMULATED:
            raise ValueError("DEMO_SIMULATED data must be labelled SIMULATED")
        if task.backend == "ASIC_BM1366" and not firmware_version:
            raise ValueError("hardware results must record the firmware version")
        body = cls._body(task, state, payload, software, firmware_version)
        return cls(task, state, payload, software, firmware_version, _digest(body))

    def verify_integrity(self) -> bool:
        return _digest(self._body(self.task, self.state, self.payload, self.software, self.firmware_version)) == self.integrity

    def to_dict(self) -> dict:
        d = self._body(self.task, self.state, self.payload, self.software, self.firmware_version)
        d["integrity"] = self.integrity
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ShaResult":
        return cls(
            ShaTask(**d["task"]), ShaState(d["state"]), d["payload"], d["software"],
            d.get("firmware_version"), d["integrity"],
        )
