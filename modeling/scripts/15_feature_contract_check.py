"""Check that the Java inference metadata and Python training contract agree."""
from pathlib import Path
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
JAVA_DIR = ROOT / "src/main/resources/modeling"
JAVA_META = JAVA_DIR / "campus_feature_cols.json"
EXPORT_SCRIPT = ROOT / "deploy/10_export_campus_model.py"
PROCESSED = ROOT / "modeling/data/02_processed/finetune_uwaste.parquet"
MODEL = JAVA_DIR / "lgbm_campus_model.txt"

def exported_features():
    tree = ast.parse(EXPORT_SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FEATS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("FEATS not found in campus export script")

def model_features():
    line = next(line for line in MODEL.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.startswith("feature_names="))
    return line.removeprefix("feature_names=").split()

def main():
    java = json.loads(JAVA_META.read_text(encoding="utf-8"))["features"]
    exported = exported_features()
    model = model_features()
    processed = []
    if PROCESSED.exists():
        import pandas as pd
        processed = list(pd.read_parquet(PROCESSED, columns=exported).columns)
    result = {
        "python_features": exported,
        "java_features": java,
        "model_file_features": model,
        "processed_features": processed,
        "same_order": java == exported == model == processed,
        "python_target_transform": "log1p(sold_qty)",
        "java_target_transform": json.loads(JAVA_META.read_text(encoding="utf-8")).get("target_transform"),
        "model_sha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        "export_script_sha256": hashlib.sha256(EXPORT_SCRIPT.read_bytes()).hexdigest(),
        "status": "pass" if java == exported == model == processed else "fail",
        "scope": "exporter/metadata/model field names and order; processed column availability only",
        "feature_values_verified": False,
        "note": "Requested parquet columns are projected into contract order; this does not verify stored order, online values or inference parity. See independent CampusInferenceParityTests.",
    }
    out = ROOT / "modeling/data/03_output/FEATURE_CONTRACT_VERIFICATION.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["same_order"] else 1)

if __name__ == "__main__":
    main()
