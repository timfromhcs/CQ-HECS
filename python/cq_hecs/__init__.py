"""
CQ-HECS Quantum Engine: Zero-Float Bit-Exactness, OpenQASM 3.0, Vulkan Compute
"""

from __future__ import annotations

__version__ = "4.6.0"

from .provider import VulkanQpuBackend

__all__ = ["VulkanQpuBackend", "__version__"]
