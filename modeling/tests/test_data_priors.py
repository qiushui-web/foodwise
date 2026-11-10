"""校准锚点必须能被复核：仿真器依赖的分布参数一旦漂移，方案 A 的前提就变了。"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIORS = ROOT / "modeling" / "data" / "03_output" / "finland_waste_priors.json"


class DataPriorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PRIORS.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/43_finland_waste_priors.py")
        cls.priors = json.loads(PRIORS.read_text(encoding="utf-8"))

    def test_covers_a_full_school_year(self):
        self.assertGreaterEqual(self.priors["rows"], 150)
        self.assertEqual(self.priors["date_min"], "2024-08-08")
        self.assertLessEqual(self.priors["ksw_per_diner_g"]["p95"], 120)

    def test_kitchen_waste_is_about_40_percent(self):
        """厨房环节浪费接近一半——这是本项目"备餐过剩"立论的定量依据。"""
        share = self.priors["kitchen_share_of_waste"]["median"]
        self.assertGreater(share, 0.30)
        self.assertLess(share, 0.55)

    def test_waste_is_decoupled_from_headcount(self):
        """真实数据里备餐过剩与就餐人数几乎不相关，支撑"按惯性备餐"的判断。"""
        self.assertLess(self.priors["corr_ksw_diners"], 0.35)
        self.assertGreater(self.priors["corr_ksw_diners"], 0.0)

    def test_waste_distribution_is_right_skewed(self):
        distribution = self.priors["ksw_per_diner_g"]
        self.assertGreater(distribution["mean"], distribution["median"])
        self.assertGreater(distribution["sd"], 10.0)


if __name__ == "__main__":
    unittest.main()