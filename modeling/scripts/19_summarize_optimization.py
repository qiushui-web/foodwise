"""Summarize completed frozen runs without selecting on the old test."""
from pathlib import Path
import json
import hashlib
import subprocess
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / 'modeling/data/03_output'
    internal = sorted(output.glob('internal_cv_*'))[-1]
    run = sorted(output.glob('optimization_*'))[-1]
    pred = pd.read_csv(run / 'predictions.csv', parse_dates=['date'])
    train_stores = set(pred.loc[pred.split == 'train', 'store'])
    test = pred[pred.split == 'old_test_exploratory'].copy()
    test['entity_seen_in_train'] = test.store.isin(train_stores)
    rows = []
    for seen, block in test.groupby('entity_seen_in_train'):
        rows.append(dict(entity_seen_in_train=bool(seen), rows=len(block), stores=sorted(block.store.unique()),
                         baseline_mae=float(abs(block.sales-block.pred_weekday_mean4).mean()),
                         fusion_mae=float(abs(block.sales-block['pred_fusion_0.5']).mean())))
    intervals = []
    for store, block in test.groupby('store'):
        for coverage in ('0.8', '0.9'):
            intervals.append(dict(store=store, rows=len(block), nominal=float(coverage),
                coverage=float(((block.sales >= block['low_'+coverage]) & (block.sales <= block['high_'+coverage])).mean())))
    pd.DataFrame(intervals).to_csv(run / 'supplement_entity_intervals.csv', index=False)
    blocks = []
    for index, dates in enumerate(np.array_split(sorted(test.date.unique()), 5), 1):
        block = test[test.date.isin(dates)]
        blocks.append(dict(block=index, start=str(pd.Timestamp(dates[0]).date()), end=str(pd.Timestamp(dates[-1]).date()),
            baseline_mae=float(abs(block.sales-block.pred_weekday_mean4).mean()),
            fusion_mae=float(abs(block.sales-block['pred_fusion_0.5']).mean())))
    frozen_sources = [ROOT/'modeling/scripts'/name for name in
                      ['13_source_audit.py', '14_public_sales_validation.py', '17_internal_model_comparison.py',
                       '18_optimization_evidence.py', '19_summarize_optimization.py', '20_verify_optimization.py']]
    snapshot = run / 'reproduction_sources'
    snapshot.mkdir(exist_ok=True)
    for source in frozen_sources:
        (snapshot/source.name).write_bytes(source.read_bytes())
    baseline = ROOT/'modeling/data/03_output/public_sales_20261012T090638369705Z/metrics.json'
    summary = dict(internal_run=internal.name, optimization_run=run.name,
        original_report_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
        source_script_hashes={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in frozen_sources},
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        dirty_workspace=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        known_vs_new_entity=rows, old_test_reporting_blocks=blocks,
        interpretation='Descriptive old-test diagnosis; no post-test weight or model selection',
        remaining_source_checks=['Upstream verification', 'Data-specific license scope', 'Scaling formula and fitted time span'],
        remaining_field_checks=['Authorized local labels', 'Independent future test', 'Campus feature/inference parity', 'Field outcome controls'])
    (run/'supplement_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    deps = subprocess.check_output([str(ROOT/'modeling/.venv/Scripts/python.exe'), '-m', 'pip', 'freeze'], text=True)
    (run/'requirements_snapshot.txt').write_text(deps, encoding='utf-8')
    (snapshot/'README.md').write_text('Restore these scripts to modeling/scripts in a checkout with the original hashed data. Run from the repository root. These are frozen source copies, not direct entrypoints in this nested directory.\n', encoding='utf-8')
    (run/'supplement_hashes.json').write_text(json.dumps({f.relative_to(run).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
         for f in run.rglob('*') if f.is_file() and f.name != 'supplement_hashes.json'}, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
