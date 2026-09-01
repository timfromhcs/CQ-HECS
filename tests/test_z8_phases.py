"""
Test Suite: J-Space Beta (Exact Z_8 Phase Ring, Clifford+T, Destructive Interference, Anti-Math)
"""

import unittest
import math
from python_bridge.cq_hecs import JSpaceBeta


class TestZ8Phases(unittest.TestCase):
    def setUp(self):
        self.beta = JSpaceBeta()

    def test_z8_gate_shifts(self):
        """Verify Clifford + T phase shifts in Z_8 ring."""
        # Initial ground state has phase 0
        p0 = 0

        # T-gate: +1 mod 8
        p_t = self.beta.apply_t_gate(p0)
        self.assertEqual(p_t, 1)

        # S-gate: +2 mod 8
        p_s = self.beta.apply_s_gate(p0)
        self.assertEqual(p_s, 2)

        # Z-gate: +4 mod 8
        p_z = self.beta.apply_z_gate(p0)
        self.assertEqual(p_z, 4)

        # T^dagger: +7 mod 8 (-1 mod 8)
        p_tdag = self.beta.apply_t_dagger(p0)
        self.assertEqual(p_tdag, 7)

        # T^8 = Identity (0 mod 8)
        p_curr = p0
        for _ in range(8):
            p_curr = self.beta.apply_t_gate(p_curr)
        self.assertEqual(p_curr, 0)

    def test_anti_math_unitary_inversion(self):
        """Verify exact anti-math inversion (U† U = I) for any gate sequence."""
        import random
        random.seed(42)

        # Sequence of gate shifts
        gate_shifts = [random.randint(0, 7) for _ in range(100)]

        # Forward transformation
        curr_phase = 0
        for shift in gate_shifts:
            curr_phase = self.beta.phase_mult(curr_phase, shift)

        # Anti-Math Inversion: apply adjoints in reverse order
        for shift in reversed(gate_shifts):
            inv_shift = self.beta.anti_math_inverse(shift)
            curr_phase = self.beta.phase_mult(curr_phase, inv_shift)

        # Must return to exact identity 0
        self.assertEqual(curr_phase, 0)

    def test_destructive_interference(self):
        """Verify exact destructive interference cancellation (diff == 4 mod 8)."""
        # Equal magnitude 150.0, anti-phase: 1 (pi/4) and 5 (5pi/4)
        mag1, phase1 = 150.0, 1
        mag2, phase2 = 150.0, 5

        net_mag, resulting_phase, is_cancelled = self.beta.interfere_pair(mag1, phase1, mag2, phase2)
        self.assertTrue(is_cancelled)
        self.assertEqual(net_mag, 0.0)

        # Unequal magnitude: 200.0 vs 80.0
        mag1, phase1 = 200.0, 2
        mag2, phase2 = 80.0, 6
        net_mag, resulting_phase, is_cancelled = self.beta.interfere_pair(mag1, phase1, mag2, phase2)
        self.assertTrue(is_cancelled)
        self.assertAlmostEqual(net_mag, 120.0, places=5)
        self.assertEqual(resulting_phase, 2)

    def test_constructive_interference(self):
        """Verify exact constructive interference (diff == 0 mod 8)."""
        mag1, phase1 = 75.0, 3
        mag2, phase2 = 25.0, 3

        net_mag, resulting_phase, is_cancelled = self.beta.interfere_pair(mag1, phase1, mag2, phase2)
        self.assertFalse(is_cancelled)
        self.assertAlmostEqual(net_mag, 100.0, places=5)
        self.assertEqual(resulting_phase, 3)


if __name__ == "__main__":
    unittest.main()
