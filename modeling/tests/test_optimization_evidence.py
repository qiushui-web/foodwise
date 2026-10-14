"""Temporal and entity isolation checks for the optimization protocol."""
from pathlib import Path
import importlib.util
import unittest
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('optimization', Path(__file__).resolve().parents[1] / 'scripts/18_optimization_evidence.py')
optimization = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimization)


class OptimizationEvidenceTests(unittest.TestCase):
    def test_leakage_gap_duplicate_and_entity_contracts(self):
        self.assertEqual(4, len(optimization.leakage_checks()))

    def test_tail_early_stopping_precedes_full_refit(self):
        observed = []

        class FakeModel:
            def __init__(self, **params):
                self.n_estimators = params['n_estimators']
                self.best_iteration_ = 17

            def fit(self, features, labels, **kwargs):
                observed.append((features.index.tolist(), kwargs))
                return self

        from unittest.mock import patch
        train = pd.DataFrame({'date': pd.date_range('2022-01-01', periods=50),
                              'sales': np.arange(50.), 'dow': np.arange(50) % 7})
        with patch.object(optimization.lgb, 'LGBMRegressor', FakeModel):
            model = optimization.fit(train, ['dow'])
        fit_indices, kwargs = observed[0]
        stop_indices = kwargs['eval_set'][0][0].index.tolist()
        self.assertLess(max(fit_indices), min(stop_indices))
        self.assertFalse(set(fit_indices) & set(stop_indices))
        self.assertEqual(list(range(50)), observed[1][0])
        self.assertEqual(17, model.n_estimators)


if __name__ == '__main__':
    unittest.main()
