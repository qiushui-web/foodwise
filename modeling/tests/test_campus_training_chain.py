"""Behavioral tests for the reconstructible campus training chain."""
from pathlib import Path
import importlib.util
import unittest
import json
import subprocess
import sys
import tempfile
import pandas as pd
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
    def replay_fixture(self, days=130):
        data = rows(days, stores=('a',))
        forecasts = []
        for i, row in enumerate(data):
            row.update(observation_id=f'obs-{i}',
                       available_at=row['business_date']+'T20:00:00+08:00',
                       revision_at=row['business_date']+'T20:00:00+08:00')
            forecasts.append(dict(row, target_date=row['business_date'],
                                  prediction_cutoff_at=row['business_date']+'T08:00:00+08:00'))
        return data, forecasts

    def test_candidate_path_keeps_calibration_independent_and_never_approves_sources(self):
        data, forecasts = self.replay_fixture()
        result = chain.run_chain(data, min_rows=50, forecasts=forecasts)
        self.assertEqual('CANDIDATES_READY', result['status'])
        self.assertTrue(result['candidate_training'])
        self.assertTrue(result['independent_calibration'])
        self.assertFalse(result['training_ready'])
        self.assertFalse(result['source_verified'])
        self.assertEqual({'weekday_baseline', 'lightgbm_l1'}, set(result['candidate_metrics']))
        self.assertEqual(result['split_rows']['test'], len(result['_test_predictions']))
        self.assertEqual({0.8, 0.9}, set(result['test_interval_metrics']))
        self.assertTrue(all(0 <= value['coverage'] <= 1 for value in result['test_interval_metrics'].values()))

    def test_calibration_outcome_revised_after_first_test_is_rejected(self):
        data, forecasts = self.replay_fixture()
        featured = chain.build_replay_features(data, forecasts).dropna(subset=chain.FEATURES)
        calibration_day = str(chain.make_splits(featured)['calibration'].iloc[0]['date'].date())
        next(row for row in data if row['business_date'] == calibration_day)['revision_at'] = '2027-01-01T20:00:00+08:00'
        result = chain.run_chain(data, min_rows=50, forecasts=forecasts)
        self.assertEqual('CALIBRATION_LABEL_UNAVAILABLE_BEFORE_TEST', result['status'])
        self.assertFalse(result['candidate_training'])

    def test_cli_persists_candidate_outputs_and_hash_bound_calibration(self):
        data, forecasts = self.replay_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accepted = root / 'accepted.csv'
            forecast_file = root / 'forecasts.csv'
            output = root / 'output'
            pd.DataFrame(data).to_csv(accepted, index=False)
            pd.DataFrame(forecasts).to_csv(forecast_file, index=False)
            completed = subprocess.run([
                sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts' / '26_campus_training_chain.py'),
                '--accepted', str(accepted), '--forecasts', str(forecast_file),
                '--min-rows', '50', '--output', str(output)
            ], capture_output=True, text=True, check=True)
            report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
            binding = json.loads((output / 'calibration.json').read_text(encoding='utf-8'))
            self.assertEqual('CANDIDATES_READY', report['status'])
            self.assertFalse(binding['production_approved'])
            model_name = 'candidate_model.txt' if (output / 'candidate_model.txt').exists() else 'baseline_model.json'
            import hashlib
            self.assertEqual(hashlib.sha256((output / model_name).read_bytes()).hexdigest(), binding['model_sha256'])
            self.assertEqual(hashlib.sha256((output / 'features.json').read_bytes()).hexdigest(), binding['feature_sha256'])
            for artifact in ('split_manifest.csv', 'calibration_predictions.csv', 'test_predictions.csv'):
                self.assertTrue((output / artifact).is_file(), artifact)
            self.assertIn('CANDIDATES_READY', completed.stdout)

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
