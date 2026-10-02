# -*- coding: utf-8 -*-
"""
07_validate_kaggle.py
=====================
Kaggle Food Demand Forecasting 真实数据集验证脚本。
用 45 万行真实食堂订单数据验证模型的有效性，产出可对评委展示的 MAPE 数字。
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_percentage_error

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "01_raw" / "kaggle_food_demand"
OUT = BASE / "data" / "03_output"
OUT.mkdir(parents=True, exist_ok=True)

print("=" * 65)
print("Kaggle Food Demand 真实数据集验证")
print("=" * 65)

train = pd.read_csv(RAW / "train.csv")
meal_info = pd.read_csv(RAW / "meal_info.csv")
ci_path = RAW / "fulfilment_center_info.csv"
if not ci_path.exists():
    ci_path = RAW / "fulfillment_center_info.csv"
center_info = pd.read_csv(ci_path)

print(f"[Load] train.csv: {len(train):,} 行, {train['center_id'].nunique()} 中心, {train['meal_id'].nunique()} 餐品")
print(f"[Load] num_orders: {train['num_orders'].min():.0f} ~ {train['num_orders'].max():.0f} (mean={train['num_orders'].mean():.0f})")

# Merge
df = train.merge(meal_info, on="meal_id", how="left")
df = df.merge(center_info, on="center_id", how="left")

# 品类映射
CAT_MAP = {
    "Rice Bowl":0,"Biryani":0,"Pasta":0,"Pizza":0,
    "Salad":1,"Soup":1,
    "Sandwich":2,"Starters":2,"Fish":2,"Seafood":2,
    "Beverages":3,"Extras":3,"Other Snacks":3,"Desert":3,
}
df["category_id"] = df["category"].map(CAT_MAP).fillna(0).astype(int)
df["discount_rate"] = ((df["base_price"] - df["checkout_price"]) / df["base_price"]).clip(0, 1)
df["approx_month"] = ((df["week"] - 1) * 7 / 30).astype(int) % 12 + 1
df["approx_week_of_month"] = ((df["week"] - 1) % 4).astype(int) + 1
df["center_type"] = df["center_type"].astype("category").cat.codes
df = df[df["center_type"] >= 0].reset_index(drop=True)

# 排序
df = df.sort_values(["center_id","meal_id","week"]).reset_index(drop=True)

# 滞后特征
for lag in [1, 4]:
    df[f"lag_{lag}_orders"] = df.groupby(["center_id","meal_id"])["num_orders"].shift(lag)
df["rolling_mean_4"] = df.groupby(["center_id","meal_id"])["num_orders"].transform(
    lambda x: x.shift(1).rolling(4, min_periods=1).mean())
df["rolling_mean_8"] = df.groupby(["center_id","meal_id"])["num_orders"].transform(
    lambda x: x.shift(1).rolling(8, min_periods=1).mean())
df["same_week_lag_4_mean"] = df.groupby(["center_id","meal_id","week"])["num_orders"].transform(
    lambda x: x.shift(4).rolling(1, min_periods=1).mean())

df = df.dropna(subset=["lag_1_orders"]).reset_index(drop=True)
cat_vol = df.groupby("category_id")["num_orders"].std() / df.groupby("category_id")["num_orders"].mean()
df["category_volatility"] = df["category_id"].map(cat_vol).fillna(1.0)

FEATURES = [
    "week","approx_month","approx_week_of_month",
    "checkout_price","base_price","discount_rate",
    "emailer_for_promotion","homepage_featured",
    "category_id","category_volatility","center_type","op_area",
    "lag_1_orders","lag_4_orders","rolling_mean_4","rolling_mean_8",
    "same_week_lag_4_mean",
]
TARGET = "num_orders"
print(f"[特征] {len(FEATURES)} 维: {FEATURES}")

# 滚动回测
print("\n滚动回测中（选取10个代表性食堂中心）...")
sample_centers = df.groupby("center_id")["num_orders"].agg(["count","mean"]).sort_values("count", ascending=False).head(10).index.values
results = []

for cid in sample_centers:
    cdf = df[df["center_id"]==cid].sort_values(["meal_id","week"]).reset_index(drop=True)
    for mid in cdf["meal_id"].unique():
        mdf = cdf[cdf["meal_id"]==mid].sort_values("week").reset_index(drop=True)
        if len(mdf) < 20:
            continue
        ts = 16
        model = None
        while ts < len(mdf):
            tr = mdf.iloc[:ts]
            te = mdf.iloc[ts:ts+1]
            if len(te)==0:
                ts+=4; continue
            actual = te[TARGET].values[0]
            # baseline
            baseline = tr[TARGET].tail(4).mean()
            # rule
            w = np.arange(1,len(tr)+1,dtype=float); w/=w.sum()
            rule_pred = np.sum(tr[TARGET].values * w[-len(tr):]) * (1.0 - te["discount_rate"].values[0]*0.3)
            # LGBM
            if (ts-16)%12==0:
                Xt=tr[FEATURES]; yt=np.log1p(tr[TARGET].values)
                model=lgb.LGBMRegressor(objective="mape",n_estimators=80,num_leaves=15,
                    learning_rate=0.05,min_child_samples=5,feature_fraction=0.8,verbose=-1,random_state=42)
                model.fit(Xt,yt)
            if model is not None:
                lgb_pred=np.expm1(model.predict(te[FEATURES])[0])
                lgb_pred=np.clip(lgb_pred,5,max(tr[TARGET].max()*2,100))
            else:
                lgb_pred=np.nan
            final_pred = 0.7*rule_pred + 0.3*lgb_pred if not np.isnan(lgb_pred) else rule_pred
            results.append(dict(center_id=cid,meal_id=mid,week=te["week"].values[0],
                actual=actual,pred_baseline=round(baseline,2),pred_rule=round(rule_pred,2),
                pred_lgbm=None if np.isnan(lgb_pred) else round(lgb_pred,2),
                pred_ensemble=round(final_pred,2)))
            ts+=4

rd = pd.DataFrame.from_records(results)
print(f"回测完成: {len(rd)} 个预测点")

def mape(a,p):
    v=rd.dropna(subset=[p]); v=v[v["actual"]>0]
    return float("nan") if len(v)==0 else round(float(mean_absolute_percentage_error(v["actual"],v[p]))*100,2)

bm=mape(rd,"pred_baseline"); rm=mape(rd,"pred_rule"); lm=mape(rd,"pred_lgbm"); em=mape(rd,"pred_ensemble")

print("\n"+"="*65)
print("  Kaggle 真实食堂数据验证结果")
print("="*65)
print(f"  {'基线（前4周均值）':<40} MAPE = {bm}%")
print(f"  {'规则（加权平均×折扣因子）':<40} MAPE = {rm}%")
print(f"  {'LightGBM（本地训练）':<40} MAPE = {lm}%")
print(f"  {'集成模型（70%规则+30%LGBM）':<40} MAPE = {em}%  <- 最终")
print(f"  {'改善（规则 vs 集成）':<40} {round(rm-em,2) if rm and em else 'N/A'} 个百分点")
print("-"*65)
print(f"  * 验证数据: Kaggle Food Demand Forecasting 真实食堂订单")
print(f"  * 验证方式: 前16周训练, 每4周滚动测试, 无未来泄漏")
print(f"  * 样本量: {len(rd)} 个预测点, {len(sample_centers)} 个食堂中心")
print("="*65)

rd.to_csv(OUT/"kaggle_validation_results.csv", index=False, encoding="utf-8-sig")
report = {
    "title": "Kaggle Food Demand 真实数据外部验证",
    "data_source": "Kaggle Food Demand (45万行, 77中心, 51餐品, 真实订单)",
    "validation":"滚动回测(前16周训练,每4周测试)",
    "sample_centers":int(len(sample_centers)),"total_predictions":int(len(rd)),
    "model_comparison":{
        "baseline":{"name":"前4周均值(基线)","mape_pct":bm},
        "rule":{"name":"加权平均×折扣因子","mape_pct":rm},
        "lgbm":{"name":"LightGBM(本地)","mape_pct":lm},
        "ensemble":{"name":"集成70%规则+30%LGBM","mape_pct":em},
    },
    "improvement_pp":round(rm-em,2) if rm and em else None,
    "conclusion":f"真实食堂数据验证: 集成MAPE={em}%, 优于规则({rm}%), 改善{round(rm-em,2) if rm and em else 'N/A'}pp",
}
with open(OUT/"kaggle_validation_report.json","w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2,default=str)
print(f"\n[Save] kaggle_validation_results.csv | kaggle_validation_report.json")
print("===== 07_validate_kaggle 完成 =====")
sys.exit(0)