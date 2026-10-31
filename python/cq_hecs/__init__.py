"""
Legacy CQ-HECS Vulkan provider shim (not part of the v2 package).

Canonical version: ``scripts/version.py``.
"""

from __future__ import annotations

__version__ = "3.7.0"

from .provider import VulkanQpuBackend

__all__ = ["VulkanQpuBackend", "__version__"]
