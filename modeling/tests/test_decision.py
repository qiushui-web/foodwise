import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foodwise_ml import decision as d  # noqa: E402


class CostModelTests(unittest.TestCase):
    def test_underage_overage_and_ratio(self):
        cost = d.CostModel(price=14.0, unit_cost=5.6, discount_price=7.0, salvage_probability=0.6)
        self.assertAlmostEqual(cost.underage, 8.4 * 1.3)
        self.assertAlmostEqual(cost.overage, 5.6 - 7.0 * 0.6)
        self.assertAlmostEqual(cost.critical_ratio, 10.92 / (10.92 + 1.4))

    def test_ratio_is_clamped_when_overage_vanishes(self):
        cost = d.CostModel(price=10.0, unit_cost=4.0, discount_price=4.0, salvage_probability=1.0)
        self.assertGreaterEqual(cost.critical_ratio, 0.99)
        self.assertLessEqual(cost.critical_ratio, 0.999)

    def test_profit_accounting(self):
        cost = d.CostModel(price=10.0, unit_cost=4.0, discount_price=5.0, salvage_probability=0.5)
        # 备 100、卖 80：80*10 + 20*5*0.5 − 100*4 = 800 + 50 − 400
        self.assertAlmostEqual(cost.profit(100, 80), 450.0)
        # 备 80、需求 100：80*10 − 80*4 = 480
        self.assertAlmostEqual(cost.profit(80, 100), 480.0)

    def test_rejects_invalid_cost_shape(self):
        with self.assertRaisesRegex(ValueError, "UNIT_COST_OUT_OF_RANGE"):
            d.CostModel(price=10.0, unit_cost=12.0, discount_price=5.0)
        with self.assertRaisesRegex(ValueError, "DISCOUNT_PRICE_OUT_OF_RANGE"):
            d.CostModel(price=10.0, unit_cost=4.0, discount_price=12.0)


class IntervalToDecisionTests(unittest.TestCase):
    def test_sigma_recovers_known_sigma(self):
        sigma = 12.0
        half = 1.6448536269514722 * sigma
        self.assertAlmostEqual(d.sigma_from_interval(100 - half, 100 + half), sigma, places=6)

    def test_newsvendor_at_median_equals_center(self):
        self.assertAlmostEqual(d.newsvendor_quantile(100.0, 10.0, 0.5), 100.0)

    def test_newsvendor_monotone_in_ratio(self):
        low = d.newsvendor_quantile(100.0, 10.0, 0.6)
        high = d.newsvendor_quantile(100.0, 10.0, 0.9)
        self.assertLess(low, high)

    def test_batch_rounds_up_and_caps(self):
        self.assertEqual(d.apply_batch(143.2, 5), 145)
        self.assertEqual(d.apply_batch(143.2, 5, capacity=140), 140)
        self.assertEqual(d.apply_batch(0.0, 5), 0)

    def test_batch_rejects_zero_step(self):
        with self.assertRaisesRegex(ValueError, "MINIMUM_BATCH_NOT_POSITIVE"):
            d.apply_batch(10, 0)


class EvaluateTests(unittest.TestCase):
    def test_perfect_foresight_has_zero_regret(self):
        cost = d.CostModel(price=10.0, unit_cost=4.0, discount_price=5.0)
        demand = [50.0, 60.0, 70.0]
        result = d.evaluate_decisions(cost, demand, demand)
        self.assertAlmostEqual(result["regret"], 0.0)
        self.assertAlmostEqual(result["stockout_rate"], 0.0)
        self.assertAlmostEqual(result["leftover_rate"], 0.0)

    def test_under_preparation_costs_less_than_over_preparation_when_margin_high(self):
        cost = d.CostModel(price=10.0, unit_cost=4.0, discount_price=5.0, salvage_probability=0.9)
        demand = [100.0] * 10
        under = d.evaluate_decisions(cost, [80.0] * 10, demand)
        over = d.evaluate_decisions(cost, [120.0] * 10, demand)
        self.assertLess(under["profit"], over["profit"])

    def test_rejects_length_mismatch(self):
        cost = d.CostModel(price=10.0, unit_cost=4.0, discount_price=5.0)
        with self.assertRaisesRegex(ValueError, "LENGTH_MISMATCH"):
            d.evaluate_decisions(cost, [1.0], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()