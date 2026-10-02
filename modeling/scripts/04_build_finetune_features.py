# -*- coding: utf-8 -*-
"""
04_build_finetune_features.py
=============================
专为98条校园台账生成微调用特征：
  - 优先复用脚本02产出的 campus_98_processed.parquet（避免重复lag计算）
  - 关键不同：回填脚本03训练得到的 category_volatility（从预训练数据学到）
  - 输出：campus_finetune_features.parquet（脚本05专用）
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "data"
PROC = BASE / "02_processed"
OUT  = BASE / "03_output"

SRC_CAMPUS_PROCESSED = PROC / "campus_98_processed.parquet"
VOLATILITY_CSV       = OUT / "category_volatility.csv"   # 脚本03产物（若不存在用默认1.0）
TARGET_PATH          = PROC / "campus_finetune_features.parquet"

FEATURE_COLS = [
    "day_of_week","week_of_month","month","is_weekend","is_exam_week",
    "has_campus_event","days_to_vacation",
    "weather_code","temp_max_c","precipitation_mm","weather_x_weekday",
    "category_id","price","unit_cost","markup_ratio",
    "price_rank_in_stall","category_volatility","discount_rate",
    "lag_1_sold","lag_7_sold","rolling_mean_3","rolling_mean_7",
    "rolling_std_7","same_dow_last_4w_mean",
]


def main() -> int:
    if not SRC_CAMPUS_PROCESSED.exists():
        print(f"[WARN] {SRC_CAMPUS_PROCESSED} 不存在，先运行脚本02")
        # 不fail-fast，允许脚本02-04在一次run_all中连续执行
        return 0

    df = pd.read_parquet(SRC_CAMPUS_PROCESSED)
    print(f"[Load] {len(df)} 行校园台账特征")

    # 回填 volatility（脚本03跑完才可用；没跑就保持1.0不影响训练）
    if VOLATILITY_CSV.exists():
        vol = pd.read_csv(VOLATILITY_CSV)
        mapping = dict(zip(vol["category_id"], vol["category_volatility"]))
        before = df["category_volatility"].mean()
        df["category_volatility"] = df["category_id"].map(mapping).fillna(df["category_volatility"])
        after = df["category_volatility"].mean()
        print(f"[Fill] category_volatility 回填完成 mean {before:.3f} -> {after:.3f}")
    else:
        print(f"[Skip] {VOLATILITY_CSV.name} 暂不存在（脚本03跑完会自动生成），保持默认值")

    # 完整性校验（Failure经验：shape要可预期）
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要特征列: {missing}")

    df.to_parquet(TARGET_PATH, index=False)
    df.to_csv(PROC / "campus_finetune_features.csv", index=False, encoding="utf-8-sig")
    print(f"[Save] {TARGET_PATH.name}")
    print(f"       行数={len(df)}  特征列={len(FEATURE_COLS)}  日期={df['date'].min().date()}~{df['date'].max().date()}")
    print(f"       档口数={df['stall_name'].nunique()}  菜品数={df['dish_id'].nunique()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
