"""
Test Suite: Real-World ARX Cryptanalysis & Carry Shadow Pruning
Tests BLAKE2b G-function, ChaCha20 quarter-round, and SHA-256 schedule expansion.
"""

import unittest
from python_bridge.arx_cryptanalysis import ARXCryptanalysisSuite


class TestARXCryptanalysis(unittest.TestCase):
    def setUp(self):
        self.suite = ARXCryptanalysisSuite()

    def test_blake2b_g_invertibility(self):
        """Verify BLAKE2b G-function step-inversion and carry exactness."""
        result = self.suite.benchmark_blake2b(rounds=300)

        self.assertTrue(result.forward_verified)
        self.assertTrue(result.inverse_verified, "BLAKE2b inverse must recover exact state!")
        self.assertTrue(result.carry_shadow_exact, "Carry shadow must match modular addition exactly!")
        self.assertGreater(result.path_pruning_ratio, 1e12)
        self.assertGreater(result.num_rounds, 0)

    def test_chacha20_quarter_round_separation(self):
        """Verify ChaCha20 quarter-round carry separation and invertibility."""
        result = self.suite.benchmark_chacha20(rounds=300)

        self.assertTrue(result.forward_verified)
        self.assertTrue(result.inverse_verified, "ChaCha20 inverse must recover exact state!")
        self.assertTrue(result.carry_shadow_exact, "Carry shadow separation must be 100% exact!")
        self.assertGreater(result.path_pruning_ratio, 1e6)

    def test_sha256_schedule_multi_carry_inversion(self):
        """Verify SHA-256 message schedule expansion and multi-term carry inversion."""
        result = self.suite.benchmark_sha256(steps=300)

        self.assertTrue(result.forward_verified)
        self.assertTrue(result.inverse_verified, "SHA-256 schedule inverse must recover original W_{t-16}!")
        self.assertTrue(result.carry_shadow_exact, "Multi-term carry decomposition must be 100% exact!")
        self.assertGreater(result.path_pruning_ratio, 1e6)


if __name__ == "__main__":
    unittest.main()
