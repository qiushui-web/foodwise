"""仿真器的校准验收：参数没调对之前，后面所有实验都不算数。

七条硬断言对应《食刻有数_v3_总方案》第 5 节：
  契约同构 / 全员真值 / 现状浪费率 / 模型优于现状 / 与固定规则打平 / 剩余右偏 / 真值不进特征
"""

import json
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "modeling" / "data" / "01_raw"
CALIB = ROOT / "modeling" / "data" / "03_output" / "sim_calibration.json"
LEDGER = ROOT / "src" / "main" / "resources" / "data" / "foodwise_operations_14d.csv"

POLICIES = ("inertia", "safety", "model")


def load(policy: str) -> pd.DataFrame:
    return pd.read_csv(RAW / f"sim_operations_{policy}.csv")


class SimulatorCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CALIB.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/45_simulate.py")
        cls.calib = json.loads(CALIB.read_text(encoding="utf-8"))

    def test_schema_matches_ledger_contract(self):
        ledger_columns = list(pd.read_csv(LEDGER, nrows=1).columns)
        for policy in POLICIES:
            frame = load(policy)
            self.assertEqual(list(frame.columns), ledger_columns + ["demand_qty", "synthetic"],
                             f"{policy} 的输出列必须与站点台账逐列同构")
            self.assertGreater(len(frame), 0)

    def test_all_rows_carry_truth_and_synthetic_flag(self):
        for policy in POLICIES:
            frame = load(policy)
            self.assertTrue(frame["synthetic"].all())
            self.assertTrue((frame["demand_qty"] >= 1).all())
            self.assertEqual(frame["business_date"].nunique(), self.calib["generated_days"])

    def test_phase_split_is_balanced(self):
        frame = load("model")
        phases = frame.groupby("phase")["business_date"].nunique().to_dict()
        self.assertEqual(phases, {"基线期": 45, "干预期": 45})
        adopted = frame.groupby("phase")["recommendation_adopted"].any().to_dict()
        self.assertEqual(adopted, {"基线期": False, "干预期": True})

    def test_inertia_unsold_rate_matches_observed_band(self):
        """现状的"卖不完"比例要落在真实台账 13.1% 附近的合理带内。"""
        unsold = self.calib["scenarios"]["inertia"]["unsold_rate"]
        self.assertGreaterEqual(unsold, 0.12)
        self.assertLessEqual(unsold, 0.21)

    def test_model_beats_inertia(self):
        model = self.calib["scenarios"]["model"]
        inertia = self.calib["scenarios"]["inertia"]
        self.assertGreater(model["profit_per_day"], inertia["profit_per_day"])
        self.assertLess(model["regret_per_100"], inertia["regret_per_100"])
        self.assertLess(model["stockout_rate"], inertia["stockout_rate"])

    def test_model_only_ties_the_fixed_rule(self):
        """这条断言是结论本身：分位方法相对"固定 +10%"没有数量级优势，差距必须在 2% 内。"""
        model = self.calib["scenarios"]["model"]["profit_per_day"]
        safety = self.calib["scenarios"]["safety"]["profit_per_day"]
        self.assertLess(abs(model - safety) / safety, 0.02)

    def test_leftover_rate_is_right_skewed(self):
        for policy in POLICIES:
            values = self.calib["scenarios"][policy]
            self.assertGreater(values["daily_rate_mean"], values["daily_rate_median"])
            self.assertGreater(values["daily_rate_p95"], values["daily_rate_median"] * 1.5)

    def test_waste_is_not_proportional_to_demand(self):
        """芬兰实测：厨房浪费与客流的相关系数只有 0.17，仿真里不能出现强正相关。"""
        for policy in POLICIES:
            self.assertLess(abs(self.calib["scenarios"][policy]["corr_daily_rate_demand"]), 0.5)

    def test_demand_truth_never_enters_features(self):
        features = self.calib["feature_contract"]
        self.assertGreater(len(features), 0)
        self.assertNotIn("demand_qty", features)

    def test_accounting_identities_hold(self):
        for policy in POLICIES:
            frame = load(policy)
            self.assertTrue((frame["sold_qty"] <= frame["prepared_qty"]).all())
            self.assertTrue((frame["leftover_qty"] >= 0).all())
            identity = frame["prepared_qty"] - frame["sold_qty"] - frame["discount_sold_qty"]
            self.assertTrue((identity == frame["leftover_qty"]).all())
            self.assertTrue((frame["revenue"] > 0).all())

    def test_weekday_effect_present(self):
        frame = load("inertia")
        frame["weekday"] = pd.to_datetime(frame["business_date"]).dt.dayofweek
        means = frame.groupby("weekday")["demand_qty"].mean()
        self.assertGreater(means[1], means[4] * 1.10)   # 周二显著高于周五
        self.assertGreater(means[0], means[4] * 1.10)   # 周一显著高于周五


if __name__ == "__main__":
    unittest.main()