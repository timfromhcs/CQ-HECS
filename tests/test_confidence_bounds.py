"""Independent re-derivation checks for the sampling bounds (H8)."""

import math
import unittest

from cqhecs.result import hoeffding_proportion_bound, hoeffding_total_variation_bound


class TestTotalVariationBound(unittest.TestCase):
    def test_binary_case_is_the_classical_hoeffding_expression(self):
        for shots in (1, 10, 1000, 10**6):
            for delta in (0.5, 0.05, 1e-6):
                expected = min(1.0, math.sqrt(math.log(2.0 / delta) / (2.0 * shots)))
                self.assertAlmostEqual(
                    hoeffding_total_variation_bound(shots, support_size=2, delta=delta),
                    expected, places=14,
                )

    def test_matches_weissman_with_phi_equal_two_and_is_conservative(self):
        # eps_TV = sqrt(ln((2^K - 2)/delta) / (2n)); the implementation may only
        # exceed it (K*ln2 >= ln(2^K - 2)), never undercut it.
        for k in range(3, 40):
            for shots in (50, 5000):
                delta = 0.05
                exact = math.sqrt(math.log((2.0 ** k - 2.0) / delta) / (2.0 * shots))
                got = hoeffding_total_variation_bound(shots, support_size=k, delta=delta)
                with self.subTest(k=k, shots=shots):
                    self.assertGreaterEqual(got + 1e-15, min(1.0, exact))
                    self.assertLessEqual(got, 1.0)

    def test_monotone_in_shots_support_and_confidence(self):
        base = hoeffding_total_variation_bound(1000, support_size=8, delta=0.05)
        self.assertLess(hoeffding_total_variation_bound(4000, support_size=8, delta=0.05), base)
        self.assertGreater(hoeffding_total_variation_bound(1000, support_size=16, delta=0.05), base)
        self.assertGreater(hoeffding_total_variation_bound(1000, support_size=8, delta=0.001), base)

    def test_degenerate_and_huge_supports(self):
        self.assertEqual(hoeffding_total_variation_bound(10, support_size=1), 0.0)
        self.assertEqual(hoeffding_total_variation_bound(10, support_size=1 << 80), 1.0)
        self.assertEqual(hoeffding_total_variation_bound(10, support_size=1 << 4000), 1.0)

    def test_invalid_arguments(self):
        for kwargs in (
            {"shots": 0}, {"shots": -3}, {"shots": 10, "support_size": 0},
            {"shots": 10, "delta": 0.0}, {"shots": 10, "delta": 1.0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    hoeffding_total_variation_bound(**kwargs)


class TestProportionBound(unittest.TestCase):
    def test_is_simultaneous_over_the_support(self):
        # delta is split across K outcomes: ln(2K/delta).
        got = hoeffding_proportion_bound(1000, delta=0.05, support_size=8)
        self.assertAlmostEqual(got, math.sqrt(math.log(2 * 8 / 0.05) / 2000), places=14)

    def test_default_support_matches_single_binary_outcome(self):
        got = hoeffding_proportion_bound(400, delta=0.05)
        self.assertAlmostEqual(got, math.sqrt(math.log(2 * 2 / 0.05) / 800), places=14)

    def test_invalid_arguments(self):
        for kwargs in ({"shots": 0}, {"shots": 5, "delta": 2.0}, {"shots": 5, "support_size": 0}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    hoeffding_proportion_bound(**kwargs)


if __name__ == "__main__":
    unittest.main()
