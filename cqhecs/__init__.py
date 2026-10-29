"""
CQ-HECS Quantum Computing Engine (Classical-Only Four-Path Architecture)
A) Stabilizer-Tableau (exact, Clifford)
B) Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C) MPS without Cutoff + NVMe-Offload (exact up to memory limit)
D) Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
"""

__version__ = "2.4.0"

from cqhecs.backend import CQHecsBackend
from cqhecs.provider import CQHecsProvider
from cqhecs.result import (
    SimulationResult,
    SimulationState,
    hoeffding_total_variation_bound,
)
from cqhecs.circuit_analyzer import (
    CircuitAnalyzer,
    CircuitProperties,
    UnsupportedCircuitInput,
)
from cqhecs.router import (
    FourPathRouter,
    EntanglementAdaptiveRouter,
    UnsupportedCircuitError,
)
from cqhecs.expectation import (
    ExpectationError,
    ExpectationResult,
    expectation_values,
)
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

__all__ = [
    "CQHecsBackend",
    "CQHecsProvider",
    "SimulationResult",
    "SimulationState",
    "hoeffding_total_variation_bound",
    "CircuitAnalyzer",
    "CircuitProperties",
    "UnsupportedCircuitInput",
    "FourPathRouter",
    "EntanglementAdaptiveRouter",
    "UnsupportedCircuitError",
    "ExpectationError",
    "ExpectationResult",
    "expectation_values",
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
