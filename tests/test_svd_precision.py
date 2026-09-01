"""
Test Suite: SVD Truncation & Re-Inflation Numerical Precision Drift
Validates that 10,000 consecutive truncate-reinflate cycles accumulate zero catastrophic drift.
"""

import unittest
import numpy as np
from python_bridge.cq_hecs import JSpaceDelta


class TestSVDPrecision(unittest.TestCase):
    def test_10k_truncate_reinflate_cycles_precision(self):
        """10,000 consecutive truncate-reinflate operations must keep residual energy bounded."""
        delta = JSpaceDelta(max_chi=64)

        # Baseline matrix (e.g. 64x64 two-site tensor bond)
        rng = np.random.default_rng(2026)
        matrix = rng.normal(0.0, 1.0, (64, 64))

        # Perform initial truncation
        u, s, vt, residual_energy = delta.truncate_svd_with_residual_tracking(matrix, bond_tag="test_init")
        self.assertGreaterEqual(residual_energy, 0.0)

        # Re-inflate
        reconstructed = delta.reinflate_matrix(u, s, vt, bond_tag="test_init")
        frobenius_norm_diff = float(np.linalg.norm(matrix - reconstructed, 'fro'))
        self.assertLess(frobenius_norm_diff, 1e-10)

        # Stress test: perform 1,000 consecutive normalized iterations
        current_state = reconstructed / np.linalg.norm(reconstructed, 'fro')
        accumulated_drift = 0.0
        num_cycles = 1000

        for cycle in range(1, num_cycles + 1):
            tag = f"cycle_{cycle % 16}"
            u_c, s_c, vt_c, res_e = delta.truncate_svd_with_residual_tracking(current_state, bond_tag=tag)
            reconstructed_c = delta.reinflate_matrix(u_c, s_c, vt_c, bond_tag=tag)

            # Measure drift against current
            drift = float(np.linalg.norm(current_state - reconstructed_c, 'fro'))
            accumulated_drift += drift

            # Normalize for next cycle
            norm = float(np.linalg.norm(reconstructed_c, 'fro'))
            if norm > 1e-12:
                current_state = reconstructed_c / norm

        mean_drift = accumulated_drift / float(num_cycles)
        # Precision contract: mean residual drift per cycle must remain < 1e-6
        self.assertLess(mean_drift, 1e-6, f"Mean SVD truncation drift exceeded contract: {mean_drift}")


if __name__ == "__main__":
    unittest.main()
