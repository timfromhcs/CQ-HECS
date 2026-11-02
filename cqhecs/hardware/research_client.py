"""Typed client for the on-device research API (`/api/research/*`).

The client never trusts the device:

* every trace the device returns is replayed through
  :func:`cqhecs.sha.round_trace.replay`, which recomputes the schedule and all 64
  rounds and rejects the first deviation;
* the response envelope must state `compute == "software_cpu"` and
  `asic_access == "none"`. A device (or a proxy, or a stale firmware) that claims
  ASIC-internal SHA state is refused, because that hardware capability does not
  exist;
* the payload is size-limited and the connection never follows a redirect, so a
  mistaken host cannot turn a 64-byte block request into a fetch of something
  else.

Transport failures raise :class:`ResearchError`. A device refusal (409 with a
typed reason such as `pool_active` or `thermal_unsafe`) is a *result*, not an
exception: refusals are expected states of the protocol and callers have to
handle them.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping

from . import firmware_profile as fw

MAX_RESPONSE_BYTES = 262144
DEFAULT_TIMEOUT_S = 10.0
_HANDLED_STATUS = frozenset({"ok", "challenge_issued"})
_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?$")


class ResearchError(RuntimeError):
    """The device could not be reached, or answered something unusable."""


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    reason: str
    status: int
    body: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceResult:
    ok: bool
    reason: str
    trace: Mapping[str, Any] | None = None
    output_state: str | None = None
    envelope: Mapping[str, Any] | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # pragma: no cover - one-line guard
        return None


class ResearchClient:
    """One explicit host, one explicit set of routes. No discovery, no proxying."""

    def __init__(self, host: str, port: int = 80, timeout: float = DEFAULT_TIMEOUT_S):
        if not host or not _HOST_RE.match(host):
            raise ValueError("host must be one exact hostname or IPv4 address (no scheme, path or range)")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be an integer in 1..65535")
        self.host = host
        self.port = port
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # -- transport
    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> tuple[int, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if len(data or b"") > fw_max_body():
            raise ResearchError("request body exceeds the firmware limit")
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            status = exc.code
        except (urllib.error.URLError, OSError) as exc:
            raise ResearchError(f"device unreachable: {exc}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ResearchError("device response exceeds the client limit")
        try:
            return status, json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise ResearchError(f"device response is not JSON ({status})") from exc

    # -- read routes
    def status(self) -> Mapping[str, Any]:
        status, body = self._request("GET", "/api/research/status")
        if status != 200:
            raise ResearchError(f"status request failed with {status}")
        if body.get("schema") != "hcs.sha.miner.v1":
            raise ResearchError("status schema is not hcs.sha.miner.v1")
        return body

    def capabilities(self) -> Mapping[str, Any]:
        status, body = self._request("GET", "/api/research/capabilities")
        if status != 200:
            raise ResearchError(f"capabilities request failed with {status}")
        fw.reject_asic_round_claim(body)
        return body

    # -- command routes
    def _command(self, path: str, payload: Mapping[str, Any] | None = None) -> CommandResult:
        status, body = self._request("POST", path, payload or {})
        result = str(body.get("result", ""))
        # 2xx with an "ok" result, or a typed refusal the caller has to interpret.
        ok = status == 200 and (result in _HANDLED_STATUS or body.get("accepted") is True)
        return CommandResult(ok=ok, reason=result or f"http_{status}", status=status, body=body)

    def challenge(self) -> CommandResult:
        """Ask the device for a pairing token. The token is NOT in the response."""
        return self._command("/api/research/challenge", {})

    def arm(self, token: int | str) -> CommandResult:
        digits = str(token).strip()
        if not digits.isdigit() or len(digits) > 10:
            raise ValueError("token must be the decimal digits shown on the device console")
        return self._command("/api/research/arm", {"token": digits})

    def pause(self) -> CommandResult:
        return self._command("/api/research/pause")

    def resume(self) -> CommandResult:
        return self._command("/api/research/resume")

    def cancel(self) -> CommandResult:
        return self._command("/api/research/cancel")

    def disarm(self) -> CommandResult:
        return self._command("/api/research/disarm")

    # -- oracle
    def trace_block(self, block: bytes, rounds: int = 64, feed_forward: bool = True) -> TraceResult:
        """Ask the device for a software trace and verify every value locally."""
        if not isinstance(block, (bytes, bytearray)) or len(block) != 64:
            raise ValueError("block must be exactly 64 bytes")
        if not 0 <= int(rounds) <= 64:
            raise ValueError("rounds must be 0..64")

        status, body = self._request(
            "POST",
            "/api/research/sha256",
            {"block_hex": bytes(block).hex(), "rounds": int(rounds), "feed_forward": bool(feed_forward)},
        )
        if status != 200:
            reason = str(body.get("message") or body.get("status") or f"http_{status}")
            return TraceResult(False, reason, envelope=body if isinstance(body, Mapping) else None)

        if not isinstance(body, Mapping) or body.get("schema") != "hcs.sha.device_sha256.v1":
            return TraceResult(False, "response is not a device_sha256 document", envelope=body)
        if body.get("compute") != "software_cpu":
            return TraceResult(False, "device does not claim a software computation", envelope=body)
        if body.get("asic_access") != "none":
            return TraceResult(False, "device claims ASIC access, which the BM1366 cannot provide", envelope=body)

        trace = body.get("trace")
        if not isinstance(trace, Mapping):
            return TraceResult(False, "response has no trace object", envelope=body)

        from cqhecs.sha import round_trace  # local import keeps module import cheap

        try:
            output_state = round_trace.replay(dict(trace))
        except (round_trace.TraceMismatch, KeyError, ValueError, TypeError) as exc:
            return TraceResult(False, f"device trace rejected by the reference replay: {exc}", envelope=body)

        if trace.get("rounds_executed") != int(rounds):
            return TraceResult(False, "device executed a different number of rounds than requested", envelope=body)
        if trace.get("feed_forward") is not bool(feed_forward):
            return TraceResult(False, "device applied a different feed-forward setting than requested", envelope=body)
        if trace.get("block") != bytes(block).hex():
            return TraceResult(False, "device traced a different block than requested", envelope=body)

        return TraceResult(True, "device trace verified", trace=dict(trace), output_state=output_state, envelope=body)

    def digest(self, message: bytes, sha256d: bool = False) -> tuple[str, Mapping[str, Any]]:
        """Ask the device for a message digest and check it against the local reference."""
        if not isinstance(message, (bytes, bytearray)) or len(message) > 512:
            raise ValueError("message must be at most 512 bytes")
        status, body = self._request(
            "POST", "/api/research/sha256", {"message_hex": bytes(message).hex(), "sha256d": bool(sha256d)}
        )
        if status != 200:
            raise ResearchError(f"digest request failed with {status}: {body.get('message')}")
        if body.get("schema") != "hcs.sha.device_sha256.v1" or body.get("compute") != "software_cpu":
            raise ResearchError("digest response is not a software_sha256 document")

        from cqhecs.sha import sha256_reference as ref

        expected = ref.sha256d(bytes(message)) if sha256d else ref.sha256(bytes(message))
        device = str(body.get("digest", "")).lower()
        if device != expected.hex():
            raise ResearchError("device digest does not match the local reference")
        return device, body


def fw_max_body() -> int:
    """The firmware rejects request bodies of this size or larger (2 KiB buffer)."""
    return 2048
