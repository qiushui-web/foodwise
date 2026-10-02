# -*- coding: utf-8 -*-
"""
10_export_campus_model.py
高校场景真实 LGBM 模型导出（可复现、可审计）
- 数据: finetune_uwaste.parquet (university_food_waste 2600行真实高校浪费实测)
- 严格滚动回测: 2 个扩展窗口, 无未来泄漏
- 产物: lgbm_campus_model.txt(全量训练最终模型) + campus_feature_cols.json
        + campus_backtest_report.json + campus_backtest_predictions.csv
        + feature_importance_campus.csv
全部直接写入 Java classpath: modeling/
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
import lightgbm as lgb
from sklearn.metrics import mean_absolute_percentage_error

MODELING = Path(r"D:\IdeaProjects\Examples\modeling")
PROC = MODELING / "data" / "02_processed"
JAVA_RES = Path(r"D:\IdeaProjects\Examples\src\main\resources\modeling")

FEATS = [
    "day_of_week", "is_weekend", "is_exam_week", "has_campus_event",
    "weather_code", "temp_max_c", "category_id", "price", "unit_cost",
    "discount_rate", "promotion_flag",
    "lag_1_sold", "lag_2_sold", "lag_3_sold", "lag_7_sold",
    "rolling_mean_3", "rolling_mean_7", "rolling_std_7", "same_dow_last_4w_mean",
    "is_school_holiday", "is_state_holiday", "special_day",
    "comp_price_ratio", "recent_trend_3d",
]
TARGET = "sold_qty"


def mape_pct(y, p):
    y = np.asarray(y, float); p = np.asarray(p, float)
    m = y > 0
    return float(mean_absolute_percentage_error(y[m], p[m]) * 100)


def train_model(train_df, n_est=400):
    X = train_df[FEATS]
    y = np.log1p(train_df[TARGET].astype(float))
    m = lgb.LGBMRegressor(
        objective="regression",
        learning_rate=0.03,
        num_leaves=15,
        min_child_samples=25,
        feature_fraction=0.85,
        bagging_fraction=0.85,
        bagging_freq=5,
        reg_lambda=1.0,
        n_estimators=n_est,
        random_state=42,
        verbosity=-1,
    )
    m.fit(X, y)
    return m


def predict_model(model, df):
    raw = model.predict(df[FEATS])
    return np.clip(np.expm1(raw), 1.0, 400.0)


def rule_predict(df):
    """工程基线: 同星期均值优先, 否则7日滚动均值"""
    p = np.where(df["same_dow_last_4w_mean"].values > 0,
                 df["same_dow_last_4w_mean"].values,
                 df["rolling_mean_7"].values)
    p = np.where(p > 0, p, df["lag_1_sold"].values)
    return np.clip(p, 1.0, 400.0)


def main():
    df = pd.read_parquet(PROC / "finetune_uwaste.parquet").reset_index(drop=True)
    print(f"[Load] {len(df)} 行, {len(FEATS)} 特征")
    print("[Check] 缺失特征:", [c for c in FEATS if c not in df.columns] or "无")
    print("[Category] sold_qty 均值 by category_id:")
    print(df.groupby("category_id")[TARGET].mean().round(1).to_dict())
    print("[day_of_week] 分布:", sorted(df["day_of_week"].unique().tolist()))

    # --- 严格滚动回测: 2 扩展窗口 ---
    windows = [(0, 2080, 2405), (0, 2405, 2600)]  # train_start, split, test_end
    details, win_reports = [], []
    for wi, (ts, split, te) in enumerate(windows, 1):
        tr = df.iloc[ts:split]
        te_df = df.iloc[split:te]
        model = train_model(tr)
        p_lgbm = predict_model(model, te_df)
        p_rule = rule_predict(te_df)
        y = te_df[TARGET].values
        m_mape = mape_pct(y, p_lgbm)
        r_mape = mape_pct(y, p_rule)
        m_mae = float(np.mean(np.abs(p_lgbm - y)))
        r_mae = float(np.mean(np.abs(p_rule - y)))
        win_reports.append(dict(window=wi, n_train=len(tr), n_test=len(te_df),
                                MAPE_pct=round(m_mape, 3), MAE=round(m_mae, 3),
                                RULE_MAPE_pct=round(r_mape, 3), RULE_MAE=round(r_mae, 3)))
        print(f"[W{wi}] n_train={len(tr)} n_test={len(te_df)} "
              f"LGBM MAPE={m_mape:.2f}% MAE={m_mae:.2f} | RULE MAPE={r_mape:.2f}%")
        for i, (idx, row) in enumerate(te_df.iterrows()):
            if len(details) < 600:
                details.append(dict(
                    row_index=int(idx),
                    category_id=int(row["category_id"]),
                    actual=round(float(row[TARGET]), 1),
                    pred_lgbm=round(float(p_lgbm[i]), 1),
                    pred_rule=round(float(p_rule[i]), 1),
                ))

    avg_mape = float(np.mean([w["MAPE_pct"] for w in win_reports]))
    avg_mae = float(np.mean([w["MAE"] for w in win_reports]))
    rule_mape = float(np.mean([w["RULE_MAPE_pct"] for w in win_reports]))
    rule_mae = float(np.mean([w["RULE_MAE"] for w in win_reports]))
    print(f"\n[SUMMARY] LGBM 平均 MAPE={avg_mape:.2f}% MAE={avg_mae:.2f} "
          f"| 规则 MAPE={rule_mape:.2f}% | 提升 {rule_mape - avg_mape:.2f}pp")

    # --- 全量训练最终模型并导出 ---
    final = train_model(df, n_est=500)
    JAVA_RES.mkdir(parents=True, exist_ok=True)
    model_txt = JAVA_RES / "lgbm_campus_model.txt"
    final.booster_.save_model(str(model_txt))
    print(f"[Save] {model_txt.name} ({model_txt.stat().st_size} bytes)")

    with open(JAVA_RES / "campus_feature_cols.json", "w", encoding="utf-8") as f:
        json.dump({"features": FEATS, "target_transform": "log1p(sold_qty)",
                   "predict_transform": "expm1(raw), clip[1,400]",
                   "n_train_rows": len(df)}, f, ensure_ascii=False, indent=2)

    imp = pd.DataFrame({
        "feature": FEATS,
        "gain": final.booster_.feature_importance(importance_type="gain"),
        "split": final.booster_.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    imp.to_csv(JAVA_RES / "feature_importance_campus.csv", index=False, encoding="utf-8-sig")
    print("[Save] feature_importance_campus.csv top5:",
          imp.head(5)[["feature", "gain"]].to_dict("records"))

    pred_df = pd.DataFrame(details)
    pred_df.to_csv(JAVA_RES / "campus_backtest_predictions.csv", index=False, encoding="utf-8-sig")

    report = {
        "scenario": "高校场景严格滚动回测: university_food_waste 2600行真实实测 (2扩展窗口, 无未来泄漏)",
        "data_source": "Kaggle university canteen food-waste 实测 (4档口x3餐次x4品类, 1学年)",
        "rolling_windows": 2,
        "avg_mae": round(avg_mae, 3),
        "avg_mape_pct": round(avg_mape, 3),
        "rule_mape_pct": round(rule_mape, 3),
        "rule_mae": round(rule_mae, 3),
        "improvement_over_rule_pct": round(rule_mape - avg_mape, 2),
        "target_transform": "log1p(sold_qty)",
        "windows_detail": win_reports,
        "model_file": "lgbm_campus_model.txt",
        "feature_count": len(FEATS),
        "n_train_final": len(df),
    }
    with open(JAVA_RES / "campus_backtest_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[Save] campus_backtest_report.json")
    print("\n===== 高校真实模型导出完成 =====")


if __name__ == "__main__":
    main()
