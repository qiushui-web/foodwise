"""Audit added historical features, gates, splits and interval semantics."""
from pathlib import Path
import importlib.util
import json
import unittest
import numpy as np
import pandas as pd


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1]/'scripts'/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


experiment = load('entity_interval', '21_entity_and_interval_validation.py')
provenance = load('upstream', '22_upstream_provenance_review.py')


class EntityAndIntervalTests(unittest.TestCase):
    def test_future_and_current_targets_cannot_change_ewma_features(self):
        raw = pd.DataFrame({'date': pd.date_range('2022-01-01', periods=60),
                            'store': 'a', 'sales': np.arange(60.)})
        future = raw.copy()
        future.loc[future.date >= '2022-02-10', 'sales'] = 1e9
        before, after = experiment.build_features(raw), experiment.build_features(future)
        columns = experiment.FEATURES+['ewma_0.2', 'ewma_0.5']
        pd.testing.assert_frame_equal(before.loc[before.date <= '2022-02-10', columns],
                                      after.loc[after.date <= '2022-02-10', columns])

    def test_unseen_entity_gate_uses_fallback_without_clipping_scaled_negatives(self):
        prediction = experiment.gate_prediction(['old', 'new'], {'old'}, [3., 4.], [-1., -2.])
        np.testing.assert_array_equal(prediction, [3., -2.])

    def test_windows_keep_every_entity_on_same_side_of_time_boundary(self):
        raw = pd.DataFrame({'date': pd.date_range('2022-01-01', periods=60),
                            'store': 'a', 'sales': np.arange(60.)})
        other = raw.assign(store='b', sales=0.)
        for _, train, valid in experiment.windows(pd.concat([raw, other])):
            self.assertLess(train.date.max(), valid.date.min())
            self.assertEqual({'a', 'b'}, set(train.store))
            self.assertEqual({'a', 'b'}, set(valid.store))

    def test_interval_score_penalizes_misses_as_well_as_width(self):
        score = experiment.interval_metrics([0., 3.], [-1., -1.], [1., 1.], .8)
        self.assertEqual(.5, score['coverage'])
        self.assertEqual(2., score['width'])
        self.assertAlmostEqual(12., score['interval_score'])

    def test_public_documentation_can_be_displayed_on_gbk_console(self):
        report = {'text': 'Bäckerei für 河北', 'url': 'https://example.org'}
        encoded = provenance.console_json(report).encode('gbk')
        self.assertEqual(report, json.loads(encoded.decode('gbk')))


if __name__ == '__main__':
    unittest.main()
