"""
Test Suite: Continuous 100k-Iteration Stress & Memory Leak Harness
Enforces:
  1. Active VRAM strictly < 120 MB across 100,000 cycles.
  2. 0 uncontrolled memory leaks in host RAM.
  3. Lyapunov growth guardian and 3-number compression under explosive perturbations.
"""

import unittest
import time
import math
import numpy as np
try:
    import psutil
except ImportError:
    psutil = None

from python_bridge.cq_hecs import (
    MPS300QubitSimulator,
    TieredMemoryGovernor,
    JSpaceAlpha,
    JSpaceEpsilon,
    GlobalWorkspaceMetaLayer
)


class TestLongRunningStress(unittest.TestCase):
    def test_continuous_100k_solver_cycles(self):
        """Execute 100,000 continuous solver cycles and assert VRAM < 120 MB with 0 leaks."""
        process = psutil.Process() if psutil else None
        ram_initial = (process.memory_info().rss / (1024 * 1024)) if process else 0

        governor = TieredMemoryGovernor(max_vram_mb=120.0)
        mps = MPS300QubitSimulator(num_qubits=300, max_chi=64, governor=governor)
        alpha = JSpaceAlpha(bit_width=64)
        gwt = GlobalWorkspaceMetaLayer()

        total_iterations = 100000
        check_step = 10000
        vram_readings = []

        for i in range(1, total_iterations + 1):
            # 1. Gate application on MPS site
            site = i % 300
            mps.apply_single_qubit_z8_gate(site, phase_shift=(i % 7) + 1)

            # 2. Fast ARX carry split & reconstruct
            sx = i ^ 0xDEADBEEFCAFEBABE
            cs = (i & 0x55AA55AA33CC33CC) << 1
            _ = (sx + cs) & 0xFFFFFFFFFFFFFFFF

            # Periodic memory check
            if i % check_step == 0:
                vram_mb = governor.active_vram_bytes / (1024.0 * 1024.0)
                vram_readings.append(vram_mb)
                # Hard contract enforcement: MUST remain < 120 MB
                self.assertLess(vram_mb, 120.0, f"VRAM budget exceeded at iteration {i}: {vram_mb} MB")

        if process:
            ram_final = process.memory_info().rss / (1024 * 1024)
            ram_delta = ram_final - ram_initial
            self.assertLess(ram_delta, 50.0, f"Host memory leak detected: {ram_delta:.2f} MB growth")

        # Assertions
        self.assertEqual(len(vram_readings), 10)
        # All readings must be under 120 MB
        for v in vram_readings:
            self.assertLess(v, 120.0)

        # Host RAM growth must remain bounded (< 50 MB over 100k iterations)
        self.assertLess(ram_delta, 50.0, f"Memory leak detected: host RAM grew by {ram_delta:.2f} MB")

    def test_lyapunov_explosion_shield_under_stress(self):
        """Force artificial exponential explosion and verify Lyapunov guardian detection."""
        eps = JSpaceEpsilon(lyapunov_threshold=2.5)

        # Stable perturbation: linear growth
        stable_lambda, is_unstable_1 = eps.evaluate_lyapunov_stability(
            initial_perturbation=1.0,
            current_perturbation=2.0,
            step=10
        )
        self.assertFalse(is_unstable_1)
        self.assertLess(stable_lambda, 2.5)

        # Artificial explosive perturbation: exponential divergence 10^12 in 5 steps
        divergent_lambda, is_unstable_2 = eps.evaluate_lyapunov_stability(
            initial_perturbation=1.0,
            current_perturbation=1e12,
            step=5
        )
        self.assertTrue(is_unstable_2, "Lyapunov shield must trigger on exponential divergence!")
        self.assertGreater(divergent_lambda, 2.5)

    def test_3_number_compression_under_explosive_scale(self):
        """Stress-test 3-number lossless compression on extreme scale int64 arrays."""
        eps = JSpaceEpsilon()
        rng = np.random.default_rng(2026)

        for _ in range(5):
            # Generate wide dynamic range integers near 64-bit bounds
            data = rng.integers(-4_000_000_000_000, 4_000_000_000_000, size=8192, dtype=np.int64)
            seed = int(rng.integers(0, 0x7FFFFFFFFFFFFFFF))

            s, delta, exp = eps.compress_3_number(data, header_seed=seed, scaling_exponent=4)
            reconstructed = eps.decompress_3_number(s, delta, exp)

            # Assert 100% bit identity (0 bit loss)
            self.assertTrue(np.array_equal(data, reconstructed))
            self.assertEqual(int(np.count_nonzero(data != reconstructed)), 0)


if __name__ == "__main__":
    unittest.main()
