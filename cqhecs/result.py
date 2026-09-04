"""
SimulationResult Schema for CQ-HECS Classical Four-Path Architecture.
Path A: Stabilizer-Tableau (exact, Clifford)
Path B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
Path C: MPS without Cutoff + NVMe-Offload (exact up to memory limit)
Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class SimulationState(str, Enum):
    """
    Explicit, machine-readable simulation states for the Four-Path architecture:
    - EXACT: Mathematically exact simulation (Path A, B, C; error_bound == 0.0).
    - CERTIFIED: Certified classical approximation within proven error bounds (Path D; error_bound <= tolerance).
    - UNRESOLVED: Circuit cannot be solved within allocated budget/tolerance without silent approximation.
    - FAILED: Runtime failure, invalid input, or unrecoverable execution error.
    """
    EXACT = "EXACT"
    CERTIFIED = "CERTIFIED"
    UNRESOLVED = "UNRESOLVED"
    FAILED = "FAILED"


@dataclass
class SimulationResult:
    """
    Standardized Simulation Result Schema for CQ-HECS Four-Path Classical Engine.

    Attributes:
        path (str): Execution path used ('A', 'B', 'C', or 'D').
        exact (bool): True if simulation is mathematically exact, False if approximate.
        error_bound (float): Proven maximum upper bound on error (0.0 for exact paths A, B, C).
        unresolved (bool): True if error bound exceeds user tolerance or memory ceiling prevents resolution.
        counts (Dict[str, int]): Measurement frequency counts per bitstring.
        probabilities (Optional[Dict[str, float]]): Exact or bounded outcome probabilities.
        expectation_values (Optional[Dict[str, float]]): Pauli or observable expectation values.
        execution_time_ms (float): Elapsed execution time in milliseconds.
        metadata (Dict[str, Any]): Detailed diagnostic metadata (qubits, gates, t-count, memory, etc.).
        state (SimulationState): Explicit machine-readable result state (EXACT, CERTIFIED, UNRESOLVED, FAILED).
    """
    path: str
    exact: bool
    error_bound: float
    unresolved: bool
    counts: Dict[str, int] = field(default_factory=dict)
    probabilities: Optional[Dict[str, float]] = None
    expectation_values: Optional[Dict[str, float]] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    state: Optional[SimulationState] = None

    def __post_init__(self):
        if self.state is None:
            if self.metadata.get("failed", False):
                self.state = SimulationState.FAILED
            elif self.unresolved:
                self.state = SimulationState.UNRESOLVED
            elif self.exact and self.error_bound == 0.0:
                self.state = SimulationState.EXACT
            else:
                self.state = SimulationState.CERTIFIED

    @property
    def is_exact(self) -> bool:
        return self.state == SimulationState.EXACT

    @property
    def is_certified(self) -> bool:
        return self.state == SimulationState.CERTIFIED

    @property
    def is_unresolved(self) -> bool:
        return self.state == SimulationState.UNRESOLVED

    @property
    def is_failed(self) -> bool:
        return self.state == SimulationState.FAILED

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        status_compat = "UNRESOLVED" if self.unresolved else ("FAILED" if self.is_failed else "SUCCESS")
        return {
            "path": self.path,
            "exact": self.exact,
            "error_bound": self.error_bound,
            "unresolved": self.unresolved,
            "state": self.state.value if self.state else status_compat,
            "status": status_compat,
            "counts": self.counts,
            "probabilities": self.probabilities,
            "expectation_values": self.expectation_values,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style indexing for backward compatibility."""
        if key == "status":
            return "UNRESOLVED" if self.unresolved else ("FAILED" if self.is_failed else "SUCCESS")
        if key == "state":
            return self.state.value if self.state else ("UNRESOLVED" if self.unresolved else "SUCCESS")
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.metadata:
            return self.metadata[key]
        raise KeyError(f"SimulationResult has no attribute or metadata key: {key}")

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or (key in ("status", "state")) or (key in self.metadata)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self) -> str:
        state_str = self.state.value if self.state else ("UNRESOLVED" if self.unresolved else "SUCCESS")
        return (
            f"SimulationResult(path='{self.path}', state='{state_str}', exact={self.exact}, "
            f"error_bound={self.error_bound:.6e}, counts_len={len(self.counts)})"
        )
