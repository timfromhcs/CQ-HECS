"""
SVD truncation diagnostics for ``JSpaceDelta``.

What is actually asserted
-------------------------
* ``lambda_res`` equals the Frobenius norm of the discarded singular components
  (within float64 roundoff). It is a *diagnostic* quantity, not a certified
  simulation error bound.
* Re-inflation is exact for the same tensor because the residual is cached; this
  is not a compression claim.
* Truncated factors reconstruct the input up to the reported residual; full-rank
  factors reconstruct it up to float64 roundoff.
* Complex, ill-conditioned, rank-deficient and near-zero matrices stay finite.

The previous version of this file claimed "10,000 cycles, zero drift" while
running 1,000 iterations with ``max_chi == matrix rank`` (i.e. no truncation at
all). The tests below measure the quantity they name.
"""

import unittest

import numpy as np

from python_bridge.cq_hecs import JSpaceDelta


def frobenius_difference(a, b):
    return float(np.linalg.norm(a - b, "fro"))


class TestSVDTruncationDiagnostics(unittest.TestCase):
    def test_no_truncation_reconstructs_at_roundoff(self):
        """max_chi == rank: lambda_res is exactly 0 and error is float64 noise."""
        delta = JSpaceDelta(max_chi=64)
        rng = np.random.default_rng(2026)
        matrix = rng.normal(0.0, 1.0, (64, 64))

        u, s, vt, residual = delta.truncate_svd_with_residual_tracking(
            matrix, bond_tag="full_rank"
        )
        self.assertEqual(residual, 0.0)
        reconstructed = delta.reinflate_matrix(u, s, vt, bond_tag="full_rank")
        self.assertLess(frobenius_difference(matrix, reconstructed), 1e-10)

    def test_truncated_residual_matches_discarded_frobenius_energy(self):
        """lambda_res must describe exactly the discarded spectral mass."""
        delta = JSpaceDelta(max_chi=8)
        rng = np.random.default_rng(7)
        matrix = rng.normal(size=(32, 32)) + 1j * rng.normal(size=(32, 32))

        u, s, vt, residual = delta.truncate_svd_with_residual_tracking(
            matrix, bond_tag="truncated"
        )
        self.assertGreater(residual, 0.0)
        self.assertEqual(u.shape[1], 8)

        truncated = (u * s) @ vt
        measured_discard = frobenius_difference(matrix, truncated)
        self.assertAlmostEqual(residual, measured_discard, delta=1e-10)

        # Cached re-inflation restores the original tensor exactly.
        restored = delta.reinflate_matrix(u, s, vt, bond_tag="truncated")
        self.assertLess(frobenius_difference(matrix, restored), 1e-10)

    def test_ill_conditioned_and_degenerate_spectra_stay_finite(self):
        """Extreme singular-value ratios and rank deficiency must not produce NaN."""
        delta = JSpaceDelta(max_chi=2)
        cases = {
            "ill_conditioned": np.diag([1e8, 1e-8, 0.0, 0.0]).astype(np.complex128),
            "rank_deficient": np.diag([1.0, 0.0, 0.0, 0.0]).astype(np.complex128),
            "near_zero": np.full((4, 4), 1e-300, dtype=np.complex128),
        }
        for name, matrix in cases.items():
            with self.subTest(case=name):
                u, s, vt, residual = delta.truncate_svd_with_residual_tracking(
                    matrix, bond_tag=name
                )
                self.assertTrue(np.all(np.isfinite(s)))
                self.assertTrue(np.isfinite(residual))
                self.assertGreaterEqual(residual, 0.0)
                restored = delta.reinflate_matrix(u, s, vt, bond_tag=name)
                self.assertLess(frobenius_difference(matrix, restored), 1e-10)

    def test_1000_reinflation_cycles_keep_per_cycle_error_bounded(self):
        """1,000 cycles: measure the per-cycle reconstruction error honestly."""
        delta = JSpaceDelta(max_chi=64)
        rng = np.random.default_rng(2026)
        current = rng.normal(size=(32, 32)).astype(np.complex128)

        max_cycle_error = 0.0
        for cycle in range(1_000):
            tag = f"cycle_{cycle}"  # unique tag: residual belongs to this tensor
            u, s, vt, residual = delta.truncate_svd_with_residual_tracking(
                current, bond_tag=tag
            )
            restored = delta.reinflate_matrix(u, s, vt, bond_tag=tag)
            error = frobenius_difference(current, restored)
            max_cycle_error = max(max_cycle_error, error)
            norm = float(np.linalg.norm(restored, "fro"))
            self.assertGreater(norm, 0.0)
            current = restored / norm

        # Cached re-inflation is exact up to float64 roundoff; this is not a
        # claim of zero error in a production MPS pipeline.
        self.assertLess(max_cycle_error, 1e-10)

    def test_mismatched_residual_cache_is_rejected(self):
        """Reusing a tag with incompatible factors must fail closed."""
        delta = JSpaceDelta(max_chi=2)
        rng = np.random.default_rng(11)
        small = rng.normal(size=(8, 8))
        delta.truncate_svd_with_residual_tracking(small, bond_tag="shared")

        other = np.eye(5, dtype=np.complex128)
        u, s, vt, _ = JSpaceDelta(max_chi=4).truncate_svd_with_residual_tracking(
            other, bond_tag="other"
        )
        with self.assertRaises(ValueError):
            delta.reinflate_matrix(u, s, vt, bond_tag="shared")


if __name__ == "__main__":
    unittest.main()
