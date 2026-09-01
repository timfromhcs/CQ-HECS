"""
SimulationResult Schema for CQ-HECS Classical Four-Path Architecture.
Path A: Stabilizer-Tableau (exact, Clifford)
Path B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
Path C: MPS without Cutoff + NVMe-Offload (exact up to memory limit)
Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "path": self.path,
            "exact": self.exact,
            "error_bound": self.error_bound,
            "unresolved": self.unresolved,
            "counts": self.counts,
            "probabilities": self.probabilities,
            "expectation_values": self.expectation_values,
            "execution_time_ms": self.execution_time_ms,
            "status": "UNRESOLVED" if self.unresolved else "SUCCESS",
            "metadata": self.metadata,
        }

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style indexing for backward compatibility."""
        if key == "status":
            return "UNRESOLVED" if self.unresolved else "SUCCESS"
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.metadata:
            return self.metadata[key]
        raise KeyError(f"SimulationResult has no attribute or metadata key: {key}")

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or (key == "status") or (key in self.metadata)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self) -> str:
        status_str = "UNRESOLVED" if self.unresolved else "SUCCESS"
        return (
            f"SimulationResult(path='{self.path}', exact={self.exact}, "
            f"error_bound={self.error_bound:.6e}, status='{status_str}', "
            f"counts_len={len(self.counts)})"
        )
