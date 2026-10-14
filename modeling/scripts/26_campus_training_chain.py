"""Reconstructible campus training chain; no derived or simulated labels accepted."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ['school_id', 'stall_id', 'dish_id', 'business_date', 'meal_period']
FEATURES = ['dow', 'lag1', 'lag7', 'mean7', 'weekday_mean4']


def training_rows(rows):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=KEY + FEATURES + ['date', 'target', 'supply_censored'])
    for field in ['label_origin', 'supply_censored']:
        if field not in frame:
            frame[field] = 'unknown' if field == 'label_origin' else True
    frame['supply_censored'] = frame['supply_censored'].map(
        lambda v: str(v).lower() in {'true', '1', 'yes'})
    frame = frame[frame.label_origin.eq('observed') & ~frame.supply_censored].copy()
    frame['date'] = pd.to_datetime(frame.business_date, errors='coerce').dt.normalize()
    frame['target'] = pd.to_numeric(frame.net_sold_qty, errors='coerce')
    frame = frame[frame.date.notna() & frame.target.notna() & np.isfinite(frame.target)]
    frame = frame[frame.target.ge(0)].copy()
    return frame.sort_values(KEY[:3] + ['date', 'meal_period']).reset_index(drop=True)


def _entity_key(frame):
    return frame['school_id'].astype(str) + '|' + frame['stall_id'].astype(str) + '|' + frame['dish_id'].astype(str) + '|' + frame['meal_period'].astype(str)


def build_features(rows):
    frame = training_rows(rows) if isinstance(rows, list) else training_rows(rows.to_dict('records'))
    if frame.empty:
        return frame
    frame['_entity'] = _entity_key(frame)
    # Reindex each entity to calendar dates so lag7 means date minus seven days.
    parts = []
    for entity, group in frame.groupby('_entity', sort=False):
        if group.date.duplicated().any():
            raise ValueError('DUPLICATE_ENTITY_DATE')
        group = group.sort_values('date').set_index('date')
        full = group.reindex(pd.date_range(group.index.min(), group.index.max(), freq='D'))
        full['_entity'] = entity
        for field in KEY:
            if field in group:
                full[field] = group[field].reindex(full.index)
        full['target'] = group['target'].reindex(full.index)
        full['dow'] = full.index.dayofweek
        prior = full['target'].shift(1)
        full['lag1'] = prior
        full['lag7'] = full['target'].shift(7)
        full['mean7'] = prior.rolling(7, min_periods=7).mean()
        # Four prior observations of the same weekday; no current target leakage.
        full['weekday_mean4'] = pd.concat([full['target'].shift(n) for n in (7, 14, 21, 28)], axis=1).mean(axis=1, skipna=False)
        full['date'] = full.index
        parts.append(full.reset_index(drop=True))
    result = pd.concat(parts, ignore_index=True)
    result = result[result['target'].notna()].copy()
    result = result.reset_index(drop=True)
    return result


def make_splits(data):
    if data.empty:
        return {name: data.copy() for name in ('fit', 'tune', 'calibration', 'test')}
    dates = np.array(sorted(pd.to_datetime(data.date).dt.normalize().unique()))
    if len(dates) < 8:
        raise ValueError('INSUFFICIENT_DISTINCT_DATES_FOR_FROZEN_SPLIT')
    cuts = [dates[max(0, int(len(dates) * ratio) - 1)] for ratio in (.60, .75, .85)]
    frame = data.copy()
    frame['date'] = pd.to_datetime(frame.date).dt.normalize()
    return {'fit': frame[frame.date <= cuts[0]],
        'tune': frame[(frame.date > cuts[0]) & (frame.date <= cuts[1])],
        'calibration': frame[(frame.date > cuts[1]) & (frame.date <= cuts[2])],
        'test': frame[frame.date > cuts[2]]}


def _baseline(train, evaluation):
    history = train.groupby('dow')['target'].mean()
    return evaluation['dow'].map(history).fillna(train['target'].mean())


def run_chain(rows, min_rows=100):
    admitted = training_rows(rows)
    report = {'input_rows': len(rows), 'admitted_rows': int(len(admitted)),
        'training_ready': False, 'status': 'INSUFFICIENT_ROWS', 'primary_target': 'net_sold_qty'}
    if admitted.empty:
        report['status'] = 'NO_ADMITTED_ROWS'
        return report
    featured = build_features(admitted).dropna(subset=FEATURES)
    report['feature_rows'] = int(len(featured))
    if len(featured) < min_rows:
        report['status'] = 'INSUFFICIENT_FEATURE_ROWS'
        return report
    splits = make_splits(featured)
    report['split_rows'] = {name: int(len(value)) for name, value in splits.items()}
    if any(splits[name].empty for name in ('fit', 'tune', 'calibration', 'test')):
        report['status'] = 'EMPTY_FROZEN_SPLIT'
        return report
    prediction = _baseline(splits['fit'], splits['test'])
    report['baseline_test_mae'] = float(np.mean(np.abs(prediction - splits['test'].target)))
    report['status'] = 'BASELINE_READY'
    report['training_ready'] = False
    report['limitation'] = 'Offline baseline only; historical availability, authorization and production acceptance remain unverified.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accepted', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--min-rows', type=int, default=100)
    args = parser.parse_args()
    args.output.mkdir(parents=False, exist_ok=False)
    frame = pd.read_csv(args.accepted)
    report = run_chain(frame.to_dict('records'), args.min_rows)
    report.update({'input_sha256': hashlib.sha256(args.accepted.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'feature_contract': FEATURES, 'online_model_overwrite': False})
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
