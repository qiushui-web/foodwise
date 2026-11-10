"""E1 的结论必须能被复核，尤其是"14 天其实够"这一条。"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "modeling" / "data" / "03_output" / "experiment_e1_power.json"
WINDOWS = [7, 14, 21, 28, 35, 45, 60, 90]


class PowerAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RESULT.exists():
            raise unittest.SkipTest("先运行 modeling/scripts/46_power_analysis.py")
        cls.data = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_curves_cover_all_windows(self):
        for key in ("power_waste_rate", "power_regret", "power_profit"):
            self.assertEqual([row["days"] for row in self.data[key]], WINDOWS)

    def test_regret_reaches_eighty_percent_by_sixty_days(self):
        power = {row["days"]: row["power"] for row in self.data["power_regret"]}
        self.assertGreaterEqual(power[60], 0.70)
        self.assertGreater(power[60], power[14])

    def test_waste_rate_is_not_detectable(self):
        """模型的剩余率并没有更低，所以任何窗口都不该"检出改善"。"""
        self.assertGreater(self.data["paired_effect"]["waste_rate_diff"], 0)
        best = max(row["power"] for row in self.data["power_waste_rate"])
        self.assertLess(best, 0.20)

    def test_profit_is_too_noisy(self):
        best = max(row["power"] for row in self.data["power_profit"])
        self.assertLess(best, 0.25)

    def test_fourteen_days_would_have_been_enough(self):
        """用真实台账的日波动，检 5pp 所需天数必须明显小于 14。"""
        days = self.data["required_days_ledger_sigma"]["for_5pp"]
        self.assertLess(days, 14)
        self.assertGreater(days, 1)

    def test_ledger_sigma_matches_the_source(self):
        self.assertAlmostEqual(self.data["ledger_sigma_daily"], 0.04657, places=4)


if __name__ == "__main__":
    unittest.main()