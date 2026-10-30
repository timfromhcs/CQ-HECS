"""
CQ-HECS Quantum Computing Engine (Classical-Only Four-Path Architecture & Hardware-Aware Bridge)
A) Stabilizer-Tableau (exact, Clifford)
B) Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C) MPS without Cutoff + NVMe-Offload (exact up to memory limit)
D) Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
Hardware-Aware Quantum Bridge: Truthful backend profiles, Kraus noise models, and provider boundaries
"""

__version__ = "2.5.1"

from cqhecs.backend import CQHecsBackend
from cqhecs.provider import (
    CQHecsProvider,
    FakeHardwareProvider,
    FakeHardwareBackend,
    RealHardwareProvider,
    RealHardwareBackend,
)
from cqhecs.result import (
    ExecutionMode,
    SimulationResult,
    SimulationState,
    hoeffding_total_variation_bound,
)
from cqhecs.hardware_bridge import (
    BackendProfile,
    NoiseModel,
    NoiseChannel,
    DepolarizingChannel,
    AmplitudeDampingChannel,
    PhaseDampingChannel,
    TwoQubitDepolarizingChannel,
    ReadoutErrorChannel,
    HardwareBridgeError,
    HardwareAuthorizationRequiredError,
    HardwareAuthenticationError,
    InvalidProfileError,
    InvalidNoiseModelError,
    InvalidTopologyError,
    create_fake_manila_profile,
    create_linear_profile,
    depolarizing_parameter_from_infidelity,
)
from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
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
    DenseStatevector,
)

__all__ = [
    "CQHecsBackend",
    "CQHecsProvider",
    "ExecutionMode",
    "SimulationResult",
    "SimulationState",
    "hoeffding_total_variation_bound",
    "BackendProfile",
    "NoiseModel",
    "NoiseChannel",
    "DepolarizingChannel",
    "AmplitudeDampingChannel",
    "PhaseDampingChannel",
    "TwoQubitDepolarizingChannel",
    "ReadoutErrorChannel",
    "FakeHardwareProvider",
    "FakeHardwareBackend",
    "RealHardwareProvider",
    "RealHardwareBackend",
    "create_fake_manila_profile",
    "create_linear_profile",
    "depolarizing_parameter_from_infidelity",
    "NoisyDensityMatrixBackend",
    "HardwareBridgeError",
    "HardwareAuthorizationRequiredError",
    "HardwareAuthenticationError",
    "InvalidProfileError",
    "InvalidNoiseModelError",
    "InvalidTopologyError",
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
    "DenseStatevector",
]
