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
    - EXACT: The computation applies no deliberate approximation beyond its
      documented numerical-rank/zero policy. This is not a claim of symbolic
      exactness or zero floating-point error; backends expose any numerical
      rank reduction separately. Finite-shot sampling is also separate: any
      backend that returns sampled `counts` reports `sampling_error_bound`.
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

class ExecutionMode(str, Enum):
    """
    Irreducibly separate execution modes for CQ-HECS:
    - IDEAL_CLASSICAL: Ideal classical simulation using a CQ-HECS engine.
    - NOISY_CLASSICAL: Classical emulation with an explicit, versioned noise model;
      output is a modelled distribution or estimator, not a physical measurement.
    - REAL_HARDWARE: Executed on an identified physical quantum processing unit (QPU).
      Silent fallback to classical emulation is strictly prohibited.
    """
    IDEAL_CLASSICAL = "IDEAL_CLASSICAL"
    NOISY_CLASSICAL = "NOISY_CLASSICAL"
    REAL_HARDWARE = "REAL_HARDWARE"


def hoeffding_proportion_bound(
    shots: int,
    delta: float = 0.05,
    support_size: int = 2,
) -> float:
    """
    Two-sided Hoeffding bound on the error of a **single** categorical outcome.

    For one fixed outcome ``y`` observed ``n`` times, Hoeffding's inequality
    gives

        |P_hat(y) - P(y)| <= sqrt(ln(2/delta) / (2n))

    with probability at least ``1 - delta``. This is a bound on one coordinate
    only.

    Args:
        shots: Number of iid samples. Must be > 0.
        delta: Failure probability, in (0, 1). With ``support_size = K`` the
            bound holds **simultaneously for all K outcomes** with probability
            at least ``1 - delta`` (union bound over ``delta / K`` each).
        support_size: Number of distinct outcomes. Defaults to 2 (a binary
            measurement). It widens the bound through the Bonferroni-corrected
            ``ln(2K / delta)`` below.

    Returns:
        Upper bound on |P_hat(y) - P(y)| that holds for every outcome y at
        once, with probability at least ``1 - delta``.

    Raises:
        ValueError: If shots <= 0, delta outside (0, 1), or support_size < 1.
    """
    import math

    if shots <= 0:
        raise ValueError(f"shots must be a positive integer, got {shots}")
    if not (0.0 < delta < 1.0):
        raise ValueError(f"delta must lie strictly in (0, 1), got {delta}")
    if support_size < 1:
        raise ValueError(f"support_size must be >= 1, got {support_size}")

    return math.sqrt(math.log(2.0 * support_size / delta) / (2.0 * shots))


def hoeffding_total_variation_bound(
    shots: int,
    support_size: int = 2,
    delta: float = 0.05,
) -> float:
    """
    Rigorous bound on the total-variation distance between an empirical
    distribution over ``shots`` iid samples and the true distribution, holding
    with probability at least ``1 - delta``.

        TV(P_emp, P_true) = 1/2 * ||P_emp - P_true||_1
                          <= sqrt( ln((2^K - 2)/delta) / (2 * shots) )

    where ``K = support_size`` is the number of distinct outcomes.

    Derivation
    ----------
    Weissman, Ordentlich, Seroussi, Verdú and Weinberger (2003), Theorem 2.1,
    via Lemma 1 of Mardia, Jiao, Tánczos, Nowak and Weissman (2019), gives

        Pr(||P_hat - P||_1 >= eps) <= (2^K - 2) * exp(-n * phi(pi_P) * eps^2 / 4)

    where ``phi(p) = ln((1-p)/p) / (1 - 2p) >= 2`` and ``pi_P`` is the
    concentration function of P. Solving for ``eps`` and using ``phi >= 2``
    gives the L1 bound ``2*sqrt(ln((2^K-2)/delta) / (2n))``; total variation is
    half the L1 distance, hence the expression above. Using ``phi >= 2`` makes
    the bound distribution-independent, which is what a result schema needs.

    Why the support size is required
    -------------------------------
    Hoeffding's per-outcome inequality is dimension-free, but total variation
    sums over all K outcomes and the concentration prefactor ``2^K - 2``
    depends on K. Dropping it is not conservative, it is wrong: for a uniform
    distribution over K = 64 outcomes with 1000 shots, the dimension-free
    expression ``sqrt(ln(2/delta)/(2n)) = 0.0429`` is exceeded 100% of the
    time, whereas this bound is never exceeded at its stated confidence.

    Note the bound is a *confidence statement*: it may be violated with
    probability up to ``delta``. For K = 2 it reduces exactly to the familiar
    ``sqrt(ln(2/delta)/(2n))``.

    For large K this becomes vacuous (it exceeds the maximum possible value of
    TV distance, which is 1.0, and the result is clamped to 1.0). That is an
    honest outcome, not a defect. For high-support cases prefer per-outcome
    confidence intervals (:func:`hoeffding_proportion_bound`).

    Args:
        shots: Number of iid samples. Must be > 0.
        support_size: Number of distinct outcomes (e.g. ``1 << num_qubits``).
        delta: Failure probability, in (0, 1).

    Returns:
        Total-variation upper bound, clamped to 1.0.

    Raises:
        ValueError: If shots <= 0, support_size < 1, or delta outside (0, 1).
    """
    import math

    if shots <= 0:
        raise ValueError(f"shots must be a positive integer, got {shots}")
    if support_size < 1:
        raise ValueError(f"support_size must be >= 1, got {support_size}")
    if not (0.0 < delta < 1.0):
        raise ValueError(f"delta must lie strictly in (0, 1), got {delta}")

    if support_size <= 2:
        # 2^K - 2 = 2 for K = 2 and 0 for K = 1; K = 1 is a degenerate
        # distribution with no deviation possible.
        if support_size == 1:
            return 0.0
        log_prefactor = math.log(2.0)
    elif isinstance(support_size, int) and support_size.bit_length() > 60:
        # For support_size >= 2^60, bound >= sqrt(2^60 * ln 2 / (2 * shots)) >> 1.0
        # for any realistic shot count. Returning 1.0 avoids int-to-float OverflowError.
        return 1.0
    else:
        # ln(2^K - 2) <= K*ln2, so K*ln2 is a valid (slightly conservative)
        # replacement. The excess is ln(2^K / (2^K - 2)): about 0.29 at K = 3,
        # 0.13 at K = 4 and below double precision from K ~ 54. Using K*ln2
        # also avoids overflowing 2^K for wide registers (K = 1000).
        log_prefactor = support_size * math.log(2.0)

    log_ratio = log_prefactor - math.log(delta)
    bound = math.sqrt(log_ratio / (2.0 * shots))
    return min(bound, 1.0)


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

    ``total_error_bound`` composes these into one figure *only* when they share
    a metric that makes the triangle inequality applicable; it is ``None``
    otherwise. See the property for the exact conditions - a bound on
    expectation values does not bound a bitstring distribution.

    Attributes:
        path (str): Execution path used ('A', 'B', 'C', or 'D').
        exact (bool): True when no deliberate approximation beyond the backend's
            documented numerical-rank/zero policy was applied.
        error_bound (float): Upper bound on deliberate approximation error;
            not a floating-point or finite-shot error bound.
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
    execution_mode: ExecutionMode = ExecutionMode.IDEAL_CLASSICAL
    backend_profile_id: Optional[str] = None
    noise_model_id: Optional[str] = None
    is_real_hardware: bool = False
    calibration_timestamp: Optional[str] = None
    provider_job_id: Optional[str] = None

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
    def total_error_bound(self) -> Optional[float]:
        """
        Sum of the component bounds, on the same metric where justified.

        Composition is only meaningful when every component bounds the *same*
        quantity in the *same* metric, so that the triangle inequality applies.
        That holds when all components are total-variation-like distances
        between a returned distribution and the ideal one:

        * ``error_bound`` - deliberate approximation of the distribution.
        * ``numerical_error_bound`` - measured roundoff in the state, which
          propagates to the distribution.
        * ``sampling_error_bound`` - finite-shot deviation of the empirical
          distribution from the exact one.

        Returns ``None`` when the components do not share a metric - in
        particular when the backend reports only expectation values, because a
        bound on observables does not bound a bitstring distribution. Summing in
        that case would produce a number that means nothing.

        The confidence levels differ too: the sampling bound holds with
        probability >= 1 - delta, not deterministically. Treat the sum as a
        confidence statement, not a worst case.
        """
        if self.unresolved or self.is_failed:
            # No successful output distribution exists to certify.
            return None
        if self.expectation_values is not None and not self.counts:
            # Observable-space bound only; there is no distribution to bound.
            return None
        if self.counts and self.metadata.get("counts_are_joint_distribution") is False:
            # Independent marginal samples are not the circuit's joint output.
            return None

        covers = self.metadata.get("error_bound_covers")
        if covers is not None and covers not in {
            "counts", "probabilities", "joint_distribution", "total_variation",
        }:
            # In particular, Path D's observable bound excludes sampled counts.
            return None
        excludes = self.metadata.get("error_bound_excludes")
        if excludes is not None and "sampled_counts" in str(excludes):
            return None

        components = [float(self.error_bound)]
        if self.numerical_error_bound is not None:
            components.append(float(self.numerical_error_bound))
        if self.sampling_error_bound is not None:
            components.append(float(self.sampling_error_bound))
        return sum(components)

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
            "error_bound_metric": (
                "total_variation" if self.total_error_bound is not None else None
            ),
            "unresolved": self.unresolved,
            "state": self.state.value if self.state else status_compat,
            "status": status_compat,
            "counts": self.counts,
            "probabilities": self.probabilities,
            "expectation_values": self.expectation_values,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
            "execution_mode": (
                self.execution_mode.value
                if isinstance(self.execution_mode, ExecutionMode)
                else str(self.execution_mode)
            ),
            "backend_profile_id": self.backend_profile_id,
            "noise_model_id": self.noise_model_id,
            "is_real_hardware": self.is_real_hardware,
            "calibration_timestamp": self.calibration_timestamp,
            "provider_job_id": self.provider_job_id,
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
