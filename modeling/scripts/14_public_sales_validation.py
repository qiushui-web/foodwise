"""Frozen, chronological public sales experiment; never exports a campus model.

Run with modeling/.venv/Scripts/python.exe. Stores immutable timestamped runs.
Sales are scaled supplier observations, not local servings or latent demand.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ['dow', 'lag1', 'lag7', 'mean7', 'weekday_mean4']
SEED = 42


def production_cost(observed, quantity, ratio, *, unit):
    """Physical proxies require an explicitly identified, nonnegative count unit."""
    y, q = np.asarray(observed, float), np.asarray(quantity, float)
    if unit not in ('servings', 'orders') or np.any(y < 0) or np.any(q < 0):
        raise ValueError('A nonnegative physical count unit is required')
    if y.shape != q.shape or not np.isfinite(y).all() or not np.isfinite(q).all() or ratio <= 0:
        raise ValueError('Finite matching observations and positive cost ratio required')
    return float(np.sum(np.maximum(q-y, 0)+ratio*np.maximum(y-q, 0)))


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    if not len(y) or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError('Nonempty finite observations required')
    den = abs(y) + abs(p)
    return dict(mae=float(np.mean(abs(y-p))),
                wape_pct=float(100*np.sum(abs(y-p))/np.sum(abs(y))) if np.sum(abs(y)) else None,
                smape_pct=float(np.mean(np.divide(200*abs(y-p), den, out=np.zeros_like(den), where=den>0))),
                rmsle=(float(np.sqrt(np.mean((np.log1p(y)-np.log1p(p))**2)))
                       if np.all(y >= 0) and np.all(p >= 0) else None))


def build_features(raw):
    if raw.duplicated(['date', 'store']).any():
        raise ValueError('Duplicate source date/store key')
    blocks = []
    for store, df in raw.groupby('store', sort=True):
        df = df.set_index('date').sort_index().reindex(
            pd.date_range(df.date.min(), df.date.max(), freq='D'))
        df.index.name = 'date'
        df['store'] = store
        df['dow'] = df.index.dayofweek
        df['lag1'] = df.sales.shift(1)
        df['lag7'] = df.sales.shift(7)
        # Missing days stay unknown, not zero, and disqualify incomplete history.
        df['mean7'] = df.sales.shift(1).rolling(7, min_periods=7).mean()
        weekly = pd.concat([df.sales.shift(7*k) for k in range(1, 5)], axis=1)
        df['weekday_mean4'] = weekly.mean(axis=1).where(weekly.notna().all(axis=1))
        blocks.append(df.reset_index())
    return pd.concat(blocks, ignore_index=True).sort_values(['date', 'store'])


def conformal_radius(residuals, coverage=.8):
    values = np.sort(np.abs(np.asarray(residuals, float)))
    if not len(values):
        raise ValueError('Calibration observations required')
    index = min(len(values), int(np.ceil((len(values)+1)*coverage))) - 1
    return float(values[index])


def main():
    started = time.perf_counter()
    source = ROOT/'modeling/data/01_raw/reduce_foodwaste/train.csv'
    raw = pd.read_csv(source, parse_dates=['date'])
    if raw.sales.isna().any() or not np.isfinite(raw.sales).all():
        raise ValueError('Invalid sales labels')
    days = sorted(raw.date.unique())
    train_end, tune_end, calibration_end = days[int(.6*len(days))-1], days[int(.7*len(days))-1], days[int(.8*len(days))-1]
    data = build_features(raw)
    usable = data.dropna(subset=FEATURES+['sales'])
    train = usable[usable.date <= train_end]
    tune = usable[(usable.date > train_end)&(usable.date <= tune_end)]
    cal = usable[(usable.date > tune_end)&(usable.date <= calibration_end)]
    test = usable[usable.date > calibration_end].copy()
    if min(map(len, (train, tune, cal, test))) == 0:
        raise ValueError('Insufficient chronological partitions')
    model = lgb.LGBMRegressor(n_estimators=150, num_leaves=15, min_child_samples=20,
                             learning_rate=.05, random_state=SEED, n_jobs=1, verbosity=-1)
    model.fit(train[FEATURES], train.sales)
    def predict(df):
        return model.predict(df[FEATURES])
    def candidates(df):
        ml = predict(df)
        return {'last_day': df.lag1.to_numpy(), 'lag7': df.lag7.to_numpy(),
                'same_weekday_mean4': df.weekday_mean4.to_numpy(), 'mean7': df.mean7.to_numpy(),
                'lgbm': ml}
    tune_scores = {name: metrics(tune.sales, p) for name, p in candidates(tune).items()}
    # Weight selection sees tune only; calibration/test never select a model.
    weights = [0., .25, .5, .75, 1.]
    weight_scores = {str(w): metrics(tune.sales, w*predict(tune)+(1-w)*tune.mean7)['mae']
                     for w in weights}
    weight = min(weights, key=lambda w: weight_scores[str(w)])
    tune_scores['frozen_fusion'] = metrics(tune.sales, weight*predict(tune)+(1-weight)*tune.mean7)
    chosen = min(tune_scores, key=lambda name: tune_scores[name]['mae'])
    def selected(df):
        options = candidates(df)
        options['frozen_fusion'] = weight*options['lgbm']+(1-weight)*options['mean7']
        return options[chosen]
    center_cal = selected(cal)
    residuals = cal.sales.to_numpy()-center_cal
    radius = conformal_radius(residuals)
    test['pred_last_day'] = test.lag1
    test['pred_lag7'] = test.lag7
    test['pred_same_weekday_mean4'] = test.weekday_mean4
    test['pred_mean7'] = test.mean7
    test['pred_lgbm'] = predict(test)
    test['pred_frozen_fusion'] = weight*test.pred_lgbm+(1-weight)*test.pred_mean7
    test['selected_prediction'] = selected(test)
    test['interval_low'] = test.selected_prediction-radius
    test['interval_high'] = test.selected_prediction+radius
    scores = {col: metrics(test.sales, test[col]) for col in test if col.startswith('pred_')}
    scores['selected_prediction'] = metrics(test.sales, test.selected_prediction)
    grouped = []
    for store, block in test.groupby('store', sort=True):
        grouped.append({'store': str(store), 'rows': len(block),
                        'metrics': {col: metrics(block.sales, block[col]) for col in scores},
                        'coverage': float(np.mean((block.sales>=block.interval_low)&(block.sales<=block.interval_high)))})
    origins = np.array_split(sorted(test.date.unique()), 5)
    folds = []
    for i, dates in enumerate(origins, 1):
        block = test[test.date.isin(dates)]
        folds.append({'fold': i, 'start': str(pd.Timestamp(dates[0]).date()),
                      'end': str(pd.Timestamp(dates[-1]).date()), 'rows': len(block),
                      'metrics': {col: metrics(block.sales, block[col]) for col in scores}})
    # Affine/scaled labels have no physical zero, capacity or integer batch.
    # Evaluate asymmetric forecast loss only; do not call this food production.
    scenarios = []
    for ratio in (.5, 1, 2, 4):
        critical = ratio/(1+ratio)
        adjustment = float(np.quantile(residuals, critical, method='higher'))
        strategies = {'mean7': test.pred_mean7.to_numpy(),
                      'selected_point': test.selected_prediction.to_numpy(),
                      'residual_quantile': test.selected_prediction.to_numpy()+adjustment}
        for name, q in strategies.items():
            over = np.maximum(q-test.sales.to_numpy(), 0)
            under = np.maximum(test.sales.to_numpy()-q, 0)
            scenarios.append(dict(predictor=name, under_to_over_loss_ratio=ratio,
                                  over_prediction_error=float(np.sum(over)),
                                  under_prediction_error=float(np.sum(under)),
                                  asymmetric_forecast_loss=float(np.sum(over+ratio*under))))
    run = ROOT/'modeling/data/03_output'/('public_sales_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True, exist_ok=False)
    report = {
        'protocol': 'public-sales-v2', 'seed': SEED, 'source': source.relative_to(ROOT).as_posix(),
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_url_status': 'verify against supplier README before public claims',
        'label_origin': 'supplier_public_scaled_sales', 'unit': 'scaled store sales (continuous; may be negative)',
        'origin_provenance_status': 'supplier_statement_not_independently_verified',
        'raw_rows': len(raw), 'usable_rows': len(usable),
        'excluded_rows_or_calendar_slots': len(data)-len(usable),
        'splits': {name: {'rows': len(df), 'start': str(df.date.min().date()), 'end': str(df.date.max().date())}
                   for name, df in [('train', train), ('tune', tune), ('calibration', cal), ('test', test)]},
        'features': FEATURES, 'model_parameters': model.get_params(), 'tune_metrics': tune_scores,
        'fusion_selection': {'candidate_weights': weights, 'tune_mae': weight_scores, 'frozen_weight': weight},
        'selected_on_tune': chosen, 'test_metrics': scores, 'test_blocks': folds,
        'test_entities': grouped,
        'protocol_detail': 'Frozen model; next-day origins use previously observed sales; five chronological test reporting blocks, no retraining.',
        'interval': {'method': 'absolute_residual_calibration', 'nominal_coverage': .8, 'radius': radius,
                     'test_coverage': float(np.mean((test.sales>=test.interval_low)&(test.sales<=test.interval_high))),
                     'mean_width': float(np.mean(test.interval_high-test.interval_low)),
                     'guarantee': 'No guaranteed coverage under temporal drift or correlated observations.'},
        'limitations': ['Observed sales may censor demand; no causal intervention or field savings evidence.',
                       'Sales are standardized/scaled continuous values; RMSLE and unit-level interpretation are not applicable when labels are negative.',
                       'No currency conversion of scaled sales; no hourly replenishment validation.',
                       'No campus export or cross-dataset generalization claim.',
                       'Asymmetric loss is in scaled units; production capacity, batches and monetary cost are NOT evaluated.'],
        'environment': {'python': sys.version, 'numpy': np.__version__, 'pandas': pd.__version__, 'lightgbm': lgb.__version__},
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'dirty_workspace': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'elapsed_seconds': time.perf_counter()-started,
        'remaining_experiments': ['Campus rule requires observed units and aligned context, not scaled sales.',
                                  'Ablation, quantile interval comparison and production strategy require separate evidence.'],
    }
    (run/'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    test.to_csv(run/'predictions.csv', index=False)
    pd.DataFrame(scenarios).to_csv(run/'asymmetric_forecast_loss.csv', index=False)
    # LightGBM's Windows writer does not accept the Unicode workspace path.
    # Serialize through Python so the run remains portable without changing the model.
    (run/'offline_model.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
    (run/'calibration.json').write_text(json.dumps({'radius': radius, 'residuals': residuals.tolist(), 'selected_model': chosen}), encoding='utf-8')
    print(json.dumps({'run': str(run), 'metrics': scores, 'interval': report['interval']}, indent=2))


if __name__ == '__main__':
    main()
