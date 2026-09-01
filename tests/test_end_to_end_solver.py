"""
Test Suite: End-to-End Cryptographic ARX Inversion Solver with Isolated Validator
Simulates crypto inversion on reduced ARX rounds using the 5 J-Spaces and Vulkan Workload Scheduler.
"""

import unittest
import random
from python_bridge.cq_hecs import (
    VulkanComputeScheduler,
    JSpaceAlpha,
    JSpaceGamma,
    JSpaceBeta,
    JSpaceEpsilon
)


class TestEndToEndSolver(unittest.TestCase):
    def setUp(self):
        self.scheduler = VulkanComputeScheduler()
        self.alpha = JSpaceAlpha(bit_width=64)
        self.gamma = JSpaceGamma(table_capacity=2048)
        self.beta = JSpaceBeta()
        self.epsilon = JSpaceEpsilon()

    def test_single_round_arx_inversion(self):
        """Test inversion of single ARX modular addition step with random keys."""
        rng = random.Random(42)
        for _ in range(20):
            secret_preimage = rng.getrandbits(64)
            fixed_salt = rng.getrandbits(64)

            # Forward ARX hash oracle
            def forward_oracle(x: int) -> int:
                return (x + fixed_salt) & 0xFFFFFFFFFFFFFFFF

            target_digest = forward_oracle(secret_preimage)

            # Invert using J-Space Alpha carry reversal
            candidate = self.alpha.reverse_arx_step(target_digest, fixed_salt)

            # Register with Gamma Cuckoo Table to ensure loop-free solution
            is_new = self.gamma.check_and_insert_cuckoo(candidate)
            self.assertTrue(is_new, "Duplicate state detected in fresh run!")

            # Validate through Top Non-Master Isolated Validator
            is_valid = self.scheduler.top_non_master_forward_validator(
                candidate_solution=candidate,
                forward_oracle_func=forward_oracle,
                expected_target=target_digest
            )

            self.assertTrue(is_valid)
            self.assertEqual(candidate, secret_preimage)

    def test_multi_round_quarter_round_arx_inversion(self):
        """Test multi-round ARX quarter round inversion."""
        rng = random.Random(777)
        for _ in range(10):
            orig_a = rng.getrandbits(64)
            orig_b = rng.getrandbits(64)
            orig_c = rng.getrandbits(64)
            orig_d = rng.getrandbits(64)

            # Forward 2-round ARX transformation
            fa1, fb1, fc1, fd1 = self.alpha.quarter_round_forward(orig_a, orig_b, orig_c, orig_d)
            fa2, fb2, fc2, fd2 = self.alpha.quarter_round_forward(fa1, fb1, fc1, fd1)

            # Inversion using backward steps with carry protection
            ba1, bb1, bc1, bd1 = self.alpha.quarter_round_backward(fa2, fb2, fc2, fd2)
            ba0, bb0, bc0, bd0 = self.alpha.quarter_round_backward(ba1, bb1, bc1, bd1)

            self.assertEqual((ba0, bb0, bc0, bd0), (orig_a, orig_b, orig_c, orig_d))

            # Isolated Non-Master Validator check
            def forward_2round(quad: tuple) -> tuple:
                a, b, c, d = self.alpha.quarter_round_forward(*quad)
                return self.alpha.quarter_round_forward(a, b, c, d)

            is_valid = self.scheduler.top_non_master_forward_validator(
                candidate_solution=(ba0, bb0, bc0, bd0),
                forward_oracle_func=forward_2round,
                expected_target=(fa2, fb2, fc2, fd2)
            )
            self.assertTrue(is_valid)

    def test_scheduler_workload_aggregation_and_nudge_during_search(self):
        """Simulate Vulkan scheduler heuristic switching and entropy nudge during search."""
        # Case 1: High carry pressure
        attn = self.scheduler.aggregate_workload_metrics(
            carry_pressure=0.9,
            phase_cancellation=0.2,
            sat_violation_ratio=0.1,
            residual_frobenius_energy=0.05,
            lyapunov_lambda=0.1
        )
        self.assertEqual(attn["dominant_space"], "Alpha")

        # Case 2: Trapped in local minimum -> Dynamic nudge
        nudge = self.scheduler.dynamic_nudge_controller(trapped_in_local_minimum=True)
        self.assertIn(nudge, (1, 7))

        # Case 3: Not trapped -> No nudge
        no_nudge = self.scheduler.dynamic_nudge_controller(trapped_in_local_minimum=False)
        self.assertIsNone(no_nudge)


if __name__ == "__main__":
    unittest.main()
