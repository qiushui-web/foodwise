"""采集工具包必须能挡住坏数据，否则它只是一张好看的表格。"""

import importlib.util
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "docs" / "采集工具包_35天_20261027"
SAMPLE = KIT / "templates" / "示例_模拟数据_仅示范格式.csv"
SAMPLE_LOG = KIT / "templates" / "示例_采纳原因_仅示范格式.csv"
SCRIPT = ROOT / "modeling" / "scripts" / "48_validate_pilot.py"

spec = importlib.util.spec_from_file_location("validate_pilot", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PilotKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = validator.load(SAMPLE)
        cls.adoption = validator.load(SAMPLE_LOG)

    def test_templates_cover_the_required_fields(self):
        header = pd.read_csv(KIT / "templates" / "daily_ledger.csv", nrows=0).columns.tolist()
        for column in validator.REQUIRED:
            self.assertIn(column, header, f"模板缺少必需列 {column}")

    def test_sample_ledger_passes(self):
        result = validator.validate(self.ledger, self.adoption)
        self.assertEqual([], result["errors"])
        self.assertEqual("passed", result["status"])
        self.assertEqual(35, result["summary"]["business_days"])
        self.assertEqual(70, result["summary"]["rows"])

    def test_quantity_identity_is_enforced(self):
        broken = self.ledger.copy()
        broken.loc[0, "leftover_qty"] = str(int(broken.loc[0, "leftover_qty"]) + 3)
        result = validator.validate(broken, self.adoption)
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("不守恒" in error for error in result["errors"]))

    def test_duplicate_keys_are_rejected(self):
        duplicated = pd.concat([self.ledger, self.ledger.iloc[[0]]], ignore_index=True)
        result = validator.validate(duplicated, self.adoption)
        self.assertTrue(any("重复键" in error for error in result["errors"]))

    def test_mixed_conditions_within_a_week_are_rejected(self):
        mixed = self.ledger.copy()
        mixed.loc[0, "condition"] = "A" if mixed.loc[0, "condition"] != "A" else "B"
        result = validator.validate(mixed, self.adoption)
        self.assertTrue(any("混了两种条件" in error for error in result["errors"]))

    def test_intervention_rows_need_a_suggestion(self):
        missing = self.ledger.copy()
        index = missing[missing["condition"] == "A"].index[0]
        missing.loc[index, "suggested_qty"] = None
        result = validator.validate(missing, self.adoption)
        self.assertTrue(any("未记录建议量" in error for error in result["errors"]))

    def test_more_than_35_days_is_rejected(self):
        longer = self.ledger.copy()
        extra = longer.iloc[[0]].copy()
        extra["business_date"] = "2026-12-31"
        result = validator.validate(pd.concat([longer, extra], ignore_index=True), self.adoption)
        self.assertTrue(any("超过 35 天" in error for error in result["errors"]))

    def test_unadopted_rows_need_a_reason_code(self):
        result = validator.validate(self.ledger, None)
        self.assertTrue(any("采纳原因表" in warning for warning in result["warnings"]))

        thinned = self.adoption.iloc[:-5]
        result = validator.validate(self.ledger, thinned)
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("缺少原因码" in error for error in result["errors"]))

    def test_adoption_rate_counts_intervention_weeks_only(self):
        result = validator.validate(self.ledger, self.adoption)
        intervention = int((self.ledger["condition"] == "A").sum())
        self.assertEqual(intervention, result["summary"]["intervention_rows"])
        self.assertAlmostEqual(1.0, result["summary"]["adoption_rate"], places=4)


if __name__ == "__main__":
    unittest.main()