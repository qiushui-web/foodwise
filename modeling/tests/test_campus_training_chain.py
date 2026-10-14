"""Behavioral tests for the reconstructible campus training chain."""
from pathlib import Path
import importlib.util
import unittest
from datetime import date, timedelta

spec = importlib.util.spec_from_file_location('campus_chain',
    Path(__file__).resolve().parents[1] / 'scripts' / '26_campus_training_chain.py')
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)


def rows(days=20, stores=('a', 'b')):
    result = []
    for store in stores:
        for i in range(days):
            day = (date(2026, 1, 1) + timedelta(days=i)).isoformat()
            result.append({'school_id': 's', 'stall_id': store, 'dish_id': 'd',
                'business_date': day, 'meal_period': 'lunch', 'unit': 'portion',
                'net_sold_qty': str(10 + i), 'label_origin': 'observed', 'supply_censored': 'False'})
    return result


class CampusTrainingChainTests(unittest.TestCase):
    def test_features_are_entity_local_and_lag7_is_calendar_based(self):
        data = chain.build_features(rows())
        first_b = data[(data.stall_id == 'b') & (data.business_date == '2026-01-01')].iloc[0]
        self.assertTrue(first_b['lag7'] != first_b['lag7'])
        day8 = data[(data.stall_id == 'a') & (data.business_date == '2026-01-08')].iloc[0]
        self.assertEqual(10, day8['lag7'])

    def test_splits_are_disjoint_and_temporally_ordered(self):
        data = chain.build_features(rows(40))
        splits = chain.make_splits(data)
        self.assertLess(splits['fit']['date'].max(), splits['tune']['date'].min())
        self.assertLess(splits['tune']['date'].max(), splits['calibration']['date'].min())
        self.assertLess(splits['calibration']['date'].max(), splits['test']['date'].min())
        self.assertEqual(0, len(set(splits['fit'].index) & set(splits['test'].index)))

    def test_derived_or_censored_rows_cannot_enter_primary_training(self):
        data = rows(12)
        data[0]['label_origin'] = 'derived'
        data[1]['supply_censored'] = 'True'
        admitted = chain.training_rows(data)
        self.assertEqual(22, len(admitted))
        self.assertTrue((admitted.label_origin == 'observed').all())
        self.assertFalse(admitted.supply_censored.any())

    def test_empty_input_does_not_claim_training_ready(self):
        report = chain.run_chain([], min_rows=1)
        self.assertFalse(report['training_ready'])
        self.assertEqual('NO_ADMITTED_ROWS', report['status'])


if __name__ == '__main__':
    unittest.main()
