"""Contract checks for leakage, missing days and zero-label metrics."""
import importlib.util
from pathlib import Path
import unittest
import pandas as pd

spec = importlib.util.spec_from_file_location('validation', Path(__file__).resolve().parents[1]/'scripts/14_public_sales_validation.py')
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class PublicSalesProtocolTests(unittest.TestCase):
    def test_scaled_sales_cannot_enter_physical_production_simulation(self):
        with self.assertRaisesRegex(ValueError, 'physical'):
            validation.production_cost([-1., 1.], [0., 1.], 2, unit='scaled_sales')

    def test_same_weekday_mean_uses_previous_weeks_and_not_current_label(self):
        raw = pd.DataFrame({'date': pd.date_range('2026-01-01', periods=29),
                            'store': ['A']*29, 'sales': list(range(29))})
        data = validation.build_features(raw)
        self.assertEqual(10.5, data.iloc[-1]['weekday_mean4'])
        raw.loc[28, 'sales'] = 10000
        self.assertEqual(10.5, validation.build_features(raw).iloc[-1]['weekday_mean4'])

    def test_missing_day_is_not_treated_as_yesterday_or_zero_sales(self):
        raw = pd.DataFrame({'date': pd.to_datetime(['2026-01-01', '2026-01-03']),
                            'store': ['A', 'A'], 'sales': [10., 30.]})
        data = validation.build_features(raw)
        self.assertTrue(pd.isna(data.loc[data.date == '2026-01-03', 'lag1'].iloc[0]))
        self.assertTrue(pd.isna(data.loc[data.date == '2026-01-02', 'sales'].iloc[0]))

    def test_changing_current_target_does_not_change_current_features(self):
        raw = pd.DataFrame({'date': pd.date_range('2026-01-01', periods=10),
                            'store': ['A']*10, 'sales': list(range(1, 11))})
        before = validation.build_features(raw).iloc[-1][validation.FEATURES]
        raw.loc[9, 'sales'] = 9999
        after = validation.build_features(raw).iloc[-1][validation.FEATURES]
        pd.testing.assert_series_equal(before, after)

    def test_zero_sales_does_not_report_infinite_percentage(self):
        result = validation.metrics([0, 0], [0, 0])
        self.assertIsNone(result['wape_pct'])
        self.assertEqual(0, result['mae'])
        self.assertEqual(0, result['smape_pct'])


if __name__ == '__main__':
    unittest.main()
