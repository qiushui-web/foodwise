from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'modeling/data/03_output'
JAVA = ROOT / 'src/main/resources/modeling'
FILES = ['campus_backtest_report.json','campus_backtest_predictions.csv','feature_importance.csv','feature_weight_rule.csv','category_coef_table.csv','category_volatility.csv','pretrain_metrics.json']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = []
    ok = True
    for name in FILES:
        src, dst = OUT / name, JAVA / name
        same = src.exists() and dst.exists() and digest(src) == digest(dst)
        ok = ok and same
        rows.append({'file': name, 'source_exists': src.exists(), 'java_exists': dst.exists(), 'sha_equal': same})
    result = {'verified': ok, 'files': rows, 'java_model_file_present': (JAVA/'lgbm_campus_model.txt').exists(), 'feature_meta_present': (JAVA/'campus_feature_cols.json').exists()}
    (OUT/'JAVA_ARTIFACT_VERIFICATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
