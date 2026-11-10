import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "modeling" / "scripts" / "51_competition_validation.py"
spec = importlib.util.spec_from_file_location("competition_validation", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

PUBLIC_SCRIPT = ROOT / "modeling" / "scripts" / "52_run_public_data_validation.py"
public_spec = importlib.util.spec_from_file_location("public_data_validation", PUBLIC_SCRIPT)
public_module = importlib.util.module_from_spec(public_spec)
assert public_spec.loader is not None
public_spec.loader.exec_module(public_module)


class CompetitionValidationTests(unittest.TestCase):
    def test_supported_units_keep_raw_and_converted_quantities(self):
        portion = module.convert_quantity(2, "份")
        self.assertEqual(portion["canonical_unit"], "portion")
        self.assertEqual(portion["canonical_qty"], 2.0)
        piece = module.convert_quantity(3, "个")
        self.assertEqual(piece["canonical_unit"], "piece")
        self.assertEqual(piece["canonical_qty"], 3.0)
        kg = module.convert_quantity(2.5, "公斤")
        self.assertEqual(kg["canonical_unit"], "gram")
        self.assertEqual(kg["canonical_qty"], 2500.0)
        jin = module.convert_quantity(2, "斤")
        self.assertEqual(jin["canonical_qty"], 1000.0)
        liter = module.convert_quantity(1.5, "升")
        self.assertEqual(liter["canonical_unit"], "milliliter")
        self.assertEqual(liter["canonical_qty"], 1500.0)
        batch = module.convert_quantity(3, "锅", batch_size=40)
        self.assertEqual(batch["canonical_unit"], "portion_equivalent")
        self.assertEqual(batch["canonical_qty"], 120.0)

    def test_batch_without_sampled_factor_is_rejected(self):
        with self.assertRaises(ValueError):
            module.convert_quantity(1, "锅")

    def test_flow_accepts_complete_accounting(self):
        module.validate_flow(100, 70, 10, 15, 5, unit="份")

    def test_flow_uses_same_unit_factor_for_mass_accounting(self):
        module.validate_flow(1, 0.5, 0, 0.25, 0.25, unit="公斤", tolerance=0.01)

    def test_flow_rejects_unexplained_difference(self):
        with self.assertRaises(ValueError):
            module.validate_flow(100, 70, 10, 10, unit="份")

    def test_invalid_quantity_and_unit_are_rejected(self):
        for value in (-1, float("nan"), float("inf"), "not-a-number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.convert_quantity(value, "份")
        with self.assertRaises(ValueError):
            module.convert_quantity(1, "碗")

    def test_multi_seed_report_is_tagged_synthetic_and_reproducible_shape(self):
        report = module.run_experiment([20261102, 20261103], days=30)
        self.assertTrue(report["synthetic"])
        self.assertEqual(len(report["seeds"]), 2)
        self.assertEqual(len(report["aggregate"]), 12)
        self.assertEqual({row["runs"] for row in report["aggregate"]}, {2})
        self.assertTrue(all("regret_per_100_mean" in row for row in report["aggregate"]))

    def test_future_truth_does_not_change_earlier_preparation(self):
        simulator = module._load_simulator()
        observed = simulator.generate_demand(40, 20261102)
        changed = observed.copy()
        cutoff = pd.Timestamp(observed["business_date"].sort_values().unique()[24])
        changed.loc[changed["business_date"] > cutoff, "demand_qty"] *= 4
        baseline = module._simulate_observation_limited(observed, "model", simulator)
        altered = module._simulate_observation_limited(changed, "model", simulator)
        before = baseline[baseline["business_date"] <= cutoff]
        changed_before = altered[altered["business_date"] <= cutoff]
        self.assertEqual(before["prepared_qty"].tolist(), changed_before["prepared_qty"].tolist())
        self.assertEqual(before["predicted_qty"].tolist(), changed_before["predicted_qty"].tolist())
        # A record that sells its complete preparation is not treated as an uncensored residual.
        self.assertTrue((baseline[baseline["sold_qty"] == baseline["prepared_qty"]]["leftover_qty"] == 0).all())

    def test_public_data_runs_use_new_directory_and_refuse_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_id, created = public_module._new_output_dir(root, "run-001")
            self.assertEqual(run_id, "run-001")
            self.assertTrue(created.is_dir())
            with self.assertRaises(FileExistsError):
                public_module._new_output_dir(root, "run-001")
            with self.assertRaises(ValueError):
                public_module._new_output_dir(root, "../overwrite")


if __name__ == "__main__":
    unittest.main()
