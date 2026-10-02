"""Evaluate legacy sales columns only; dates and splits cannot be recovered."""
import importlib.util
import json
from pathlib import Path
import pandas as pd
spec=importlib.util.spec_from_file_location('campus',Path(__file__).with_name('12_campus_rolling_baseline.py'))
campus=importlib.util.module_from_spec(spec)
spec.loader.exec_module(campus)
def main():
 out=campus.OUT
 df=pd.read_csv(out/'campus_backtest_predictions.csv')
 cols=[c for c in ('pred_lightgbm','pred_rule_avg') if c in df]
 report={'status':'legacy_unverified','rolling_windows':None,'reason':'No dates, series keys or recoverable training provenance; metrics do not establish out-of-sample performance.',
 'excluded':{'pred_prepare':'Preparation decision, not naive sales forecast','pred_waste':'Waste estimate, not sales forecast'},
 'metrics':{c:campus.score(df.actual,df[c]) for c in cols}}
 (out/'legacy_metrics_report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
 print('Legacy descriptive metrics saved; not a rolling backtest.')
if __name__=='__main__': main()
