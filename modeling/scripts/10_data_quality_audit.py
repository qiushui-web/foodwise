from pathlib import Path
import json,hashlib,pandas as pd
ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'modeling/data'; OUT=BASE/'03_output'; RAW=BASE/'01_raw'; PROC=BASE/'02_processed'
def sha(p):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def main():
 f=RAW/'university_food_waste/university_canteen_waste.csv'; df=pd.read_csv(f)
 dates=pd.to_datetime(df.Date)
 daily=dates.dt.normalize().drop_duplicates().sort_values()
 gaps=int((daily.diff().dropna()>pd.Timedelta(days=1)).sum())
 checks={'rows':len(df),'duplicate_keys':int(df.duplicated(['Date','Meal','Canteen_Section','Food_Category']).sum()),'negative_values':{c:int((df[c]<0).sum()) for c in ['Waste_Weight_kg','Unit_Price_per_kg','Cost_Loss']},'cost_formula_mismatch':int((abs(df.Cost_Loss-df.Waste_Weight_kg*df.Unit_Price_per_kg)>0.02).sum()),'date_range':[str(df.Date.min()),str(df.Date.max())],'unique_days':int(dates.nunique()),'date_gap_count':gaps,'quantity_conservation_check':'not applicable: raw waste dataset has no prepare/sold quantities','outlier_counts':{c:int(((df[c]-df[c].median()).abs()>6*df[c].std()).sum()) for c in ['Waste_Weight_kg','Cost_Loss']},'feature_leakage_check':'manual review required; lag/rolling builder uses shift(1)'}
 ops=ROOT/'src/main/resources/data/foodwise_operations_14d.csv'
 odf=pd.read_csv(ops)
 checks['operations_duplicate_keys']=int(odf.duplicated(['business_date','stall','dish_id']).sum())
 checks['operations_quantity_conservation_violations']=int((odf.sold_qty+odf.leftover_qty!=odf.prepared_qty).sum())
 files={str(p.relative_to(BASE)):{'bytes':p.stat().st_size,'sha256':sha(p)} for root in [RAW,PROC,OUT] for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ['.csv','.parquet','.json']}
 java_root=BASE.parent.parent/'src'/'main'/'resources'/'modeling'
 java_files={p.name:sha(p) for p in java_root.glob('*') if p.is_file() and p.suffix.lower() in ['.csv','.json','.txt']}
 (OUT/'data_quality_report.json').write_text(json.dumps({'checks':checks,'notes':['waste_rate is derived downstream','time-series leakage requires feature builder review']},ensure_ascii=False,indent=2),encoding='utf-8')
 canonical=PROC/'campus_daily_canonical.parquet'
 checks['canonical_dataset_present']=canonical.exists()
 checks['java_model_sources_present']=all((java_root/n).exists() for n in ['lgbm_campus_model.txt','campus_feature_cols.json'])
 (OUT/'DATA_VERSION.json').write_text(json.dumps({'schema_version':'1.2','artifacts':files,'java_classpath_artifacts':java_files,'consistency':{'canonical_dataset':str(canonical.relative_to(BASE)),'java_model_files':['lgbm_campus_model.txt','campus_feature_cols.json']}},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(checks,ensure_ascii=False))
if __name__=='__main__': main()
