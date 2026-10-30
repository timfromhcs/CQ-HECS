"""
CQ-HECS Quantum Computing Engine (Classical-Only Four-Path Architecture & Hardware-Aware Bridge)
A) Stabilizer-Tableau (exact, Clifford)
B) Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C) MPS without Cutoff + NVMe-Offload (exact up to memory limit)
D) Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
Hardware-Aware Quantum Bridge: Truthful backend profiles, Kraus noise models, and provider boundaries
"""

__version__ = "3.2.0"

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
    BitFlipChannel,
    AmplitudeDampingChannel,
    PhaseDampingChannel,
    TwoQubitDepolarizingChannel,
    ReadoutErrorChannel,
    HardwareBridgeError,
    OutOfModelError,
    ThermalRelaxationChannel,
    TensorChannel,
    ComposedChannel,
    average_gate_infidelity,
    depolarizing_parameter_with_relaxation,
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
from cqhecs.noisy_expectation import noisy_expectation_values
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
    "BitFlipChannel",
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
    "OutOfModelError",
    "noisy_expectation_values",
    "ThermalRelaxationChannel",
    "TensorChannel",
    "ComposedChannel",
    "average_gate_infidelity",
    "depolarizing_parameter_with_relaxation",
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
