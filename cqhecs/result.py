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
    - EXACT: The underlying computation introduces no approximation error
      (no truncation, no deliberate approximation). Note this describes the
      *computation*, not finite-shot sampling: any backend that returns sampled
      `counts` also reports `sampling_error_bound`.
    - CERTIFIED: The computation is approximate but carries a rigorous,
      derived error bound within the caller's tolerance.
    - UNRESOLVED: Circuit cannot be solved within allocated budget/tolerance
      without silent approximation. No counts/probabilities are returned.
    - FAILED: Runtime failure, invalid input, or unrecoverable execution error.
    """
    EXACT = "EXACT"
    CERTIFIED = "CERTIFIED"
    UNRESOLVED = "UNRESOLVED"
    FAILED = "FAILED"


def hoeffding_total_variation_bound(shots: int, delta: float = 0.05) -> float:
    """
    Rigorous two-sided Hoeffding bound on the total-variation distance between an
    empirical distribution over `shots` iid samples and the true distribution.

    TV(P_emp, P_true) <= sqrt(ln(2/delta) / (2 * shots))

    This covers the *sampling* error only. It is intentionally kept separate from
    the numerical/approximation `error_bound` so that a result never claims
    "zero error" when it is in fact a finite-shot estimate.

    Args:
        shots: Number of measurement samples. Must be > 0.
        delta: Total failure probability, in (0, 1). Default 0.05.

    Returns:
        A non-negative TV-distance upper bound.

    Raises:
        ValueError: If shots <= 0 or delta is outside (0, 1).
    """
    import math

    if shots <= 0:
        raise ValueError(f"shots must be a positive integer, got {shots}")
    if not (0.0 < delta < 1.0):
        raise ValueError(f"delta must lie strictly in (0, 1), got {delta}")

    return math.sqrt(math.log(2.0 / delta) / (2.0 * shots))


@dataclass
class SimulationResult:
    """
    Standardized Simulation Result Schema for CQ-HECS Four-Path Classical Engine.

    Correctness contract
    --------------------
    Three independent sources of error are tracked and never conflated:

    1. ``error_bound`` - **deliberate approximation** error: discarded singular
       values beyond numerical rank, truncated Pauli terms, and any other
       intentional approximation the caller opted into. ``0.0`` means the
       algorithm deliberately approximates nothing.
    2. ``numerical_error_bound`` - **floating-point roundoff** incurred by the
       arithmetic itself. For a float64 implementation this is rarely 0.0 even
       when nothing was deliberately discarded. It is measured where the
       backend can measure it, and left ``None`` where it is not quantified.
    3. ``sampling_error_bound`` - error introduced by turning a distribution
       into ``shots`` sampled counts, via
       :func:`hoeffding_total_variation_bound`.

    ``total_error_bound`` is their sum, so the overall guarantee on the returned
    distribution is always visible and honest.

    Attributes:
        path (str): Execution path used ('A', 'B', 'C', or 'D').
        exact (bool): True when no *deliberate approximation* was applied.
        error_bound (float): Upper bound on deliberate approximation error.
        numerical_error_bound (Optional[float]): Measured floating-point roundoff.
        sampling_error_bound (Optional[float]): TV bound for finite-shot counts.
        unresolved (bool): True if the circuit could not be resolved without
            silent approximation, or the error bound exceeded the tolerance.
        counts (Dict[str, int]): Measurement frequency counts per bitstring.
        probabilities (Optional[Dict[str, float]]): Exact or bounded outcome probabilities.
        expectation_values (Optional[Dict[str, float]]): Pauli or observable expectation values.
        execution_time_ms (float): Elapsed execution time in milliseconds.
        metadata (Dict[str, Any]): Detailed diagnostic metadata.
        state (SimulationState): Explicit machine-readable result state.
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
    sampling_error_bound: Optional[float] = None
    numerical_error_bound: Optional[float] = None

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
    def total_error_bound(self) -> float:
        """Total bound on distance between the returned distribution and the true one."""
        total = float(self.error_bound)
        if self.numerical_error_bound is not None:
            total += float(self.numerical_error_bound)
        if self.sampling_error_bound is not None:
            total += float(self.sampling_error_bound)
        return total

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
            "numerical_error_bound": self.numerical_error_bound,
            "sampling_error_bound": self.sampling_error_bound,
            "total_error_bound": self.total_error_bound,
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
