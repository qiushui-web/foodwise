"""Five expanding daily forecast origins; simulation is not field evidence."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'modeling/data'
OUT=BASE/'03_output'
FEATURES=['day_of_week','lag_1_sold','lag_7_sold','rolling_mean_3','rolling_mean_7']

def score(y,p):
 y=np.asarray(y,float); p=np.asarray(p,float)
 if len(y)==0 or not np.isfinite(y).all() or not np.isfinite(p).all():
  raise ValueError('Metrics require nonempty finite observations and predictions')
 den=np.abs(y)+np.abs(p)
 return {'mae':float(np.mean(abs(y-p))),
  'wape_pct':float(np.sum(abs(y-p))/np.sum(abs(y))*100) if np.sum(abs(y)) else None,
  'smape_pct':float(np.mean(np.divide(200*abs(y-p),den,out=np.zeros_like(den),where=den>0))),
  'rmsle':float(np.sqrt(np.mean((np.log1p(np.maximum(y,0))-np.log1p(np.maximum(p,0)))**2)))}

def features(df):
 out=df.sort_values(['stall_name','dish_id','date']).copy()
 if out.duplicated(['date','stall_name','dish_id']).any(): raise ValueError('Duplicate business key')
 grp=out.groupby(['stall_name','dish_id']).sold_qty
 out['day_of_week']=out.date.dt.dayofweek
 out['lag_1_sold']=grp.shift(1)
 out['lag_7_sold']=grp.shift(7)
 for n in (3,7):
  out[f'rolling_mean_{n}']=grp.transform(lambda x:x.shift(1).rolling(n,min_periods=1).mean())
 return out.sort_values(['date','stall_name','dish_id']).reset_index(drop=True)

def main():
 src=ROOT/'src/main/resources/data/foodwise_operations_14d.csv'
 df=pd.read_csv(src).rename(columns={'business_date':'date','stall':'stall_name'})
 df['date']=pd.to_datetime(df.date)
 df['source_id']='foodwise_operations_simulation'
 df['label_origin']='simulation'
 df['target_unit']='servings'
 data=features(df)
 (BASE/'02_processed').mkdir(exist_ok=True)
 data.to_parquet(BASE/'02_processed/campus_daily_canonical.parquet',index=False)
 dates=sorted(df.date.unique())
 if len(dates)<12: raise ValueError('Need at least 12 dates for 7 history days + 5 origins')
 records=[]; windows=[]
 for fold,day in enumerate(dates[-5:],1):
  train=data[(data.date<day)&data[FEATURES].notna().all(axis=1)]
  test=data[data.date==day]
  if train.empty or test[FEATURES].isna().any().any(): raise ValueError('Insufficient historical features')
  model=lgb.LGBMRegressor(n_estimators=40,num_leaves=4,min_child_samples=2,learning_rate=.05,random_state=42,n_jobs=1,verbosity=-1)
  model.fit(train[FEATURES],np.log1p(train.sold_qty))
  test=test[['date','stall_name','dish_id','sold_qty']].rename(columns={'sold_qty':'actual'}).copy()
  source=data[data.date==day]
  test['pred_last_day']=source.lag_1_sold.to_numpy()
  test['pred_same_weekday']=source.lag_7_sold.to_numpy()
  test['pred_mean_7']=source.rolling_mean_7.to_numpy()
  test['pred_local_lgbm']=np.maximum(0,np.expm1(model.predict(source[FEATURES])))
  test['fold']=fold; test['train_end']=train.date.max()
  records.append(test)
  windows.append({'fold':fold,'train_rows':len(train),'test_rows':len(test),
   'train_end':str(train.date.max().date()),'test_date':str(pd.Timestamp(day).date()),
   'metrics':{c:score(test.actual,test[c]) for c in test if c.startswith('pred_')}})
 pred=pd.concat(records,ignore_index=True)
 report={'source':'src/main/resources/data/foodwise_operations_14d.csv','label_origin':'simulation',
  'limitation':'14-day simulated ledger; no evidence of real campus generalization or intervention benefit.',
  'rolling_windows':5,'protocol':'Expanding training, next-day prediction; previous day actuals available at next origin.',
  'features':FEATURES,'seed':42,'windows':windows,
  'metrics':{c:score(pred.actual,pred[c]) for c in pred if c.startswith('pred_')}}
 pred.to_csv(OUT/'campus_baseline_predictions.csv',index=False,encoding='utf-8-sig')
 (OUT/'campus_metrics_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 print(json.dumps({'rolling_windows':5,'test_rows':len(pred),'metrics':report['metrics']},indent=2))
if __name__=='__main__': main()
