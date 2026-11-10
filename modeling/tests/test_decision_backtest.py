import importlib.util
import sys
import unittest
from argparse import Namespace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modeling"))


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, ROOT / "modeling" / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backtest = load("33_decision_backtest.py")


def frame():
    return pd.DataFrame(
        {
            "sold_qty": [80.0, 90.0, 70.0, 100.0, 60.0, 85.0],
            "lo_raw": [70.0, 80.0, 60.0, 90.0, 50.0, 75.0],
            "hi_raw": [86.0, 96.0, 76.0, 106.0, 66.0, 91.0],
            "lo_cal": [66.0, 76.0, 56.0, 86.0, 46.0, 71.0],
            "hi_cal": [90.0, 100.0, 80.0, 110.0, 70.0, 95.0],
            "price": [12.0] * 6,
            "unit_cost": [5.0] * 6,
        }
    )


ARGS = Namespace(
    discount_ratio=0.5,
    shortage_lambda=0.3,
    safety_factor=1.10,
    minimum_batch=5.0,
    capacity=250.0,
)


class DecisionBacktestTests(unittest.TestCase):
    def test_scenario_returns_all_methods_with_sane_regret(self):
        data = frame()
        centers = [((lo + hi) / 2.0) for lo, hi in zip(data["lo_cal"], data["hi_cal"])]
        sigma_raw = [backtest.sigma_from_interval(lo, hi) for lo, hi in zip(data["lo_raw"], data["hi_raw"])]
        sigma_cal = [backtest.sigma_from_interval(lo, hi) for lo, hi in zip(data["lo_cal"], data["hi_cal"])]
        result = backtest.run_scenario(data, centers, sigma_raw, sigma_cal, 0.6, ARGS)
        self.assertEqual(
            set(result["methods"]),
            {"rule_10pct", "newsvendor_raw", "newsvendor_calibrated", "newsvendor_batch"},
        )
        for name, row in result["methods"].items():
            self.assertGreaterEqual(row["regret"], 0.0, name)
            self.assertLess(row["regret"], 1.0, name)
            self.assertEqual(row["n"], 6)

    def test_degenerate_salvage_is_detected(self):
        data = frame()
        self.assertEqual(backtest.degenerate_rows(data, 0.6, 0.5), 0)
        self.assertGreater(backtest.degenerate_rows(data, 1.0, 0.5), 0)

    def test_bootstrap_ci_brackets_mean(self):
        data = frame()
        centers = [((lo + hi) / 2.0) for lo, hi in zip(data["lo_cal"], data["hi_cal"])]
        sigma_raw = [backtest.sigma_from_interval(lo, hi) for lo, hi in zip(data["lo_raw"], data["hi_raw"])]
        sigma_cal = [backtest.sigma_from_interval(lo, hi) for lo, hi in zip(data["lo_cal"], data["hi_cal"])]
        models = backtest.scenario_inputs(data, 0.6, ARGS)
        prepared = backtest.quantities_for(models, centers, sigma_raw, sigma_cal, ARGS)
        stats = backtest.bootstrap_regret_diff(
            models, prepared["rule_10pct"], prepared["newsvendor_calibrated"], data["sold_qty"].tolist(), reps=200, block=3
        )
        self.assertLessEqual(stats["ci95"][0], stats["mean"])
        self.assertGreaterEqual(stats["ci95"][1], stats["mean"])
        self.assertEqual(stats["block"], 3)


if __name__ == "__main__":
    unittest.main()