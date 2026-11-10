import importlib.util
from pathlib import Path
import tempfile
import unittest
import pandas as pd


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, Path(__file__).resolve().parents[1] / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bundle = load('27_build_local_model_bundle.py')
replay = load('28_availability_revision_interval.py')


class LocalBundleAndReplayTests(unittest.TestCase):
    def test_bundle_copies_hashes_and_does_not_claim_online_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, features = root / 'm.txt', root / 'f.json'
            model.write_text('tree=0\n', encoding='utf-8')
            features.write_text('{"features": []}', encoding='utf-8')
            manifest = bundle.build_bundle(model, features, None, root / 'out', 'test')
            self.assertEqual(manifest['artifacts']['model.txt']['sha256'], bundle.sha256(root / 'out/model.txt'))
            self.assertFalse(manifest['online_model_overwrite'])

    def test_bundle_rejects_calibration_for_another_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, features, calibration = root / 'm.txt', root / 'f.json', root / 'c.json'
            model.write_text('tree=0\n', encoding='utf-8')
            features.write_text('{"features": []}', encoding='utf-8')
            calibration.write_text('{"model_sha256":"wrong"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'CALIBRATION_MODEL_SHA256_MISMATCH'):
                bundle.build_bundle(model, features, calibration, root / 'out', 'test')

    def test_replay_uses_latest_revision_visible_at_cutoff_only(self):
        observations = pd.DataFrame([
            {'observation_id': 'a', 'available_at': '2026-01-01T08:00:00Z', 'revision_at': '2026-01-01T08:00:00Z', 'target': 10},
            {'observation_id': 'a', 'available_at': '2026-01-03T08:00:00Z', 'revision_at': '2026-01-03T08:00:00Z', 'target': 99},
            {'observation_id': 'b', 'available_at': '2026-01-01T08:00:00Z', 'revision_at': '2026-01-01T08:00:00Z', 'target': 4},
        ])
        visible = replay.visible_at(observations, '2026-01-02T00:00:00Z')
        self.assertEqual(['a', 'b'], visible.observation_id.tolist())
        self.assertEqual([10, 4], visible.target.tolist())

    def test_bundle_rejects_unbound_calibration_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, features, calibration = root / 'm.txt', root / 'f.json', root / 'c.json'
            model.write_text('tree=0\n', encoding='utf-8')
            features.write_text('[]', encoding='utf-8')
            calibration.write_text('{"radius":3}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'CALIBRATION_MODEL_SHA256_REQUIRED'):
                bundle.build_bundle(model, features, calibration, root / 'out', 'test')
            self.assertFalse((root / 'out').exists())

    def test_replay_rejects_invalid_and_future_revisions(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_REPLAY_TIMESTAMP'):
            replay.visible_at(pd.DataFrame([{'observation_id': 'x', 'available_at': None, 'revision_at': '2026-01-01'}]), '2026-01-02')
        observations = pd.DataFrame([{
            'observation_id': 'x', 'available_at': '2026-01-01T08:00:00Z',
            'revision_at': '2026-01-03T08:00:00Z', 'target': 99,
        }])
        self.assertTrue(replay.visible_at(observations, '2026-01-02T00:00:00Z').empty)

    def test_calibration_is_independent_and_returns_explicit_radius(self):
        calibration = pd.DataFrame({'actual': [10, 12, 8, 20, 15], 'prediction': [9, 10, 10, 18, 12]})
        result = replay.calibrate_residual_interval(calibration, .8)
        self.assertEqual(5, result['rows'])
        self.assertGreaterEqual(result['radius'], 3)
        self.assertIn('drift', result['warning'])

    def test_training_chain_deduplicates_revisions_before_features(self):
        chain = load('26_campus_training_chain.py')
        rows = [{
            'school_id': 's', 'stall_id': 'a', 'dish_id': 'd', 'business_date': '2026-01-01',
            'meal_period': 'lunch', 'net_sold_qty': '10', 'label_origin': 'observed',
            'supply_censored': 'False', 'observation_id': 'o1',
            'available_at': '2026-01-02T00:00:00Z', 'revision_at': '2026-01-02T00:00:00Z'},
            {
            'school_id': 's', 'stall_id': 'a', 'dish_id': 'd', 'business_date': '2026-01-01',
            'meal_period': 'lunch', 'net_sold_qty': '99', 'label_origin': 'observed',
            'supply_censored': 'False', 'observation_id': 'o1',
            'available_at': '2026-01-03T00:00:00Z', 'revision_at': '2026-01-03T00:00:00Z'}]
        admitted = chain.training_rows(rows)
        self.assertEqual(1, len(admitted))
        self.assertEqual(99, admitted.iloc[0].target)

    def test_training_features_replay_prior_value_instead_of_future_revision(self):
        chain = load('26_campus_training_chain.py')
        base = {'school_id': 's', 'stall_id': 'a', 'dish_id': 'd', 'meal_period': 'lunch',
                'label_origin': 'observed', 'supply_censored': 'False'}
        rows = [dict(base, business_date='2026-01-01', observation_id='one', net_sold_qty='10',
                     available_at='2026-01-01T18:00:00+08:00', revision_at='2026-01-01T18:00:00+08:00'),
                dict(base, business_date='2026-01-01', observation_id='one', net_sold_qty='99',
                     available_at='2026-01-01T18:00:00+08:00', revision_at='2026-01-03T18:00:00+08:00'),
                dict(base, business_date='2026-01-02', observation_id='two', net_sold_qty='12',
                     available_at='2026-01-02T18:00:00+08:00', revision_at='2026-01-02T18:00:00+08:00')]
        forecasts = [dict(base, target_date='2026-01-02', prediction_cutoff_at='2026-01-02T08:00:00+08:00')]
        result = chain.build_replay_features(rows, forecasts)
        self.assertEqual(10, result.iloc[0].lag1)
        changed = [dict(row) for row in rows]
        changed[1]['net_sold_qty'] = '1000000'
        self.assertEqual(10, chain.build_replay_features(changed, forecasts).iloc[0].lag1)

    def test_training_without_snapshots_cannot_claim_replay(self):
        chain = load('26_campus_training_chain.py')
        rows = [{'school_id':'s','stall_id':'a','dish_id':'d','meal_period':'lunch',
                 'business_date':'2026-01-01','label_origin':'observed','supply_censored':'False','net_sold_qty':'10'}]
        report = chain.run_chain(rows, min_rows=1)
        self.assertFalse(report['availability_replay'])
        self.assertEqual('MISSING_FORECAST_SNAPSHOTS', report['status'])

    def test_calibration_uses_finite_sample_rank_and_rejects_unsupported_small_sample(self):
        frame = pd.DataFrame({'actual': list(range(1, 10)), 'prediction': [0] * 9})
        self.assertEqual(8, replay.calibrate_residual_interval(frame, .8)['radius'])
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_CALIBRATION_ROWS_FOR_NOMINAL'):
            replay.calibrate_residual_interval(frame.iloc[:2], .95)

    def test_replay_rejects_timezone_equivalent_revision_conflicts(self):
        frame = pd.DataFrame([
            dict(observation_id='a', available_at='2026-01-01T00:00:00Z', revision_at='2026-01-01T08:00:00+08:00', target=10),
            dict(observation_id='a', available_at='2026-01-01T00:00:00Z', revision_at='2026-01-01T00:00:00Z', target=99)])
        with self.assertRaisesRegex(ValueError, 'AMBIGUOUS_REVISION_TIMESTAMP'):
            replay.visible_at(frame, '2026-01-02T00:00:00Z')


if __name__ == '__main__':
    unittest.main()
