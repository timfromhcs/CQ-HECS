"""
Test Suite: J-Space Epsilon Lossless 3-Number Compression & Decompression
Verifies 100% bit identity and 0 bit loss across roundtrip tests.
"""

import unittest
import numpy as np
from python_bridge.cq_hecs import JSpaceEpsilon


class TestCompressionLossless(unittest.TestCase):
    def setUp(self):
        self.epsilon = JSpaceEpsilon()

    def test_roundtrip_bit_identity_basic(self):
        """Test roundtrip bit identity on deterministic array."""
        original = np.array([0, 1, -1, 42, -1337, 2147483647, -2147483648], dtype=np.int64)
        seed = 0x1122334455667788
        exp = 0

        header_seed, delta, scaling_exp = self.epsilon.compress_3_number(
            original, header_seed=seed, scaling_exponent=exp
        )
        reconstructed = self.epsilon.decompress_3_number(header_seed, delta, scaling_exp)

        # Assert 100% bit identity
        self.assertTrue(np.array_equal(original, reconstructed))
        self.assertEqual(original.tobytes(), reconstructed.tobytes())
        self.assertEqual(int(np.count_nonzero(original != reconstructed)), 0)

    def test_roundtrip_large_random_tensors(self):
        """Test roundtrip bit identity across large random tensors with multiple exponents."""
        rng = np.random.default_rng(1337)

        for size in [128, 4096, 32768]:
            raw_data = rng.integers(-10_000_000, 10_000_000, size=size, dtype=np.int64)
            for exp in [-4, -1, 0, 2, 5]:
                seed = int(rng.integers(0, 0x7FFFFFFFFFFFFFFF))
                s, delta, e = self.epsilon.compress_3_number(raw_data, header_seed=seed, scaling_exponent=exp)
                recon = self.epsilon.decompress_3_number(s, delta, e)

                mismatches = int(np.count_nonzero(raw_data != recon))
                self.assertEqual(mismatches, 0, f"Failed at size={size}, exp={exp}")
                self.assertEqual(raw_data.tobytes(), recon.tobytes())

    def test_extreme_int64_boundaries(self):
        """Test roundtrip on extreme 64-bit integer values."""
        extreme_values = np.array([
            np.iinfo(np.int64).min,
            np.iinfo(np.int64).min + 1,
            -1,
            0,
            1,
            np.iinfo(np.int64).max - 1,
            np.iinfo(np.int64).max
        ], dtype=np.int64)

        s, delta, e = self.epsilon.compress_3_number(extreme_values, header_seed=0xabcdef0123456789, scaling_exponent=1)
        recon = self.epsilon.decompress_3_number(s, delta, e)

        self.assertTrue(np.array_equal(extreme_values, recon))
        self.assertEqual(extreme_values.tobytes(), recon.tobytes())
        self.assertEqual(int(np.count_nonzero(extreme_values != recon)), 0)

    def test_zero_bit_loss_contract(self):
        """Strict verification of 0 bit loss contract."""
        data = np.arange(1000, dtype=np.int64) * 31337
        s, delta, e = self.epsilon.compress_3_number(data, header_seed=0x5555aaaa5555aaaa, scaling_exponent=3)
        recon = self.epsilon.decompress_3_number(s, delta, e)

        # Compute XOR bit distance across all elements
        bit_diff_sum = int(np.sum(np.bitwise_xor(data, recon)))
        self.assertEqual(bit_diff_sum, 0, "Non-zero bit diff detected; contract violated!")


if __name__ == "__main__":
    unittest.main()
