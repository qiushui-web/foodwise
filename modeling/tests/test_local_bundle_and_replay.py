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

    def test_replay_uses_latest_revision_visible_at_cutoff_only(self):
        observations = pd.DataFrame([
            {'observation_id': 'a', 'available_at': '2026-01-01T08:00:00Z', 'revision_at': '2026-01-01T08:00:00Z', 'target': 10},
            {'observation_id': 'a', 'available_at': '2026-01-03T08:00:00Z', 'revision_at': '2026-01-03T08:00:00Z', 'target': 99},
            {'observation_id': 'b', 'available_at': '2026-01-01T08:00:00Z', 'revision_at': '2026-01-01T08:00:00Z', 'target': 4},
        ])
        visible = replay.visible_at(observations, '2026-01-02T00:00:00Z')
        self.assertEqual(['a', 'b'], visible.observation_id.tolist())
        self.assertEqual([10, 4], visible.target.tolist())

    def test_calibration_is_independent_and_returns_explicit_radius(self):
        calibration = pd.DataFrame({'actual': [10, 12, 8, 20, 15], 'prediction': [9, 10, 10, 18, 12]})
        result = replay.calibrate_residual_interval(calibration, .8)
        self.assertEqual(5, result['rows'])
        self.assertGreaterEqual(result['radius'], 3)
        self.assertIn('drift', result['warning'])


if __name__ == '__main__':
    unittest.main()
