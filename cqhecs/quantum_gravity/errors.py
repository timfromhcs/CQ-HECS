"""Typed errors and typed refusals for the Quantum Gravity model layer.

The rule from the mission is fail-closed: when a model, encoding, backend or resource
cannot be supported exactly as declared, raise one of these instead of returning a
plausible but unsupported number.
"""

from __future__ import annotations

from typing import Optional


class QGError(Exception):
    """Base class for all Quantum Gravity layer errors."""


class QGModelError(QGError):
    """The declared model is malformed or self-inconsistent (e.g. Hermiticity, parity)."""


class QGUnsupported(QGError):
    """A requested operation is outside the declared, tested capability boundary."""

    def __init__(self, message: str, *, code: str = "QG_UNSUPPORTED") -> None:
        super().__init__(message)
        self.code = code


class QGResourceError(QGError):
    """A declared resource budget would be exceeded; no partial result is returned."""

    def __init__(self, message: str, *, code: str = "QG_RESOURCE", estimate: Optional[dict] = None) -> None:
        super().__init__(message)
        self.code = code
        self.estimate = estimate or {}


class QGBlocker(QGError):
    """An external dependency (credential, provider, hardware) blocks the operation.

    This is deliberately distinct from :class:`QGUnsupported`: the operation may be
    supported in principle but cannot run now. The caller must not silently fall back.
    """

    def __init__(self, message: str, *, code: str = "QG_BLOCKED", next_action: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
