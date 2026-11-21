"""Quantum Gravity research primitives for CQ-HECS (campaign ``qg-2026-01``).

This package is a *specialist model layer*, not a second simulator. It defines typed
models, Hamiltonians, encodings and observables for a small, bounded set of Quantum
Gravity research experiments, and adapts them to the existing CQ-HECS result and
provenance contracts. It deliberately does not add a generic circuit parser, a new
result type, or a second UI framework.

Scientific boundary
-------------------
A quantum processor running ``U_ZZ(theta)`` **emulates** a model; it is not coupling two
test masses through gravity. Finite-N SYK is a finite model experiment, not a spacetime
wormhole. Every public value produced here is a model quantity with an explicit
classification from :data:`cqhecs.quantum_gravity.catalog.ExecutionSurface`. Nothing in
this package establishes, disproves, or measures quantum gravity.
"""

from __future__ import annotations

from cqhecs.quantum_gravity.catalog import (
    EXECUTION_SURFACES,
    ExecutionSurface,
    MethodCard,
    catalog,
)
from cqhecs.quantum_gravity.errors import (
    QGBlocker,
    QGError,
    QGModelError,
    QGResourceError,
    QGUnsupported,
)
from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel
from cqhecs.quantum_gravity.observables import (
    chsh_from_correlators,
    concurrence_2qubit,
    entanglement_entropy,
    negativity_2qubit,
    partial_transpose,
)
from cqhecs.quantum_gravity.noise import NoiseConfig, witness_under_noise
from cqhecs.quantum_gravity.results import (
    QGExperimentResult,
    SchemaVersionError,
    UNCERTAINTY_CLASSES,
    build_experiment_result,
)

__all__ = [
    "EXECUTION_SURFACES",
    "ExecutionSurface",
    "MethodCard",
    "catalog",
    "QGBlocker",
    "QGError",
    "QGModelError",
    "QGResourceError",
    "QGUnsupported",
    "BMVEffectivePhaseModel",
    "chsh_from_correlators",
    "concurrence_2qubit",
    "entanglement_entropy",
    "negativity_2qubit",
    "partial_transpose",
    "NoiseConfig",
    "witness_under_noise",
    "QGExperimentResult",
    "SchemaVersionError",
    "UNCERTAINTY_CLASSES",
    "build_experiment_result",
]

# Subpackages ``fermions``, ``hamiltonians``, ``circuits`` and ``references`` are imported
# on demand by callers so that a light import of the package never pulls NumPy/SciPy-heavy
# work into an unrelated code path.
