"""Read-only legacy chain audit; controlled probes use no observed field data."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import warnings
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]


def legacy_functions(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('add_lag_features', '_fill_lag_with_group_median')]
    scope = {'pd': pd, 'np': np, 'TARGET': 'sold_qty'}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), scope)
    return scope


def probes(scope):
    add, fill = scope['add_lag_features'], scope['_fill_lag_with_group_median']
    def example(sales, dates=None, stall='a'):
        dates = pd.date_range('2022-01-01', periods=len(sales)) if dates is None else dates
        return pd.DataFrame(dict(date=dates, stall_name=stall, dish_id=0,
                                 day_of_week=pd.DatetimeIndex(dates).dayofweek,
                                 category_id=0, sold_qty=sales))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        combined = add(pd.concat([example([10., 20., 30.]), example([1000., 2000., 3000.], stall='b')]),
                       ['stall_name', 'dish_id'])
        first_b = combined[combined.stall_name == 'b'].iloc[0]
        raw = example([1., 2., 3., 4., 5., 6.])
        changed = raw.copy()
        changed.loc[changed.date >= '2022-01-03', 'sold_qty'] += 1000
        before = fill(add(raw, ['stall_name', 'dish_id']), ['lag_1_sold'])
        after = fill(add(changed, ['stall_name', 'dish_id']), ['lag_1_sold'])
        gaps = add(example(np.arange(1., 11.), pd.date_range('2022-01-01', periods=10, freq='2D')),
                   ['stall_name', 'dish_id'])
    return dict(
        probe_origin='Constructed counterexamples only; not field accuracy data',
        cross_entity_rolling=dict(first_b_rolling_mean_3=float(first_b.rolling_mean_3),
            expected='unknown: b has no own history', confirmed=bool(pd.notna(first_b.rolling_mean_3))),
        future_imputation=dict(earliest_lag_before=float(before.iloc[0].lag_1_sold),
            earliest_lag_after_future_target_change=float(after.iloc[0].lag_1_sold),
            confirmed=bool(before.iloc[0].lag_1_sold != after.iloc[0].lag_1_sold)),
        calendar_mismatch=dict(date=str(gaps.iloc[7].date.date()), lag7_rows=float(gaps.iloc[7].lag_7_sold),
            expected_calendar_lag7='unknown: calendar day 2022-01-08 absent', confirmed=True))


def main():
    run = ROOT/'modeling/data/03_output'/('training_chain_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True, exist_ok=False)
    paths = [ROOT/'modeling/scripts'/f'{number:02d}_{name}.py' for number, name in
             [(2, 'build_pretrain_features'), (3, 'train_pretrain_lgbm'), (4, 'build_finetune_features'), (5, 'finetune_and_backtest')]]
    export = ROOT/'deploy/10_export_campus_model.py'
    paths.append(export)
    probe = probes(legacy_functions(paths[0]))
    parquet_info = []
    for filename in ('pretrain_all.parquet', 'finetune_uwaste.parquet', 'campus_daily_canonical.parquet'):
        path = ROOT/'modeling/data/02_processed'/filename
        info = dict(file=path.relative_to(ROOT).as_posix(), exists=path.exists())
        if path.exists():
            meta = pq.ParquetFile(path)
            info.update(rows=meta.metadata.num_rows, columns=meta.schema.names,
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            selected = [name for name in ('date', 'source') if name in meta.schema.names]
            if selected:
                df = pd.read_parquet(path, columns=selected)
                if 'source' in df:
                    info['source_counts'] = {str(key): int(value) for key, value in df.source.value_counts(dropna=False).items()}
                if 'date' in df:
                    dates = pd.to_datetime(df.date)
                    info['date_sorted_in_file'] = bool(dates.is_monotonic_increasing)
                    info['date_range'] = [str(dates.min()), str(dates.max())]
                    if filename == 'finetune_uwaste.parquet':
                        info['export_row_boundary_checks'] = [dict(split=split,
                            train_max=str(dates.iloc[:split].max()),
                            valid_min=str(dates.iloc[split:end].min()),
                            strict_time_order=bool(dates.iloc[:split].max() < dates.iloc[split:end].min()))
                            for split, end in [(2080, 2405), (2405, 2600)]]
        parquet_info.append(info)
    source_lines = {}
    terms = ['shift(-', 'grp.shift(1).transform', 's.fillna(s.median())', 'split_idx',
             'iloc[ts:split]', 'init_model', 'finetune_uwaste', 'df["Demand"]', 'clip']
    for path in paths:
        source_lines[path.relative_to(ROOT).as_posix()] = [dict(line=index, text=text.strip())
            for index, text in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1)
            if any(term in text for term in terms)]
    artifacts = [ROOT/'src/main/resources/modeling'/name for name in
                 ['lgbm_campus_model.txt', 'campus_feature_cols.json', 'campus_backtest_report.json']]
    metadata_path = ROOT/'modeling/data/02_processed/finetune_uwaste_metadata.csv'
    metadata = pd.read_csv(metadata_path, parse_dates=['date'])
    processed = pd.read_parquet(ROOT/'modeling/data/02_processed/finetune_uwaste.parquet', columns=['sold_qty', 'category_id'])
    alignment = dict(rows=len(metadata), metadata_sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        aligned_by_row_values_only=bool(len(metadata) == len(processed) and
            np.array_equal(metadata.sold_qty.to_numpy(), processed.sold_qty.to_numpy()) and
            np.array_equal(metadata.category_id.to_numpy(), processed.category_id.to_numpy())),
        limitation='Row-value matches do not establish a stable source primary key or missing generator provenance',
        export_boundaries=[dict(split=split, train_max=str(metadata.date.iloc[:split].max()),
            valid_min=str(metadata.date.iloc[split:end].min()),
            strict_date_order=bool(metadata.date.iloc[:split].max() < metadata.date.iloc[split:end].min()))
            for split, end in [(2080, 2405), (2405, 2600)]])
    report = dict(reviewed_at=datetime.now(timezone.utc).isoformat(), counterexamples=probe,
        parquet_metadata=parquet_info, metadata_row_alignment=alignment, code_evidence=source_lines,
        source_hashes={path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        artifact_hashes={path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts if path.exists()},
        chain_gaps=['No finetune_uwaste generator found in modeling/scripts or deploy',
                    'Historical pretrain and current campus export use different feature lists',
                    'Historical CC0 loader selects Demand, not Units Sold: target semantics require audit'],
        action='Quarantine legacy accuracy claims; use isolated chronological protocols; do not rerun online-writing export',
        limitation='Historical builder probes do not prove the absent uwaste generator used the same functions')
    (run/'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (run/'23_legacy_training_chain_audit.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(run=str(run), counterexamples=probe, parquet_metadata=parquet_info), ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
