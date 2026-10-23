"""Legacy CQ-HECS compatibility shim (not part of the v2 package).

Canonical version: ``scripts/version.py``.
"""

from .provider import CQHecsBackend, CQHecsProvider

__all__ = ["CQHecsBackend", "CQHecsProvider"]
__version__ = "2.2.0"
