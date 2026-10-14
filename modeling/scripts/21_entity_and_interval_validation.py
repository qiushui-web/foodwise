"""Preregistered offline entity, objective, EWMA and interval comparisons."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('public_protocol', Path(__file__).with_name('14_public_sales_validation.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
FEATURES = p.FEATURES
OBJECTIVES = {'l2': 'regression', 'l1': 'regression_l1'}


def build_features(raw):
    data = p.build_features(raw)
    for alpha in (.2, .5):
        data[f'ewma_{alpha}'] = data.groupby('store', sort=False).sales.transform(
            lambda values: values.shift(1).ewm(alpha=alpha, adjust=False,
                ignore_na=False, min_periods=7).mean())
    return data


def windows(train):
    chunks = np.array_split(sorted(train.date.unique()), 5)
    for fold, index in enumerate((2, 3, 4), 1):
        fit = train[train.date.isin(np.concatenate(chunks[:index]))]
        valid = train[train.date.isin(chunks[index])]
        assert fit.date.max() < valid.date.min()
        yield fold, fit, valid


def fit(train, objective='regression', alpha=None):
    dates = sorted(train.date.unique())
    cutoff = dates[int(.8 * len(dates))]
    inner, stop = train[train.date < cutoff], train[train.date >= cutoff]
    assert len(inner) and len(stop) and inner.date.max() < stop.date.min()
    params = dict(objective=objective, metric='quantile' if objective == 'quantile' else 'l1',
                  num_leaves=7, min_child_samples=50, learning_rate=.03,
                  random_state=42, n_jobs=1, verbosity=-1)
    if alpha is not None:
        params['alpha'] = alpha
    trial = lgb.LGBMRegressor(n_estimators=300, **params)
    trial.fit(inner[FEATURES], inner.sales, eval_set=[(stop[FEATURES], stop.sales)],
              callbacks=[lgb.early_stopping(30, first_metric_only=True, verbose=False)])
    model = lgb.LGBMRegressor(n_estimators=trial.best_iteration_, **params)
    model.fit(train[FEATURES], train.sales)
    return model


def gate_prediction(stores, seen_stores, ml_prediction, fallback):
    return np.where(np.asarray([store in seen_stores for store in stores]),
                    np.asarray(ml_prediction), np.asarray(fallback))


def point_options(df, models, seen):
    options = {'last_day': df.lag1.to_numpy(), 'lag7': df.lag7.to_numpy(),
               'mean7': df.mean7.to_numpy(), 'weekday_mean4': df.weekday_mean4.to_numpy(),
               'ewma_0.2': df['ewma_0.2'].to_numpy(), 'ewma_0.5': df['ewma_0.5'].to_numpy()}
    for name, model in models.items():
        ml = model.predict(df[FEATURES])
        fusion = .5*ml+.5*df.weekday_mean4.to_numpy()
        options['direct_'+name] = ml
        options['fusion_'+name] = fusion
        options['gated_'+name] = gate_prediction(df.store, seen, fusion, df.weekday_mean4)
    return options


def interval_metrics(y, low, high, coverage):
    y, low, high = map(lambda value: np.asarray(value, float), (y, low, high))
    assert np.all(np.isfinite(low)) and np.all(high >= low)
    score = high-low + 2/(1-coverage)*(np.maximum(low-y, 0)+np.maximum(y-high, 0))
    return dict(coverage=float(np.mean((y >= low) & (y <= high))),
                width=float(np.mean(high-low)), interval_score=float(np.mean(score)))


def main():
    started = time.perf_counter()
    run = ROOT/'modeling/data/03_output'/('entity_interval_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (run/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    source = ROOT/'modeling/data/01_raw/reduce_foodwaste/train.csv'
    save('protocol.json', dict(version='entity-interval-v1', seed=42, point_objectives=OBJECTIVES,
        features=FEATURES, ewma_alphas=[.2, .5], ewma_policy='Shift one calendar day; no zero fill; unknown gaps decay weights',
        budget='7 leaves; min child 50; max 300 trees; lr .03; MAE stopping for points; quantile stopping for quantiles',
        entity_validation='Three original-train expanding windows; each omit one fit store; past target history allowed for omitted store',
        gate='Entity absent from model fitting: weekday4 baseline; otherwise fixed half fusion',
        gate_scope='Model-unseen entities with 28-day usable history; no zero-history performance claim',
        point_selection='Original tune MAE only; repeatedly reused data means exploratory selection',
        intervals='Global residual; per-store residual (min50 else global); raw sorted quantiles; nonnegative-score CQR',
        calibration='Original calibration only; 80/90% fixed; no selection on test or calibrated results',
        old_test='Exploratory reporting only; no old-test model/method/threshold selection',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        imported_sha256=hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest(),
        unit='Supplier scaled daily sales; no physical or monetary claims', online_export=False))
    raw = pd.read_csv(source, parse_dates=['date'])
    days = sorted(raw.date.unique())
    bounds = [days[int(q*len(days))-1] for q in (.6, .7, .8)]
    data = build_features(raw).dropna(subset=FEATURES+['sales', 'ewma_0.2', 'ewma_0.5'])
    train, tune, cal, test = [data[mask].copy() for mask in
        [data.date <= bounds[0], (data.date > bounds[0]) & (data.date <= bounds[1]),
         (data.date > bounds[1]) & (data.date <= bounds[2]), data.date > bounds[2]]]
    assert train.date.max() < tune.date.min() <= tune.date.max() < cal.date.min() <= cal.date.max() < test.date.min()
    split = pd.concat([df[['date', 'store']].assign(split=name) for name, df in
                      [('train', train), ('tune', tune), ('calibration', cal), ('old_test_exploratory', test)]])
    split.to_csv(run/'split_manifest.csv', index=False)
    predictions, summary, trees = [], [], []
    def record(scope, fold, heldout, fitting, valid, models):
        seen = set(fitting.store)
        block = valid[['date', 'store', 'sales']].copy()
        block['scope'], block['fold'], block['heldout_store'] = scope, fold, heldout
        block['entity_seen_in_fit'] = block.store.isin(seen)
        for name, pred in point_options(valid, models, seen).items():
            block['pred_'+name] = pred
            summary.append(dict(scope=scope, fold=fold, heldout_store=heldout, model=name, rows=len(valid),
                fit_end=str(fitting.date.max().date()), valid_start=str(valid.date.min().date()),
                valid_end=str(valid.date.max().date()), **p.metrics(valid.sales, pred)))
        predictions.append(block)
    for fold, fitting, valid in windows(train):
        models = {name: fit(fitting, objective) for name, objective in OBJECTIVES.items()}
        for name, model in models.items():
            (run/f'fold{fold}_{name}.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
            trees.append(dict(scope='temporal', fold=fold, heldout_store='', model=name, trees=model.n_estimators))
        record('temporal', fold, '', fitting, valid, models)
        for store in sorted(fitting.store.unique()):
            reduced, target = fitting[fitting.store != store], valid[valid.store == store]
            assert store not in set(reduced.store) and reduced.date.max() < target.date.min()
            omitted_models = {name: fit(reduced, objective) for name, objective in OBJECTIVES.items()}
            for name, model in omitted_models.items():
                (run/f'fold{fold}_omit_{store}_{name}.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
                trees.append(dict(scope='leave_store_out', fold=fold, heldout_store=store, model=name, trees=model.n_estimators))
            record('leave_store_out', fold, store, reduced, target, omitted_models)
    scores = pd.DataFrame(summary)
    scores.to_csv(run/'window_metrics.csv', index=False)
    pd.concat(predictions).to_csv(run/'internal_predictions.csv', index=False)
    pooled = {scope: {name: float(np.average(block.mae, weights=block.rows))
                     for name, block in subgroup.groupby('model')} for scope, subgroup in scores.groupby('scope')}
    models = {name: fit(train, objective) for name, objective in OBJECTIVES.items()}
    for name, model in models.items():
        (run/f'final_{name}.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
        trees.append(dict(scope='final_train', fold=0, heldout_store='', model=name, trees=model.n_estimators))
    options_tune = point_options(tune, models, set(train.store))
    tune_metrics = {name: p.metrics(tune.sales, pred) for name, pred in options_tune.items()}
    selected = min(tune_metrics, key=lambda name: tune_metrics[name]['mae'])
    centers = {'calibration': point_options(cal, models, set(train.store))[selected],
               'old_test_exploratory': point_options(test, models, set(train.store))[selected]}
    residuals = cal.sales.to_numpy()-centers['calibration']
    global_radii, grouped_radii, cqr_radii = {}, {}, {}
    interval_rows, interval_predictions = [], []
    for coverage in (.8, .9):
        global_radius = p.conformal_radius(residuals, coverage)
        global_radii[str(coverage)] = global_radius
        groups = {store: p.conformal_radius(residuals[cal.store.to_numpy() == store], coverage)
                  for store, group in cal.groupby('store') if len(group) >= 50}
        grouped_radii[str(coverage)] = groups
        alpha = (1-coverage)/2
        lower_model, upper_model = fit(train, 'quantile', alpha), fit(train, 'quantile', 1-alpha)
        for role, model in [('lower', lower_model), ('upper', upper_model)]:
            (run/f'quantile_{coverage}_{role}.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
            trees.append(dict(scope='quantile_train', fold=0, heldout_store='', model=f'{coverage}_{role}', trees=model.n_estimators))
        cal_bounds = np.sort(np.column_stack([lower_model.predict(cal[FEATURES]), upper_model.predict(cal[FEATURES])]), axis=1)
        nonconformity = np.maximum(np.maximum(cal_bounds[:, 0]-cal.sales.to_numpy(), cal.sales.to_numpy()-cal_bounds[:, 1]), 0)
        radius = p.conformal_radius(nonconformity, coverage)
        cqr_radii[str(coverage)] = radius
        for split_name, df in [('calibration', cal), ('old_test_exploratory', test)]:
            center = centers[split_name]
            grouped = np.array([groups.get(store, global_radius) for store in df.store])
            quantiles = np.column_stack([lower_model.predict(df[FEATURES]), upper_model.predict(df[FEATURES])])
            crossings = float(np.mean(quantiles[:, 0] > quantiles[:, 1]))
            quantiles.sort(axis=1)
            methods = {'global_residual': (center-global_radius, center+global_radius),
                       'grouped_residual': (center-grouped, center+grouped),
                       'raw_quantiles': (quantiles[:, 0], quantiles[:, 1]),
                       'clipped_cqr': (quantiles[:, 0]-radius, quantiles[:, 1]+radius)}
            for method, (low, high) in methods.items():
                interval_rows.append(dict(split=split_name, method=method, nominal=coverage, store='ALL', rows=len(df),
                    raw_quantile_crossing_fraction=crossings, **interval_metrics(df.sales, low, high, coverage)))
                block = df[['date', 'store', 'sales']].copy()
                block['split'], block['method'], block['nominal'] = split_name, method, coverage
                block['low'], block['high'] = low, high
                interval_predictions.append(block)
                for store, indices in df.groupby('store').indices.items():
                    interval_rows.append(dict(split=split_name, method=method, nominal=coverage, store=store, rows=len(indices),
                        raw_quantile_crossing_fraction=crossings,
                        **interval_metrics(df.sales.to_numpy()[indices], low[indices], high[indices], coverage)))
    pd.DataFrame(interval_rows).to_csv(run/'interval_metrics.csv', index=False)
    pd.concat(interval_predictions).to_csv(run/'interval_predictions.csv', index=False)
    test_options = point_options(test, models, set(train.store))
    test_predictions = test[['date', 'store', 'sales']].copy()
    for name, values in test_options.items():
        test_predictions['pred_'+name] = values
    test_predictions['entity_seen_in_train'] = test.store.isin(set(train.store))
    test_predictions.to_csv(run/'old_test_exploratory_predictions.csv', index=False)
    report = dict(internal_pooled_mae=pooled, tune_metrics=tune_metrics, selected_on_tune=selected,
        old_test_exploratory={name: p.metrics(test.sales, pred) for name, pred in test_options.items()},
        interval_comparison=[row for row in interval_rows if row['store'] == 'ALL'],
        elapsed_seconds=time.perf_counter()-started,
        environment=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, lightgbm=lgb.__version__),
        limitations=['Repeated internal/tune use is exploratory; independent confirmation absent',
                     'Five fit stores and correlated dates; row counts are not independent replicates',
                     'Group calibration min50 is an engineering rule, not a coverage guarantee',
                     'Upstream scaling definition/fit period unknown; no campus production claim'])
    save('metrics.json', report)
    save('tree_counts.json', trees)
    save('calibration.json', dict(selected_point=selected, global_radii=global_radii,
                                 grouped_radii=grouped_radii, cqr_radii=cqr_radii,
                                 residuals=residuals.tolist(), min_group_size=50))
    copies = run/'reproduction_sources'
    copies.mkdir()
    for script in [Path(__file__), Path(p.__file__)]:
        (copies/script.name).write_bytes(script.read_bytes())
    (run/'requirements_snapshot.txt').write_text(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True), encoding='utf-8')
    save('artifact_hashes.json', {f.relative_to(run).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in run.rglob('*') if f.is_file()})
    print(json.dumps(dict(run=str(run), internal_pooled_mae=pooled, selected_on_tune=selected,
                         interval_comparison=report['interval_comparison'][-8:]), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
