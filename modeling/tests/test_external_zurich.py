"""外部效度的结论必须能被复核：不是"我们跑了一遍真实数据"，而是差异到底有多大、是否算得上差异。"""

import json
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "modeling" / "data" / "03_output" / "external_zurich.json"
DECISIONS = ROOT / "modeling" / "data" / "03_output" / "external_zurich.csv"


class ZurichExternalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RESULT.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/47_external_zurich.py")
        cls.data = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.frame = pd.read_csv(DECISIONS)

    def test_scope_of_the_experiment(self):
        self.assertEqual(60, self.data["days"])
        self.assertEqual(4, len(self.data["articles"]))
        self.assertEqual(400, self.data["decisions"], "4 菜单线 × 20 天 × 5 方法")
        for name, metrics in self.data["methods"].items():
            self.assertEqual(80, metrics["n"], f"{name} 的决定数不对")

    def test_no_negative_regret(self):
        self.assertGreaterEqual(self.frame["regret"].min(), -1e-9,
                                "regret 是按 oracle 利润算的，不可能为负")

    def test_best_method_matches_the_table(self):
        best = min(self.data["methods"].items(), key=lambda item: item[1]["regret_per_100"])[0]
        self.assertEqual(best, self.data["best_by_regret"])
        self.assertEqual(best, self.data["ordering_by_regret"][0])

    def test_gbdt_accuracy_edge_is_not_significant(self):
        """真实数据上 GBDT 的 MAE 更低，但配对区间跨 0——不能写成"模型更准"。"""
        comparison = next(c for c in self.data["comparisons"] if c["comparison"].startswith("gbdt - same_weekday"))
        low, high = comparison["mae_diff_ci95"]
        self.assertLess(low, 0, "点估计应为负（GBDT 误差更小）")
        self.assertGreater(high, 0, "但区间必须跨 0，否则就该改口说'显著更准'")

    def test_decision_level_difference_is_a_tie(self):
        comparison = next(c for c in self.data["comparisons"] if c["comparison"].startswith("gbdt - mean_roll7"))
        low, high = comparison["regret_diff_ci95"]
        self.assertLess(low, 0)
        self.assertGreater(high, 0)
        self.assertLess(abs(comparison["regret_diff_mean"]), 2.0, "regret 差应不到 2 元/百份")

    def test_cost_model_matches_the_site(self):
        cost = self.data["cost_model"]
        # ZHAW 单价 7 瑞郎，成本按 0.4 倍估；临界比与站内一致（0.886），因为两边成本率相同
        self.assertAlmostEqual(0.8864, cost["critical_ratio"], places=3)
        self.assertAlmostEqual((cost["price"] - cost["unit_cost"]) * 1.3, cost["underage"], places=4)
        self.assertAlmostEqual(cost["unit_cost"] - cost["discount"] * 0.6, cost["overage"], places=4)


if __name__ == "__main__":
    unittest.main()