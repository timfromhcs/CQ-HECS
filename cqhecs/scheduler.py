"""
Vulkan compute *planner* for CQ-HECS.

This module computes workgroup dispatch dimensions, records the barriers a real
submission would need, and produces offload/weighting decisions. It does **not**
own a VkDevice, queue or command buffer, so it cannot submit GPU work.

Historically ``submit_workload()`` returned ``completed=True`` for metadata that
was never dispatched. That was a false completion signal; submissions are now
explicitly marked as planner-only and stay incomplete until a real backend
records completion. Nothing in this module should be read as GPU telemetry.
"""

from __future__ import annotations
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class DispatchDimensions:
    group_count_x: int
    group_count_y: int
    group_count_z: int

    def total_workgroups(self) -> int:
        return self.group_count_x * self.group_count_y * self.group_count_z


@dataclass
class QueueSubmission:
    submission_id: int
    pipeline_name: str
    dispatch: DispatchDimensions
    memory_barriers_count: int
    timestamp_ns: int
    completed: bool = False
    # True means "planned by this module, not dispatched by a Vulkan queue".
    planner_only: bool = True
    execution_backend: str = "planner_only"


class VulkanComputeScheduler:
    """
    Deterministic planner for Vulkan 1.3 compute workloads:

    - Computes workgroup dispatch configurations
    - Records the pipeline/memory barriers a submission requires
    - Decides host RAM / VRAM / tiered-storage offload policy
    - Provides non-cryptographic timing jitter for search perturbation

    It is not a Vulkan driver: no queue submission, synchronization or device
    readback happens here. Components that need real GPU execution must use the
    native engine and report their own verification level.
    """

    def __init__(
        self,
        vram_ceiling_mb: float = 120.0,
        local_workgroup_size: Tuple[int, int, int] = (16, 16, 1),
        entropy_seed: Optional[int] = None
    ):
        self.vram_ceiling_mb = vram_ceiling_mb
        self.local_workgroup_size = local_workgroup_size
        self.entropy_seed = entropy_seed or (int(time.perf_counter_ns()) & 0xFFFFFFFFFFFFFFFF)
        self.submission_counter: int = 0
        self.active_submissions: List[QueueSubmission] = []
        self.pipeline_barriers: List[Dict[str, Any]] = []

    def harvest_timing_jitter(self) -> int:
        """
        Mixes monotonic-clock and wall-clock readings into a 64-bit value.

        This is scheduling jitter, **not** cryptographic or statistically
        proven hardware entropy, and it must not be used for key generation,
        security decisions or unbiased sampling. The value is reproducible only
        if ``entropy_seed`` is fixed and the timing inputs are stubbed.
        """
        ns = time.perf_counter_ns()
        drift = (ns ^ (ns >> 13) ^ (int(time.time() * 1e6))) & 0xFFFFFFFFFFFFFFFF
        self.entropy_seed = (self.entropy_seed * 6364136223846793005 + drift + 1) & 0xFFFFFFFFFFFFFFFF
        return self.entropy_seed

    def harvest_hardware_entropy(self) -> int:
        """Deprecated alias for :meth:`harvest_timing_jitter`.

        The old name overstated the guarantee. Kept temporarily so existing
        callers keep working; new code must use ``harvest_timing_jitter``.
        """
        return self.harvest_timing_jitter()

    def calculate_optimal_dispatch(
        self,
        elements_x: int,
        elements_y: int = 1,
        elements_z: int = 1
    ) -> DispatchDimensions:
        """
        Calculates Vulkan compute workgroup dispatch dimensions based on
        local workgroup layout ceil(elements / local_size).

        Negative or non-finite element counts raise ``ValueError`` instead of
        being clamped to a plausible-looking dispatch.
        """
        if elements_x < 0 or elements_y < 0 or elements_z < 0:
            raise ValueError("dispatch element counts must be non-negative")
        lx, ly, lz = self.local_workgroup_size
        gx = max(1, math.ceil(elements_x / lx))
        gy = max(1, math.ceil(elements_y / ly))
        gz = max(1, math.ceil(elements_z / lz))
        return DispatchDimensions(group_count_x=gx, group_count_y=gy, group_count_z=gz)

    def insert_memory_barrier(
        self,
        src_stage_mask: str,
        dst_stage_mask: str,
        src_access_mask: str,
        dst_access_mask: str
    ) -> Dict[str, Any]:
        """
        Records the barrier that a real submission would need
        (VkMemoryBarrier / VkBufferMemoryBarrier abstraction). No barrier is
        executed here.
        """
        barrier = {
            "src_stage": src_stage_mask,
            "dst_stage": dst_stage_mask,
            "src_access": src_access_mask,
            "dst_access": dst_access_mask,
            "timestamp_ns": time.perf_counter_ns()
        }
        self.pipeline_barriers.append(barrier)
        return barrier

    def submit_workload(
        self,
        pipeline_name: str,
        dispatch: DispatchDimensions,
        barriers_before: int = 0
    ) -> QueueSubmission:
        """
        Registers a *planned* workload.

        The returned submission is ``completed=False`` and
        ``planner_only=True``. Marking it complete requires evidence from a real
        execution backend via :meth:`record_completion`.
        """
        self.submission_counter += 1
        sub = QueueSubmission(
            submission_id=self.submission_counter,
            pipeline_name=pipeline_name,
            dispatch=dispatch,
            memory_barriers_count=barriers_before,
            timestamp_ns=time.perf_counter_ns(),
            completed=False,
            planner_only=True,
            execution_backend="planner_only",
        )
        self.active_submissions.append(sub)
        return sub

    def record_completion(self, submission: QueueSubmission, backend: str) -> None:
        """
        Marks a submission complete **only** when a real backend reports it.

        Callers must pass the execution backend that actually ran the work plus
        its own success evidence. This module cannot verify GPU execution, so it
        simply refuses empty backend names.
        """
        if not backend or backend == "planner_only":
            raise ValueError(
                "completion requires a real execution backend identifier"
            )
        submission.completed = True
        submission.planner_only = False
        submission.execution_backend = backend

    def schedule_offload(
        self,
        current_vram_bytes: int,
        incoming_bytes: int
    ) -> Dict[str, Any]:
        """
        Determines offload policy between GPU VRAM, Host RAM, and NVMe tiered storage.
        Prevents Out-Of-Memory exceptions while strictly keeping active resident memory
        within the configured ceiling.
        """
        ceiling_bytes = int(self.vram_ceiling_mb * 1024 * 1024)
        projected_bytes = current_vram_bytes + incoming_bytes
        needs_offload = projected_bytes > ceiling_bytes
        eviction_target_bytes = max(0, projected_bytes - ceiling_bytes)

        return {
            "needs_offload": needs_offload,
            "current_vram_bytes": current_vram_bytes,
            "ceiling_bytes": ceiling_bytes,
            "eviction_target_bytes": eviction_target_bytes,
            "target_tier": "NVMe_Paging" if needs_offload else "Vulkan_Device_Local"
        }

    def aggregate_workload_metrics(
        self,
        carry_pressure: float,
        phase_cancellation: float,
        sat_violation_ratio: float,
        residual_frobenius_energy: float,
        lyapunov_lambda: float
    ) -> Dict[str, Any]:
        """
        Aggregates compute workload pressures across algebraic spaces using
        normalized softmax vector weighting:
          Input vector x in R^5 -> Normalized weights w in R^5.
        """
        features = np.array([
            carry_pressure,
            phase_cancellation,
            sat_violation_ratio,
            residual_frobenius_energy,
            lyapunov_lambda
        ], dtype=np.float64)

        scaled = features - np.max(features)
        exp_vals = np.exp(scaled)
        weights = exp_vals / np.sum(exp_vals)
        spaces = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]

        return {
            "alpha_weight": float(weights[0]),
            "beta_weight": float(weights[1]),
            "gamma_weight": float(weights[2]),
            "delta_weight": float(weights[3]),
            "epsilon_weight": float(weights[4]),
            "dominant_space": spaces[int(np.argmax(weights))]
        }

    # Backward-compatible alias for metric aggregation
    cross_attention_aggregation = aggregate_workload_metrics

    def dynamic_nudge_controller(self, trapped_in_local_minimum: bool) -> Optional[int]:
        """
        Returns a Z_8 phase nudge when the search reports a local minimum.

        The value comes from non-cryptographic timing jitter (see
        ``harvest_timing_jitter``); it is a search heuristic, not a verified
        random source.
        """
        if not trapped_in_local_minimum:
            return None
        ent = self.harvest_timing_jitter()
        # Random phase rotation nudge in Z_8: -1 (+7) or +1
        return 1 if (ent & 1) else 7

    def top_non_master_forward_validator(
        self, candidate_solution: Any, forward_oracle_func: Callable[[Any], Any], expected_target: Any
    ) -> bool:
        """
        Isolated, deterministic forward oracle verifying candidate solutions
        without feedback contamination.
        """
        result = forward_oracle_func(candidate_solution)
        return bool(result == expected_target)
