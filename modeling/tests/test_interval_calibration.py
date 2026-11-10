import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foodwise_ml import intervals as iv  # noqa: E402


class ConformalTests(unittest.TestCase):
    def test_conformal_quantile_matches_finite_sample_rank(self):
        scores = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        self.assertEqual(iv.conformal_quantile(scores, 0.1), 9)  # ceil(10*0.9)=9
        self.assertEqual(iv.conformal_quantile(list(range(1, 100)), 0.1), 90)  # ceil(100*0.9)=90

    def test_conformal_quantile_is_conservative_for_tiny_samples(self):
        self.assertEqual(iv.conformal_quantile([0.5, 1.5], 0.1), 1.5)

    def test_conformity_scores_flag_miss_on_both_sides(self):
        scores = iv.conformity_scores([10, 5, 20], [8, 6, 12], [12, 9, 18])
        self.assertEqual(scores.tolist(), [-2.0, 1.0, 2.0])

    def test_conformity_rejects_crossed_interval(self):
        with self.assertRaisesRegex(ValueError, "UPPER_BELOW_LOWER"):
            iv.conformity_scores([1], [5], [3])

    def test_shrink_pulls_small_strata_to_global(self):
        self.assertAlmostEqual(iv.shrink_offset(10.0, 30.0, 0, 20.0), 10.0)
        self.assertAlmostEqual(iv.shrink_offset(10.0, 30.0, 20, 20.0), 20.0)
        self.assertAlmostEqual(iv.shrink_offset(10.0, 30.0, 5, 20.0), 14.0)
        self.assertAlmostEqual(iv.shrink_offset(10.0, 30.0, 10_000, 20.0), 30.0, places=1)

    def test_apply_offset_never_inverts_interval(self):
        lo, hi = iv.apply_offset([10.0], [12.0], 5.0)
        self.assertEqual(lo.tolist(), [5.0])
        self.assertEqual(hi.tolist(), [17.0])
        lo, hi = iv.apply_offset([10.0], [12.0], -100.0)
        self.assertTrue(np.all(lo <= hi))


class ACITests(unittest.TestCase):
    def test_miss_lowers_alpha_and_widens_next_interval(self):
        aci = iv.ACIController(alpha_target=0.1, mode="fixed", gamma0=0.01)
        before = aci.alpha_current
        after = aci.update(covered=False)
        self.assertLess(after, before)
        self.assertEqual(aci.errors, [1])

    def test_cover_raises_alpha(self):
        aci = iv.ACIController(alpha_target=0.1, mode="fixed", gamma0=0.01)
        after = aci.update(covered=True)
        self.assertGreater(after, 0.1)
        self.assertEqual(aci.errors, [0])

    def test_alpha_is_clamped(self):
        aci = iv.ACIController(alpha_target=0.1, mode="fixed", gamma0=10.0)
        for _ in range(20):
            aci.update(covered=True)
        self.assertLessEqual(aci.alpha_current, 0.5)
        self.assertGreaterEqual(aci.alpha_current, 0.01)

    def test_decay_gamma_shrinks_over_time(self):
        aci = iv.ACIController(alpha_target=0.1, gamma0=0.01, gamma_min=0.002)
        first = aci.gamma()
        aci.errors = [0] * 100
        self.assertLess(aci.gamma(), first)
        self.assertGreaterEqual(aci.gamma(), 0.002)

    def test_roundtrip_serialization_keeps_history(self):
        aci = iv.ACIController(alpha_target=0.1)
        aci.update(True)
        aci.update(False)
        restored = iv.ACIController.from_dict(aci.to_dict())
        self.assertEqual(restored.errors, [0, 1])
        self.assertAlmostEqual(restored.alpha_current, aci.alpha_current)
        self.assertEqual(restored.t, 2)

    def test_rejects_bad_target(self):
        with self.assertRaisesRegex(ValueError, "ALPHA_TARGET_OUT_OF_RANGE"):
            iv.ACIController(alpha_target=1.5)


class IntervalMetricTests(unittest.TestCase):
    def test_picp_and_pinaw(self):
        y = [10, 12, 20]
        lo = [8, 11, 15]
        hi = [12, 13, 19]
        self.assertAlmostEqual(iv.picp(y, lo, hi), 2 / 3)
        self.assertAlmostEqual(iv.pinaw(y, lo, hi), np.mean([4, 2, 4]) / 10)

    def test_winkler_penalizes_misses_harder_than_width(self):
        y = [10]
        self.assertAlmostEqual(iv.winkler_score(y, [9], [11], 0.1), 2.0)
        self.assertAlmostEqual(iv.winkler_score([12], [9], [11], 0.1), 2.0 + 20 * 1.0)
        self.assertAlmostEqual(iv.winkler_score([8], [9], [11], 0.1), 2.0 + 20 * 1.0)

    def test_interval_report_is_self_consistent(self):
        report = iv.interval_report([10, 12, 20], [8, 11, 15], [12, 13, 19], 0.1)
        self.assertEqual(report["n"], 3)
        self.assertAlmostEqual(report["picp"], 2 / 3)
        self.assertIn("winkler", report)


class CalibrationArtifactTests(unittest.TestCase):
    def _artifact(self, **overrides):
        payload = dict(
            alpha=0.1,
            global_offset=12.5,
            strata={"1|1": {"offset": 9.0, "n": 93}},
            kappa=20.0,
            model_sha256="a" * 64,
            feature_sha256="b" * 64,
            split={"train_rows": 2000, "calib_rows": 300, "test_rows": 300},
        )
        payload.update(overrides)
        return iv.build_calibration_artifact(**payload)

    def test_valid_artifact_has_no_errors(self):
        doc = self._artifact()
        self.assertEqual(iv.validate_calibration_artifact(doc), [])
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["aci"]["alpha_current"], 0.1)

    def test_rejects_unknown_schema(self):
        doc = self._artifact()
        doc["schema_version"] = 99
        self.assertIn("CALIBRATION_SCHEMA_UNSUPPORTED:99", iv.validate_calibration_artifact(doc))

    def test_rejects_unbound_model(self):
        doc = self._artifact()
        doc["model_sha256"] = "not-a-hash"
        self.assertIn("CALIBRATION_BINDING_INVALID:model_sha256", iv.validate_calibration_artifact(doc))

    def test_rejects_bad_stratum(self):
        doc = self._artifact()
        doc["strata"]["1|1"]["n"] = 0
        self.assertIn("STRATUM_ROWS_INVALID:1|1", iv.validate_calibration_artifact(doc))

    def test_rejects_missing_split(self):
        doc = self._artifact()
        doc["split"] = {}
        self.assertIn("CALIBRATION_SPLIT_MISSING", iv.validate_calibration_artifact(doc))

    def test_builder_refuses_invalid_payload(self):
        with self.assertRaisesRegex(ValueError, "CALIBRATION_ALPHA_INVALID"):
            self._artifact(alpha=1.2)


if __name__ == "__main__":
    unittest.main()