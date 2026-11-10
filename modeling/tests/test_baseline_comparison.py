"""14 天对照的结论必须能被复核：这条断言锁住"复杂模型在小样本上不占优"这个事实。"""

import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "modeling" / "data" / "03_output" / "baseline_vs_gbdt_14d.json"


class BaselineComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RESULT.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/44_baseline_vs_gbdt.py")
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.metrics = cls.result["metrics"]

    def test_evaluates_the_whole_ledger_tail(self):
        self.assertEqual(self.result["rows_evaluated"], 77)
        self.assertEqual(self.result["days_evaluated"], 11)
        self.assertEqual(self.result["min_train_days"], 3)

    def test_all_methods_present(self):
        for method in ("median_roll7", "mean_roll7", "median_same_dow",
                       "yesterday", "rule_10pct", "gbdt", "actual"):
            self.assertIn(method, self.metrics)

    def test_numbers_are_finite(self):
        for method, values in self.metrics.items():
            for key, value in values.items():
                self.assertTrue(math.isfinite(value), f"{method}.{key} = {value}")

    def test_rolling_median_beats_gbdt(self):
        """小样本下 7 日中位数应当优于 24 维 GBDT；不成立说明结论或数据有问题。"""
        self.assertLess(
            self.metrics["median_roll7"]["regret_per_100"],
            self.metrics["gbdt"]["regret_per_100"])
        self.assertLess(
            self.metrics["median_roll7"]["mae"],
            self.metrics["gbdt"]["mae"])

    def test_gbdt_is_no_better_than_naive(self):
        """GBDT 在 77 行上不应显著优于"昨天"朴素基线。"""
        self.assertLessEqual(
            abs(self.metrics["gbdt"]["regret_per_100"] - self.metrics["yesterday"]["regret_per_100"]),
            5.0)

    def test_critical_ratios_are_valid(self):
        for dish_id, ratio in self.result["critical_ratio_by_dish"].items():
            self.assertGreater(ratio, 0.0, f"dish {dish_id}")
            self.assertLessEqual(ratio, 1.0, f"dish {dish_id}")

    def test_residual_sigma_trades_stockouts_for_leftovers(self):
        """残差尺度压低了缺货率，却抬高了整体 regret——这个权衡必须被记录，不能被当成改进。"""
        base = self.metrics["median_roll7"]
        residual = self.metrics["median_roll7_rs"]
        self.assertLess(residual["stockout_rate"], base["stockout_rate"])
        self.assertGreater(residual["leftover_rate"], base["leftover_rate"])
        self.assertGreater(residual["regret_per_100"], base["regret_per_100"])

    def test_sigma_scan_is_flat_around_one(self):
        scan = {row["k"]: row for row in self.result["sigma_scan"]}
        self.assertEqual(sorted(scan), [0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6])
        best = min(scan.values(), key=lambda row: row["regret_per_100"])
        self.assertGreaterEqual(best["k"], 0.7)
        self.assertLessEqual(best["k"], 1.1)
        # 曲线足够平：k=1.0 与最优值的差距不超过 10%
        self.assertLess(
            (scan[1.0]["regret_per_100"] - best["regret_per_100"]) / best["regret_per_100"], 0.10)
        # 缺货率随 k 单调下降
        stockouts = [scan[k]["stockout_rate"] for k in sorted(scan)]
        self.assertEqual(stockouts, sorted(stockouts, reverse=True))


if __name__ == "__main__":
    unittest.main()