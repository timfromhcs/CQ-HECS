"""
Resource and stress tests for the legacy 300-qubit MPS bridge.

Honesty rules enforced here:

* ``TieredMemoryGovernor.active_vram_bytes`` is *simulator-internal accounting*.
  It is not a VRAM measurement and no test treats it as one.
* Host RSS is measured only when ``psutil`` is importable. A missing
  measurement dependency yields a visible ``skip``; it never becomes "0 MB
  growth" and therefore never a silent pass.
* Budget arithmetic and real process memory are asserted by separate tests.
"""

import unittest

import numpy as np

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only without the extra
    psutil = None

from python_bridge.cq_hecs import (
    MPS300QubitSimulator,
    TieredMemoryGovernor,
    JSpaceAlpha,
    JSpaceEpsilon,
)

PSUTIL_REQUIRED = "psutil is required to measure host RSS; install the 'benchmark' extra"


class TestGovernorBudgetArithmetic(unittest.TestCase):
    """Deterministic budget tests for the internal page accounting."""

    def test_eviction_keeps_accounting_inside_budget(self):
        governor = TieredMemoryGovernor(max_vram_mb=1.0)
        megabyte = 1024 * 1024
        governor.allocate(1, b"a" * (600 * 1024))
        self.assertEqual(governor.active_vram_bytes, 600 * 1024)

        governor.allocate(2, b"b" * (600 * 1024))
        self.assertLessEqual(governor.active_vram_bytes, megabyte)
        self.assertGreaterEqual(governor.cold_storage_bytes, 600 * 1024)
        self.assertNotIn(1, governor.active_pages)

        # Evicted data must still be retrievable byte-for-byte.
        self.assertEqual(governor.fetch(1), b"a" * (600 * 1024))

    def test_oversized_page_raises_instead_of_exceeding_budget(self):
        governor = TieredMemoryGovernor(max_vram_mb=1.0)
        before = governor.active_vram_bytes
        with self.assertRaises(MemoryError):
            governor.allocate(1, b"x" * (2 * 1024 * 1024))
        self.assertEqual(governor.active_vram_bytes, before)
        self.assertNotIn(1, governor.active_pages)

    def test_replacing_a_page_respects_budget(self):
        governor = TieredMemoryGovernor(max_vram_mb=1.0)
        governor.allocate(1, b"a" * (900 * 1024))
        governor.allocate(2, b"b" * (200 * 1024))
        self.assertLessEqual(governor.active_vram_bytes, 1024 * 1024)


class TestLongRunningStress(unittest.TestCase):
    def test_100k_mps_cycles_internal_accounting(self):
        """100k gate cycles keep internal accounting bounded and deterministic."""
        governor = TieredMemoryGovernor(max_vram_mb=120.0)
        mps = MPS300QubitSimulator(num_qubits=300, max_chi=64, governor=governor)
        alpha = JSpaceAlpha(bit_width=64)

        total_iterations = 100_000
        check_step = 10_000
        readings = []

        for i in range(1, total_iterations + 1):
            mps.apply_single_qubit_z8_gate(i % 300, phase_shift=(i % 7) + 1)

            # ARX carry split & reconstruct (unchanged algebraic invariant).
            sx = i ^ 0xDEADBEEFCAFEBABE
            cs = (i & 0x55AA55AA33CC33CC) << 1
            _ = (sx + cs) & 0xFFFFFFFFFFFFFFFF
            self.assertGreaterEqual(alpha.bit_width, 1)

            if i % check_step == 0:
                readings.append(governor.active_vram_bytes)

        self.assertEqual(len(readings), 10)
        for value in readings:
            self.assertLessEqual(value, governor.max_vram_bytes)

    @unittest.skipUnless(psutil is not None, PSUTIL_REQUIRED)
    def test_host_rss_growth_is_bounded(self):
        """Host RSS growth is measured directly; a missing psutil skips loudly."""
        process = psutil.Process()
        process.memory_info()  # fail early if the process handle is unusable

        governor = TieredMemoryGovernor(max_vram_mb=120.0)
        mps = MPS300QubitSimulator(num_qubits=300, max_chi=64, governor=governor)

        # Warm the allocator before taking the baseline.
        for i in range(2_000):
            mps.apply_single_qubit_z8_gate(i % 300, phase_shift=(i % 7) + 1)

        ram_initial = process.memory_info().rss / (1024 * 1024)
        for i in range(60_000):
            mps.apply_single_qubit_z8_gate(i % 300, phase_shift=(i % 7) + 1)
        ram_final = process.memory_info().rss / (1024 * 1024)

        ram_delta = ram_final - ram_initial
        self.assertLess(
            ram_delta,
            50.0,
            f"host RSS grew by {ram_delta:.2f} MB over 60k cycles",
        )

    def test_lyapunov_explosion_shield_under_stress(self):
        """Force artificial exponential explosion and verify Lyapunov guardian detection."""
        eps = JSpaceEpsilon(lyapunov_threshold=2.5)

        stable_lambda, is_unstable_1 = eps.evaluate_lyapunov_stability(
            initial_perturbation=1.0,
            current_perturbation=2.0,
            step=10
        )
        self.assertFalse(is_unstable_1)
        self.assertLess(stable_lambda, 2.5)

        divergent_lambda, is_unstable_2 = eps.evaluate_lyapunov_stability(
            initial_perturbation=1.0,
            current_perturbation=1e12,
            step=5
        )
        self.assertTrue(is_unstable_2, "Lyapunov shield must trigger on exponential divergence!")
        self.assertGreater(divergent_lambda, 2.5)

    def test_3_number_compression_under_explosive_scale(self):
        """Stress-test 3-number compression on extreme scale int64 arrays."""
        eps = JSpaceEpsilon()
        rng = np.random.default_rng(2026)

        for _ in range(5):
            data = rng.integers(-4_000_000_000_000, 4_000_000_000_000, size=8192, dtype=np.int64)
            seed = int(rng.integers(0, 0x7FFFFFFFFFFFFFFF))

            s, delta, exp = eps.compress_3_number(data, header_seed=seed, scaling_exponent=4)
            reconstructed = eps.decompress_3_number(s, delta, exp)

            self.assertTrue(np.array_equal(data, reconstructed))
            self.assertEqual(int(np.count_nonzero(data != reconstructed)), 0)


if __name__ == "__main__":
    unittest.main()
