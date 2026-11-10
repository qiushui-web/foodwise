import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modeling"))


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, ROOT / "modeling" / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


attr = load("34_attribute.py")


class AttrRecoveryTests(unittest.TestCase):
    """归因方法的最低门槛：能估回已知效应，且区间真的覆盖真值。"""

    def test_its_recovers_known_effect_with_small_bias(self):
        estimates = []
        for k in range(12):
            y, t0 = attr.simulate(effect_pp=-10.0, seed=1000 + k)
            fit = attr.its_fit(y, t0)
            estimates.append(fit["effect"] / attr.BASE_QTY * 100.0)
        mean = float(np.mean(estimates))
        self.assertLess(abs(mean + 10.0), 2.0, f"ITS 平均估计 {mean:.2f}pp 偏离真值 -10pp 超过 2pp")

    def test_its_coverage_is_close_to_nominal(self):
        covered = []
        for k in range(20):
            y, t0 = attr.simulate(effect_pp=-5.0, seed=2000 + k)
            fit = attr.its_fit(y, t0)
            lo = fit["ci_low"] / attr.BASE_QTY * 100.0
            hi = fit["ci_high"] / attr.BASE_QTY * 100.0
            covered.append(lo <= -5.0 <= hi)
        rate = float(np.mean(covered))
        self.assertGreater(rate, 0.8, f"ITS 95% 区间覆盖率只有 {rate:.2f}")
        self.assertLessEqual(rate, 1.0)

    def test_zero_effect_mostly_not_significant(self):
        hits = 0
        for k in range(16):
            y, t0 = attr.simulate(effect_pp=0.0, seed=3000 + k)
            hits += attr.its_fit(y, t0)["p_value"] < attr.ALPHA
        self.assertLessEqual(hits / 16, 0.25, "真值为 0 时假阳性过多，方法在制造效应")

    def test_weekday_controls_remove_seasonal_leak(self):
        # 后段只有 6 天（周三到周一）时，不控星期效应会把“周末客流”读成干预效应。
        seasonal = np.array([0, 4, 6, 8, 20, 26, 10], dtype=float)
        without, with_controls = [], []
        for k in range(20):
            rng = np.random.default_rng(5000 + k)
            weekday = np.arange(90) % 7
            y = 300 + seasonal[weekday] + rng.normal(0, 8, 90)
            y = y + np.where(np.arange(90) >= 84, -15.0, 0.0)
            without.append(attr.its_fit(y, 84, weekday_controls=False)["effect"])
            with_controls.append(attr.its_fit(y, 84, weekday_controls=True)["effect"])
        bias_without = float(np.mean(without)) + 15.0
        bias_with = float(np.mean(with_controls)) + 15.0
        self.assertGreater(abs(bias_without), 6.0, f"不控星期效应时应出现明显偏差，实测 {bias_without:.2f}")
        self.assertLess(abs(bias_with), 3.0, f"控制星期效应后偏差应大幅缩小，实测 {bias_with:.2f}")


class AttrArtifactTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "modeling" / "data" / "03_output" / "attribution_backtest.json"
        if not self.path.exists():
            self.skipTest("attribution_backtest.json 尚未生成")
        self.report = json.loads(self.path.read_text(encoding="utf-8"))

    def test_contract_fields_present(self):
        for key in ("protocol", "recovery", "placebo", "real_ledger", "limits"):
            self.assertIn(key, self.report)
        self.assertEqual(self.report["protocol"], "attribution-recovery-v1")

    def test_real_ledger_makes_no_effect_claim(self):
        ledger = self.report["real_ledger"]
        self.assertEqual(ledger["verdict"], "not_identifiable")
        self.assertIn("warning", ledger)
        self.assertGreater(ledger["min_detectable_effect_pp"], 5.0, "14 天数据不应能识别 5pp 级效应")
        self.assertEqual(len(ledger["leftover_rate_pct"]), 14)

    def test_recovery_reports_both_methods_and_bias(self):
        for bucket in self.report["recovery"].values():
            self.assertIn("its", bucket)
            self.assertIn("bsts", bucket)
            self.assertLess(abs(bucket["its"]["bias"]), 1.0)
            self.assertGreater(bucket["its"]["coverage95"], 0.85)

    def test_java_resource_copy_matches(self):
        resource = ROOT / "src" / "main" / "resources" / "modeling" / "attribution_backtest.json"
        self.assertTrue(resource.exists())
        self.assertEqual(json.loads(resource.read_text(encoding="utf-8"))["protocol"],
                         self.report["protocol"])


if __name__ == "__main__":
    unittest.main()