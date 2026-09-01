"""
Test Suite: J-Space Alpha (ARX Linearization, Carry-Shadow Splitting & 64-Bit Overflow Protection)
"""

import unittest
import random
from python_bridge.cq_hecs import JSpaceAlpha


class TestCarryProtection(unittest.TestCase):
    def setUp(self):
        self.alpha = JSpaceAlpha(bit_width=64)

    def test_linearize_and_reconstruct(self):
        """Test carry splitting and exact modular sum reconstruction."""
        test_pairs = [
            (0, 0),
            (12345, 67890),
            (0xFFFFFFFFFFFFFFFF, 1),
            (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF),
            (0x8000000000000000, 0x8000000000000000),
            (0xDEADBEEFCAFEBABE, 0x1337133713371337)
        ]

        for a, b in test_pairs:
            sum_xor, carry_shadow = self.alpha.linearize_add(a, b)
            reconstructed = self.alpha.reconstruct_add(sum_xor, carry_shadow)
            expected = (a + b) & 0xFFFFFFFFFFFFFFFF
            self.assertEqual(reconstructed, expected, f"Failed on pair ({hex(a)}, {hex(b)})")

    def test_random_64bit_overflows(self):
        """Test 1,000 random 64-bit integer additions with overflows."""
        rng = random.Random(999)
        mask = 0xFFFFFFFFFFFFFFFF

        for _ in range(1000):
            a = rng.getrandbits(64)
            b = rng.getrandbits(64)

            sum_xor, carry_shadow = self.alpha.linearize_add(a, b)
            reconstructed = self.alpha.reconstruct_add(sum_xor, carry_shadow)
            expected = (a + b) & mask
            self.assertEqual(reconstructed, expected)

    def test_full_carry_chain_resolve(self):
        """Test iterative carry propagation until carry shadow resolves to 0."""
        a = 0xFFFFFFFFFFFFFFFF
        b = 1
        final_sum, carries = self.alpha.full_carry_chain_resolve(a, b)

        # Expected overflow wrap to 0
        self.assertEqual(final_sum, 0)
        # Final carry must be 0
        self.assertEqual(carries[-1], 0)
        # Propagation depth must be non-zero
        self.assertGreater(len(carries), 1)

    def test_reverse_arx_step(self):
        """Test exact reverse calculation of operands with 64-bit overflow wrap."""
        rng = random.Random(1234)
        for _ in range(500):
            a = rng.getrandbits(64)
            b = rng.getrandbits(64)
            target_sum = (a + b) & 0xFFFFFFFFFFFFFFFF

            recovered_b = self.alpha.reverse_arx_step(target_sum, a)
            self.assertEqual(recovered_b, b)

            recovered_a = self.alpha.reverse_arx_step(target_sum, b)
            self.assertEqual(recovered_a, a)

    def test_quarter_round_invertibility(self):
        """Test forward and inverse ARX quarter-round transform."""
        rng = random.Random(5678)
        for _ in range(100):
            a = rng.getrandbits(64)
            b = rng.getrandbits(64)
            c = rng.getrandbits(64)
            d = rng.getrandbits(64)

            fa, fb, fc, fd = self.alpha.quarter_round_forward(a, b, c, d)
            ba, bb, bc, bd = self.alpha.quarter_round_backward(fa, fb, fc, fd)

            self.assertEqual((a, b, c, d), (ba, bb, bc, bd))


if __name__ == "__main__":
    unittest.main()
