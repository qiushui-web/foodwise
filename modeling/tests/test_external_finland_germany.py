"""这两份外部数据的价值，一半在"能用"，一半在"证明不能用"。"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "modeling" / "data" / "03_output"


class FinlandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = OUT / "external_finland.json"
        if not path.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/49_external_finland.py")
        cls.data = json.loads(path.read_text(encoding="utf-8"))["summary"]

    def test_scope(self):
        self.assertGreaterEqual(self.data["days"], 150)
        self.assertEqual("2024-08-08", self.data["date_from"])

    def test_kitchen_share_is_about_half(self):
        self.assertAlmostEqual(0.47, self.data["kitchen_share_of_waste"], places=2)

    def test_headcount_explains_little(self):
        """如果人数能解释过剩，我们该改成人均模型；数据说不能。"""
        self.assertLess(self.data["corr_diners_ksw"], 0.25)

    def test_weekday_rhythm_peaks_on_friday(self):
        profile = self.data["weekday_ksw_per_diner_g"]
        self.assertEqual(max(profile, key=profile.get), "4", "周五（weekday=4）应该是峰值")

    def test_their_intervention_moved_the_needle_a_lot(self):
        change = self.data["intervention"]["change_pct"]
        self.assertLess(change, -0.4)
        self.assertGreater(change, -0.7)


class GermanyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = OUT / "external_germany.json"
        if not path.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/50_external_germany.py")
        cls.data = json.loads(path.read_text(encoding="utf-8"))

    def test_scaling_is_rejected_with_evidence(self):
        scaling = self.data["scaling"]
        self.assertEqual("scaled_and_anonymised", scaling["verdict"])
        self.assertGreater(scaling["negative_unsold_share"], 0.5, "过半剩余为负，说明被标准化过")
        self.assertGreater(scaling["identity_abs_p95"], 0.5, "守恒检查必须失败")

    def test_naive_rate_is_flagged_not_quoted(self):
        """31.5% 这个数只能作为"如果硬算会得到什么"的反例出现。"""
        self.assertIsNotNone(self.data["scaling"]["naive_overproduction_rate"])
        self.assertIn("备餐过剩率", self.data["not_usable_for"])

    def test_weekday_rhythm_exists(self):
        profile = self.data["weekday_profile"]["by_weekday"]
        peak = max(profile, key=profile.get)
        self.assertIn(peak, ("0", "1"), "周一/周二最高（2.07 vs 2.14，几乎并列）")
        self.assertEqual("6", min(profile, key=profile.get), "周日应是谷值")

    def test_holiday_lifts_sales(self):
        self.assertGreater(self.data["holiday_effect"]["difference"], 0.2)


if __name__ == "__main__":
    unittest.main()