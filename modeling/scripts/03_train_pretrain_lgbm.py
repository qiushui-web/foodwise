# -*- coding: utf-8 -*-
"""
03_train_pretrain_lgbm.py
=========================
在 SmartBite 33k 数据上做 LightGBM 预训练，学到高校食堂销量预测的通用规律：
  - 输入：24维特征（来自脚本02产物 pretrain_smartbite.parquet）
  - 目标：sold_qty（对 log1p 回归，缓解长尾）
  - 划分：严格按时间前80%/后20%（防泄漏）
  - 输出：
      (a) lgbm_pretrained_model.txt       -> 脚本05微调init_model
      (b) feature_importance.csv          -> PPT特征重要性图
      (c) category_coef_table.csv         -> Java侧品类系数（4品类x[天气/星期/事件] 系数）
      (d) category_volatility.csv         -> 回填脚本02的category_volatility列
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error

BASE = Path(__file__).resolve().parent.parent / "data"
PROC = BASE / "02_processed"
OUT  = BASE / "03_output"
OUT.mkdir(parents=True, exist_ok=True)

PRETRAIN = PROC / "pretrain_smartbite.parquet"

FEATURE_COLS = [
    "day_of_week","week_of_month","month","is_weekend","is_exam_week",
    "has_campus_event","days_to_vacation",
    "weather_code","temp_max_c","precipitation_mm","weather_x_weekday",
    "category_id","price","unit_cost","markup_ratio",
    "price_rank_in_stall","category_volatility","discount_rate",
    "lag_1_sold","lag_7_sold","rolling_mean_3","rolling_mean_7",
    "rolling_std_7","same_dow_last_4w_mean",
]
TARGET = "sold_qty"
CATEGORY_NAMES = ["套餐主食", "轻食沙拉", "粉面", "烘焙点心"]


def train() -> dict:
    if not PRETRAIN.exists():
        raise FileNotFoundError(f"未找到 {PRETRAIN}，请先运行脚本02")

    df = pd.read_parquet(PRETRAIN)
    print(f"[Load] {PRETRAIN.name}: {len(df):,} 行")

    # 严格按日期排序 -> 前80%/后20% 时间切分（绝对不能shuffle，经验教训Failure 3）
    df = df.sort_values("date").reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    val_df   = df.iloc[split_idx:].copy()
    print(f"[Split] 时间划分 train={len(train_df):,} ({train_df['date'].min().date()}~{train_df['date'].max().date()})  val={len(val_df):,} ({val_df['date'].min().date()}~{val_df['date'].max().date()})")

    X_tr = train_df[FEATURE_COLS]
    y_tr = np.log1p(train_df[TARGET].astype(float))
    X_va = val_df[FEATURE_COLS]
    y_va = np.log1p(val_df[TARGET].astype(float))

    params = dict(
        objective="mape",
        learning_rate=0.03,
        num_leaves=63,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=5,
        verbose=-1,
        n_estimators=1500,
        early_stopping_rounds=50,
        random_state=42,
    )
    model = lgb.LGBMRegressor(**params)
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_va, y_va)],
        callbacks=[lgb.log_evaluation(100)],
    )

    # ===== 预测（反log） =====
    pred_va = np.expm1(model.predict(X_va))
    true_va = val_df[TARGET].values.astype(float)
    mape_pct = mean_absolute_percentage_error(true_va, pred_va) * 100
    mae     = mean_absolute_error(true_va, pred_va)
    print(f"[Val] MAPE={mape_pct:.2f}%   MAE={mae:.2f}  (目标MAPE<15%即可用于下游微调)")

    # ===== (a) 保存模型（Text格式 Java可读）=====
    model_path = OUT / "lgbm_pretrained_model.txt"
    model.booster_.save_model(str(model_path))
    print(f"[Save] {model_path.name}")

    # ===== (b) 特征重要性 =====
    imp = pd.DataFrame({
        "feature": FEATURE_COLS,
        "gain": model.booster_.feature_importance(importance_type="gain"),
        "split": model.booster_.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False).reset_index(drop=True)
    imp["pct"] = (imp["gain"] / imp["gain"].sum() * 100).round(2)
    imp.to_csv(OUT / "feature_importance.csv", index=False, encoding="utf-8-sig")
    print("[Save] feature_importance.csv  -> Top5:")
    for _, row in imp.head(5).iterrows():
        print(f"       #{_+1:>2}  {row['feature']:<26}  gain%={row['pct']:>5.2f}%")

    # ===== (c) 品类系数表：SHAP近似的分组加权 =====
    # 用"分组平均预测 / 全局平均预测"作为系数（Java可直接乘）
    global_mean_pred = float(np.mean(pred_va))
    coef_rows = []
    for cat_id in range(4):
        for wc in range(6):
            for dow in range(7):
                mask = ((val_df["category_id"].values == cat_id) &
                        (val_df["weather_code"].values == wc)  &
                        (val_df["day_of_week"].values  == dow))
                if mask.sum() >= 3:
                    group_pred = float(np.mean(pred_va[mask]))
                    coef = group_pred / global_mean_pred
                    coef = float(np.clip(coef, 0.70, 1.30))
                else:
                    coef = 1.0
                coef_rows.append(dict(
                    category_id=cat_id, category=CATEGORY_NAMES[cat_id],
                    weather_code=wc, day_of_week=dow,
                    coef=round(coef, 4),
                    sample_count=int(mask.sum()),
                ))
    for cat_id in range(4):
        for ev in [0, 1]:
            for ex in [0, 1]:
                mask = ((val_df["category_id"].values == cat_id) &
                        (val_df["has_campus_event"].values == ev) &
                        (val_df["is_exam_week"].values == ex))
                if mask.sum() >= 3:
                    gp = float(np.mean(pred_va[mask]))
                    coef = float(np.clip(gp / global_mean_pred, 0.70, 1.30))
                else:
                    coef = 1.0
                coef_rows.append(dict(
                    category_id=cat_id, category=CATEGORY_NAMES[cat_id],
                    event_flag=ev, exam_week_flag=ex,
                    coef=round(coef, 4), sample_count=int(mask.sum()),
                ))
    pd.DataFrame(coef_rows).to_csv(OUT / "category_coef_table.csv", index=False, encoding="utf-8-sig")
    print(f"[Save] category_coef_table.csv  ({len(coef_rows)} 行分组系数)")

    # ===== (d) 品类波动率：每个category_id的 sold_qty CV =====
    vol = df.groupby("category_id")[TARGET].agg(["mean","std"]).reset_index()
    vol["category_volatility"] = (vol["std"] / vol["mean"].replace(0, np.nan)).round(4).fillna(1.0)
    vol["category"] = vol["category_id"].map(dict(enumerate(CATEGORY_NAMES)))
    vol[["category_id","category","category_volatility"]].to_csv(
        OUT / "category_volatility.csv", index=False, encoding="utf-8-sig")
    print("[Save] category_volatility.csv")

    metrics = dict(
        pretrain_dataset=f"SmartBite ({len(df):,} rows, {df['dish_id'].nunique()} dishes)",
        time_split=f"80/20 by date",
        val_mape_pct=round(float(mape_pct), 2),
        val_mae=round(float(mae), 2),
        n_features=len(FEATURE_COLS),
        top_5_features=imp.head(5)["feature"].tolist(),
        n_trees=model.booster_.num_trees(),
    )
    with open(OUT / "pretrain_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"[Save] pretrain_metrics.json  -> MAPE={metrics['val_mape_pct']}%")
    return metrics


if __name__ == "__main__":
    r = train()
    print("\n===== 03_train_pretrain_lgbm 完成 =====")
    sys.exit(0)
