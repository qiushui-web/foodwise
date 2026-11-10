"""ZHAW 食堂数据的聚合面板要能支撑需求回测与真实干预归因。

这组断言同时是"数据可用性"的证明：如果哪天换了源文件或编码，面板会立刻失败。
"""

import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MEAL_PANEL = ROOT / "modeling" / "data" / "01_raw" / "zhaw_canteen_daily_panel.csv"
LABEL_PANEL = ROOT / "modeling" / "data" / "01_raw" / "zhaw_canteen_daily_label_panel.csv"


class ZhawPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MEAL_PANEL.exists() or not LABEL_PANEL.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/41_zhaw_daily_panel.py")
        cls.meal = pd.read_csv(MEAL_PANEL)
        cls.label = pd.read_csv(LABEL_PANEL)
        cls.meal["date"] = pd.to_datetime(cls.meal["date"])
        cls.label["date"] = pd.to_datetime(cls.label["date"])

    def test_panel_covers_full_semester(self):
        self.assertEqual(self.meal["date"].nunique(), 60)
        self.assertEqual(self.meal["shop"].nunique(), 2)
        self.assertEqual(str(self.meal["date"].min().date()), "2017-10-02")
        self.assertEqual(str(self.meal["date"].max().date()), "2017-12-22")

    def test_conditions_are_balanced(self):
        days = self.meal.groupby("condit")["date"].nunique().to_dict()
        self.assertEqual(days.get("Basis"), 30)
        self.assertEqual(days.get("Intervention"), 30)

    def test_vegetarian_share_rises_during_intervention(self):
        """源数据是真实的 12 周菜谱实验，干预周素食占比应高于基准周。"""
        for shop, part in self.label.groupby("shop"):
            shares = {}
            for condition, block in part.groupby("condit"):
                total = block["qty"].sum()
                shares[condition] = (block["qty"] * block["is_veg"]).sum() / total
            self.assertGreater(
                shares["Intervention"], shares["Basis"] + 0.05,
                f"{shop} 的干预周素食占比没有明显上升：{shares}")

    def test_quantities_are_clean(self):
        self.assertFalse(self.meal["qty"].isna().any())
        self.assertTrue((self.meal["qty"] >= 0).all())
        self.assertTrue((self.label["qty"] >= 0).all())
        self.assertGreater(self.meal["qty"].sum(), 20000)

    def test_label_panel_has_usable_series(self):
        """菜单轮换导致部分品类天数很少：建模只用长序列，必须明确哪些够长。"""
        series = self.label.groupby(["shop", "label"]).size().sort_values(ascending=False)
        self.assertEqual(len(series), 16)
        self.assertGreaterEqual(int((series >= 55).sum()), 4, series.to_string())
        self.assertGreaterEqual(int((series >= 12).sum()), 8, series.to_string())
        # 未标注与鱼类只有个位数天数，不能单独建模
        self.assertLessEqual(int(series.min()), 5)


if __name__ == "__main__":
    unittest.main()