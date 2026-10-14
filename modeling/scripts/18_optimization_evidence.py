"""Bounded offline ablation, provenance, drift and interval audit. No online export."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import platform
import time
import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


p = module('public_protocol', '14_public_sales_validation.py')
audit = module('source_audit', '13_source_audit.py')
FEATURE_GROUPS = {
    'full': p.FEATURES,
    'without_calendar': [f for f in p.FEATURES if f != 'dow'],
    'without_short_history': ['dow', 'lag7', 'weekday_mean4'],
    'without_weekly_history': ['dow', 'lag1', 'mean7'],
}


def fit(train, features):
    dates = sorted(train.date.unique())
    boundary = dates[int(.8 * len(dates))]
    inner, stop = train[train.date < boundary], train[train.date >= boundary]
    assert inner.date.max() < stop.date.min()
    params = dict(num_leaves=7, min_child_samples=50, learning_rate=.03,
                  n_jobs=1, random_state=42, verbosity=-1)
    trial = lgb.LGBMRegressor(n_estimators=300, **params)
    trial.fit(inner[features], inner.sales, eval_set=[(stop[features], stop.sales)],
              callbacks=[lgb.early_stopping(30, verbose=False)])
    model = lgb.LGBMRegressor(n_estimators=trial.best_iteration_, **params)
    model.fit(train[features], train.sales)
    return model


def leakage_checks():
    raw = pd.DataFrame({'date': pd.date_range('2022-01-01', periods=70),
                        'store': 'a', 'sales': np.arange(70, dtype=float)})
    cutoff = pd.Timestamp('2022-02-10')
    changed = raw.copy()
    changed.loc[changed.date >= cutoff, 'sales'] = 99999.
    a, b = p.build_features(raw), p.build_features(changed)
    pd.testing.assert_frame_equal(a.loc[a.date <= cutoff, p.FEATURES],
                                  b.loc[b.date <= cutoff, p.FEATURES])
    missing = p.build_features(raw[raw.date != pd.Timestamp('2022-02-01')])
    row = missing[missing.date == pd.Timestamp('2022-02-08')].iloc[0]
    assert pd.isna(row.lag7) and pd.isna(row.mean7)
    try:
        p.build_features(pd.concat([raw, raw.iloc[:1]]))
    except ValueError:
        pass
    else:
        raise AssertionError('Duplicate entity/date accepted')
    second = raw.assign(store='b', sales=raw.sales + 1000)
    joined = p.build_features(pd.concat([raw, second]))
    pd.testing.assert_frame_equal(a[p.FEATURES].reset_index(drop=True),
        joined[joined.store == 'a'][p.FEATURES].reset_index(drop=True))
    return ['future/current target mutation invariance', 'calendar gap remains unknown',
            'duplicate primary key rejected', 'entity lag isolation']


def main():
    started = time.perf_counter()
    run = ROOT / 'modeling/data/03_output' / ('optimization_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (run / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    source = ROOT / 'modeling/data/01_raw/reduce_foodwaste/train.csv'
    source_dir = source.parent
    save('protocol.json', dict(version='optimization-v1', seed=42, groups=FEATURE_GROUPS,
        candidates='Small direct LightGBM selected in original-train internal CV; 4 ablations',
        selection='Ablation on internal folds; baseline/fusion choice on original tune only',
        calibration='Original calibration only; 80% and 90% absolute residual intervals',
        old_test='Already inspected: exploratory reporting only; never model selection',
        online_export=False, unit='supplier scaled sales; no servings or monetary conversion',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        imported_protocol_sha256=hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest()))
    save('source_audit.json', audit.audit())
    save('source_manifest.json', dict(files={name: hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
        for name in ['train.csv', 'README.md', 'LICENSE']},
        publisher_statement='Green-AI Hub Mittelstand; German confectionery chain; anonymized daily store sales',
        original_links=['https://www.green-ai-hub.de/pilotprojekte/pilotprojekt-brammibals-donuts-foodtracks',
                        'https://www.kaggle.com/competitions/pastry-prediction'],
        review='Local README/LICENSE reviewed 2026-10-13; upstream identity and collection not independently verified',
        license='Local MIT text copyright 2025 Green-AI Hub Mittelstand; explicit data-specific rights scope remains unconfirmed',
        scale='README says scaled by store; exact transformation/inverse/fit period not documented locally',
        future_weather='Observed opening-hour weather excluded; forecast issue timestamps absent'))
    checks = leakage_checks()
    raw = pd.read_csv(source, parse_dates=['date'])
    assert raw.sales.notna().all() and np.isfinite(raw.sales).all()
    days = sorted(raw.date.unique())
    boundaries = [days[int(q * len(days)) - 1] for q in (.6, .7, .8)]
    data = p.build_features(raw).dropna(subset=p.FEATURES + ['sales'])
    masks = [data.date <= boundaries[0], (data.date > boundaries[0]) & (data.date <= boundaries[1]),
             (data.date > boundaries[1]) & (data.date <= boundaries[2]), data.date > boundaries[2]]
    parts = dict(zip(['train', 'tune', 'calibration', 'old_test_exploratory'], [data[m].copy() for m in masks]))
    split_rows = pd.concat([df[['date', 'store']].assign(split=name) for name, df in parts.items()])
    split_rows.to_csv(run / 'split_manifest.csv', index=False)
    train = parts['train']
    chunks = np.array_split(sorted(train.date.unique()), 5)
    ablations, tree_counts = [], []
    for fold, i in enumerate((2, 3, 4), 1):
        tr, va = train[train.date.isin(np.concatenate(chunks[:i]))], train[train.date.isin(chunks[i])]
        assert tr.date.max() < va.date.min()
        for name, features in FEATURE_GROUPS.items():
            model = fit(tr, features)
            ablations.append(dict(fold=fold, group=name, rows=len(va),
                                   **p.metrics(va.sales, model.predict(va[features]))))
            tree_counts.append(dict(stage=f'inner_fold_{fold}', group=name, trees=model.n_estimators))
            (run / f'fold{fold}_{name}.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
    ablation = pd.DataFrame(ablations)
    ablation.to_csv(run / 'ablation_metrics.csv', index=False)
    scores = {name: float(np.average(df.mae, weights=df.rows)) for name, df in ablation.groupby('group')}
    selected_group = min(scores, key=scores.get)
    features = FEATURE_GROUPS[selected_group]
    model = fit(train, features)
    tree_counts.append(dict(stage='final_train', group=selected_group, trees=model.n_estimators))
    (run / 'candidate_model.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
    def options(df):
        out = {name: df[col].to_numpy() for name, col in
               [('last_day', 'lag1'), ('lag7', 'lag7'), ('mean7', 'mean7'), ('weekday_mean4', 'weekday_mean4')]}
        out['candidate_lgbm'] = model.predict(df[features])
        for weight in (.25, .5, .75):
            out[f'fusion_{weight}'] = weight*out['candidate_lgbm']+(1-weight)*out['weekday_mean4']
        return out
    tune = parts['tune']
    tune_scores = {name: p.metrics(tune.sales, pred) for name, pred in options(tune).items()}
    selected = min(tune_scores, key=lambda name: tune_scores[name]['mae'])
    cal = parts['calibration']
    residuals = cal.sales.to_numpy() - options(cal)[selected]
    intervals = {str(c): p.conformal_radius(residuals, c) for c in (.8, .9)}
    save('calibration.json', dict(selected=selected, radii=intervals, residuals=residuals.tolist(),
         guarantee='No guaranteed coverage under temporal dependence or drift'))
    scored, interval_scores, entity_scores, distributions = [], [], [], []
    for name, df in parts.items():
        block = df.copy()
        for candidate, prediction in options(df).items():
            block['pred_' + candidate] = prediction
        block['split'] = name
        for (store), sub in block.groupby('store'):
            distributions.append(dict(split=name, store=str(store), rows=len(sub),
                sales_mean=float(sub.sales.mean()), sales_std=float(sub.sales.std()),
                sales_q10=float(sub.sales.quantile(.1)), sales_q90=float(sub.sales.quantile(.9)),
                negative_fraction=float((sub.sales < 0).mean()),
                outside_train_range=float(((sub.sales < train.sales.min()) | (sub.sales > train.sales.max())).mean())))
            for candidate in options(df):
                entity_scores.append(dict(split=name, store=str(store), model=candidate,
                    **p.metrics(sub.sales, sub['pred_' + candidate])))
        for coverage, radius in intervals.items():
            center = block['pred_' + selected]
            low, high = center-radius, center+radius
            block['low_' + coverage], block['high_' + coverage] = low, high
            alpha = 1-float(coverage)
            score = 2*radius + (2/alpha)*np.maximum(low-block.sales, 0)+(2/alpha)*np.maximum(block.sales-high, 0)
            interval_scores.append(dict(split=name, nominal=float(coverage),
                coverage=float(((block.sales >= low) & (block.sales <= high)).mean()),
                width=2*radius, interval_score=float(score.mean())))
        scored.append(block)
    pd.concat(scored).to_csv(run / 'predictions.csv', index=False)
    pd.DataFrame(entity_scores).to_csv(run / 'entity_metrics.csv', index=False)
    pd.DataFrame(distributions).to_csv(run / 'distribution_diagnostics.csv', index=False)
    pd.DataFrame(interval_scores).to_csv(run / 'interval_metrics.csv', index=False)
    checks.append('expanding folds and inner stopping chronological')
    save('verification.json', dict(passed=checks, count=len(checks)))
    save('tree_counts.json', tree_counts)
    test = parts['old_test_exploratory']
    report = dict(selected_feature_group=selected_group, ablation_pooled_mae=scores,
        tune_scores=tune_scores, selected_on_tune=selected,
        old_test_exploratory={name: p.metrics(test.sales, pred) for name, pred in options(test).items()},
        intervals=interval_scores, elapsed_seconds=time.perf_counter()-started,
        environment=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, lightgbm=lgb.__version__),
        limitations=['Feature elimination on few correlated time windows is exploratory',
                     'Scaling fit period unknown: upstream scaling leakage cannot be ruled out',
                     'No campus accuracy, serving recommendation or field savings evidence'])
    save('metrics.json', report)
    save('artifact_hashes.json', {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in run.iterdir() if f.is_file()})
    print(json.dumps(dict(run=str(run), **report), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
