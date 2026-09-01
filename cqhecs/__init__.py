"""
CQ-HECS Quantum Computing Engine
Bit-Exact Giles-Selinger Ring Z[1/sqrt(2), i] & Hybrid Stabilizer-MPS Backend
"""

from cqhecs.backend import CQHecsBackend
from cqhecs.provider import CQHecsProvider

__version__ = "4.5.0"
__all__ = ["CQHecsBackend", "CQHecsProvider"]
