"""Freeze native LightGBM predictions for the Java inference contract test.

This verifies inference on supplied finite vectors, NOT online feature building
or the observational validity of the derived training labels.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]


def main():
    model_path = ROOT/'src/main/resources/modeling/lgbm_campus_model.txt'
    model_text = model_path.read_text(encoding='utf-8')
    model = lgb.Booster(model_str=model_text)
    features = model.feature_name()
    data = pd.read_parquet(ROOT/'modeling/data/02_processed/finetune_uwaste.parquet', columns=features)
    positions = np.linspace(0, len(data)-1, 32, dtype=int)
    samples = data.iloc[positions].copy().reset_index(drop=True)
    samples.loc[len(samples)] = np.zeros(len(features))
    samples.loc[len(samples)] = np.full(len(features), 400.)
    if not np.isfinite(samples.to_numpy()).all():
        raise ValueError('This fixture only covers finite vectors')
    raw = model.predict(samples, raw_score=True)
    samples['expected_raw'] = raw
    samples['expected_prediction'] = np.clip(np.expm1(raw), 1., 400.)
    output = ROOT/'src/test/resources/modeling'
    output.mkdir(parents=True, exist_ok=True)
    samples.to_csv(output/'campus_native_predictions.csv', index=False, float_format='%.17g')
    metadata = {'model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
                'rows': len(samples), 'absolute_tolerance': 1e-8,
                'feature_names': features, 'source_positions': positions.tolist(),
                'lightgbm_version': lgb.__version__,
                'scope': 'finite-vector inference only; feature construction and missing values not certified'}
    (output/'campus_native_model.sha256').write_text(metadata['model_sha256']+'\n', encoding='ascii')
    (output/'campus_native_predictions.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
