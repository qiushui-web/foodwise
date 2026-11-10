import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foodwise_ml import manifest as m  # noqa: E402


def _valid_doc(**overrides):
    base = m.build_manifest(
        base_dir=Path(overrides.pop("base_dir")),
        model_file="m.txt",
        feature_file="f.json",
        data_file=Path(overrides.pop("data_file")),
        dataset="unit-test",
        model_version="test-1",
    )
    base.update(overrides)
    return base


class ManifestContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.root = root
        (root / "m.txt").write_text("tree=0\n", encoding="utf-8")
        (root / "f.json").write_text('{"features": ["a"]}', encoding="utf-8")
        data = root / "d.csv"
        data.write_text("sold\n1\n2\n3\n", encoding="utf-8")
        self.data = data

    def tearDown(self):
        self._tmp.cleanup()

    def test_generated_manifest_is_valid_and_hash_bound(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        self.assertEqual(m.validate_manifest(doc), [])
        self.assertEqual(m.verify_artifact_hashes(doc, self.root), [])
        self.assertEqual(doc["data"]["rows"], 3)
        self.assertEqual(doc["metrics"]["picp90"], None)
        self.assertEqual(doc["calibration"]["status"], "uncalibrated")

    def test_artifact_hash_mismatch_is_detected(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        (self.root / "m.txt").write_text("tree=1\n", encoding="utf-8")
        self.assertIn("ARTIFACT_HASH_MISMATCH:model_file", m.verify_artifact_hashes(doc, self.root))

    def test_missing_key_is_rejected(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc.pop("metrics")
        self.assertTrue(any(err.startswith("MISSING_KEYS") for err in m.validate_manifest(doc)))

    def test_calibrated_without_coverage_is_rejected(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["calibration"] = {
            "method": "cqr+aci",
            "status": "calibrated",
            "alpha": 0.1,
            "artifact": "c.json",
            "artifact_sha256": "a" * 64,
            "picp90": None,
        }
        self.assertIn("CALIBRATED_WITHOUT_COVERAGE", m.validate_manifest(doc))

    def test_calibrated_with_coverage_is_accepted(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        (self.root / "c.json").write_text("{}", encoding="utf-8")
        digest = m.sha256_file(self.root / "c.json")
        doc["calibration"] = {
            "method": "cqr+aci",
            "status": "calibrated",
            "alpha": 0.1,
            "artifact": "c.json",
            "artifact_sha256": digest,
            "picp90": 0.9,
        }
        doc["model_kind"] = "calibrated-quantile"
        doc["quantiles"] = [0.05, 0.95]
        (self.root / "q05.txt").write_text("tree=0\n", encoding="utf-8")
        (self.root / "q95.txt").write_text("tree=0\n", encoding="utf-8")
        doc["quantile_models"] = {
            "0.05": {"file": "q05.txt", "sha256": m.sha256_file(self.root / "q05.txt")},
            "0.95": {"file": "q95.txt", "sha256": m.sha256_file(self.root / "q95.txt")},
        }
        doc["metrics"]["picp90"] = 0.9
        self.assertEqual(m.validate_manifest(doc), [])
        self.assertEqual(m.verify_artifact_hashes(doc, self.root), [])

    def test_calibrated_kind_requires_evaluated_coverage(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["model_kind"] = "calibrated-quantile"
        doc["quantiles"] = [0.1, 0.5, 0.9]
        doc["calibration"] = {
            "method": "cqr+aci",
            "status": "calibrated",
            "alpha": 0.1,
            "artifact": "c.json",
            "artifact_sha256": "b" * 64,
            "picp90": 0.9,
        }
        self.assertIn("CALIBRATED_MODEL_WITHOUT_EVALUATION", m.validate_manifest(doc))

    def test_point_model_cannot_declare_quantiles(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["quantiles"] = [0.1, 0.9]
        self.assertIn("POINT_MODEL_WITH_QUANTILES", m.validate_manifest(doc))

    def test_quantiles_must_be_ascending_and_bounded(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["model_kind"] = "quantile"
        doc["quantiles"] = [0.9, 0.1]
        self.assertIn("QUANTILES_NOT_ASCENDING", m.validate_manifest(doc))
        doc["quantiles"] = [0.0, 1.0]
        self.assertIn("QUANTILES_OUT_OF_RANGE", m.validate_manifest(doc))

    def test_limits_must_be_present_and_meaningful(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["limits"] = []
        self.assertIn("LIMITS_MISSING", m.validate_manifest(doc))
        doc["limits"] = ["短"]
        self.assertIn("LIMITS_ENTRY_TOO_SHORT", m.validate_manifest(doc))

    def test_data_rows_must_be_positive_integer(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["data"]["rows"] = 0
        self.assertIn("DATA_ROWS_INVALID", m.validate_manifest(doc))
        doc["data"]["rows"] = 2.5
        self.assertIn("DATA_ROWS_INVALID", m.validate_manifest(doc))

    def test_bad_sha256_is_rejected(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["model_sha256"] = "not-a-hash"
        self.assertIn("SHA256_INVALID:model_sha256", m.validate_manifest(doc))

    def test_assert_valid_raises_with_reason(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["schema_version"] = 1
        with self.assertRaisesRegex(m.ManifestError, "SCHEMA_VERSION_UNSUPPORTED"):
            m.assert_valid(doc)

    def test_refuses_to_build_from_missing_artifacts(self):
        with self.assertRaisesRegex(m.ManifestError, "MODEL_FILE_MISSING"):
            m.build_manifest(
                base_dir=self.root,
                model_file="absent.txt",
                feature_file="f.json",
                data_file=self.data,
                dataset="unit-test",
                model_version="test-1",
            )

    def test_interval_model_requires_quantile_models(self):
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["model_kind"] = "calibrated-quantile"
        doc["quantiles"] = [0.05, 0.95]
        doc["calibration"] = {
            "method": "cqr+aci",
            "status": "calibrated",
            "alpha": 0.1,
            "artifact": "c.json",
            "artifact_sha256": "c" * 64,
            "picp90": 0.9,
        }
        doc["metrics"]["picp90"] = 0.9
        self.assertIn("QUANTILE_MODELS_MISSING", m.validate_manifest(doc))

    def test_quantile_levels_must_match_declared_quantiles(self):
        (self.root / "q05.txt").write_text("tree=0\n", encoding="utf-8")
        (self.root / "q95.txt").write_text("tree=0\n", encoding="utf-8")
        doc = _valid_doc(base_dir=self.root, data_file=self.data)
        doc["model_kind"] = "quantile"
        doc["quantiles"] = [0.05, 0.90]
        doc["quantile_models"] = {
            "0.05": {"file": "q05.txt", "sha256": m.sha256_file(self.root / "q05.txt")},
            "0.95": {"file": "q95.txt", "sha256": m.sha256_file(self.root / "q95.txt")},
        }
        self.assertIn("QUANTILE_LEVELS_MISMATCH", m.validate_manifest(doc))

    def test_quantile_artifact_hash_mismatch_is_detected(self):
        (self.root / "q05.txt").write_text("tree=0\n", encoding="utf-8")
        (self.root / "q95.txt").write_text("tree=0\n", encoding="utf-8")
        doc = m.build_manifest(
            base_dir=self.root,
            model_file="m.txt",
            feature_file="f.json",
            data_file=self.data,
            dataset="unit-test",
            model_version="test-1",
            model_kind="quantile",
            quantiles=[0.05, 0.95],
            quantile_models={"0.05": "q05.txt", "0.95": "q95.txt"},
        )
        self.assertEqual(m.validate_manifest(doc), [])
        self.assertEqual(m.verify_artifact_hashes(doc, self.root), [])
        (self.root / "q95.txt").write_text("tree=1\n", encoding="utf-8")
        self.assertIn("ARTIFACT_HASH_MISMATCH:quantile:0.95", m.verify_artifact_hashes(doc, self.root))


if __name__ == "__main__":
    unittest.main()