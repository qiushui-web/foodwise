"""Training-period-only chronological comparisons. No campus export or field claims."""
from pathlib import Path
import importlib.util
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('public_protocol', Path(__file__).with_name('14_public_sales_validation.py'))
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)


def main():
    started = time.perf_counter()
    source = ROOT / 'modeling/data/01_raw/reduce_foodwaste/train.csv'
    raw = pd.read_csv(source, parse_dates=['date'])
    days = sorted(raw.date.unique())
    cutoff = days[int(.6 * len(days)) - 1]
    # Preserve original outer train boundary; no outer tune/calibration/test scoring.
    data = protocol.build_features(raw[raw.date <= cutoff].copy())
    data = data.dropna(subset=protocol.FEATURES + ['sales'])
    dates = sorted(data.date.unique())
    chunks = np.array_split(dates, 5)
    windows = [(np.concatenate(chunks[:i]), chunks[i]) for i in (2, 3, 4)]
    configs = [{'name': 'existing_lgbm', 'kind': 'direct', 'leaves': 15, 'child': 20, 'trees': 150, 'lr': .05}]
    for kind in ('direct', 'residual'):
        for leaves in (7, 15):
            for child in (20, 50):
                configs.append(dict(name=f'{kind}_l{leaves}_m{child}', kind=kind,
                                    leaves=leaves, child=child, trees=300, lr=.03))
    run = ROOT / 'modeling/data/03_output' / ('internal_cv_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True, exist_ok=False)
    manifest = dict(protocol='internal-cv-v1', seed=42, outer_train_end=str(pd.Timestamp(cutoff).date()),
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), candidates=configs,
                    features=protocol.FEATURES, scope='Exploratory model selection within original training period only',
                    future_sets='Previously viewed outer test is not independent confirmation',
                    validation='Three expanding chronological windows; separate inner early-stopping tail',
                    label_unit='supplier scaled store sales; not servings or currency',
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (run / 'protocol.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    outputs, summaries = [], []
    for fold, (tr_dates, va_dates) in enumerate(windows, 1):
        train = data[data.date.isin(tr_dates)]
        valid = data[data.date.isin(va_dates)].copy()
        valid['fold'] = fold
        predictions = dict(last_day=valid.lag1, lag7=valid.lag7,
                           mean7=valid.mean7, weekday_mean4=valid.weekday_mean4)
        tail = tr_dates[max(1, int(.8 * len(tr_dates)))]
        fit = train[train.date < tail]
        stop = train[train.date >= tail]
        assert fit.date.max() < stop.date.min() <= stop.date.max() < valid.date.min()
        for cfg in configs:
            params = dict(num_leaves=cfg['leaves'], min_child_samples=cfg['child'],
                          learning_rate=cfg['lr'], random_state=42, n_jobs=1, verbosity=-1)
            def target(df):
                return df.sales - df.weekday_mean4 if cfg['kind'] == 'residual' else df.sales
            if cfg['name'] == 'existing_lgbm':
                trees = cfg['trees']
            else:
                trial = lgb.LGBMRegressor(n_estimators=cfg['trees'], **params)
                trial.fit(fit[protocol.FEATURES], target(fit),
                          eval_set=[(stop[protocol.FEATURES], target(stop))],
                          callbacks=[lgb.early_stopping(30, verbose=False)])
                trees = trial.best_iteration_
            model = lgb.LGBMRegressor(n_estimators=trees, **params)
            model.fit(train[protocol.FEATURES], target(train))
            pred = model.predict(valid[protocol.FEATURES])
            if cfg['kind'] == 'residual':
                pred += valid.weekday_mean4.to_numpy()
            predictions[cfg['name']] = pred
            (run / f'fold{fold}_{cfg["name"]}.txt').write_text(model.booster_.model_to_string(), encoding='utf-8')
        for name, p in predictions.items():
            valid['pred_' + name] = np.asarray(p)
            summaries.append(dict(fold=fold, model=name, train_rows=len(train), valid_rows=len(valid),
                                  train_end=str(train.date.max().date()), valid_start=str(valid.date.min().date()),
                                  valid_end=str(valid.date.max().date()), **protocol.metrics(valid.sales, p)))
        outputs.append(valid)
    scored = pd.concat(outputs, ignore_index=True)
    names = list(predictions)
    overall = {name: protocol.metrics(scored.sales, scored['pred_' + name]) for name in names}
    entity_metrics = []
    for (fold, store), block in scored.groupby(['fold', 'store']):
        for name in names:
            entity_metrics.append(dict(fold=int(fold), store=store, model=name, rows=len(block),
                                       **protocol.metrics(block.sales, block['pred_' + name])))
    pd.DataFrame(summaries).to_csv(run / 'window_metrics.csv', index=False)
    pd.DataFrame(entity_metrics).to_csv(run / 'entity_metrics.csv', index=False)
    scored.to_csv(run / 'predictions.csv', index=False)
    report = dict(overall=overall, selected_by_pooled_mae=min(names, key=lambda n: overall[n]['mae']),
                  elapsed_seconds=time.perf_counter() - started,
                  environment=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, lightgbm=lgb.__version__),
                  limitation='Selection scores, not independent test accuracy; no campus model export')
    (run / 'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(run=str(run), **report), indent=2))


if __name__ == '__main__':
    main()
