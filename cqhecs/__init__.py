"""
CQ-HECS Quantum Computing Engine (Classical-Only Four-Path Architecture)
A) Stabilizer-Tableau (exact, Clifford)
B) Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C) MPS without Cutoff + NVMe-Offload (exact up to memory limit)
D) Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
"""

from cqhecs.backend import CQHecsBackend
from cqhecs.provider import CQHecsProvider
from cqhecs.result import SimulationResult
from cqhecs.circuit_analyzer import CircuitAnalyzer, CircuitProperties
from cqhecs.router import FourPathRouter, EntanglementAdaptiveRouter
from cqhecs.scheduler import VulkanComputeScheduler
from cqhecs.backends import (
    PathAStabilizerBackend,
    StabilizerTableauSimulator,
    PathBStabilizerRankBackend,
    StabilizerRankSimulator,
    PathCMPSExactBackend,
    ExactMPSTensorChain,
    PathDSparsePauliBackend,
    SparsePauliDynamicsSimulator,
)

__version__ = "0.2.0"
__all__ = [
    "CQHecsBackend",
    "CQHecsProvider",
    "SimulationResult",
    "CircuitAnalyzer",
    "CircuitProperties",
    "FourPathRouter",
    "EntanglementAdaptiveRouter",
    "VulkanComputeScheduler",
    "PathAStabilizerBackend",
    "StabilizerTableauSimulator",
    "PathBStabilizerRankBackend",
    "StabilizerRankSimulator",
    "PathCMPSExactBackend",
    "ExactMPSTensorChain",
    "PathDSparsePauliBackend",
    "SparsePauliDynamicsSimulator",
]
