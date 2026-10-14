"""Public admission boundary; constructed records are tests, not field evidence."""
from pathlib import Path
import importlib.util
import unittest

spec = importlib.util.spec_from_file_location('campus_admission',
    Path(__file__).resolve().parents[1]/'scripts'/'25_campus_admission.py')
admission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admission)


class CampusAdmissionTests(unittest.TestCase):
    def sample(self, **changes):
        row = dict(school_id='school', stall_id='stall', dish_id='dish',
            business_date='2026-10-12', meal_period='lunch', unit='portion',
            business_status='open', opening_qty='0', prepared_qty='100',
            transfer_in_qty='0', transfer_out_qty='0', sold_regular_qty='70',
            sold_discount_qty='10', refund_qty='2', returned_to_kitchen_qty='0',
            discarded_qty='5', closing_qty='15', revenue='800',
            stockout_at='', unavailable_minutes='0', actual_plan_qty='100',
            override_reason='', source_id='pos', label_origin='observed',
            recorded_at='2026-10-12T20:00:00+08:00', quality_flags='')
        row.update(changes)
        source = dict(source_id='pos', publisher='school', source_url='local:pos',
            acquired_at='2026-10-12T21:00:00+08:00', authorization_reference='permit1',
            license_reference='permit1', permitted_use='model_training', region='Hebei',
            time_granularity='meal', entity_granularity='dish',
            target_definition='net_sales_disjoint_refunds_already_deducted',
            unit='portion', label_origin='observed', provenance_status='verified',
            sha256='a'*64, quality_version='campus-v1')
        return row, source

    def check(self, **changes):
        row, source = self.sample(**changes)
        return admission.validate_observations([row], [source], '2026-10-13T10:00:00+08:00')

    def test_balanced_authorized_observation_preserves_net_sales_and_raw_refunds(self):
        result = self.check()
        self.assertEqual(1, result['summary']['accepted_rows'])
        self.assertEqual('80', result['accepted'][0]['net_sold_qty'])
        self.assertEqual('2', result['accepted'][0]['refund_qty'])
        self.assertFalse(result['summary']['training_ready'])

    def test_empty_template_is_not_training_ready(self):
        result = admission.validate_observations([], [], '2026-10-13T10:00:00+08:00')
        self.assertFalse(result['summary']['training_ready'])
        self.assertEqual(0, result['summary']['input_rows'])

    def test_bad_labels_numbers_and_inventory_are_quarantined_without_silent_repair(self):
        for changes, code in [({'label_origin': 'derived'}, 'NON_OBSERVED_LABEL'),
            ({'prepared_qty': ''}, 'INVALID_NUMBER:prepared_qty'),
            ({'prepared_qty': 'NaN'}, 'INVALID_NUMBER:prepared_qty'),
            ({'closing_qty': '16'}, 'INVENTORY_IMBALANCE'),
            ({'sold_regular_qty': '-1'}, 'INVALID_NUMBER:sold_regular_qty'),
            ({'recorded_at': '2026-10-14T20:00:00+08:00'}, 'OBSERVATION_TIME_INVALID'),
            ({'business_status': 'closed'}, 'CLOSED_NOT_SALES_TRAINING_ROW')]:
            with self.subTest(changes=changes):
                result = self.check(**changes)
                self.assertEqual([], result['accepted'])
                self.assertIn(code, result['quarantined'][0]['reason_codes'].split(';'))

    def test_all_duplicate_rows_are_retained_and_rejected(self):
        row, source = self.sample()
        result = admission.validate_observations([row, dict(row)], [source], '2026-10-13T10:00:00+08:00')
        self.assertEqual(2, result['summary']['quarantined_rows'])
        self.assertEqual(2, result['summary']['reason_counts']['DUPLICATE_PRIMARY_KEY'])

    def test_stockout_is_observed_sales_with_supply_censoring(self):
        result = self.check(stockout_at='2026-10-12T12:30:00+08:00')
        self.assertEqual('80', result['accepted'][0]['net_sold_qty'])
        self.assertTrue(result['accepted'][0]['supply_censored'])

    def test_source_permission_and_duplicate_registry_are_fail_closed(self):
        row, source = self.sample()
        for sources, reason in [([dict(source, permitted_use='display')], 'SOURCE_NOT_AUTHORIZED'),
                                ([source, source], 'SOURCE_MISSING_OR_AMBIGUOUS')]:
            result = admission.validate_observations([row], sources, '2026-10-13T10:00:00+08:00')
            self.assertEqual([], result['accepted'])
            self.assertIn(reason, result['quarantined'][0]['reason_codes'])

    def test_zero_sales_is_valid_but_unit_changes_and_fractional_portions_are_not(self):
        result = self.check(sold_regular_qty='0', sold_discount_qty='0', closing_qty='95')
        self.assertEqual('0', result['accepted'][0]['net_sold_qty'])
        self.assertEqual(1, self.check(prepared_qty='100.5', closing_qty='15.5')['summary']['quarantined_rows'])
        row, source = self.sample()
        other = dict(row, business_date='2026-10-11', unit='kg')
        result = admission.validate_observations([row, other], [source], '2026-10-13T10:00:00+08:00')
        self.assertEqual(2, result['summary']['reason_counts']['ENTITY_UNIT_CHANGED'])

    def test_schema_only_sources_cannot_prove_raw_file_authenticity(self):
        result = self.check()
        self.assertFalse(result['summary']['training_ready'])
        self.assertIn('manual source evidence', result['summary']['limitation'])

    def test_optional_forecast_missing_values_stay_missing_and_future_inputs_fail(self):
        row = dict(school_id='school', stall_id='stall', dish_id='dish', target_date='2026-10-13',
            meal_period='lunch', prediction_cutoff_at='2026-10-13T08:00:00+08:00',
            available_at='2026-10-13T07:00:00+08:00', forecast_temperature='', source_id='plan')
        sources = [dict(source_id='plan', authorization_reference='permit',
            permitted_use='model_features', provenance_status='verified')]
        valid = admission.validate_forecasts([row], sources)
        self.assertEqual('', valid['accepted'][0]['forecast_temperature'])
        invalid = admission.validate_forecasts([dict(row, available_at='2026-10-13T08:01:00+08:00')], sources)
        self.assertIn('FEATURES_AFTER_CUTOFF', invalid['quarantined'][0]['reason_codes'])

    def test_forecast_cannot_use_weather_issued_after_cutoff(self):
        row = dict(school_id='school', stall_id='stall', dish_id='dish', target_date='2026-10-13',
            meal_period='lunch', prediction_cutoff_at='2026-10-13T08:00:00+08:00',
            available_at='2026-10-13T07:00:00+08:00', forecast_temperature='20',
            forecast_issued_at='2026-10-13T09:00:00+08:00', source_id='weather')
        result = admission.validate_forecasts([row], [{'source_id': 'weather',
            'authorization_reference': 'permit', 'permitted_use': 'model_features',
            'provenance_status': 'verified'}])
        self.assertEqual([], result['accepted'])
        self.assertIn('WEATHER_AFTER_CUTOFF', result['quarantined'][0]['reason_codes'])


if __name__ == '__main__':
    unittest.main()
