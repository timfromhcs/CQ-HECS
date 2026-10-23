"""
Contract tests for ``cqhecs.scheduler``.

The module plans Vulkan work; it does not own a device or queue. These tests
pin the honesty contracts that a previous version violated:

* ``submit_workload`` must not report ``completed=True`` for metadata that was
  never dispatched.
* Completion requires a real backend identifier.
* Dispatch arithmetic must be exact and reject impossible inputs.
* Timing jitter is not advertised as cryptographic entropy.
"""

import unittest

from cqhecs.scheduler import DispatchDimensions, VulkanComputeScheduler


class TestSubmissionSemantics(unittest.TestCase):
    def test_submission_is_not_completed_without_dispatch(self):
        scheduler = VulkanComputeScheduler()
        dispatch = scheduler.calculate_optimal_dispatch(1024)
        submission = scheduler.submit_workload("mps_contract", dispatch, barriers_before=2)

        self.assertFalse(submission.completed)
        self.assertTrue(submission.planner_only)
        self.assertEqual(submission.execution_backend, "planner_only")
        self.assertEqual(submission.dispatch.total_workgroups(), 64)

    def test_completion_requires_real_backend(self):
        scheduler = VulkanComputeScheduler()
        submission = scheduler.submit_workload(
            "mps_contract", scheduler.calculate_optimal_dispatch(16)
        )

        for invalid_backend in ("", "planner_only", None):
            with self.subTest(backend=invalid_backend):
                with self.assertRaises(ValueError):
                    scheduler.record_completion(submission, invalid_backend)
                self.assertFalse(submission.completed)

        scheduler.record_completion(submission, "native_vulkan_queue")
        self.assertTrue(submission.completed)
        self.assertFalse(submission.planner_only)
        self.assertEqual(submission.execution_backend, "native_vulkan_queue")


class TestDispatchArithmetic(unittest.TestCase):
    def test_rounds_up_and_never_returns_zero_groups(self):
        scheduler = VulkanComputeScheduler(local_workgroup_size=(16, 8, 4))
        dispatch = scheduler.calculate_optimal_dispatch(1, 1, 1)
        self.assertEqual(
            (dispatch.group_count_x, dispatch.group_count_y, dispatch.group_count_z),
            (1, 1, 1),
        )

        dispatch = scheduler.calculate_optimal_dispatch(17, 16, 9)
        self.assertEqual(
            (dispatch.group_count_x, dispatch.group_count_y, dispatch.group_count_z),
            (2, 2, 3),
        )

    def test_negative_elements_are_rejected(self):
        scheduler = VulkanComputeScheduler()
        with self.assertRaises(ValueError):
            scheduler.calculate_optimal_dispatch(-1)

    def test_total_workgroups_multiplication(self):
        dims = DispatchDimensions(3, 4, 5)
        self.assertEqual(dims.total_workgroups(), 60)


class TestOffloadPolicy(unittest.TestCase):
    def test_offload_only_above_ceiling(self):
        scheduler = VulkanComputeScheduler(vram_ceiling_mb=1.0)
        ceiling = 1024 * 1024

        below = scheduler.schedule_offload(ceiling - 1, 0)
        self.assertFalse(below["needs_offload"])
        self.assertEqual(below["eviction_target_bytes"], 0)

        above = scheduler.schedule_offload(ceiling, 1024)
        self.assertTrue(above["needs_offload"])
        self.assertEqual(above["target_tier"], "NVMe_Paging")
        self.assertEqual(above["eviction_target_bytes"], 1024)


class TestTimingJitterContract(unittest.TestCase):
    def test_alias_and_primary_are_both_non_cryptographic_integers(self):
        scheduler = VulkanComputeScheduler(entropy_seed=12345)
        primary = scheduler.harvest_timing_jitter()
        alias = scheduler.harvest_hardware_entropy()
        for value in (primary, alias):
            self.assertIsInstance(value, int)
            self.assertGreaterEqual(value, 0)
            self.assertLess(value, 1 << 64)

    def test_values_are_64_bit(self):
        scheduler = VulkanComputeScheduler()
        value = scheduler.harvest_timing_jitter()
        self.assertGreaterEqual(value, 0)
        self.assertLess(value, 1 << 64)


if __name__ == "__main__":
    unittest.main()
