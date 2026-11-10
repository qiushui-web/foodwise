"""Reconstructible campus training chain; no derived or simulated labels accepted."""
import argparse
import importlib.util
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
    if {'observation_id', 'available_at', 'revision_at'}.issubset(frame.columns):
        frame['available_at'] = pd.to_datetime(frame['available_at'], utc=True, errors='coerce')
        frame['revision_at'] = pd.to_datetime(frame['revision_at'], utc=True, errors='coerce')
        frame = frame.dropna(subset=['observation_id', 'available_at', 'revision_at'])
        frame = frame.sort_values(['observation_id', 'revision_at'])
        frame = frame.drop_duplicates('observation_id', keep='last')
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


def build_replay_features(rows, forecasts):
    """Replay each recorded forecast; final outcomes are labels, never feature inputs."""
    spec = importlib.util.spec_from_file_location('campus_availability', Path(__file__).with_name('28_availability_revision_interval.py'))
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    raw = pd.DataFrame(rows)
    final = training_rows(rows)
    if final.empty:
        return final
    if not {'observation_id', 'available_at', 'revision_at'}.issubset(raw.columns):
        raise ValueError('MISSING_OBSERVATION_AVAILABILITY')
    truth = {tuple(str(row[field]) for field in KEY): row for row in final.to_dict('records')}
    output, seen = [], set()
    for forecast in forecasts:
        target = pd.Timestamp(forecast['target_date']).normalize()
        cutoff = pd.Timestamp(forecast['prediction_cutoff_at'])
        if cutoff.tzinfo is None:
            raise ValueError('FORECAST_CUTOFF_TIMEZONE_REQUIRED')
        if cutoff.tz_convert('Asia/Shanghai').date() > target.date():
            raise ValueError('FORECAST_CUTOFF_AFTER_TARGET')
        key = tuple(str(forecast.get(field, '')) if field != 'business_date' else str(target.date()) for field in KEY)
        if key in seen:
            raise ValueError('DUPLICATE_FORECAST_ENTITY_DATE')
        seen.add(key)
        if key not in truth:
            continue
        visible = training_rows(replay.visible_at(raw, cutoff).to_dict('records'))
        history = visible[visible.date.lt(target)].copy()
        for field in ('school_id', 'stall_id', 'dish_id', 'meal_period'):
            history = history[history[field].astype(str).eq(str(forecast[field]))]
        if history.date.duplicated().any():
            raise ValueError('DUPLICATE_ENTITY_DATE')
        series = history.set_index('date')['target']
        prior = series.reindex(pd.date_range(target-pd.Timedelta(days=7), periods=7))
        weekdays = series.reindex([target-pd.Timedelta(days=n) for n in (7, 14, 21, 28)])
        output.append(dict(truth[key], dow=target.dayofweek,
            lag1=series.get(target-pd.Timedelta(days=1), np.nan),
            lag7=series.get(target-pd.Timedelta(days=7), np.nan),
            mean7=prior.mean() if prior.notna().all() else np.nan,
            weekday_mean4=weekdays.mean() if weekdays.notna().all() else np.nan,
            prediction_cutoff_at=cutoff.tz_convert('UTC').isoformat()))
    return pd.DataFrame(output, columns=list(final.columns)+[f for f in FEATURES if f not in final.columns]+['prediction_cutoff_at'])


def _baseline(train, evaluation):
    history = train.groupby('dow')['target'].mean()
    return evaluation['dow'].map(history).fillna(train['target'].mean())


def _lgbm_predictions(train, evaluation):
    """Fit the bounded candidate only after the replayed, frozen split exists."""
    from lightgbm import LGBMRegressor
    model = LGBMRegressor(
        objective='regression_l1', n_estimators=120, learning_rate=0.04,
        num_leaves=15, max_depth=5, min_child_samples=12,
        reg_alpha=0.2, reg_lambda=0.5, random_state=20261015,
        n_jobs=1, verbosity=-1)
    model.fit(train[FEATURES], train['target'])
    return model, np.maximum(0, model.predict(evaluation[FEATURES]))


def _mae(actual, prediction):
    return float(np.mean(np.abs(np.asarray(actual, dtype=float) - np.asarray(prediction, dtype=float))))


def _interval_metrics(actual, prediction, interval):
    radius = float(interval['radius'])
    error = np.abs(np.asarray(actual, dtype=float) - np.asarray(prediction, dtype=float))
    return {'coverage': float(np.mean(error <= radius)), 'mean_width': 2 * radius,
            'rows': int(len(error)), 'descriptive_only': True}


def run_chain(rows, min_rows=100, forecasts=None):
    admitted = training_rows(rows)
    report = {'input_rows': len(rows), 'admitted_rows': int(len(admitted)),
        'training_ready': False, 'status': 'INSUFFICIENT_ROWS', 'primary_target': 'net_sold_qty',
        'availability_replay': False, 'source_verified': False,
        'candidate_training': False, 'independent_calibration': False}
    if admitted.empty:
        report['status'] = 'NO_ADMITTED_ROWS'
        return report
    if not forecasts:
        report['status'] = 'MISSING_FORECAST_SNAPSHOTS'
        return report
    featured = build_replay_features(rows, forecasts).dropna(subset=FEATURES)
    report['availability_replay'] = True
    report['feature_rows'] = int(len(featured))
    if len(featured) < min_rows:
        report['status'] = 'INSUFFICIENT_FEATURE_ROWS'
        return report
    splits = make_splits(featured)
    report['split_rows'] = {name: int(len(value)) for name, value in splits.items()}
    if any(splits[name].empty for name in ('fit', 'tune', 'calibration', 'test')):
        report['status'] = 'EMPTY_FROZEN_SPLIT'
        return report
    # Every fitted label must already be available before the first validation forecast.
    first_validation_cutoff = pd.to_datetime(splits['tune'].prediction_cutoff_at, utc=True).min()
    if any(pd.to_datetime(splits['fit'][field], utc=True).ge(first_validation_cutoff).any()
           for field in ('available_at', 'revision_at')):
        report['status'] = 'FIT_LABEL_REVISED_AFTER_VALIDATION_CUTOFF'
        return report
    baseline_tune = _baseline(splits['fit'], splits['tune'])
    first_calibration_cutoff = pd.to_datetime(splits['calibration'].prediction_cutoff_at, utc=True).min()
    fit_tune = pd.concat([splits['fit'], splits['tune']])
    if any(pd.to_datetime(fit_tune[field], utc=True).ge(first_calibration_cutoff).any()
           for field in ('available_at', 'revision_at')):
        report['status'] = 'TRAIN_LABEL_UNAVAILABLE_BEFORE_CALIBRATION'
        return report
    if len(splits['calibration']) < 9:
        report['status'] = 'INSUFFICIENT_CALIBRATION_ROWS_FOR_NOMINAL'
        return report
    first_test_cutoff = pd.to_datetime(splits['test'].prediction_cutoff_at, utc=True).min()
    if any(pd.to_datetime(splits['calibration'][field], utc=True).ge(first_test_cutoff).any()
           for field in ('available_at', 'revision_at')):
        report['status'] = 'CALIBRATION_LABEL_UNAVAILABLE_BEFORE_TEST'
        return report
    baseline_test = _baseline(fit_tune, splits['test'])
    candidates = {'weekday_baseline': {'tune_mae': _mae(splits['tune'].target, baseline_tune)}}
    model, lgbm_tune = _lgbm_predictions(splits['fit'], splits['tune'])
    candidates['lightgbm_l1'] = {'tune_mae': _mae(splits['tune'].target, lgbm_tune)}
    selected = min(candidates, key=lambda name: candidates[name]['tune_mae'])
    # Refit the selected point model on fit+tune only. Calibration and test remain untouched.
    train_until_calibration = pd.concat([splits['fit'], splits['tune']], ignore_index=True)
    if selected == 'lightgbm_l1':
        selected_model, calibration_prediction = _lgbm_predictions(train_until_calibration, splits['calibration'])
        test_prediction = np.maximum(0, selected_model.predict(splits['test'][FEATURES]))
    else:
        selected_model = None
        calibration_prediction = _baseline(train_until_calibration, splits['calibration'])
        test_prediction = _baseline(train_until_calibration, splits['test'])
    calibration_frame = pd.DataFrame({'actual': splits['calibration'].target.to_numpy(),
                                      'prediction': np.asarray(calibration_prediction)})
    replay = importlib.util.spec_from_file_location('availability_interval', Path(__file__).with_name('28_availability_revision_interval.py'))
    interval_module = importlib.util.module_from_spec(replay)
    replay.loader.exec_module(interval_module)
    intervals = {str(nominal): interval_module.calibrate_residual_interval(calibration_frame, nominal)
                 for nominal in (0.8, 0.9)}
    interval_test_metrics = {nominal: _interval_metrics(splits['test'].target, test_prediction, intervals[str(nominal)])
                             for nominal in (0.8, 0.9)}
    report.update({
        'candidate_training': True,
        'candidate_metrics': candidates,
        'selected_model': selected,
        'calibration': intervals,
        'test_interval_metrics': interval_test_metrics,
        'independent_calibration': True,
        'test_mae': _mae(splits['test'].target, test_prediction),
        'baseline_test_mae': _mae(splits['test'].target, baseline_test),
        'test_rows': int(len(splits['test'])),
        'status': 'CANDIDATES_READY',
        'training_ready': False,
        'limitation': 'Offline candidate evaluation only; source verification, entity validation, parity and production acceptance remain separate gates.'
    })
    report['_selected_model'] = selected_model
    report['_baseline_parameters'] = {'weekday_means': {str(k): float(v) for k, v in train_until_calibration.groupby('dow').target.mean().items()},
                                      'fallback': float(train_until_calibration.target.mean())}
    report['_split_manifest'] = pd.concat([part.assign(split=name) for name, part in splits.items()], ignore_index=True)
    report['_calibration_predictions'] = calibration_frame
    report['_test_predictions'] = pd.DataFrame({
        'date': splits['test'].date.astype(str),
        'school_id': splits['test'].school_id.astype(str),
        'stall_id': splits['test'].stall_id.astype(str),
        'dish_id': splits['test'].dish_id.astype(str),
        'meal_period': splits['test'].meal_period.astype(str),
        'actual': splits['test'].target.to_numpy(),
        'prediction': np.asarray(test_prediction)
    })
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accepted', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--min-rows', type=int, default=100)
    parser.add_argument('--forecasts', type=Path, help='Admitted historical prediction snapshots, one per entity/date/meal')
    args = parser.parse_args()
    args.output.mkdir(parents=False, exist_ok=False)
    frame = pd.read_csv(args.accepted)
    forecasts = pd.read_csv(args.forecasts).to_dict('records') if args.forecasts else None
    report = run_chain(frame.to_dict('records'), args.min_rows, forecasts)
    report.update({'input_sha256': hashlib.sha256(args.accepted.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'feature_contract': FEATURES, 'online_model_overwrite': False})
    if args.forecasts:
        report['forecast_sha256'] = hashlib.sha256(args.forecasts.read_bytes()).hexdigest()
    selected_model = report.pop('_selected_model', None)
    baseline_parameters = report.pop('_baseline_parameters', None)
    split_manifest = report.pop('_split_manifest', None)
    calibration_predictions = report.pop('_calibration_predictions', None)
    test_predictions = report.pop('_test_predictions', None)
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if test_predictions is not None:
        test_predictions.to_csv(args.output / 'test_predictions.csv', index=False)
    if selected_model is not None:
        (args.output / 'candidate_model.txt').write_text(selected_model.booster_.model_to_string(), encoding='utf-8')
    if split_manifest is not None:
        split_manifest.to_csv(args.output / 'split_manifest.csv', index=False)
        calibration_predictions.to_csv(args.output / 'calibration_predictions.csv', index=False)
        model_path = args.output / ('candidate_model.txt' if selected_model is not None else 'baseline_model.json')
        if selected_model is None:
            model_path.write_text(json.dumps(baseline_parameters, sort_keys=True), encoding='utf-8')
        feature_path = args.output / 'features.json'
        feature_path.write_text(json.dumps(FEATURES), encoding='utf-8')
        (args.output / 'calibration.json').write_text(json.dumps({
            'selected_model': report['selected_model'], 'calibration': report['calibration'],
            'model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
            'feature_sha256': hashlib.sha256(feature_path.read_bytes()).hexdigest(),
            'source_verified': False, 'production_approved': False
        }, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
